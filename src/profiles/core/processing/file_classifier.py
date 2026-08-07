"""File system domain operations for ProFiles.

Contains business logic for file classification, version extraction,
and path operations specific to the ProFiles domain.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from profiles.core.processing.column_extractor import ColumnExtractor


def ensure_trailing_separator(path: str | Path) -> str:
    """Ensure the path ends with the OS path separator.

    Args:
        path: Directory path.

    Returns:
        Path string guaranteed to end with os.sep.
    """
    path_str = str(path)
    if not path_str.endswith(os.sep):
        path_str += os.sep
    return path_str


def directory_exists(path: str | Path) -> bool:
    """Check if a directory exists.

    Args:
        path: Directory path to check.

    Returns:
        True if the path exists and is a directory.
    """
    return Path(path).is_dir()


def extract_version(filename: str, extension: str = "") -> str:
    """Extract the version string from a filename.

    The version is extracted from the pattern '_V<version>' (case-insensitive),
    For example::

        ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl -> '01-Rel6.2.1'

    Args:
        filename: The file name to extract the version from.
        extension: Optional file extension to strip from the version.

    Returns:
        Extracted version string, or empty string if no version found.
    """
    match = re.search(r"_V(.+)", filename, re.IGNORECASE)
    if not match:
        return ""

    version = match.group(1)
    return _strip_extension_from_version(version, extension)


def _strip_extension_from_version(version: str, extension: str) -> str:
    """Strip the file extension suffix from a version string if present.

    Args:
        version: The version string (e.g. ``"01-Rel6.2.1.mttl"``).
        extension: The file extension to strip (e.g. ``"mttl"``).

    Returns:
        Version string with the extension removed.
    """
    ext_lower = extension.lower().lstrip(".")
    if ext_lower and version.lower().endswith(f".{ext_lower}"):
        return version[: -len(ext_lower) - 1]
    return version


def get_file_info(file_path: str | Path, extension: str = "") -> tuple[str, str]:
    """Get filename and version for a file.

    Args:
        file_path: Path to the file.
        extension: The extension being filtered (for version extraction).

    Returns:
        Tuple of (filename, version).
    """
    filename = Path(file_path).name
    version = extract_version(filename, extension)
    return filename, version


def _build_column_extractor(
    columns: object | None,
    column_names: tuple[str, ...],
) -> ColumnExtractor:
    """Build a :class:`ColumnExtractor` from config column definitions.

    Args:
        columns: Dictionary of ``ColumnConfiguration`` objects, or a
            falsy value to activate legacy mode.
        column_names: Ordered list of column names.

    Returns:
        A configured :class:`ColumnExtractor` instance.
    """
    extractor = ColumnExtractor()

    if columns:
        for col_name, col_config in _iter_columns(columns):
            if col_config.match:  # Only add if a match pattern is defined
                extractor.add_rule(
                    col_name,
                    col_config.match,
                    col_config.transform,
                    col_config.priority,
                    col_config.default,
                )
    else:
        # Legacy mode: add default Version rule if Version is in column_names
        if "Version" in column_names:
            extractor.add_rule("Version", r"_V(.+)", group=1, priority=10)

    return extractor


def _iter_columns(columns: object) -> list[tuple[str, object]]:
    """Safely iterate over a columns dict, returning ``(name, config)`` pairs.

    Works around the weak ``dict | None`` type by accepting a generic
    object and extracting items when possible.  Returns an empty list
    for non-dict values (legacy callers that pass ``""``).
    """
    if isinstance(columns, dict):
        return list(columns.items())
    return []


def get_file_info_dynamic(
    file_path: str | Path,
    extension: str = "",
    column_names: tuple[str, ...] = ("File", "Version"),
    columns: object | None = None,
) -> dict[str, str]:
    """Get file metadata using dynamic column extraction rules.

    This function uses the ``ColumnExtractor`` to populate multiple columns
    based on regex patterns defined in the configuration.

    Args:
        file_path: Path to the file.
        extension: The extension being filtered (for version extraction).
        column_names: Ordered list of column names to extract.
        columns: Dictionary of ``ColumnConfiguration`` objects from config.
            A falsy value (``None`` / ``""``) activates legacy mode.

    Returns:
        Dictionary mapping column names to extracted values.
        The ``"File"`` column contains the full file path.
    """
    full_path = str(file_path)
    extractor = _build_column_extractor(columns, column_names)
    result = extractor.extract_all(full_path, column_names)

    # File column always gets the full path, unless user defined custom COLUMN_File
    if "File" in column_names and "File" not in result:
        result["File"] = full_path

    # Strip extension from Version if present (only if Version column exists)
    if "Version" in result and extension:
        result["Version"] = _strip_extension_from_version(result["Version"], extension)

    return result
