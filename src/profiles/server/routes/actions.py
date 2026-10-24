"""Actions endpoints for OS launch, explorer reveal, and hash generation."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from profiles.core import actions
from profiles.core.processing.file_metadata import get_file_metadata
from profiles.core.telemetry.diagnostics import default_log_path
from profiles.server.state import ServerState
from profiles.utils.file_utils import open_file_explorer
from profiles.utils.network import get_username

logger = logging.getLogger("profiles.server.actions")

router = APIRouter(prefix="/api/actions", tags=["actions"])


class LaunchRequest(BaseModel):
    directory: str
    filename: str
    release: str = ""
    args: str = ""


class PathRequest(BaseModel):
    file_path: str


class LaunchWithArgsRequest(BaseModel):
    file_path: str
    args: str = ""


@router.post("/open-folder")
async def open_folder(payload: PathRequest) -> dict:
    """Open folder in host file manager."""
    path = Path(payload.file_path).expanduser().resolve()
    target_dir = path if path.is_dir() else path.parent
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directory does not exist")
    success = open_file_explorer(str(target_dir))
    return {"success": success}


@router.post("/open-terminal")
async def open_terminal(payload: PathRequest) -> dict:
    """Open host terminal in file's directory."""
    path = Path(payload.file_path).expanduser().resolve()
    target_dir = path if path.is_dir() else path.parent
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directory does not exist")
    res = actions.open_terminal_in_directory(target_dir)
    return {
        "status": str(res.status.value) if hasattr(res.status, "value") else str(res.status),
        "message": res.message,
    }


@router.post("/launch-with-args")
async def launch_with_args(payload: LaunchWithArgsRequest) -> dict:
    """Launch file with explicit arguments."""
    path = Path(payload.file_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")
    launched = actions.launch_file_with_args(path, payload.args)
    if not launched:
        raise HTTPException(status_code=400, detail=f"Failed to launch file: {path}")
    return {
        "status": "success",
        "message": f"Launched {path}",
    }


@router.post("/open-log")
async def open_log() -> dict:
    """Open log file in default application."""
    log_path = default_log_path()
    res = actions.open_log_file(log_path)
    return {
        "status": str(res.status.value) if hasattr(res.status, "value") else str(res.status),
        "message": res.message,
    }


@router.post("/open-config")
async def open_config(request: Request) -> dict:
    """Open the active configuration file in default application."""
    state: ServerState = request.app.state.server_state
    res = actions.open_config_file(state.active_config_path())
    return {
        "status": str(res.status.value) if hasattr(res.status, "value") else str(res.status),
        "message": res.message,
    }


class HashRequest(BaseModel):
    file_path: str
    algorithm: str = "md5"


@router.post("/launch")
async def launch_file(payload: LaunchRequest, request: Request) -> dict:
    """Launch selected program via OS association and workflow actions."""
    state = getattr(request.app.state, "server_state", None)
    config = getattr(state, "config", None) if state else None
    logger = getattr(state, "logger", None) if state else None
    res = actions.launch_selected_file(
        directory=payload.directory,
        filename=payload.filename,
        release=payload.release,
        username=get_username(),
        args=payload.args,
        config=config,
        logger=logger,
    )
    if res.status != actions.ActionStatus.SUCCESS:
        raise HTTPException(status_code=400, detail=res.message)
    return {
        "status": str(res.status.value) if hasattr(res.status, "value") else str(res.status),
        "message": res.message,
        "path": str(res.path) if res.path else None,
    }


@router.post("/reveal")
async def reveal_file(payload: PathRequest) -> dict:
    """Reveal file in host file explorer."""
    path = Path(payload.file_path).expanduser().resolve()
    result = actions.reveal_in_file_manager(path)
    if result.status != actions.ActionStatus.SUCCESS:
        status_code = 404 if result.status == actions.ActionStatus.NOT_FOUND else 500
        raise HTTPException(status_code=status_code, detail=result.message)
    return {
        "status": str(result.status.value),
        "message": result.message,
        "path": str(result.path) if result.path else None,
    }


@router.post("/metadata")
async def file_metadata(payload: PathRequest) -> dict:
    """Return basic metadata for a file."""
    path = Path(payload.file_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="File does not exist")
    try:
        return get_file_metadata(path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read file metadata: {exc}") from exc


@router.post("/delete")
async def delete_file(payload: PathRequest) -> dict:
    """Delete a file after the client has obtained user confirmation."""
    path = Path(payload.file_path).expanduser().resolve()
    result = actions.clear_file(path)
    if result.status != actions.ActionStatus.SUCCESS:
        status_code = 404 if result.status == actions.ActionStatus.NOT_FOUND else 400
        raise HTTPException(status_code=status_code, detail=result.message)
    return {
        "status": str(result.status.value),
        "message": result.message,
        "path": str(result.path) if result.path else None,
    }


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


class BarcodeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    file_path: str | None = Field(default=None, alias="filePath")
    content: str | None = None


@router.post("/barcode")
async def generate_barcode(payload: BarcodeRequest):
    """Generate a QR code image encoding the file location as a ProFiles barcode payload.

    The QR content uses the structured ``key=value`` format that the ProFiles
    barcode scanner understands so the recipient can scan it directly into
    their instance.

    **Payload format (default):** ``dir=<parent>;filter=<filename>;scan=1``
    """
    from io import BytesIO

    import qrcode

    if payload.content:
        qr_content = payload.content
    elif payload.file_path:
        path = Path(payload.file_path).expanduser().resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail="File does not exist")

        # Build the barcode payload that the scanner can parse back
        if path.is_dir():
            dir_str = str(path)
            filename = ""
            ext = ""
        else:
            dir_str = str(path.parent)
            filename = path.name
            ext = path.suffix

        parts = [f"dir={dir_str}"]
        if filename:
            parts.append(f"filter={filename}")
        if ext:
            parts.append(f"ext={ext}")
        parts.append("scan=1")

        qr_content = ";".join(parts)
    else:
        raise HTTPException(status_code=400, detail="Missing file_path or content")

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

    buf = BytesIO()
    img.save(buf, format="PNG")
    png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "image": f"data:image/png;base64,{png_b64}",
        "content": qr_content,
    }
