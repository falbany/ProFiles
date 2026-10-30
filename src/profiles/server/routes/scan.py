"""Scanner endpoints with scan execution and result retrieval."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from profiles.core.environment.matcher import select_most_specific_pattern
from profiles.core.processing import scanner
from profiles.server.state import ServerState
from profiles.utils.path_utils import normalize_user_path

router = APIRouter(prefix="/api/scan", tags=["scan"])


class ScanRequest(BaseModel):
    directory: str = ""
    extension: str = ""
    filter_text: str = ""
    recursive: bool = True


@router.post("")
async def execute_scan(payload: ScanRequest, request: Request) -> dict:
    """Execute dynamic scan on the active directory and cache results."""
    state: ServerState = request.app.state.server_state
    state.scan_generation += 1
    scan_generation = state.scan_generation
    if payload.directory:
        state.active_directory = normalize_user_path(payload.directory)

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
        )
        if scan_generation == state.scan_generation:
            state.cached_results = results
        return {"count": len(results), "directory": str(scan_directory)}
    finally:
        if scan_generation == state.scan_generation:
            state.scan_in_progress = False


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


@router.get("/results")
async def get_scan_results(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=50_000),
    sort_by: str | None = Query(default=None),
    sort_dir: Literal["asc", "desc"] | None = Query(default=None),
) -> dict:
    """Return cached scan results formatted for table rendering.

    Supports pagination via ``offset`` / ``limit`` so the frontend never has
    to serialise tens of thousands of rows at once. When ``limit`` is omitted
    the full list is returned (backwards compatible).

    Sorting is applied to the *whole* cached result set before paging, so
    pages fetched later keep the requested order. When ``sort_by`` names a
    column that does not exist, the list is left in scan order.
    """
    state: ServerState = request.app.state.server_state
    cached = state.cached_results
    total = len(cached)

    sort_applied = False
    descending = sort_dir == "desc"
    if sort_by and any(sort_by in (getattr(r, "column_values", None) or {}) for r in cached):
        cached = sorted(cached, key=_sort_key(sort_by), reverse=descending)
        sort_applied = True

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


@router.get("/events")
async def scan_events(request: Request) -> EventSourceResponse:
    """Server-Sent Events streaming scan status."""
    state: ServerState = request.app.state.server_state

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            yield {
                "event": "status",
                "data": {
                    "in_progress": state.scan_in_progress,
                    "count": len(state.cached_results),
                    "directory": str(state.active_directory) if state.active_directory else "",
                },
            }
            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
