"""FastAPI application factory for ProFiles."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from profiles.core.telemetry import events
from profiles.server.routes.actions import router as actions_router
from profiles.server.routes.config import router as config_router
from profiles.server.routes.fs import router as fs_router
from profiles.server.routes.instance import router as instance_router
from profiles.server.routes.logs import router as logs_router
from profiles.server.routes.scan import router as scan_router
from profiles.server.routes.system import router as system_router
from profiles.server.routes.workflow import router as workflow_router
from profiles.server.state import ServerState

# Server-side telemetry logger (the "profiles" logger writes profiles.log).
_LOGGER = logging.getLogger("profiles")

# A client counts as gone once it has not sent a request for this long. The
# web UI polls /api/notifications every 4s in the foreground, but browsers
# throttle background tabs down to ~60s, so the threshold must sit above
# that to avoid disconnect/reconnect churn for merely-hidden tabs.
CLIENT_IDLE_DISCONNECT_S = 120.0

# How often the lifespan watchdog looks for clients past the idle threshold.
CLIENT_SWEEP_INTERVAL_S = 15.0


def sweep_disconnected_clients(
    last_seen: dict[str, float],
    now: float,
    logger: logging.Logger,
    timeout_s: float = CLIENT_IDLE_DISCONNECT_S,
) -> None:
    """Log and drop clients idle for more than ``timeout_s``.

    Pure bookkeeping over the ``ip -> last-seen`` map: mutates ``last_seen``
    in place and emits one ``WEB_CLIENT event="disconnected"`` per stale
    entry. Called periodically by the app lifespan and directly by tests.

    Args:
        last_seen: Client IP to last-request monotonic timestamp map.
        now: Current ``time.monotonic()`` value.
        logger: Application logger receiving the events.
        timeout_s: Idle duration after which a client counts as gone.
    """
    for ip, seen_at in list(last_seen.items()):
        idle_s = now - seen_at
        if idle_s > timeout_s:
            del last_seen[ip]
            events.web_client_left(logger, ip=ip, idle_s=int(idle_s))


async def _sweep_loop(app: FastAPI) -> None:
    """Periodically sweep the client map until the task is cancelled."""
    last_seen: dict[str, float] = app.state.client_last_seen
    while True:
        await asyncio.sleep(CLIENT_SWEEP_INTERVAL_S)
        sweep_disconnected_clients(last_seen, time.monotonic(), _LOGGER)


@asynccontextmanager
async def _client_watchdog_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run the disconnect watchdog for the server's lifetime."""
    task = asyncio.create_task(_sweep_loop(app))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def create_app(state: ServerState, static_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        state: ServerState instance storing app configuration and scan cache.
        static_dir: Optional custom directory to mount static assets from.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(title="ProFiles API", version="1.0.0", lifespan=_client_watchdog_lifespan)
    app.state.server_state = state
    # client_id -> monotonic last-seen timestamp (dict[str, float]); attribute
    # annotations are not a supported statement form, so it's documented here.
    app.state.client_last_seen = {}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_web_client(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Emit WEB_CLIENT on first connect or reconnect after a long idle."""
        client_ip = request.client.host if request.client else "unknown"
        last_seen: dict[str, float] = request.app.state.client_last_seen
        now = time.monotonic()
        previous = last_seen.get(client_ip)
        if previous is None:
            events.web_client(
                _LOGGER,
                ip=client_ip,
                path=request.url.path,
                user_agent=request.headers.get("user-agent", "")[:120],
            )
        elif now - previous > CLIENT_IDLE_DISCONNECT_S:
            events.web_client_reconnected(_LOGGER, ip=client_ip, path=request.url.path)
        last_seen[client_ip] = now
        return await call_next(request)

    app.include_router(system_router)
    app.include_router(instance_router)
    app.include_router(config_router)
    app.include_router(fs_router)
    app.include_router(scan_router)
    app.include_router(actions_router)
    app.include_router(workflow_router)
    app.include_router(logs_router)

    # Mount compiled web frontend
    from profiles.server.static import mount_static_app

    mount_static_app(app, static_dir=static_dir)

    return app
