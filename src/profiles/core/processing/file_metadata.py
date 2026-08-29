"""File metadata extraction for ProFiles.

Pure-domain helper that turns a filesystem path into a small dict
suitable for display in a properties dialog, tooltip, or CLI table.
Kept independent of any GUI/CLI front-end.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypedDict


class FileMetadata(TypedDict):
    """Snapshot of a file's basic properties."""

    name: str
    path: str
    size_bytes: int
    modified: str
    created: str


def get_file_metadata(file_path: Path) -> FileMetadata:
    """Return a metadata dict for *file_path*.

    Args:
        file_path: The file to inspect.

    Returns:
        A :class:`FileMetadata` with ``name``, ``path``, ``size_bytes``,
        ``modified`` and ``created`` (ISO-formatted timestamps).

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        OSError: If stat lookup fails for any other reason.
    """
    stat = file_path.stat()
    return FileMetadata(
        name=file_path.name,
        path=str(file_path),
        size_bytes=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        created=datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
    )
