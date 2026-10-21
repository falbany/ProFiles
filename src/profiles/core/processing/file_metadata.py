"""File metadata extraction for ProFiles.

Pure-domain helper that turns a filesystem path into a small dict
suitable for display in a properties dialog, tooltip, or CLI table.
Kept independent of any GUI/CLI front-end.
"""

from __future__ import annotations

import hashlib
import os
import stat as stat_module
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict


class FileMetadata(TypedDict):
    """Snapshot of a file's basic properties."""

    name: str
    path: str
    size_bytes: int
    modified: str
    created: str
    type: str
    md5: str
    sha256: str
    attributes: dict[str, Any]


def get_file_metadata(file_path: Path) -> FileMetadata:
    """Return a metadata dict for *file_path*.

    Args:
        file_path: The file to inspect.

    Returns:
        A :class:`FileMetadata` with comprehensive file information including
        cryptographic hashes and system attributes.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        OSError: If stat lookup fails for any other reason.
    """
    stat = file_path.stat()

    # Compute hashes
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            md5_hash.update(chunk)
            sha256_hash.update(chunk)

    # Determine file type
    file_type = _detect_file_type(file_path)

    # Extract system-specific attributes
    attributes = _extract_file_attributes(file_path, stat)

    return FileMetadata(
        name=file_path.name,
        path=str(file_path),
        size_bytes=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        created=datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds"),
        type=file_type,
        md5=md5_hash.hexdigest(),
        sha256=sha256_hash.hexdigest(),
        attributes=attributes,
    )


def _detect_file_type(file_path: Path) -> str:
    """Detect file type based on extension and content."""
    ext = file_path.suffix.lower()

    # Common file type mappings
    type_map = {
        ".py": "Python Script",
        ".js": "JavaScript File",
        ".ts": "TypeScript File",
        ".tsx": "React TypeScript Component",
        ".html": "HTML Document",
        ".css": "Cascading Style Sheet",
        ".json": "JSON Data File",
        ".xml": "XML Document",
        ".md": "Markdown Document",
        ".txt": "Text File",
        ".csv": "Comma-Separated Values",
        ".yaml": "YAML Configuration",
        ".yml": "YAML Configuration",
        ".toml": "TOML Configuration",
        ".ini": "INI Configuration",
        ".log": "Log File",
        ".exe": "Windows Executable",
        ".dll": "Dynamic Link Library",
        ".so": "Shared Object Library",
        ".png": "PNG Image",
        ".jpg": "JPEG Image",
        ".jpeg": "JPEG Image",
        ".gif": "GIF Image",
        ".svg": "SVG Vector Image",
        ".webp": "WebP Image",
        ".mp3": "MP3 Audio",
        ".mp4": "MP4 Video",
        ".wav": "WAV Audio",
        ".zip": "ZIP Archive",
        ".tar": "TAR Archive",
        ".gz": "GZIP Archive",
        ".7z": "7-Zip Archive",
        ".rar": "RAR Archive",
    }

    return type_map.get(ext, "Unknown File Type")


def _extract_file_attributes(file_path: Path, stat_result: Any) -> dict[str, Any]:
    """Extract system-specific file attributes."""
    attributes: dict[str, Any] = {
        "is_file": file_path.is_file(),
        "is_dir": file_path.is_dir(),
        "is_symlink": file_path.is_symlink(),
        "extension": file_path.suffix,
        "stem": file_path.stem,
        "parent": str(file_path.parent),
    }

    # Windows-specific attributes. CPython maps the DOS read-only attribute
    # onto st_mode: S_IWRITE is set when the file is writable, so read-only
    # is its negation. (The archive/hidden attributes are not represented
    # in st_mode and cannot be derived here.)
    if os.name == "nt":
        try:
            mode = stat_result.st_mode
            attributes["is_readonly"] = not mode & stat_module.S_IWRITE
        except OSError:
            pass
    else:
        # Unix permissions
        try:
            mode = stat_result.st_mode
            attributes["permissions"] = stat_module.filemode(mode)
            attributes["owner_uid"] = stat_result.st_uid
            attributes["group_gid"] = stat_result.st_gid
            attributes["is_executable"] = bool(mode & stat_module.S_IXUSR)
            attributes["is_readable"] = bool(mode & stat_module.S_IRUSR)
            attributes["is_writable"] = bool(mode & stat_module.S_IWUSR)
        except OSError:
            pass

    return attributes
