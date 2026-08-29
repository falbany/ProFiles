"""Tests for the DirectoryManager controller.

Covers the pure helpers (``format_dir_entry`` / ``strip_dir_label``)
and the manager methods that don't need a real MainWindow.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from profiles.core.config import service as config_service
from profiles.gui.controllers.directory_manager import (
    DirectoryManager,
    format_dir_entry,
    strip_dir_label,
)

# ── Pure helpers ──────────────────────────────────────────────────────────


class TestFormatDirEntry:
    def test_single_path_no_suffix(self) -> None:
        e = config_service.DirectoryEntry(label="prod", paths=("/a",), icon="📁")
        assert format_dir_entry(e) == "📁 prod"

    def test_multi_path_appends_count(self) -> None:
        e = config_service.DirectoryEntry(label="g", paths=("/a", "/b", "/c"), icon="📁")
        assert format_dir_entry(e) == "📁 g (3 paths)"

    def test_file_icon_multi_path_no_suffix(self) -> None:
        """File icon never gets the (N paths) suffix even with multiple paths."""
        e = config_service.DirectoryEntry(label="x", paths=("/a", "/b"), icon="📄")
        assert format_dir_entry(e) == "📄 x"


class TestStripDirLabel:
    def test_strips_folder_icon(self) -> None:
        assert strip_dir_label("📁 prod") == "prod"

    def test_strips_file_icon(self) -> None:
        assert strip_dir_label("📄 doc") == "doc"

    def test_strips_count_suffix(self) -> None:
        assert strip_dir_label("📁 group (3 paths)") == "group"

    def test_no_icon_returns_unchanged(self) -> None:
        assert strip_dir_label("naked") == "naked"

    def test_strips_whitespace(self) -> None:
        assert strip_dir_label("  spaced  ") == "spaced"


# ── Manager methods (with mocks) ───────────────────────────────────────────


def _view() -> MagicMock:
    """A minimal DirectoryView mock."""
    v = MagicMock()
    v._config.configurations = []
    v._config.config_path.exists.return_value = False
    return v


class TestDirectoryManagerResolve:
    """resolve() returns paths for a known label, or [label] as fallback."""

    def test_resolve_known_label(self) -> None:
        v = _view()
        # Mock get_directory_combobox_values to return a single entry
        with pytest.MonkeyPatch.context() as mp:
            entry = config_service.DirectoryEntry(label="prod", paths=("/a", "/b"), icon="📁")
            mp.setattr(
                "profiles.gui.controllers.directory_manager"
                ".config_service.get_directory_combobox_values",
                lambda _c: [entry],
            )
            mgr = DirectoryManager(view=v, hostname="host")
            assert mgr.resolve("prod") == ["/a", "/b"]

    def test_resolve_unknown_label_falls_back_to_self(self) -> None:
        v = _view()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "profiles.gui.controllers.directory_manager"
                ".config_service.get_directory_combobox_values",
                lambda _c: [],
            )
            mgr = DirectoryManager(view=v, hostname="host")
            assert mgr.resolve("/some/raw/path") == ["/some/raw/path"]


class TestDirectoryManagerAutoSelect:
    """auto_select() uses cwd when no config file exists."""

    def test_falls_back_to_cwd(self) -> None:
        v = _view()
        v._config.config_path.exists.return_value = False
        mgr = DirectoryManager(view=v, hostname="host")
        mgr.auto_select()
        v._dir_var.set.assert_called_once()
        # The arg is str(Path.cwd()) — verify it's the cwd string
        from pathlib import Path

        assert v._dir_var.set.call_args.args[0] == str(Path.cwd())


class TestDirectoryManagerCurrentLabel:
    def test_strips_icon_and_count(self) -> None:
        v = _view()
        v._dir_var.get.return_value = "📁 group (3 paths)"
        mgr = DirectoryManager(view=v, hostname="host")
        assert mgr.current_label() == "group"
