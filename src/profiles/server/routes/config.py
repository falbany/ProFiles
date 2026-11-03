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
from profiles.utils.path_utils import normalize_user_path

router = APIRouter(prefix="/api/config", tags=["config"])


class SelectDirectoryRequest(BaseModel):
    directory: str


class LoadConfigRequest(BaseModel):
    config_path: str


class LoadContentRequest(BaseModel):
    filename: str
    content: str


class CreateConfigRequest(BaseModel):
    directory: str


class ValidateRequest(BaseModel):
    content: str
    filename: str


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


def _choose_active_directory(cfg: AppConfig, config_path: Path | None) -> Path:
    """Re-derive the active directory exactly like a launch with *cfg*.

    Uses the shared launch-time selection (``search_dir`` → hostname-matched
    machine config → first existing scan dir). ``config_path.parent`` — the
    folder containing the ``.profiles`` file — is only a last resort for
    configs whose scan dirs exist nowhere, ahead of ``Path.cwd()``. For
    dropped (path-less) configs, pass ``config_path=None``.
    """
    from profiles.core.config import service as config_service
    from profiles.utils.network import get_hostname

    selected = config_service.choose_active_directory(cfg, get_hostname())
    if selected is not None:
        return selected
    if config_path is not None and config_path.parent.exists() and config_path.parent.is_dir():
        return config_path.parent
    return Path.cwd()


def _apply_config_from_disk(state: ServerState, config_path: Path) -> dict:
    """Validate, load, and apply a config file from disk; return the response.

    Shared by the in-app load endpoint and the cross-instance handoff
    (issue #4) so both apply a launch-equivalent state: config swap,
    ``config_path`` recorded, and the active directory re-derived exactly
    like a launch with this file.

    Raises:
        HTTPException: 400 when the path is missing or not a config file.
    """
    if not config_path.exists():
        raise HTTPException(status_code=400, detail=f"Config file does not exist: {config_path}")
    if not _is_config_path(config_path):
        raise HTTPException(
            status_code=400,
            detail=f"Not a ProFiles configuration file: {config_path}",
        )

    loaded = ConfigReader(config_path).load()
    state.config = loaded
    state.session_trial = False
    state.config_path = config_path
    state.active_directory = _choose_active_directory(loaded, config_path)
    return _config_response(state)


def validate_issues(content: str, display_name: str) -> list[dict[str, str]]:
    """Validate configuration *content* in memory without touching live state.

    Parses *content* strictly with :meth:`ConfigReader.from_content` and
    reports the outcome as a plain issue list, so the YAML editor can
    validate content that is not applied to the session.

    Args:
        content: Raw YAML configuration content.
        display_name: Human-readable file name used in error messages.

    Returns:
        ``[]`` when the content parses and validates, otherwise a single
        ``{"severity": "error", "message": ...}`` dict describing the
        failure.
    """
    try:
        ConfigReader.from_content(content, display_name=display_name)
    except ValueError as exc:
        return [{"severity": "error", "message": str(exc)}]
    return []


def has_disk_path(state: ServerState) -> bool:
    """Return True when the active configuration is backed by a recorded file.

    The explicit :attr:`ServerState.session_trial` flag takes precedence
    over path presence: a configuration applied from dropped content
    (``POST /load-content``) is a session trial with no disk anchor, even
    though the shared ``_config_response`` helper re-records a resolved
    path into the state for every response (existing shared behavior).
    Save endpoints gate on this helper to refuse writing to a merely
    CWD-resolved path instead of the trial's source.
    """
    return not state.session_trial and (
        state.config_path is not None or getattr(state.config, "config_path", None) is not None
    )


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
    return _apply_config_from_disk(state, config_path)


_ACCEPTED_DROP_SUFFIXES = (
    ".profiles",
    ".profiles.yaml",
    ".profiles.yml",
    ".yaml",
    ".yml",
)


@router.post("/load-content")
async def load_content_endpoint(payload: LoadContentRequest, request: Request) -> dict:
    """Apply a dropped configuration file as a session-only trial.

    The content is parsed in memory and swaps the live configuration.
    Nothing is written to disk and ``config_path`` stays untouched, so
    restart resolution is unaffected. ``active_directory`` IS re-derived
    from the new config exactly like a launch (search_dir → hostname
    match → first existing scan dir), because the extension/filter merge
    pipeline is keyed on that directory — keeping the previous one would
    evaluate the new config against a stale directory.
    """
    state: ServerState = request.app.state.server_state
    if not payload.filename.lower().endswith(_ACCEPTED_DROP_SUFFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Not a ProFiles configuration file: {payload.filename}",
        )

    try:
        loaded = ConfigReader.from_content(payload.content, display_name=payload.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state.config = loaded
    state.session_trial = True
    state.active_directory = _choose_active_directory(loaded, None)
    response = _config_response(state)
    response["session_trial"] = True
    return response


@router.post("/create")
async def create_config_endpoint(payload: CreateConfigRequest, request: Request) -> dict:
    """Create a starter config in the requested directory."""
    state: ServerState = request.app.state.server_state
    target_dir = normalize_user_path(payload.directory)
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
    state.session_trial = False
    state.config_path = target_config
    state.active_directory = _choose_active_directory(loaded, target_config)
    return _config_response(state)


@router.post("/reload")
async def reload_config_endpoint(request: Request) -> dict:
    """Re-read the active configuration file from disk.

    The active path is resolved exactly like launch time
    (``ServerState.active_config_path``), so Reload picks up edits made
    to the attached ``.profiles`` file without restarting the server.
    """
    state: ServerState = request.app.state.server_state
    config_path = state.active_config_path()

    if not config_path.exists():
        # Degrade gracefully: keep the in-memory configuration and let the
        # client explain the situation instead of silently wiping state.
        response = _config_response(state)
        response["reloaded"] = False
        return response

    try:
        loaded = ConfigReader.from_content(
            config_path.read_text(encoding="utf-8"),
            display_name=config_path.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded.config_path = config_path
    state.config = loaded
    state.session_trial = False
    state.config_path = config_path
    state.active_directory = _choose_active_directory(loaded, config_path)
    response = _config_response(state)
    response["reloaded"] = True
    return response


@router.post("/validate")
async def validate_config_endpoint(payload: ValidateRequest) -> dict:
    """Validate editor content in memory; never applied to the session state.

    Returns ``{"valid": bool, "issues": [...]}`` rather than an HTTP error
    status, so invalid drafts reach the editor as data to display.
    """
    issues = validate_issues(payload.content, display_name=payload.filename)
    return {"valid": not issues, "issues": issues}


@router.get("/content")
async def get_config_content(request: Request) -> dict:
    """Return the active configuration file's text for the YAML editor.

    Responds ``{"filename", "content", "config_path", "session_trial"}``.
    A session trial (config applied from dropped content) answers an
    empty body flagged ``session_trial=True`` — ``config_path`` stays
    ``None`` so the stale CWD-resolved path never leaks, and ``filename``
    carries the config's display name — instead of file text; a
    recorded-but-missing file answers 404.
    """
    state: ServerState = request.app.state.server_state
    if not has_disk_path(state):
        return {
            "filename": state.config.title or "session-trial",
            "content": "",
            "config_path": None,
            "session_trial": True,
        }

    config_path = state.active_config_path()
    if not config_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Configuration file not found: {config_path}",
        )

    return {
        "filename": config_path.name,
        "content": config_path.read_text(encoding="utf-8"),
        "config_path": str(config_path),
        "session_trial": False,
    }


@router.post("/select-directory")
async def select_directory(payload: SelectDirectoryRequest, request: Request) -> dict:
    """Update active directory."""
    state: ServerState = request.app.state.server_state
    path = normalize_user_path(payload.directory)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Directory does not exist")
    state.active_directory = path
    return _config_response(state)
