"""Round-trip YAML I/O for ProFiles configuration files.

Single Responsibility: read and write the YAML file while preserving
comments, ordering, and formatting (via ``ruamel.yaml``). No domain
knowledge, no models.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

# ``.profiles`` is the primary configuration file; ``.profiles.yaml`` is
# kept as a backward-compatible fallback when the primary is absent.
PRIMARY_CONFIG_NAME = ".profiles"
FALLBACK_CONFIG_NAME = ".profiles.yaml"

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

    Args:
        start: Resolved directory to start the search from.
        name: Exact filename to look for (e.g. ``.profiles``).
        max_depth: Maximum depth of subdirectories to search.

    Returns:
        The first matching file path, or ``None``.
    """
    for candidate in start.rglob(name):
        try:
            relative = candidate.relative_to(start)
            depth = len(relative.parts) - 1
            if depth <= max_depth and candidate.is_file():
                return candidate
        except ValueError:
            continue
    return None


def find_config_file(
    start_path: Path | None = None,
    max_depth: int = 5,
) -> Path | None:
    """Search the CWD subtree for a ProFiles configuration file.

    The primary ``.profiles`` file wins; ``.profiles.yaml`` is used as a
    fallback only when no ``.profiles`` file is found in the tree.

    Args:
        start_path: Starting directory (default: current working directory).
        max_depth: Maximum depth of subdirectories to search (default: 5).

    Returns:
        The path to the first ``.profiles`` (or ``.profiles.yaml``) found,
        or ``None``.
    """
    if start_path is None:
        start_path = Path.cwd()

    start = start_path.resolve()
    if not start.is_dir():
        return None

    primary = _find_named_file(start, PRIMARY_CONFIG_NAME, max_depth)
    if primary is not None:
        return primary
    return _find_named_file(start, FALLBACK_CONFIG_NAME, max_depth)


__all__ = [
    "FALLBACK_CONFIG_NAME",
    "PRIMARY_CONFIG_NAME",
    "find_config_file",
    "read_yaml",
    "write_value",
]
