"""Round-trip YAML I/O for ProFiles configuration files.

Single Responsibility: read and write the YAML file while preserving
comments, ordering, and formatting (via ``ruamel.yaml``). No domain
knowledge, no models.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections import deque
from pathlib import Path

from ruamel.yaml import YAML

# ``.profiles`` is the primary configuration file; the fallbacks below are
# used, in order, only when no ``.profiles`` exists anywhere in the tree.
PRIMARY_CONFIG_NAME = ".profiles"
FALLBACK_CONFIG_NAMES: tuple[str, ...] = (".profiles.yaml", ".profiles.yml")

#: Every accepted configuration file name, primary first.
CONFIG_FILE_NAMES: tuple[str, ...] = (PRIMARY_CONFIG_NAME, *FALLBACK_CONFIG_NAMES)


def is_config_file_name(name: str) -> bool:
    """True when a file *name* matches the accepted config whitelist.

    Case-insensitive on purpose: the save-as endpoint accepts
    ``BACKUP.PROFILES`` (issue #95 wave), so every apply-path gate must
    re-accept what it wrote. Shared by the server's config-name check and
    the desktop odoc applier's skip guard (issue #193).
    """
    return name.lower().endswith(CONFIG_FILE_NAMES)


_yaml = YAML()
_yaml.preserve_quotes = True


def read_yaml(path: Path | str) -> dict:
    """Read a YAML file into a plain dict (or raise).

    Args:
        path: Path to the configuration file.

    Returns:
        The parsed YAML mapping.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ruamel.yaml.YAMLError: If the file is not valid YAML.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    with p.open("r", encoding="utf-8") as fh:
        return _yaml.load(fh) or {}


def read_yaml_text(text: str) -> dict:
    """Parse a YAML string into a plain dict (or raise).

    In-memory counterpart of :func:`read_yaml` — same parser, no disk
    access. Used for content that never touches a file (e.g. dropped
    configuration previews).

    Raises:
        ruamel.yaml.YAMLError: If *text* is not valid YAML.
    """
    return _yaml.load(text) or {}


def write_value(path: Path | str, dotted_key: str, value: object) -> None:
    """Set a nested key in the YAML file, preserving comments/formatting.

    Args:
        path: Path to the configuration file.
        dotted_key: Dotted path, e.g. ``"defaults.theme"``.
        value: Value to write (bool, str, int, list, ...).
    """
    p = Path(path)
    if p.exists():
        with p.open("r", encoding="utf-8") as fh:
            data = _yaml.load(fh) or {}
    else:
        data = {}

    parts = dotted_key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value

    with p.open("w", encoding="utf-8") as fh:
        _yaml.dump(data, fh)


def write_text_atomic(path: Path | str, content: str) -> None:
    """Write *content* to *path* atomically (temp file + ``os.replace``).

    A plain ``write_text`` can leave a truncated file behind when the
    process dies or power is lost mid-write — and the configuration file
    is the user's only one. The text is written to a temp file created in
    the *same directory* (so ``os.replace`` stays on one filesystem and
    remains atomic), flushed to disk, then renamed over the target.

    Args:
        path: Destination file path.
        content: Full text to write (UTF-8 encoded).
    """
    p = Path(path)
    fd, tmp_name = tempfile.mkstemp(
        dir=p.parent,
        prefix=f"{p.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, p)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def content_hash(content: str) -> str:
    """Return the SHA-256 hex digest of *content* (UTF-8 encoded).

    Version marker returned by ``GET /api/config/content`` and compared
    by ``POST /api/config/save`` against the on-disk file, so an external
    edit landing between the editor's load and its Save is detected
    instead of silently clobbered (issue #116).

    Args:
        content: Text to fingerprint.

    Returns:
        Lowercase hex digest string.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _find_named_file(start: Path, name: str, max_depth: int) -> Path | None:
    """Return the first *name* file within *max_depth* of *start*.

    The search is breadth-first, so when several matches exist the one
    closest to the tree root wins.  Symlinked directories are not
    descended into, which keeps the walk finite.

    Args:
        start: Resolved directory to start the search from.
        name: Exact filename to look for (e.g. ``.profiles``).
        max_depth: Maximum depth of subdirectories to search.

    Returns:
        The first matching file path, or ``None``.
    """
    queue: deque[tuple[Path, int]] = deque([(start, 0)])
    while queue:
        current, depth = queue.popleft()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        children: list[tuple[Path, int]] = []
        for entry in entries:
            try:
                if entry.is_file() and entry.name == name:
                    return Path(entry.path)
                if entry.is_dir(follow_symlinks=False) and depth + 1 <= max_depth:
                    children.append((Path(entry.path), depth + 1))
            except OSError:
                continue
        queue.extend(children)
    return None


def _is_unsafe_search_root(path: Path) -> bool:
    """Return True when *path* must never be walked as a search root.

    Briefcase bundles launch the app with ``CWD=/``; a depth-N subtree
    scan from the filesystem root (POSIX ``/``, Windows drive roots)
    would walk the entire disk looking for a config file.
    """
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return resolved.parent == resolved


def _find_wildcard_config(start: Path, max_depth: int) -> Path | None:
    """Breadth-first search for any ``<name>.profiles(…yaml|…yml)`` file.

    Reached only when no canonical name exists anywhere in the tree, so
    named configurations such as ``a.profiles`` or ``backup.profiles.yaml``
    are still discovered. All matches are collected, then sorted ascending
    by ``(depth, name, path)``: the shallowest match wins, ties broken by
    ascending file name — in the common single-folder case, simply the
    alphabetically first configuration file.

    Args:
        start: Resolved directory to start the search from.
        max_depth: Maximum depth of subdirectories to search.

    Returns:
        The first matching configuration file path, or ``None``.
    """
    candidates: list[tuple[int, str, str]] = []
    queue: deque[tuple[Path, int]] = deque([(start, 0)])
    while queue:
        current, depth = queue.popleft()
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        children: list[tuple[Path, int]] = []
        for entry in entries:
            try:
                if entry.is_file() and entry.name.endswith(CONFIG_FILE_NAMES):
                    candidates.append((depth, entry.name, entry.path))
                elif entry.is_dir(follow_symlinks=False) and depth + 1 <= max_depth:
                    children.append((Path(entry.path), depth + 1))
            except OSError:
                continue
        queue.extend(children)
    if not candidates:
        return None
    candidates.sort()
    return Path(candidates[0][2])


def find_config_file(
    start_path: Path | None = None,
    max_depth: int = 5,
) -> Path | None:
    """Search the subtree of *start_path* for a ProFiles configuration file.

    The canonical names are searched first, breadth-first: the primary
    ``.profiles`` file wins wherever it appears; ``.profiles.yaml`` then
    ``.profiles.yml`` are used as fallbacks only when no ``.profiles`` file
    is found in the tree. When no canonical name exists anywhere, ANY file
    whose name ends with one of these suffixes (``a.profiles``,
    ``backup.profiles.yaml``, …) is accepted: the shallowest match wins,
    ties broken by ascending file name — in the common single-folder case,
    the alphabetically first configuration file is launched.

    Args:
        start_path: Starting directory (default: current working directory).
        max_depth: Maximum depth of subdirectories to search (default: 5).

    Returns:
        The path to the first matching configuration file, or ``None``.
    """
    if start_path is None:
        start_path = Path.cwd()

    start = start_path.resolve()
    if not start.is_dir():
        return None

    if _is_unsafe_search_root(start):
        return None

    for name in CONFIG_FILE_NAMES:
        found = _find_named_file(start, name, max_depth)
        if found is not None:
            return found
    return _find_wildcard_config(start, max_depth)


__all__ = [
    "CONFIG_FILE_NAMES",
    "FALLBACK_CONFIG_NAMES",
    "PRIMARY_CONFIG_NAME",
    "content_hash",
    "find_config_file",
    "is_config_file_name",
    "read_yaml",
    "write_text_atomic",
    "write_value",
]
