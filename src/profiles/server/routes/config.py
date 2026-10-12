"""Config endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from profiles.server.state import ServerState

router = APIRouter(prefix="/api/config", tags=["config"])


class SelectDirectoryRequest(BaseModel):
    directory: str


@router.get("")
async def get_config(request: Request) -> dict:
    """Return active application configuration and available directories."""
    state: ServerState = request.app.state.server_state
    cfg = state.config

    from profiles.core.config import service as config_service
    from profiles.utils.network import get_hostname

    available_dirs = config_service.get_unique_directories(cfg)

    # Ensure active directory is set
    if not state.active_directory:
        selected = config_service.auto_select_directory(cfg, get_hostname())
        if selected and Path(selected).exists():
            state.active_directory = Path(selected)
        elif available_dirs:
            state.active_directory = Path(available_dirs[0])
        else:
            state.active_directory = Path.cwd()

    if not available_dirs:
        available_dirs = [str(state.active_directory)]

    return {
        "title": cfg.title,
        "release": cfg.release,
        "search_dir": cfg.search_dir,
        "directories": available_dirs,
        "extensions": list(cfg.extensions),
        "filters": list(cfg.filters),
        "active_directory": str(state.active_directory) if state.active_directory else "",
        "column_headers": list(cfg.column_headers or cfg.column_names),
        "column_names": list(cfg.column_names),
        "row_colors": [[rule[0], rule[1]] for rule in cfg.row_colors],
    }


@router.post("/select-directory")
async def select_directory(payload: SelectDirectoryRequest, request: Request) -> dict:
    """Update active directory."""
    state: ServerState = request.app.state.server_state
    path = Path(payload.directory).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Directory does not exist")
    state.active_directory = path
    return {"active_directory": str(path)}
