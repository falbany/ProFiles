"""Log viewer endpoints for inspecting the rotating ``profiles.log``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from profiles.core.telemetry import log_viewer

router = APIRouter(prefix="/api/logs", tags=["logs"])

# Matches the default used by ProFileApp; overridable per request.
_DEFAULT_LOG_PATH = "profiles.log"


@router.get("")
async def get_logs(
    limit: int = Query(default=500, ge=1, le=5000),
    level: str | None = Query(default=None),
    search: str = Query(default=""),
) -> dict:
    """Return the tail of the log file as structured entries.

    Args:
        limit: Maximum number of entries to return.
        level: Optional level name; entries at or above that severity are kept.
        search: Optional case-insensitive substring filter.

    Returns:
        A payload with ``path``, ``size_bytes``, ``total_returned`` and
        ``entries`` (oldest first). An empty entry list means the log is
        absent or fully filtered out — both are valid, non-error states.
    """
    normalized_level = level.upper() if level else None
    if normalized_level and normalized_level not in log_viewer.LOG_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown level '{level}'. Expected one of {list(log_viewer.LOG_LEVELS)}",
        )

    entries = log_viewer.read_log_entries(
        _DEFAULT_LOG_PATH,
        limit=limit,
        level=normalized_level,
        search=search,
    )
    return {
        "path": _DEFAULT_LOG_PATH,
        "size_bytes": log_viewer.log_file_size(_DEFAULT_LOG_PATH),
        "total_returned": len(entries),
        "entries": [
            {
                "timestamp": entry.timestamp,
                "level": entry.level,
                "source": entry.source,
                "message": entry.message,
                "event": entry.event,
                "raw": entry.raw,
            }
            for entry in entries
        ],
    }
