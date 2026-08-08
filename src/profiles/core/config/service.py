"""Configuration domain operations.

Single Responsibility: pure operations over :class:`AppConfig` — merging
per-host overrides, auto-selecting directories, hostname matching. No I/O,
no UI dependencies.

Extracted from ``profiles.gui.main_window`` so that config merging,
directory auto-selection, and other domain logic can be reused by CLI
and future TUI front-ends without importing Tkinter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from profiles.core.config.matcher import matches_machine_config, select_active_configuration
from profiles.core.config.models import AppConfig, MachineConfiguration


@dataclass(frozen=True)
class DirectoryEntry:
    """A single entry in the directory combobox.

    Attributes:
        label: Display text (config name or path).
        icon: Visual prefix — ``"📁"`` for a config group, ``"📄"`` for a
            single path.
        paths: Filesystem paths to scan when this entry is selected.
    """

    label: str
    icon: str
    paths: list[str]


def find_active_config(
    config: AppConfig,
    directory: str,
) -> MachineConfiguration | None:
    """Return the ``MachineConfiguration`` matching *directory*.

    *directory* may be either a config display name (from the combobox)
    or a filesystem path. When it is a config name, the config with that
    name is returned directly. When it is a path, the config whose
    ``scan`` list contains that path is returned.

    Returns ``None`` when no match is found.
    """
    if not directory:
        return None

    # Try matching by config name first (case-insensitive)
    for cfg in config.configurations:
        if cfg.name and cfg.name.lower() == directory.lower():
            return cfg

    # Fall back to path-based matching
    selected_dir_normalized = str(Path(directory).resolve())

    for cfg in config.configurations:
        if matches_machine_config(cfg, "", "", selected_dir_normalized):
            return cfg
    return None


def find_config_by_name(
    config: AppConfig,
    name: str,
) -> MachineConfiguration | None:
    """Return the first ``MachineConfiguration`` whose ``name`` matches.

    Matching is case-insensitive. Returns ``None`` when no config has
    the given name.
    """
    if not name:
        return None
    for cfg in config.configurations:
        if cfg.name and cfg.name.lower() == name.lower():
            return cfg
    return None


def find_configuration_by_hostname(
    config: AppConfig,
    hostname: str,
) -> MachineConfiguration | None:
    """Find the machine configuration matching *hostname*, IP, or path using MatchCriteria.

    Args:
        config: Application configuration to search.
        hostname: Hostname to match.

    Returns:
        The matching :class:`MachineConfiguration`, or the first configuration
        when no exact match is found, or ``None`` when the configuration list
        is empty.
    """
    return select_active_configuration(config, hostname, "", "")


def _merge_unique(
    active_items: Sequence[str],
    default_items: Sequence[str],
) -> list[str]:
    """Merge *active_items* (per-config) with *default_items* ([LAUNCHER] defaults).

    Per-config items come first, followed by default items that are not
    already present.  Uses ``dict.fromkeys`` for O(1) dedup while
    preserving insertion order.
    """
    merged: dict[str, None] = dict.fromkeys(active_items)
    merged.update(dict.fromkeys(default_items))
    return list(merged)


def merge_config_overrides(
    config: AppConfig,
    directory: str,
) -> tuple[list[str], list[str]]:
    """Merge per-config extensions/filters with the generic ``[LAUNCHER]`` defaults.

    Returns ``(merged_extensions, merged_filters)``.
    """
    active = find_active_config(config, directory)

    merged_extensions = (
        _merge_unique(active.extensions, config.extensions)
        if active and active.extensions
        else list(config.extensions)
    )

    merged_filters = (
        _merge_unique(active.filters, config.filters)
        if active and active.filters
        else list(config.filters)
    )

    return merged_extensions, merged_filters


def auto_select_directory(config: AppConfig, hostname: str) -> str:
    """Return the best initial combobox selection for *hostname*.

    Priority:
    1. Configuration whose `match` criteria matches *hostname* — returns
       the config's display name (``name`` or first ``scan`` path).
    2. First configuration with a non-empty ``scan`` list — returns its
       display name or first scan path.
    3. ``config.search_dir`` (may be empty).
    """
    active_cfg = select_active_configuration(config, hostname, "", "")

    if active_cfg:
        if active_cfg.scan:
            return active_cfg.name or active_cfg.scan[0]
        if active_cfg.name:
            return active_cfg.name

    for cfg in config.configurations:
        if cfg.scan:
            return cfg.name or cfg.scan[0]

    return config.search_dir


def get_unique_directories(config: AppConfig) -> list[str]:
    """Return the list of unique directories from all combined configurations.

    Order is preserved (first occurrence wins).
    """
    seen: set[str] = set()
    result: list[str] = []

    # Check default search dir
    if config.search_dir and config.search_dir not in seen:
        seen.add(config.search_dir)
        result.append(config.search_dir)

    for cfg in config.configurations:
        for scan_dir in cfg.scan:
            if scan_dir and scan_dir not in seen:
                seen.add(scan_dir)
                result.append(scan_dir)
    return result


def get_directory_combobox_values(config: AppConfig) -> list[DirectoryEntry]:
    """Build the list of entries for the directory combobox.

    Each entry is either a config group (📁, scans all its ``scan`` paths)
    or an individual path (📄, scans just that path).

    Order:
    1. ``search_dir`` (if set) as a 📄 path entry.
    2. Each config's display name as a 📁 entry with **all** its ``scan`` paths.
    3. Individual scan paths from all configs as 📄 entries.

    Every ``scan`` path from every config appears both as part of its
    config group (📁) **and** as its own individual entry (📄).  This lets
    users scan an entire config group or pick a single path from it.

    Config groups always include their complete ``scan`` list, even if
    some paths also appear in ``search_dir`` — the scan merges results
    from all paths with deduplication by resolved path.

    Returns:
        List of :class:`DirectoryEntry` objects.
    """
    entries: list[DirectoryEntry] = []
    covered_paths: set[str] = set()

    # 1. Default search_dir as a single-path entry
    if config.search_dir:
        covered_paths.add(config.search_dir)
        entries.append(
            DirectoryEntry(
                label=config.search_dir,
                icon="📄",
                paths=[config.search_dir],
            )
        )

    # 2. Config groups with ALL their scan paths (no filtering)
    for cfg in config.configurations:
        if not cfg.scan:
            continue
        display_name = cfg.name or ""
        if not display_name:
            continue
        paths = [p for p in cfg.scan if p]
        if not paths:
            continue
        entries.append(
            DirectoryEntry(
                label=display_name,
                icon="📁",
                paths=paths,
            )
        )
        # Don't mark these paths as covered — they should also appear
        # as individual 📄 entries so users can scan a single path
        # from the group without removing the config from their .profiles

    # 3. Remaining individual scan paths (including those owned by configs)
    for cfg in config.configurations:
        for scan_dir in cfg.scan:
            if scan_dir and scan_dir not in covered_paths:
                covered_paths.add(scan_dir)
                entries.append(
                    DirectoryEntry(
                        label=scan_dir,
                        icon="📄",
                        paths=[scan_dir],
                    )
                )

    return entries


__all__ = [
    "DirectoryEntry",
    "auto_select_directory",
    "find_active_config",
    "find_config_by_name",
    "find_configuration_by_hostname",
    "get_directory_combobox_values",
    "get_unique_directories",
    "merge_config_overrides",
]
