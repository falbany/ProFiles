"""Config endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from profiles.core.config.diagnostics import collect_config_issues
from profiles.core.config.io.yaml_io import CONFIG_FILE_NAMES
from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
from profiles.core.config.template import STARTER_CONFIG_TEMPLATE
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


class SaveRequest(BaseModel):
    content: str
    force: bool = False


class SaveAsRequest(BaseModel):
    content: str
    filename: str
    directory: str
    force: bool = False
    overwrite: bool = False


def _is_config_path(path: Path) -> bool:
    """True when *path*'s name matches the documented config whitelist.

    Case-insensitive on purpose: the save-as endpoint accepts
    ``BACKUP.PROFILES`` (its whitelist checks ``filename.lower()``), so the
    apply step that re-reads what was just written must accept it too — a
    case-sensitive comparison here turned a successful save-as into a 400
    with the file already on disk (branch review, issue #95 wave).
    """
    return path.name.lower().endswith(CONFIG_FILE_NAMES)


def _is_safe_filename(filename: str) -> bool:
    """Return True when *filename* is a bare name that cannot escape its directory.

    Hygiene guard for write endpoints: rejects empty names, ``.``/``..``
    dot segments, and path separators (``/``, ``\\``) so joining the
    filename onto a user directory can never traverse (cf. the
    path-traversal fix in issue #28).
    """
    if not filename or filename in {".", ".."}:
        return False
    return "/" not in filename and "\\" not in filename


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
    state.trial_content = None
    state.config_path = config_path
    state.active_directory = _choose_active_directory(loaded, config_path)
    return _config_response(state)


def validate_issues(content: str) -> list[dict[str, str]]:
    """Validate configuration *content* in memory without touching live state.

    Delegates to :func:`collect_config_issues`, which reports EVERY
    problem in the draft — unknown keys, bad ``extends`` references,
    cycles, schema violations — so the editor's Problems panel can list
    them all. Only the first YAML *syntax* error is reported (the parser
    stops there); until it is fixed there is no tree to validate further.

    Args:
        content: Raw YAML configuration content.

    Returns:
        ``[]`` when the content parses and validates, otherwise
        ``{"severity": "error", "message": ...}`` dicts, one per problem.
    """
    return collect_config_issues(content)


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
    # Remember the raw payload (issue #97): parsing discards it, and it is
    # the only record GET /content can echo for a path-less trial.
    state.trial_content = payload.content
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


@router.post("/template")
async def template_config_endpoint(request: Request) -> dict:
    """Render the starter configuration in memory; nothing written, no state change.

    In-memory render of the same content ``--init``/``propose_creation``
    writes to disk (the canonical :data:`STARTER_CONFIG_TEMPLATE`), powering
    the editor's New action. The ``{cwd}`` placeholder — the template's
    only single-brace placeholder — is substituted with the active
    directory so the rendered draft scans where the session points.
    """
    state: ServerState = request.app.state.server_state
    cwd = str(state.active_directory) if state.active_directory else str(Path.cwd())
    return {
        "content": STARTER_CONFIG_TEMPLATE.format(cwd=cwd),
        "filename": ".profiles",
    }


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
    state.trial_content = None
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
    issues = validate_issues(payload.content)
    return {"valid": not issues, "issues": issues}


@router.get("/content")
async def get_config_content(request: Request) -> dict:
    """Return the active configuration file's text for the YAML editor.

    Responds ``{"filename", "content", "config_path", "session_trial"}``.
    A session trial (config applied from dropped content) answers the
    text that was applied (``ServerState.trial_content``, issue #97) with
    ``session_trial=True`` and ``config_path=None`` — ``config_path``
    stays ``None`` so the stale CWD-resolved path never leaks, and
    ``filename`` carries the config's display name. A
    recorded-but-missing file answers 404.
    """
    state: ServerState = request.app.state.server_state
    if not has_disk_path(state):
        return {
            "filename": state.config.title or "session-trial",
            "content": state.trial_content or "",
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


@router.post("/save")
async def save_config_endpoint(payload: SaveRequest, request: Request) -> dict:
    """Write editor content to the active config file and apply it.

    Gate order: session-trial refusal (:func:`has_disk_path`) →
    :func:`validate_issues` → 400 with the issues list when invalid and
    not ``force`` → write the file → :func:`_apply_config_from_disk`, so
    the live configuration is always re-read from what is on disk.
    ``force=True`` is the escape hatch that lets a broken draft reach the
    disk (it will load as defaults until fixed); without it, bad YAML
    never touches the file.

    Returns ``{"status": "SAVED", "path": str, "config": <config dict>}``;
    the apply step clears ``session_trial``, anchoring the saved config
    to its file.
    """
    state: ServerState = request.app.state.server_state
    if not has_disk_path(state):
        raise HTTPException(
            status_code=400,
            detail="Cannot save: the active configuration is a session trial "
            "with no file on disk. Load or create a configuration first.",
        )

    config_path = state.active_config_path()
    issues = validate_issues(payload.content)
    if issues and not payload.force:
        raise HTTPException(status_code=400, detail=issues)

    config_path.write_text(payload.content, encoding="utf-8")
    config = _apply_config_from_disk(state, config_path)
    return {"status": "SAVED", "path": str(config_path), "config": config}


SAVE_AS_EXTENSIONS = (".profiles", ".profiles.yaml")


@router.post("/save-as")
async def save_as_config_endpoint(payload: SaveAsRequest, request: Request) -> dict:
    """Write editor content to a new config file and apply it.

    Unlike :func:`save_config_endpoint`, save-as is anchored to a
    user-supplied directory and filename, so it works both to copy a
    disk-anchored config and to anchor a session trial onto disk. Gate
    order: filename hygiene (:func:`_is_safe_filename` — no separators,
    dot segments, or empty names) → extension whitelist
    (:data:`SAVE_AS_EXTENSIONS`) → :func:`normalize_user_path` +
    directory existence → existence/overwrite guard (409 when the target
    exists without ``overwrite=True``) → :func:`validate_issues` → 400
    with the issues list when invalid and not ``force`` → write the file
    → :func:`_apply_config_from_disk`, so the live configuration is
    always re-read from what is on disk (which also clears
    ``session_trial``).

    Returns ``{"status": "SAVED", "path": str, "config": <config dict>}``,
    the same shape as ``POST /save``.
    """
    state: ServerState = request.app.state.server_state

    if not _is_safe_filename(payload.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration file name: {payload.filename}",
        )

    if not payload.filename.lower().endswith(SAVE_AS_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Not a ProFiles configuration file: {payload.filename}. "
            f"Allowed extensions: {', '.join(SAVE_AS_EXTENSIONS)}",
        )

    target_dir = normalize_user_path(payload.directory)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="Directory does not exist")

    target = target_dir / payload.filename
    if target.exists() and not payload.overwrite:
        raise HTTPException(
            status_code=409,
            detail=f"Configuration already exists at {target}. "
            "Retry with overwrite=true to replace it.",
        )

    issues = validate_issues(payload.content)
    if issues and not payload.force:
        raise HTTPException(status_code=400, detail=issues)

    target.write_text(payload.content, encoding="utf-8")
    config = _apply_config_from_disk(state, target)
    return {"status": "SAVED", "path": str(target), "config": config}


@router.post("/select-directory")
async def select_directory(payload: SelectDirectoryRequest, request: Request) -> dict:
    """Update active directory."""
    state: ServerState = request.app.state.server_state
    path = normalize_user_path(payload.directory)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Directory does not exist")
    state.active_directory = path
    return _config_response(state)
