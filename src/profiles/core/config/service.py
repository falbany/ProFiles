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
from pathlib import Path

from profiles.core.config.matcher import select_active_configuration, matches_machine_config
from profiles.core.config.models import AppConfig, MachineConfiguration


def find_active_config(
    config: AppConfig,
    directory: str,
) -> MachineConfiguration | None:
    """Return the ``MachineConfiguration`` closest to *directory*.

    Returns ``None`` when no match is found.
    """
    if not directory:
        return None

    selected_dir_normalized = str(Path(directory).resolve())

    for cfg in config.configurations:
        # Match using matcher engine with directory constraint
        if matches_machine_config(cfg, "", "", selected_dir_normalized):
            return cfg

    # Fallback to legacy path comparison for compatibility
    for cfg in config.configurations:
        if cfg.scan:
            for scan_path in cfg.scan:
                cfg_dir_normalized = str(Path(scan_path).resolve())
                if selected_dir_normalized == cfg_dir_normalized:
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
    """Return the directory (the first scanned dir) that matches *hostname*, or the best fallback.

    Priority:
    1. Configuration whose `match` criteria matches *hostname*.
    2. First configuration with a non-empty `scan` items list.
    3. `config.search_dir` (may be empty).
    """
    active_cfg = select_active_configuration(config, hostname, "", "")

    if active_cfg and active_cfg.scan:
        return active_cfg.scan[0]

    for cfg in config.configurations:
        if cfg.scan:
            return cfg.scan[0]

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


__all__ = [
    "auto_select_directory",
    "find_active_config",
    "find_configuration_by_hostname",
    "get_unique_directories",
    "merge_config_overrides",
]
