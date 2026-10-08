"""Tests for Qt DirectoryManager controller."""

from unittest.mock import MagicMock

import pytest

from profiles.core.config.models import AppConfig
from profiles.gui.qt.controllers.directory_manager import (
    DirectoryManager,
    format_dir_entry,
    strip_dir_label,
)


class TestFormatDirEntry:
    """Tests for format_dir_entry helper."""

    def test_single_path_no_suffix(self):
        """Single path entry has no (N paths) suffix."""
        entry = MagicMock()
        entry.icon = "📁"
        entry.label = "Test Dir"
        entry.paths = ["/path/to/dir"]

        result = format_dir_entry(entry)
        assert result == "📁 Test Dir"

    def test_multi_path_has_suffix(self):
        """Multi-path entry has (N paths) suffix."""
        entry = MagicMock()
        entry.icon = "📁"
        entry.label = "Multi Dir"
        entry.paths = ["/path1", "/path2", "/path3"]

        result = format_dir_entry(entry)
        assert result == "📁 Multi Dir (3 paths)"

    def test_file_icon_single_path(self):
        """File icon entries have no suffix even with single path."""
        entry = MagicMock()
        entry.icon = "📄"
        entry.label = "File Entry"
        entry.paths = ["/path/to/file"]

        result = format_dir_entry(entry)
        assert result == "📄 File Entry"


class TestStripDirLabel:
    """Tests for strip_dir_label helper."""

    def test_strip_folder_icon_and_suffix(self):
        """Strip icon prefix and (N paths) suffix."""
        raw = "📁 Test Dir (5 paths)"
        result = strip_dir_label(raw)
        assert result == "Test Dir"

    def test_strip_file_icon(self):
        """Strip file icon prefix."""
        raw = "📄 File Entry"
        result = strip_dir_label(raw)
        assert result == "File Entry"

    def test_no_icon_returns_as_is(self):
        """Plain text without icon returns unchanged."""
        raw = "Plain Path"
        result = strip_dir_label(raw)
        assert result == "Plain Path"

    def test_strip_only_suffix(self):
        """Strip only suffix when no icon present."""
        raw = "Dir Name (2 paths)"
        result = strip_dir_label(raw)
        assert result == "Dir Name"


class TestDirectoryManager:
    """Tests for DirectoryManager controller."""

    @pytest.fixture
    def mock_view(self):
        """Create a mock view with required attributes."""
        view = MagicMock()
        view._config = MagicMock(spec=AppConfig)
        view._dir_combo = {"values": []}
        view._dir_var = MagicMock()
        view._dir_var.get.return_value = "📁 Test Dir"
        view._ext_combo = {"values": []}
        view._ext_var = MagicMock()
        view._filter_combo = {"values": []}
        view._filter_var = MagicMock()
        return view

    @pytest.fixture
    def manager(self, mock_view):
        """Create a DirectoryManager instance."""
        return DirectoryManager(mock_view, "test-host")

    def test_directory_manager_updates_on_combo_change(self, manager):
        """Verify dir_text reflects current combo selection."""
        manager._view._dir_var.get.return_value = "📁 /test/path"
        result = manager.current_label()
        assert result == "/test/path"

    def test_directory_manager_ext_combo_changes(self, manager):
        """Verify ext_text updates when apply_config_overrides is called."""
        # Mock the config service to return test values
        import profiles.gui.qt.controllers.directory_manager as dm_module

        original_merge = dm_module.config_service.merge_config_overrides
        dm_module.config_service.merge_config_overrides = MagicMock(
            return_value=([".txt", ".log"], ["*"])
        )

        manager.apply_config_overrides()

        assert manager._view._ext_combo["values"] == [".txt", ".log"]
        assert manager._view._ext_var.set.called

        dm_module.config_service.merge_config_overrides = original_merge

    def test_directory_manager_filter_combo_changes(self, manager):
        """Verify filter_text updates when apply_config_overrides is called."""
        import profiles.gui.qt.controllers.directory_manager as dm_module

        original_merge = dm_module.config_service.merge_config_overrides
        dm_module.config_service.merge_config_overrides = MagicMock(
            return_value=([".txt"], ["*filter*"])
        )

        manager.apply_config_overrides()

        assert manager._view._filter_combo["values"] == ["*filter*"]
        assert manager._view._filter_var.set.called

        dm_module.config_service.merge_config_overrides = original_merge

    def test_resolve_single_path(self, manager):
        """Resolve a known label to its paths."""
        import profiles.gui.qt.controllers.directory_manager as dm_module

        entry = MagicMock()
        entry.label = "Test Dir"
        entry.paths = ["/path1", "/path2"]

        original_get = dm_module.config_service.get_directory_combobox_values
        dm_module.config_service.get_directory_combobox_values = MagicMock(return_value=[entry])

        result = manager.resolve("Test Dir")
        assert result == ["/path1", "/path2"]

        dm_module.config_service.get_directory_combobox_values = original_get

    def test_resolve_fallback(self, manager):
        """Resolve unknown label returns label as path."""
        import profiles.gui.qt.controllers.directory_manager as dm_module

        dm_module.config_service.get_directory_combobox_values = MagicMock(return_value=[])

        result = manager.resolve("Unknown Path")
        assert result == ["Unknown Path"]
