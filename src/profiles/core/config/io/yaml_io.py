"""Round-trip YAML I/O for ProFiles configuration files.

Single Responsibility: read and write the YAML file while preserving
comments, ordering, and formatting (via ``ruamel.yaml``). No domain
knowledge, no models.
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path

from ruamel.yaml import YAML

# ``.profiles`` is the primary configuration file; the fallbacks below are
# used, in order, only when no ``.profiles`` exists anywhere in the tree.
PRIMARY_CONFIG_NAME = ".profiles"
FALLBACK_CONFIG_NAMES: tuple[str, ...] = (".profiles.yaml", ".profiles.yml")

#: Every accepted configuration file name, primary first.
CONFIG_FILE_NAMES: tuple[str, ...] = (PRIMARY_CONFIG_NAME, *FALLBACK_CONFIG_NAMES)

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


def find_config_file(
    start_path: Path | None = None,
    max_depth: int = 5,
) -> Path | None:
    """Search the subtree of *start_path* for a ProFiles configuration file.

    The primary ``.profiles`` file wins wherever it appears; ``.profiles.yaml``
    then ``.profiles.yml`` are used as fallbacks only when no ``.profiles``
    file is found in the tree.

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

    for name in CONFIG_FILE_NAMES:
        found = _find_named_file(start, name, max_depth)
        if found is not None:
            return found
    return None


__all__ = [
    "CONFIG_FILE_NAMES",
    "FALLBACK_CONFIG_NAMES",
    "PRIMARY_CONFIG_NAME",
    "find_config_file",
    "read_yaml",
    "write_value",
]
