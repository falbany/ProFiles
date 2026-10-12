"""Actions endpoints for OS launch, explorer reveal, and hash generation."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from profiles.core import actions
from profiles.utils.file_utils import open_file_explorer
from profiles.utils.network import get_username

router = APIRouter(prefix="/api/actions", tags=["actions"])


class LaunchRequest(BaseModel):
    directory: str
    filename: str
    release: str = ""
    args: str = ""


class RevealRequest(BaseModel):
    file_path: str


class HashRequest(BaseModel):
    file_path: str
    algorithm: str = "md5"


@router.post("/launch")
async def launch_file(payload: LaunchRequest) -> dict:
    """Launch selected program via OS association and workflow actions."""
    res = actions.launch_selected_file(
        directory=payload.directory,
        filename=payload.filename,
        release=payload.release,
        username=get_username(),
        args=payload.args,
    )
    if res.status != actions.ActionStatus.SUCCESS:
        raise HTTPException(status_code=400, detail=res.message)
    return {
        "status": str(res.status.value) if hasattr(res.status, "value") else str(res.status),
        "message": res.message,
        "path": str(res.path) if res.path else None,
    }


@router.post("/reveal")
async def reveal_file(payload: RevealRequest) -> dict:
    """Reveal file in host file explorer."""
    path = Path(payload.file_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")
    success = open_file_explorer(str(path))
    return {"success": success}


@router.post("/hash")
async def compute_hash(payload: HashRequest) -> dict:
    """Compute cryptographic hash of file."""
    path = Path(payload.file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File does not exist")

    algo = payload.algorithm.lower()
    if algo == "sha256":
        hasher = hashlib.sha256()
    elif algo == "md5":
        hasher = hashlib.md5()
    else:
        raise HTTPException(status_code=400, detail="Unsupported hash algorithm")

    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Error reading file") from exc

    return {"algorithm": algo, "hash": hasher.hexdigest()}
