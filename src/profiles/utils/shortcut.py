"""Desktop shortcut creation utilities.

Provides cross-platform functions to create desktop shortcuts for applications.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path


def get_desktop_path() -> Path:
    """Get the desktop directory path for the current platform.

    Returns:
        Path to the desktop directory.

    Raises:
        RuntimeError: If desktop directory cannot be determined.
    """
    system = platform.system()
    desktop_path: Path | None = None

    if system == "Windows":
        desktop_path = _get_windows_desktop()
        if desktop_path is None:
            desktop_path = Path.home() / "Desktop"

    elif system == "Darwin":  # macOS
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            desktop_path = desktop
        else:
            fallback = Path.home() / "Documents" / "Desktop"
            desktop_path = fallback if fallback.exists() else desktop

    else:  # Linux and other Unix
        desktop_path = _get_linux_desktop()
        if desktop_path is None:
            desktop_path = Path.home() / "Desktop"

    return desktop_path


def _get_windows_desktop() -> Path | None:
    """Get Windows desktop path using API or environment fallback.

    Returns:
        Path to desktop or None if not found.
    """
    try:
        import ctypes

        csidl_desktop = 0x000C
        shgfp_type_current = 0

        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        result = ctypes.windll.shell32.SHGetFolderPathW(
            None, csidl_desktop, None, shgfp_type_current, buf
        )

        # Check if the API call succeeded
        if result == 0:
            desktop_path = Path(buf.value)
            if desktop_path.exists():
                return desktop_path
    except (AttributeError, ImportError, TypeError):
        pass

    # Fallback to environment variable
    desktop_env = os.environ.get("USERPROFILE")
    if desktop_env:
        fallback = Path(desktop_env) / "Desktop"
        if fallback.exists():
            return fallback

    return None


def _get_linux_desktop() -> Path | None:
    """Get Linux desktop path using XDG or common locations.

    Returns:
        Path to desktop or None if not found.
    """
    # Check for XDG desktop directory
    desktop = os.environ.get("XDG_DESKTOP_DIR")
    if desktop:
        path = Path.home() / desktop
        if path.exists():
            return path

    # Try common desktop locations
    for candidate in ["Desktop", "Bureau", "desktop"]:
        path = Path.home() / candidate
        if path.exists():
            return path

    return None


def create_shortcut(
    source_file: Path,
    desktop: Path | None = None,
    shortcut_name: str = "ProFiles",
) -> Path:
    """Copy ProFiles.pyw to the desktop for easy access.

    The copied file will use its own directory as CWD when launched.

    Args:
        source_file: Path to ProFiles.pyw
        desktop: Optional desktop path (auto-detected if not provided)
        shortcut_name: Name for the copied file (without extension)

    Returns:
        Path to the copied .pyw file on the desktop.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        RuntimeError: If desktop directory cannot be determined.
    """
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    if desktop is None:
        desktop = get_desktop_path()

    if not desktop.exists():
        raise RuntimeError(f"Desktop directory not found: {desktop}")

    # Copy the .pyw file to desktop
    dest_file = desktop / f"{shortcut_name}.pyw"
    shutil.copy2(source_file, dest_file)

    return dest_file
