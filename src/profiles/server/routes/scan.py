"""Scanner endpoints with scan execution and result retrieval."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from profiles.core.config import service as config_service
from profiles.core.processing import scanner
from profiles.server.state import ServerState

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
    if payload.directory:
        state.active_directory = Path(payload.directory).expanduser().resolve()

    if not state.active_directory:
        raise HTTPException(status_code=400, detail="Active directory is not set")

    if not state.active_directory.exists():
        state.cached_results = []
        return {
            "count": 0,
            "directory": str(state.active_directory),
            "warning": "Directory does not exist",
        }

    state.scan_in_progress = True
    try:
        active = config_service.find_active_config(state.config, str(state.active_directory))
        exclude_files = (
            active.search_exclude_files if active is not None else state.config.search_exclude_files
        )
        results = await asyncio.to_thread(
            scanner.scan_and_process_dynamic,
            directories=str(state.active_directory),
            config=state.config,
            extension=payload.extension,
            filter_text=payload.filter_text,
            recursive=payload.recursive,
            exclude_dirs=state.config.search_exclude_dirs,
            exclude_files=exclude_files,
            column_names=state.config.column_names,
            columns=state.config.columns,
        )
        state.cached_results = results
        return {"count": len(results), "directory": str(state.active_directory)}
    finally:
        state.scan_in_progress = False


@router.get("/results")
async def get_scan_results(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=50_000),
) -> dict:
    """Return cached scan results formatted for table rendering.

    Supports pagination via ``offset`` / ``limit`` so the frontend never has
    to serialise tens of thousands of rows at once. When ``limit`` is omitted
    the full list is returned (backwards compatible).
    """
    state: ServerState = request.app.state.server_state
    cached = state.cached_results
    total = len(cached)
    page = cached if limit is None else cached[offset : offset + limit]

    items = []
    for r in page:
        file_path = getattr(r, "path", None)
        path_obj = Path(file_path) if file_path is not None else None
        fname = path_obj.name if path_obj else str(r)
        col_vals = getattr(r, "column_values", {})
        items.append(
            {
                "filename": fname,
                "path": str(path_obj) if path_obj else "",
                "column_values": col_vals,
                "rel_path": getattr(r, "rel_path", ""),
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
