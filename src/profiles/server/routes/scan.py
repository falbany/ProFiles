"""Scanner endpoints with scan execution and result retrieval."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from profiles.core.config.models import AppConfig
from profiles.core.environment.matcher import select_most_specific_pattern
from profiles.core.processing import scanner
from profiles.core.processing.column_extractor import ATTRIBUTE_KEYWORDS
from profiles.core.processing.file_metadata import FileAttrs
from profiles.core.processing.watcher import DirectoryWatcher
from profiles.server.state import ServerState
from profiles.utils.path_utils import normalize_user_path

router = APIRouter(prefix="/api/scan", tags=["scan"])

# Attribute keyword → :class:`FileAttrs` field read for typed sorting.
# ``ATTRIBUTE_KEYWORDS`` (core) gates which keywords resolve at all; this
# map is the authority for the raw stat field each keyword sorts on.
_ATTR_FIELD_BY_KEYWORD: dict[str, str] = {
    "size": "size_bytes",
    "size_bytes": "size_bytes",
    "modified": "mtime",
    "created": "birthtime",
}


class ScanRequest(BaseModel):
    directory: str = ""
    extension: str = ""
    filter_text: str = ""
    recursive: bool = True


@router.post("")
async def execute_scan(payload: ScanRequest, request: Request) -> dict:
    """Execute dynamic scan on the active directory and cache results.

    Keeps the watch in step with the scan (#223): records the recursion
    intent, re-targets a running watcher onto the scanned directory, and
    stops the watch when the scanned directory is missing.
    """
    state: ServerState = request.app.state.server_state
    state.scan_generation += 1
    scan_generation = state.scan_generation
    # Reset BEFORE any early return so every scan start — including the
    # missing-directory one — begins the progress strip from zero (#152).
    state.scan_progress_count = 0
    if payload.directory:
        state.active_directory = normalize_user_path(payload.directory)

    # Watch re-target (issue #223): every scan records the recursion intent
    # it was issued with, then a running watcher follows the active
    # directory — restarted onto the new root (a full restart IS the
    # re-target: it re-baselines the snapshot and re-resolves the
    # per-directory boundary), or stopped when the root is dead so no
    # poller is left watching a missing directory. The helpers take
    # ``_watch_lock`` themselves; no outer lock here (double-acquire on a
    # non-reentrant Lock deadlocks).
    state.watch_recursive = payload.recursive
    if state.watcher is not None:
        target = state.active_directory
        if target is None or not target.exists():
            _stop_watcher(state, error="Watch stopped: directory does not exist")
        else:
            _start_watcher(state, recursive=payload.recursive)

    scan_directory = state.active_directory
    if not scan_directory:
        raise HTTPException(status_code=400, detail="Active directory is not set")

    if not scan_directory.exists():
        if scan_generation == state.scan_generation:
            state.cached_results = []
            state.scan_in_progress = False
        return {
            "count": 0,
            "directory": str(scan_directory),
            "warning": "Directory does not exist",
        }

    state.scan_in_progress = True

    def _push_progress(count: int) -> None:
        # Generation-guarded: late callbacks from a superseded scan must
        # not pollute a newer scan's counter (#152).
        if scan_generation == state.scan_generation:
            state.scan_progress_count = count

    try:
        results = await asyncio.to_thread(
            scanner.scan_and_process_dynamic,
            directories=str(scan_directory),
            config=state.config,
            extension=payload.extension,
            filter_text=payload.filter_text,
            recursive=payload.recursive,
            # The web checkbox is explicit user intent: it always wins over
            # any matching machine-config recursive_search override
            # (recursive= is still honored when the override is somehow None).
            recursive_override=payload.recursive,
            column_names=state.config.column_names,
            columns=state.config.columns,
            on_progress=_push_progress,
        )
        if scan_generation == state.scan_generation:
            state.cached_results = results
        return {"count": len(results), "directory": str(scan_directory)}
    finally:
        if scan_generation == state.scan_generation:
            state.scan_in_progress = False


class WatchRequest(BaseModel):
    """Body of the watch-mode toggle."""

    enabled: bool
    recursive: bool = True


def _shutdown_watcher(state: ServerState, *, error: str | None) -> None:
    """Lock-free watcher teardown shared by the start/stop helpers.

    The caller must hold ``state._watch_lock``. Stops the active watcher
    (if any), drops it from state and records or clears ``watch_error``.
    """
    watcher = state.watcher
    if watcher is not None:
        watcher.stop()
    state.watcher = None
    state.watch_error = error


def _stop_watcher(state: ServerState, *, error: str | None = None) -> None:
    """Stop the active watch and record or clear its error state.

    Safe against concurrent enable/disable: the whole body runs under
    ``state._watch_lock``. ``watcher.stop()`` joins the poller thread
    (bounded by the watcher's join timeout); a same-thread call — an
    ``on_error`` fired from the watcher thread — returns without joining
    (guarded inside the watcher).
    """
    # ``_watch_lock`` is the brief-specified watch-state lock owned by
    # ServerState; the server routes are its designated operator, so the
    # underscore access is intra-package, not a client-class reach-in.
    with state._watch_lock:  # pylint: disable=protected-access
        _shutdown_watcher(state, error=error)


def _start_watcher(state: ServerState, *, recursive: bool) -> None:
    """Start (or replace) the directory watcher on the active directory.

    The probe's depth and excludes come from
    :func:`scanner.effective_search_boundary` — the same merge that
    governs a scan of the same root. Callbacks capture *state* only:
    ``on_change`` bumps ``watch_seq`` under the lock (cheap and
    non-blocking — the watcher-thread contract), ``on_error`` stops and
    records the message. Any previous watcher is stopped first, so at
    most one poller runs; a fresh enable clears a stale ``watch_error``.
    """
    with state._watch_lock:  # pylint: disable=protected-access
        _shutdown_watcher(state, error=None)
        directory = state.active_directory
        if directory is None:  # The route 400s before this; fail safe.
            return

        depth, exclude_dirs = scanner.effective_search_boundary(
            str(directory), state.config, recursive=recursive
        )

        def _on_change() -> None:
            with state._watch_lock:  # pylint: disable=protected-access
                state.watch_seq += 1

        def _on_error(message: str) -> None:
            _stop_watcher(state, error=message)

        watcher = DirectoryWatcher(
            directory,
            exclude_dirs=exclude_dirs,
            max_depth=depth,
            on_change=_on_change,
            on_error=_on_error,
        )
        watcher.start()
        state.watcher = watcher
        state.watch_error = None


@router.post("/watch")
async def set_watch_mode(payload: WatchRequest, request: Request) -> dict:
    """Enable or disable watch mode on the active directory.

    Returns the resulting watching state and the watcher's current
    adaptive interval (``None`` when not watching).
    """
    state: ServerState = request.app.state.server_state
    if payload.enabled:
        if not state.active_directory:
            raise HTTPException(status_code=400, detail="Active directory is not set")
        # Record the recursion intent on enable too (#223): enable-with-
        # recursive-false must mirror the non-recursive boundary on a
        # later re-enable, exactly like a scan does.
        state.watch_recursive = payload.recursive
        _start_watcher(state, recursive=payload.recursive)
    else:
        _stop_watcher(state)
    watcher = state.watcher
    return {
        "watching": watcher is not None,
        "interval_s": watcher.interval_s if watcher is not None else None,
    }


def _sort_key(column: str) -> Callable[[Any], Any]:
    """Build a case-insensitive natural sort key for a scan result column.

    Values are text extracted from the file name or the extracted columns, so
    digit runs compare numerically: ``item2`` sorts before ``item10``. Rows
    whose column value is missing or identical fall back to the file name,
    which keeps large scans usefully ordered instead of leaving ties in
    arbitrary scan order.
    """

    def natural(text: str) -> list[int | str]:
        return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]

    def key(row: Any) -> tuple[list[int | str], list[int | str]]:
        return (natural(_column_value(row, column)), natural(_row_filename(row)))

    return key


def _row_filename(row: Any) -> str:
    """Return the file name of a scan result row as a string."""
    path = getattr(row, "path", None)
    return Path(path).name if path is not None else str(row)


def _column_value(row: Any, column: str) -> str:
    """Return the display value of *row* for *column* as a string."""
    values = getattr(row, "column_values", None) or {}
    value = values.get(column)
    if value is None or value == "":
        value = _row_filename(row)
    return str(value)


def _attr_field(column: str, config: AppConfig | None) -> str | None:
    """Return the :class:`FileAttrs` field backing *column*, else ``None``.

    A column is attribute-backed when its configured ``match`` keyword is
    one of the core ``ATTRIBUTE_KEYWORDS`` (``size``, ``size_bytes``,
    ``modified``, ``created``); the returned field names the raw stat value
    that typed sorting must use. Unconfigured columns, plain regex columns
    and missing configurations yield ``None`` so the caller keeps its
    natural-text sort.
    """
    if config is None:
        return None
    rule = config.columns.get(column)
    if rule is None:
        return None
    keyword = str(getattr(rule, "match", "")).lower()
    if keyword not in ATTRIBUTE_KEYWORDS:
        return None
    return _ATTR_FIELD_BY_KEYWORD.get(keyword)


def _attrs_payload(attrs: FileAttrs | None) -> dict[str, int | float] | None:
    """Serialize a row's stat snapshot for the JSON payload.

    Returns ``None`` for rows without a snapshot (the scan never statted
    the file) so the web client can render the cell as empty.
    """
    if attrs is None:
        return None
    return {
        "size_bytes": attrs.size_bytes,
        "mtime": attrs.mtime,
        "birthtime": attrs.birthtime,
    }


def _sorted_results(
    cached: list[Any],
    sort_by: str | None,
    descending: bool,
    config: AppConfig | None,
) -> tuple[list[Any], bool]:
    """Order *cached* for *sort_by* and report whether any row moved.

    An attribute-backed column sorts on the raw :class:`FileAttrs` field
    (``900 KB`` ranks below ``10 MB`` by bytes, not by text); rows without
    a snapshot trail the sorted rows in *both* directions. Other columns
    keep the natural-text key; an unknown column leaves the list in scan
    order.

    Returns:
        The ordered list and ``sort_applied`` — ``True`` only when the
        sort actually reordered at least one row.
    """
    attr_field = _attr_field(sort_by, config) if sort_by else None
    if attr_field is not None:
        with_attrs = [r for r in cached if getattr(r, "attrs", None) is not None]
        without_attrs = [r for r in cached if getattr(r, "attrs", None) is None]
        with_attrs.sort(key=lambda row: getattr(row.attrs, attr_field), reverse=descending)
        return with_attrs + without_attrs, bool(with_attrs)
    if sort_by and any(sort_by in (getattr(r, "column_values", None) or {}) for r in cached):
        return sorted(cached, key=_sort_key(sort_by), reverse=descending), True
    return cached, False


@router.get("/results")
async def get_scan_results(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=50_000),
    sort_by: str | None = Query(default=None),
    sort_dir: Literal["asc", "desc"] | None = Query(default=None),
    find_path: str | None = Query(default=None),
) -> dict:
    """Return cached scan results formatted for table rendering.

    Supports pagination via ``offset`` / ``limit`` so the frontend never has
    to serialise tens of thousands of rows at once. When ``limit`` is omitted
    the full list is returned (backwards compatible).

    Sorting is applied to the *whole* cached result set before paging, so
    pages fetched later keep the requested order. When ``sort_by`` names a
    column that does not exist, the list is left in scan order.

    An attribute-backed column (``match`` resolves to a stat keyword) sorts
    on the raw :class:`FileAttrs` field instead of the rendered text; see
    :func:`_sorted_results` for the ordering contract.

    When ``find_path`` is given, the response short-circuits to
    ``{"count": int, "offset": int}`` — the row's position in the ordered
    set (``-1`` when absent) with no ``items`` key (#218 selection
    preservation).
    """
    state: ServerState = request.app.state.server_state
    total = len(state.cached_results)

    # ``sort_dir == "desc"`` is inlined (single use) to keep the local count
    # within the pylint budget — the find_path parameter is the 20th.
    cached, sort_applied = _sorted_results(
        state.cached_results, sort_by, sort_dir == "desc", state.config
    )

    # Selection lookup (#218): the client only wants a row's offset in the
    # ordered set — skip item serialization so huge caches answer without
    # building thousands of dicts.
    if find_path is not None:
        return {
            "count": total,
            "offset": next(
                (i for i, row in enumerate(cached) if str(getattr(row, "path", "")) == find_path),
                -1,
            ),
        }

    page = cached if limit is None else cached[offset : offset + limit]

    hook_patterns = list(state.config.launch_hooks.keys()) if state.config.launch_hooks else []

    items = []
    for r in page:
        file_path = getattr(r, "path", None)
        path_obj = Path(file_path) if file_path is not None else None
        fname = path_obj.name if path_obj else str(r)
        col_vals = getattr(r, "column_values", {})
        matched_hook = select_most_specific_pattern(hook_patterns, fname) if hook_patterns else None
        items.append(
            {
                "filename": fname,
                "path": str(path_obj) if path_obj else "",
                "column_values": col_vals,
                "rel_path": getattr(r, "rel_path", ""),
                "has_hook": bool(matched_hook),
                "hook_pattern": matched_hook,
                "attrs": _attrs_payload(getattr(r, "attrs", None)),
            }
        )
    response: dict = {
        "count": total,
        "in_progress": state.scan_in_progress,
        "items": items,
    }
    if limit is not None:
        response["offset"] = offset
        response["limit"] = limit
        response["has_more"] = offset + len(items) < total
    if sort_applied:
        response["sort_by"] = sort_by
        response["sort_dir"] = sort_dir or "asc"
    return response


def scan_status_payload(state: ServerState) -> dict:
    """Build one `status` SSE event payload from the current scan state."""
    watcher = state.watcher
    return {
        "in_progress": state.scan_in_progress,
        "count": len(state.cached_results),
        "progress": state.scan_progress_count,
        "directory": str(state.active_directory) if state.active_directory else "",
        "watching": watcher is not None,
        "watch_interval_s": watcher.interval_s if watcher is not None else None,
        "watch_seq": state.watch_seq,
        "watch_error": state.watch_error,
    }


@router.get("/events")
async def scan_events(request: Request) -> EventSourceResponse:
    """Server-Sent Events streaming scan status."""
    state: ServerState = request.app.state.server_state

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            # Pre-serialize: the installed sse-starlette str()-ifies dict
            # payloads (Python repr, unparseable by browser EventSource
            # clients — the reason this endpoint was dead surface in #143).
            yield {
                "event": "status",
                "data": json.dumps(scan_status_payload(state)),
            }
            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
