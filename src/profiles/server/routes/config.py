"""Config endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from profiles.core.config.io.yaml_io import CONFIG_FILE_NAMES
from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
from profiles.launch.creation import propose_creation
from profiles.server.state import ServerState

router = APIRouter(prefix="/api/config", tags=["config"])


class SelectDirectoryRequest(BaseModel):
    directory: str


class LoadConfigRequest(BaseModel):
    config_path: str


class CreateConfigRequest(BaseModel):
    directory: str


def _is_config_path(path: Path) -> bool:
    return path.name.endswith(CONFIG_FILE_NAMES)


def _config_response(state: ServerState) -> dict:
    cfg: AppConfig = state.config
    config_path = state.active_config_path()

    state.config_path = config_path
    cfg.config_path = config_path

    from profiles.core.config import service as config_service
    from profiles.utils.network import get_hostname

    available_dirs = config_service.get_unique_directories(cfg)
    if not state.active_directory:
        hostname = get_hostname()
        selected = config_service.auto_select_directory(cfg, hostname)
        if selected and Path(selected).exists():
            state.active_directory = Path(selected)
        elif available_dirs:
            state.active_directory = Path(available_dirs[0])
        else:
            state.active_directory = Path.cwd()

    if not available_dirs:
        available_dirs = [str(state.active_directory)]

    extensions, filters = config_service.merge_config_overrides(cfg, str(state.active_directory))

    # Find the active config matching the selected directory to get its row_colors
    active_config = config_service.find_active_config(cfg, str(state.active_directory))
    row_colors_to_return = active_config.row_colors if active_config is not None else cfg.row_colors

    return {
        "title": cfg.title,
        "release": cfg.release,
        "search_dir": cfg.search_dir,
        "recursive_search": bool(cfg.recursive_search),
        "theme": cfg.theme,
        "directories": available_dirs,
        "extensions": extensions,
        "filters": filters,
        "search_exclude_dirs": list(cfg.search_exclude_dirs),
        "search_exclude_files": list(cfg.search_exclude_files),
        "active_directory": str(state.active_directory) if state.active_directory else "",
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "column_headers": list(cfg.column_headers or cfg.column_names),
        "column_names": list(cfg.column_names),
        "row_colors": [[rule[0], rule[1]] for rule in row_colors_to_return],
    }


def _choose_active_directory(config_path: Path, cfg: AppConfig) -> Path:
    from profiles.core.config import service as config_service
    from profiles.utils.network import get_hostname

    hostname = get_hostname()
    active = (
        config_service.find_configuration_by_hostname(cfg, hostname) if cfg.configurations else None
    )
    if active and active.scan:
        for scan_dir in active.scan:
            candidate = Path(scan_dir)
            if candidate.exists():
                return candidate

    if config_path.parent.exists() and config_path.parent.is_dir():
        return config_path.parent

    fallback_dirs = config_service.get_unique_directories(cfg)
    for directory in fallback_dirs:
        candidate = Path(directory)
        if candidate.exists():
            return candidate
    return Path.cwd()


@router.get("")
async def get_config(request: Request) -> dict:
    """Return active application configuration and available directories."""
    state: ServerState = request.app.state.server_state
    return _config_response(state)


@router.post("/load")
async def load_config_endpoint(payload: LoadConfigRequest, request: Request) -> dict:
    """Load and apply a configuration file from disk."""
    state: ServerState = request.app.state.server_state
    config_path = Path(payload.config_path).expanduser().resolve()

    if not config_path.exists():
        raise HTTPException(status_code=400, detail=f"Config file does not exist: {config_path}")
    if not _is_config_path(config_path):
        raise HTTPException(
            status_code=400,
            detail=f"Not a ProFiles configuration file: {config_path}",
        )

    loaded = ConfigReader(config_path).load()
    state.config = loaded
    state.config_path = config_path
    state.active_directory = _choose_active_directory(config_path, loaded)
    return _config_response(state)


@router.post("/create")
async def create_config_endpoint(payload: CreateConfigRequest, request: Request) -> dict:
    """Create a starter config in the requested directory."""
    state: ServerState = request.app.state.server_state
    target_dir = Path(payload.directory).expanduser().resolve()
    target_config = target_dir / ".profiles"

    if target_config.exists():
        raise HTTPException(
            status_code=400, detail=f"Configuration already exists at {target_config}"
        )

    result = propose_creation(target_dir)
    if result.status in {"SKIPPED", "FAILED"}:
        raise HTTPException(status_code=400, detail=result.message)

    loaded = ConfigReader(target_config).load()
    state.config = loaded
    state.config_path = target_config
    state.active_directory = _choose_active_directory(target_config, loaded)
    return _config_response(state)


@router.post("/select-directory")
async def select_directory(payload: SelectDirectoryRequest, request: Request) -> dict:
    """Update active directory."""
    state: ServerState = request.app.state.server_state
    path = Path(payload.directory).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Directory does not exist")
    state.active_directory = path
    return _config_response(state)
