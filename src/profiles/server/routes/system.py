"""System, health and bind-status endpoints for the local FastAPI server."""

from __future__ import annotations

import logging
import platform
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from profiles.core.environment import system
from profiles.core.telemetry import events
from profiles.server.state import BindableServer

# Telemetry logger (the "profiles" logger writes profiles.log).
_LOGGER = logging.getLogger("profiles")

# Grace period so the HTTP response is fully flushed before the rebind
# worker starts shutting the old server down. Without it, the response
# could race the listener close and the client would see a reset socket.
_REBIND_DRAIN_WAIT_S = 0.25

router = APIRouter(prefix="/api", tags=["system"])


class BindRequest(BaseModel):
    """Body of ``POST /api/system/bind``."""

    lan: bool


def _background_server(request: Request) -> BindableServer | None:
    """Return the registered running server, or ``None`` when unknown.

    Registered by ``BackgroundServer.start()`` on ``app.state``; a bare
    app factory (tests, static harnesses) has none.
    """
    server: BindableServer | None = getattr(request.app.state, "background_server", None)
    return server


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for process readiness."""
    return {"status": "ok"}


@router.get("/system")
async def system_info(request: Request) -> dict[str, object]:
    """Return local host/user diagnostics and the current bind state."""
    info = system.collect_system_info()
    server = _background_server(request)
    return {
        "hostname": info.hostname,
        "ip": info.ip,
        "username": info.username,
        "os_release": platform.platform(),
        "lan_enabled": None if server is None else server.host == "0.0.0.0",
    }


def _rebind_worker(server: BindableServer, target_host: str) -> None:
    """Run the rebind off the serving thread and log the outcome.

    The route handler runs on the uvicorn thread, so a synchronous rebind
    would have ``stop()`` join the *current* thread (RuntimeError) — and a
    server cannot release its port while still serving the very request
    that asked for the rebind. This worker therefore runs strictly after
    the HTTP response has been sent.
    """
    time.sleep(_REBIND_DRAIN_WAIT_S)
    # Lazy import: desktop.lifecycle imports server.app at module level, so a
    # top-level import here would create an import cycle.
    from profiles.desktop.lifecycle import ServerStartError

    try:
        server.rebind(target_host)
    except ServerStartError as exc:
        events.bind_change_failed(_LOGGER, host=target_host, error=str(exc))
    else:
        events.bind_changed(_LOGGER, host=server.host, lan=target_host == "0.0.0.0")


def _schedule_rebind(server: BindableServer, target_host: str) -> threading.Thread:
    """Start the rebind on a daemon thread; returns it so tests can join."""
    worker = threading.Thread(
        target=_rebind_worker,
        args=(server, target_host),
        name="profiles-rebind",
        daemon=True,
    )
    worker.start()
    return worker


@router.post("/system/bind")
async def bind_server(payload: BindRequest, request: Request) -> dict[str, object]:
    """Rebind the running server between LAN exposure and loopback-only.

    Asynchronous on purpose: the response is sent before the old server
    shuts down (a server cannot release its port while serving the request
    that asked for the rebind). The actual rebind runs on a worker thread
    and the client observes the outcome through ``GET /api/system`` —
    including a failed rebind, which reverts to the previous host.
    """
    server = _background_server(request)
    if server is None:
        raise HTTPException(status_code=503, detail="no running server to rebind")
    target_host = "0.0.0.0" if payload.lan else "127.0.0.1"
    _schedule_rebind(server, target_host)
    return {
        "host": target_host,
        "lan_enabled": payload.lan,
        "status": "rebinding",
    }
