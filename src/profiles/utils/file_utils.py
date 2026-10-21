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
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from functools import lru_cache
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
    return suffix_of_name(os.path.basename(str(file)))


def suffix_of_name(name: str) -> str:
    """Full compound extension of a *name* — the ``Path.suffixes`` rule.

    Reproduces ``"".join(Path(name).suffixes)`` exactly (including the
    empty result for trailing-dot and all-dot names, and the leading-dot
    handling for dotfiles), without constructing a :class:`Path`.

    Args:
        name: The file name (may include no dots at all).

    Returns:
        The full compound extension (leading dots included), or ``""``.
    """
    if name.endswith("."):
        return ""
    stem = name.lstrip(".")
    return "".join("." + part for part in stem.split(".")[1:])


def _matches_extension(file: Path | str, ext_lower: str) -> bool:
    """Check if a file matches the given extension filter.

    Supports compound extensions (e.g. ``.my.pdf``) by comparing
    against the full suffix via :func:`suffix_of_name`.

    Args:
        file: The file path or string filename to check.
        ext_lower: Lowercase extension without leading dot (e.g. 'mttl').
            Empty string or 'all' matches every file.

    Returns:
        True if the file matches the filter.
    """
    name = file if isinstance(file, str) else os.path.basename(str(file))
    return not ext_lower or ext_lower == "all" or suffix_of_name(name).lower() == f".{ext_lower}"


def _match_nothing(_name: str) -> bool:
    """Predicate for an empty pattern tuple: excludes nothing."""
    return False


@lru_cache(maxsize=64)
def _compile_excludes(patterns: tuple[str, ...]) -> Callable[[str], bool]:
    """Build a memoized ``name -> bool`` predicate for glob *patterns*.

    One combined regex from every ``fnmatch.translate`` pattern,
    both patterns and names lowercased (case-insensitive semantics as
    in the previous per-pattern ``fnmatch.fnmatchcase`` loop).
    """
    if not patterns:
        return _match_nothing
    combined = "|".join(fnmatch.translate(p.lower()) for p in patterns)
    regex = re.compile(combined)

    def match(name: str) -> bool:
        return regex.match(name.lower()) is not None

    return match


def _is_excluded(name: str, patterns: tuple[str, ...]) -> bool:
    """Return True if *name* matches any glob *pattern* (case-insensitive).

    Patterns use shell-style wildcards (``*``, ``?``, ``[seq]``) — see
    :mod:`fnmatch`. An entry of bare ``"*"`` excludes every directory,
    which is rarely useful in practice but is allowed for completeness.
    """
    return _compile_excludes(patterns)(name)


def _report_skip(
    on_skip: Callable[[str, str], None] | None, path: object, exc: BaseException
) -> None:
    """Report a scan skip through the caller's ``on_skip`` callback.

    Args:
        on_skip: The ``path, error_text`` callback (``None`` keeps the
            historical silent behavior).
        path: The unreadable entry or directory path.
        exc: The OS error that caused the skip.
    """
    if on_skip is not None:
        on_skip(str(path), str(exc))


def _classify(
    entry: os.DirEntry[str],
    ext_lower: str,
    exclude_dirs: tuple[str, ...],
    exclude_files: tuple[str, ...],
    name_filter: Callable[[str], bool] | None,
    on_skip: Callable[[str, str], None] | None,
) -> tuple[str, Path] | None:
    """Classify one directory entry.

    Returns:
        ``("dir", path)`` to descend into the (non-excluded) directory,
        ``("file", path)`` for a file that passes every check, or
        ``None`` to skip the entry. Unreadable entries are reported via
        *on_skip* (silent when ``None``).
    """
    try:
        if entry.is_dir(follow_symlinks=False):
            if _is_excluded(entry.name, exclude_dirs):
                return None
            return ("dir", Path(entry.path))
        if (
            entry.is_file(follow_symlinks=False)
            and _matches_extension(entry.name, ext_lower)
            and not _is_excluded(entry.name, exclude_files)
        ):
            if name_filter is not None and not name_filter(entry.name):
                return None
            return ("file", Path(entry.path))
    except OSError as exc:
        _report_skip(on_skip, entry.path, exc)
    return None


def _scan_subtree(
    root: Path | str,
    ext_lower: str,
    exclude_dirs: tuple[str, ...] = (),
    exclude_files: tuple[str, ...] = (),
    current_depth: int = 1,
    max_depth: int = 10,
    on_skip: Callable[[str, str], None] | None = None,
    name_filter: Callable[[str], bool] | None = None,
) -> list[Path]:
    """Worker: recursively scan a directory subtree for matching files.

    Designed for use with ThreadPoolExecutor — one subtree per thread.
    Directories whose name matches any glob pattern in *exclude_dirs*
    are skipped entirely (including all their children).  Files whose
    name matches any glob pattern in *exclude_files* are skipped.

    Unreadable entries or directories are skipped and reported through
    the *on_skip* callback (``None`` keeps silent behavior).

    Args:
        root: The root of the subtree to scan.
        ext_lower: Lowercase extension filter (empty = all files).
        exclude_dirs: Glob patterns (case-insensitive) for directory
            basenames to skip during recursive walk.
        exclude_files: Glob patterns (case-insensitive) for file
            basenames to skip during recursive walk.
        current_depth: Internal recursion tracker (root files = depth 0).
        max_depth: Maximum directory recursion depth.
        on_skip: Optional ``(path, error_text)`` callback invoked for
            every entry or directory that cannot be read.
        name_filter: Optional predicate applied to each *matching* file
            name (after the extension and exclude-files checks, before
            the Path is built); returning ``False`` skips the file.

    Returns:
        List of matching file paths in this subtree.
    """
    if current_depth > max_depth:
        return []

    files: list[Path] = []
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                classified = _classify(
                    entry, ext_lower, exclude_dirs, exclude_files, name_filter, on_skip
                )
                if classified is None:
                    continue
                tag, path = classified
                if tag == "dir":
                    files.extend(
                        _scan_subtree(
                            path,
                            ext_lower,
                            exclude_dirs,
                            exclude_files,
                            current_depth + 1,
                            max_depth,
                            on_skip,
                            name_filter,
                        )
                    )
                else:
                    files.append(path)
    except OSError as exc:
        _report_skip(on_skip, root, exc)
    return files


def scan_directory(
    directory: str | Path,
    extension: str = "",
    recursive: bool = False,
    exclude_dirs: tuple[str, ...] = (),
    exclude_files: tuple[str, ...] = (),
    max_depth: int = 10,
    on_skip: Callable[[str, str], None] | None = None,
    name_filter: Callable[[str], bool] | None = None,
) -> list[Path]:
    """Scan a directory for files matching the given extension.

    Non-recursive scans use a single-pass ``os.scandir``.
    Recursive scans dispatch each top-level subdirectory to a thread
    pool for parallel I/O on large trees. Directories whose name
    matches any glob pattern in *exclude_dirs* are skipped entirely.
    Files whose name matches any glob pattern in *exclude_files* are
    skipped (applies to both recursive and non-recursive scans).

    Unreadable entries or directories are skipped; when *on_skip* is
    given it receives ``(path, error_text)`` for each one (``None``
    keeps the historical silent behavior).

    Args:
        directory: The directory to scan.
        extension: File extension to filter by (e.g., 'pdf').
            NOTE: contrast with the search pipeline's extension filter
            (:func:`profiles.utils.search_parser.match_filter`,
            substring matching) — this parameter uses exact suffix
            equality.  If empty or 'All', returns all files.
        recursive: If True, scan subdirectories recursively.
        exclude_dirs: Glob patterns (case-insensitive) for directory
            basenames to skip during recursive walk. Supports ``*``,
            ``?`` and ``[seq]`` wildcards (e.g. ``Debug*``,
            ``*tmp``, ``node_modules``).
        exclude_files: Glob patterns (case-insensitive) for file
            basenames to skip. Supports the same wildcards as
            *exclude_dirs* (e.g. ``*backup*``, ``*.tmp``, ``~$*``).
        max_depth: Maximum recursion depth for recursive scan (default 10).
        on_skip: Optional ``(path, error_text)`` callback invoked for
            every entry or directory that cannot be read.
        name_filter: Optional predicate applied to each *matching* file
            name (after the extension and exclude-files checks, before
            the Path is built); returning ``False`` skips the file.

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
                    classified = _classify(
                        entry, ext_lower, exclude_dirs, exclude_files, name_filter, on_skip
                    )
                    if classified is not None and classified[0] == "file":
                        files.append(classified[1])
        except OSError as exc:
            _report_skip(on_skip, scan_path, exc)
        return sorted(files)

    # ── Recursive: parallel subtree scanning via os.scandir ──────────
    # Collect top-level children first (skip excluded directories)
    subdirs: list[Path] = []
    root_files: list[Path] = []
    try:
        with os.scandir(scan_path) as entries:
            for entry in entries:
                classified = _classify(
                    entry, ext_lower, exclude_dirs, exclude_files, name_filter, on_skip
                )
                if classified is None:
                    continue
                tag, path = classified
                if tag == "dir":
                    subdirs.append(path)
                else:
                    root_files.append(path)
    except OSError as exc:
        _report_skip(on_skip, scan_path, exc)

    # Scan each subdirectory subtree in parallel
    collections = [root_files]
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_dir = {
            executor.submit(
                _scan_subtree,
                subdir,
                ext_lower,
                exclude_dirs,
                exclude_files,
                1,
                max_depth,
                on_skip,
                name_filter,
            ): subdir
            for subdir in subdirs
        }
        for future in concurrent.futures.as_completed(future_to_dir):
            try:
                result = future.result()
                if result:
                    collections.append(result)
            except Exception as exc:  # noqa: BLE001  # guard against worker crashes
                _report_skip(on_skip, future_to_dir[future], exc)

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

    Args are split with ``shlex`` (POSIX rules; no shell is invoked on
    POSIX — the command vector is passed directly to the OS).  Empty
    *args* returns ``False`` — the caller falls back to
    :func:`launch_file`.

    Returns ``True`` once the launcher process was spawned; the child is
    never waited on.  Exceptions are swallowed to match
    :func:`launch_file`.

    Windows caveat: the Windows branch still goes through ``cmd.exe``
    (``cmd /c start``), so shell metacharacters are interpreted there;
    ``os.startfile`` cannot take arguments.
    """
    try:
        tokens = shlex.split(args)
    except ValueError:
        return False
    if not tokens:
        return False

    try:
        if _IS_WINDOWS:
            # Windows keeps ``cmd /c start``: os.startfile cannot take arguments.
            subprocess.Popen(["cmd", "/c", "start", "", str(path), *tokens])
        elif _IS_MACOS:
            subprocess.Popen(["open", str(path), *tokens])
        else:
            subprocess.Popen(["xdg-open", str(path), *tokens])
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
