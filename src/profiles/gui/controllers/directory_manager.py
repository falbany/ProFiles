"""Directory combobox manager — populates, formats, resolves, auto-selects.

Owns the directory / extension / filter combobox state. Pure logic
delegates to ``profiles.core.config.service``; widget access is
limited to the combobox + vars passed in by the view.

Decoupled from MainWindow via a small :class:`DirectoryView` protocol
documented below.
"""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from profiles.core.config import service as config_service
from profiles.core.config.loader import load_config
from profiles.core.config.models import AppConfig, MachineConfiguration

# Icon prefixes used in combobox display strings.
_FOLDER_ICON = "📁"
_FILE_ICON = "📄"
_PATH_COUNT_SUFFIX_PATTERN = " (N paths)"


class DirectoryView:
    """Adapter exposing the widgets DirectoryManager touches.

    Documented as a Protocol — no runtime cost. MainWindow implements
    this.
    """

    # ── directory combobox ────────────────────────────────────────
    _dir_combo: ttk.Combobox
    _dir_var: tk.StringVar
    # ── extension / filter comboboxes (for apply_config_overrides) ─
    _ext_combo: ttk.Combobox
    _ext_var: tk.StringVar
    _filter_combo: ttk.Combobox
    _filter_var: tk.StringVar
    # ── view deps ─────────────────────────────────────────────────
    _config: AppConfig
    _logger: logging.Logger


def format_dir_entry(entry: config_service.DirectoryEntry) -> str:
    """Render a :class:`DirectoryEntry` as a combobox display string.

    Format: ``{icon} {label}`` with an optional ``(N paths)`` suffix
    for multi-path config groups.
    """
    icon = entry.icon
    if icon == _FOLDER_ICON and len(entry.paths) > 1:
        return f"{icon} {entry.label} ({len(entry.paths)} paths)"
    return f"{icon} {entry.label}"


def strip_dir_label(raw: str) -> str:
    """Strip the icon prefix and the ``(N paths)`` suffix from a label.

    Inverse of :func:`format_dir_entry`.
    """
    for prefix in (f"{_FOLDER_ICON} ", f"{_FILE_ICON} "):
        if raw.startswith(prefix):
            label = raw[len(prefix) :]
            break
    else:
        label = raw
    if label.endswith(")"):
        idx = label.rfind(" (")
        if idx != -1:
            label = label[:idx]
    return label.strip()


class DirectoryManager:
    """Owns the directory / extension / filter combobox state."""

    def __init__(self, view: DirectoryView, hostname: str) -> None:
        self._view = view
        self._hostname = hostname

    # ── directory combobox ────────────────────────────────────────

    def populate(self) -> None:
        """Populate the directory combobox from configurations."""
        entries = config_service.get_directory_combobox_values(self._view._config)
        self._view._dir_combo["values"] = [format_dir_entry(e) for e in entries]

    def resolve(self, label: str) -> list[str]:
        """Resolve a combobox label to its list of scan paths.

        Falls back to ``[label]`` (treating it as a raw path) when no
        config entry matches.
        """
        entries = config_service.get_directory_combobox_values(self._view._config)
        for entry in entries:
            if entry.label == label:
                return list(entry.paths)
        return [label]

    def set_selection(self, label: str) -> None:
        """Set the combobox to the entry matching *label*, else *label* itself."""
        entries = config_service.get_directory_combobox_values(self._view._config)
        for entry in entries:
            if entry.label == label:
                self._view._dir_var.set(format_dir_entry(entry))
                return
        self._view._dir_var.set(label)

    def auto_select(self) -> None:
        """Auto-select the directory matching the current host.

        Sets the directory combobox to the matched label (formatted as
        a known entry when applicable) or to the current working
        directory as a fallback.
        """
        config_path = self._view._config.config_path
        if not config_path.exists():
            self._view._dir_var.set(str(Path.cwd()))
            return
        try:
            fresh = load_config(config_path)
        except (FileNotFoundError, OSError):
            self._view._dir_var.set(str(Path.cwd()))
            return
        try:
            matched = config_service.auto_select_directory(fresh, self._hostname)
        except (AttributeError, OSError):
            matched = None
        if matched:
            self.set_selection(matched)
        else:
            self._view._dir_var.set(str(Path.cwd()))

    def current_label(self) -> str:
        """Return the current combobox selection, icon and count stripped."""
        return strip_dir_label(self._view._dir_var.get())

    def find_active_config(self) -> MachineConfiguration | None:
        """Find the config matching the currently selected directory."""
        return config_service.find_active_config(self._view._config, self.current_label())

    # ── extensions / filters ──────────────────────────────────────

    def apply_config_overrides(self) -> None:
        """Merge per-config extensions/filters with generic defaults."""
        merged_extensions, merged_filters = config_service.merge_config_overrides(
            self._view._config,
            self.current_label(),
        )
        self._view._ext_combo["values"] = merged_extensions
        self._view._ext_var.set(merged_extensions[0] if merged_extensions else "")
        self._view._filter_combo["values"] = merged_filters
        self._view._filter_var.set(merged_filters[0] if merged_filters else "")
