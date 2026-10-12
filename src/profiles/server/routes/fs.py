"""Filesystem exploration endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/fs", tags=["fs"])


@router.get("/browse")
async def browse_fs(path: str = Query(default="")) -> dict:
    """Browse filesystem directory entries."""
    target_path = Path(path).expanduser().resolve() if path else Path.home()
    if not target_path.exists() or not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not an accessible directory")

    items = []
    try:
        for entry in sorted(target_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            # Skip hidden files
            if entry.name.startswith("."):
                continue
            items.append(
                {
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                }
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc

    return {
        "current_path": str(target_path),
        "parent_path": str(target_path.parent) if target_path.parent != target_path else None,
        "items": items,
    }
