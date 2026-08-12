"""File system utilities for ProFiles.

Provides stateless helper functions for scanning directories, launching files,
and other filesystem operations. Domain-specific logic (classification, version
extraction) is delegated to profiles.core.file_service.
"""

from __future__ import annotations

import concurrent.futures
import fnmatch
import hashlib
import os
import shlex
import subprocess
import sys
from pathlib import Path

# Cache sys.platform to avoid the attribute lookup on every call.
_IS_WINDOWS = sys.platform.startswith("win") or os.name == "nt"
_IS_MACOS = sys.platform == "darwin"

# Default thread count for parallel recursive scanning
_MAX_WORKERS = min(32, (os.cpu_count() or 1) * 2)


def _full_suffix(file: Path | str) -> str:
    """Get the full compound extension of a file or filename.

    Unlike :attr:`Path.suffix` (which only returns the *last* extension,
    e.g. ``.lnk`` for ``foo.mttx.lnk``), this returns all extension
    parts joined together (e.g. ``.mttx.lnk``).

    Args:
        file: The file path or string filename.

    Returns:
        The full compound extension string, including the leading dot.
        Returns ``""`` for files without an extension.
    """
    if isinstance(file, Path):
        return "".join(file.suffixes)
    name = os.path.basename(file)
    dot_idx = name.find(".")
    if dot_idx in (-1, 0):
        return ""
    return name[dot_idx:]


def _matches_extension(file: Path | str, ext_lower: str) -> bool:
    """Check if a file matches the given extension filter.

    Supports compound extensions (e.g. ``.my.pdf``) by comparing
    against the full suffix via :func:`_full_suffix`.

    Args:
        file: The file path or string filename to check.
        ext_lower: Lowercase extension without leading dot (e.g. 'mttl').
            Empty string or 'all' matches every file.

    Returns:
        True if the file matches the filter.
    """
    return not ext_lower or ext_lower == "all" or _full_suffix(file).lower() == f".{ext_lower}"


def _is_excluded(name: str, patterns: tuple[str, ...]) -> bool:
    """Return True if *name* matches any glob *pattern* (case-insensitive).

    Patterns use shell-style wildcards (``*``, ``?``, ``[seq]``) — see
    :mod:`fnmatch`. An entry of bare ``"*"`` excludes every directory,
    which is rarely useful in practice but is allowed for completeness.
    """
    name_lower = name.lower()
    return any(fnmatch.fnmatchcase(name_lower, p.lower()) for p in patterns)


def _scan_subtree(
    root: Path | str,
    ext_lower: str,
    exclude_dirs: tuple[str, ...] = (),
    exclude_files: tuple[str, ...] = (),
) -> list[Path]:
    """Worker: recursively scan a directory subtree for matching files.

    Designed for use with ThreadPoolExecutor — one subtree per thread.
    Directories whose name matches any glob pattern in *exclude_dirs*
    are skipped entirely (including all their children).  Files whose
    name matches any glob pattern in *exclude_files* are skipped.
    Silently skips directories without read permission.

    Args:
        root: The root of the subtree to scan.
        ext_lower: Lowercase extension filter (empty = all files).
        exclude_dirs: Glob patterns (case-insensitive) for directory
            basenames to skip during recursive walk.
        exclude_files: Glob patterns (case-insensitive) for file
            basenames to skip during recursive walk.

    Returns:
        List of matching file paths in this subtree.
    """
    files: list[Path] = []
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not _is_excluded(entry.name, exclude_dirs):
                            files.extend(
                                _scan_subtree(entry.path, ext_lower, exclude_dirs, exclude_files)
                            )
                        continue
                    if (
                        entry.is_file(follow_symlinks=False)
                        and _matches_extension(entry.name, ext_lower)
                        and not _is_excluded(entry.name, exclude_files)
                    ):
                        files.append(Path(entry.path))
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return files


def scan_directory(
    directory: str | Path,
    extension: str = "",
    recursive: bool = False,
    exclude_dirs: tuple[str, ...] = (),
    exclude_files: tuple[str, ...] = (),
) -> list[Path]:
    """Scan a directory for files matching the given extension.

    Non-recursive scans use a single-pass ``os.scandir``.
    Recursive scans dispatch each top-level subdirectory to a thread
    pool for parallel I/O on large trees. Directories whose name
    matches any glob pattern in *exclude_dirs* are skipped entirely.
    Files whose name matches any glob pattern in *exclude_files* are
    skipped (applies to both recursive and non-recursive scans).

    Args:
        directory: The directory to scan.
        extension: File extension to filter by (e.g., 'pdf').
            If empty or 'All', returns all files.
        recursive: If True, scan subdirectories recursively.
        exclude_dirs: Glob patterns (case-insensitive) for directory
            basenames to skip during recursive walk. Supports ``*``,
            ``?``, and ``[seq]`` wildcards (e.g. ``Debug*``,
            ``*tmp``, ``node_modules``).
        exclude_files: Glob patterns (case-insensitive) for file
            basenames to skip. Supports the same wildcards as
            *exclude_dirs* (e.g. ``*backup*``, ``*.tmp``, ``~$*``).

    Returns:
        Sorted list of matching file paths.
    """
    scan_path = Path(directory)
    if not scan_path.is_dir():
        return []

    ext_lower = extension.lower().lstrip(".")

    # ── Non-recursive: fast single-pass via os.scandir ───────────────
    if not recursive:
        files: list[Path] = []
        try:
            with os.scandir(scan_path) as entries:
                for entry in entries:
                    try:
                        if (
                            entry.is_file(follow_symlinks=False)
                            and _matches_extension(entry.name, ext_lower)
                            and not _is_excluded(entry.name, exclude_files)
                        ):
                            files.append(Path(entry.path))
                    except (PermissionError, OSError):
                        pass
        except (PermissionError, OSError):
            pass
        return sorted(files)

    # ── Recursive: parallel subtree scanning via os.scandir ──────────
    # Collect top-level children first (skip excluded directories)
    subdirs: list[Path] = []
    root_files: list[Path] = []
    try:
        with os.scandir(scan_path) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not _is_excluded(entry.name, exclude_dirs):
                            subdirs.append(Path(entry.path))
                    elif (
                        entry.is_file(follow_symlinks=False)
                        and _matches_extension(entry.name, ext_lower)
                        and not _is_excluded(entry.name, exclude_files)
                    ):
                        root_files.append(Path(entry.path))
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass

    # Scan each subdirectory subtree in parallel
    collections = [root_files]
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = [
            executor.submit(_scan_subtree, subdir, ext_lower, exclude_dirs, exclude_files)
            for subdir in subdirs
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result:
                    collections.append(result)
            except Exception:  # noqa: BLE001  # guard against worker crashes
                pass

    # Flatten and sort
    all_files: list[Path] = []
    for col in collections:
        all_files.extend(col)
    return sorted(all_files)


def open_file_explorer(directory: str | Path) -> bool:
    """Open a directory in the system file explorer.

    Args:
        directory: The directory to open.

    Returns:
        True if successful, False otherwise.
    """
    try:
        path = Path(directory)
        if path.is_dir():
            if _IS_WINDOWS:
                os.startfile(str(path))
            elif _IS_MACOS:
                subprocess.run(["open", str(path)], check=True)
            else:
                subprocess.run(["xdg-open", str(path)], check=True)
            return True
        return False
    except Exception:
        return False


def launch_file(file_path: str | Path) -> bool:
    """Launch/Open a file using the OS default association.

    Args:
        file_path: Path to the file to launch.

    Returns:
        True if the file was launched successfully, False otherwise.
    """
    try:
        path = Path(file_path)
        if not path.is_file():
            return False

        if _IS_WINDOWS:
            os.startfile(str(path))
        elif _IS_MACOS:
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        return True
    except Exception:
        return False


def open_with_default_app(file_path: str | Path) -> bool:
    """Open a file with the OS default application.

    Same backend as :func:`launch_file` but skips the *is_file* check so
    it can be used for documents like ``.log`` or ``.ini`` that should
    open in the user's default text editor / viewer.

    Args:
        file_path: Path to the file to open.

    Returns:
        True if the file was opened successfully, False otherwise.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return False
        if _IS_WINDOWS:
            os.startfile(str(path))
        elif _IS_MACOS:
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        return True
    except Exception:
        return False


def launch_file_with_args(path: Path, args: str) -> bool:
    """Launch *path* with extra CLI *args* using the OS default association.

    Args are split with ``shlex`` (POSIX rules); no shell metacharacter
    injection.  Empty *args* returns ``False`` — the caller falls back
    to :func:`launch_file`.

    Returns ``True`` only when the child process was successfully
    spawned.  Exceptions are swallowed to match :func:`launch_file`.
    """
    try:
        tokens = shlex.split(args)
    except ValueError:
        return False
    if not tokens:
        return False

    try:
        if sys.platform == "win32":
            with subprocess.Popen(  # noqa: S602,S607 - intentional shell invocation
                ["cmd", "/c", "start", "", str(path), *tokens]
            ):
                pass
        elif sys.platform == "darwin":
            with subprocess.Popen(["open", str(path), *tokens]):  # noqa: S607
                pass
        else:
            with subprocess.Popen(["xdg-open", str(path), *tokens]):  # noqa: S607
                pass
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def list_directory_paths(directories: list[str | Path]) -> list[Path]:
    """Convert a list of path strings to Path objects, filtering non-directories.

    Args:
        directories: List of directory paths.

    Returns:
        List of valid Path objects representing existing directories.
    """
    return [Path(d) for d in directories if Path(d).is_dir()]


# Chunk size for streaming hash reads. 64 KiB matches the underlying
# hashlib block size for the standard algorithms.
_HASH_CHUNK_SIZE = 65536


def hash_file(file_path: str | Path, algorithm: str = "sha256") -> str:
    """Compute the hex digest of *file_path* using the given *algorithm*.

    Streams the file in 64 KiB chunks so it works for large test
    programs without loading them into memory.

    Args:
        file_path: Path to the file to hash.
        algorithm: Name of the algorithm (``"md5"`` or ``"sha256"``).
            Anything supported by :func:`hashlib.new` works.

    Returns:
        Lowercase hex digest of the file contents.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
        OSError: If the file cannot be read.
        ValueError: If *algorithm* is not a valid hashlib algorithm.
    """
    hasher = hashlib.new(algorithm.lower())
    with open(file_path, "rb") as fh:
        while True:
            block = fh.read(_HASH_CHUNK_SIZE)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()
