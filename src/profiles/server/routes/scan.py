"""Scanner endpoints with scan execution and result retrieval."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from profiles.core.processing import scanner
from profiles.server.state import ServerState

router = APIRouter(prefix="/api/scan", tags=["scan"])


class ScanRequest(BaseModel):
    extension: str = ""
    filter_text: str = ""
    recursive: bool = True


@router.post("")
async def execute_scan(payload: ScanRequest, request: Request) -> dict:
    """Execute dynamic scan on the active directory and cache results."""
    state: ServerState = request.app.state.server_state
    if not state.active_directory or not state.active_directory.exists():
        raise HTTPException(status_code=400, detail="Active directory is not set or does not exist")

    state.scan_in_progress = True
    try:
        results = await asyncio.to_thread(
            scanner.scan_and_process_dynamic,
            directories=str(state.active_directory),
            config=state.config,
            extension=payload.extension,
            filter_text=payload.filter_text,
            recursive=payload.recursive,
        )
        state.cached_results = results
        return {"count": len(results), "directory": str(state.active_directory)}
    finally:
        state.scan_in_progress = False


@router.get("/results")
async def get_scan_results(request: Request) -> dict:
    """Return cached scan results formatted for table rendering."""
    state: ServerState = request.app.state.server_state
    items = []
    for r in state.cached_results:
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
    return {
        "count": len(items),
        "in_progress": state.scan_in_progress,
        "items": items,
    }


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
