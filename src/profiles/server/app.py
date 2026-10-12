"""FastAPI application factory for ProFiles."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from profiles.server.routes.actions import router as actions_router
from profiles.server.routes.config import router as config_router
from profiles.server.routes.fs import router as fs_router
from profiles.server.routes.scan import router as scan_router
from profiles.server.routes.system import router as system_router
from profiles.server.state import ServerState


def create_app(state: ServerState) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        state: ServerState instance storing app configuration and scan cache.

    Returns:
        Configured FastAPI instance.
    """
    app = FastAPI(title="ProFiles API", version="1.0.0")
    app.state.server_state = state

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system_router)
    app.include_router(config_router)
    app.include_router(fs_router)
    app.include_router(scan_router)
    app.include_router(actions_router)

    return app
