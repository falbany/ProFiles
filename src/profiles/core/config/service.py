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

from profiles.core.config.models import AppConfig, MachineConfiguration


def find_active_config(
    config: AppConfig,
    directory: str,
) -> MachineConfiguration | None:
    """Return the ``MachineConfiguration`` whose directory matches *directory*.

    Returns ``None`` when no match is found.
    """
    if not directory:
        return None

    selected_dir_normalized = str(Path(directory).resolve())

    for cfg in config.configurations:
        if cfg.directory:
            cfg_dir_normalized = str(Path(cfg.directory).resolve())
            if selected_dir_normalized == cfg_dir_normalized:
                return cfg
    return None


def find_configuration_by_hostname(
    config: AppConfig,
    hostname: str,
) -> MachineConfiguration | None:
    """Find the machine configuration whose ``pc_hostname`` matches *hostname*.

    Args:
        config: Application configuration to search.
        hostname: Hostname to match (case-insensitive).

    Returns:
        The matching :class:`MachineConfiguration`, or the first configuration
        when no exact match is found, or ``None`` when the configuration list
        is empty.
    """
    hostname_lower = hostname.strip().lower()

    for machine in config.configurations:
        if machine.pc_hostname.strip().lower() == hostname_lower:
            return machine

    if config.configurations:
        return config.configurations[0]

    return None


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
    """Return the directory that matches *hostname*, or the best fallback.

    Priority:
    1. Configuration whose ``pc_hostname`` matches *hostname*.
    2. First configuration with a non-empty directory.
    3. ``config.search_dir`` (may be empty).
    """
    hostname_lower = hostname.lower()
    for cfg in config.configurations:
        if cfg.pc_hostname.strip().lower() == hostname_lower and cfg.directory:
            return cfg.directory

    for cfg in config.configurations:
        if cfg.directory:
            return cfg.directory

    return config.search_dir


def get_unique_directories(config: AppConfig) -> list[str]:
    """Return the list of unique directories from all configurations.

    Order is preserved (first occurrence wins).
    """
    seen: set[str] = set()
    result: list[str] = []
    for cfg in config.configurations:
        if cfg.directory and cfg.directory not in seen:
            seen.add(cfg.directory)
            result.append(cfg.directory)
    return result


__all__ = [
    "auto_select_directory",
    "find_active_config",
    "find_configuration_by_hostname",
    "get_unique_directories",
    "merge_config_overrides",
]
