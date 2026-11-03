"""System, health and bind-status endpoints for the local FastAPI server."""

from __future__ import annotations

import platform

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from profiles.core.environment import system
from profiles.server.state import BindableServer

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


@router.post("/system/bind")
async def bind_server(payload: BindRequest, request: Request) -> dict[str, object]:
    """Rebind the running server between LAN exposure and loopback-only.

    Transient on purpose: the choice resets to the launch default on the
    next restart. The desktop lifecycle reverts a failed bind, so on error
    the reported state is still the previous one.
    """
    server = _background_server(request)
    if server is None:
        raise HTTPException(status_code=503, detail="no running server to rebind")
    target_host = "0.0.0.0" if payload.lan else "127.0.0.1"
    # Lazy import: desktop.lifecycle imports server.app at module level, so a
    # top-level import here would create an import cycle.
    from profiles.desktop.lifecycle import ServerStartError

    try:
        server.rebind(target_host)
    except ServerStartError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"host": server.host, "lan_enabled": payload.lan}
