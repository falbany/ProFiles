"""FastAPI application factory for ProFiles."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from profiles.core.telemetry import events
from profiles.server.routes.actions import router as actions_router
from profiles.server.routes.config import router as config_router
from profiles.server.routes.fs import router as fs_router
from profiles.server.routes.logs import router as logs_router
from profiles.server.routes.scan import router as scan_router
from profiles.server.routes.system import router as system_router
from profiles.server.routes.workflow import router as workflow_router
from profiles.server.state import ServerState

# Server-side telemetry logger (the "profiles" logger writes profiles.log).
_LOGGER = logging.getLogger("profiles")


def create_app(state: ServerState, static_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        state: ServerState instance storing app configuration and scan cache.
        static_dir: Optional custom directory to mount static assets from.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(title="ProFiles API", version="1.0.0")
    app.state.server_state = state
    app.state.seen_client_ips: set[str] = set()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_web_client(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Emit WEB_CLIENT once per client IP (first request from it)."""
        client_ip = request.client.host if request.client else "unknown"
        seen: set[str] = request.app.state.seen_client_ips
        if client_ip not in seen:
            seen.add(client_ip)
            events.web_client(
                _LOGGER,
                ip=client_ip,
                path=request.url.path,
                user_agent=request.headers.get("user-agent", "")[:120],
            )
        return await call_next(request)

    app.include_router(system_router)
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
