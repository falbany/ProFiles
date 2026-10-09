"""Tests for Qt main window integration."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from profiles.core.config.models import AppConfig

# Set backend to qt BEFORE any gui imports
os.environ["PROFILES_GUI_BACKEND"] = "qt"

# Load modules directly to avoid gui/__init__.py which tries to import tk backend
import importlib.util

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QShortcut

test_dir = Path(__file__).parent
src_path = test_dir.parent.parent.parent / "src"

# Load main_window module directly
main_window_path = src_path / "profiles" / "gui" / "qt" / "main_window.py"
spec = importlib.util.spec_from_file_location("qt_main_window", str(main_window_path))
qt_main_window = importlib.util.module_from_spec(spec)

# Load ui module first (dependency)
ui_path = src_path / "profiles" / "gui" / "qt" / "ui.py"
ui_spec = importlib.util.spec_from_file_location("qt_ui", str(ui_path))
qt_ui = importlib.util.module_from_spec(ui_spec)
ui_spec.loader.exec_module(qt_ui)

# Load scan_controller module (dependency)
scan_controller_path = src_path / "profiles" / "gui" / "qt" / "controllers" / "scan_controller.py"
scan_spec = importlib.util.spec_from_file_location("qt_scan_controller", str(scan_controller_path))
qt_scan_controller = importlib.util.module_from_spec(scan_spec)
scan_spec.loader.exec_module(qt_scan_controller)

# Now load main_window
spec.loader.exec_module(qt_main_window)

# Import after loading
MainWindow = qt_main_window.MainWindow
HeaderWidget = qt_main_window.HeaderWidget
DirectoryBar = qt_main_window.DirectoryBar
ActionBar = qt_main_window.ActionBar
FileTree = qt_main_window.FileTree
StatusBar = qt_main_window.StatusBar
ContextMenu = qt_main_window.ContextMenu


# pytest-qt fixture for QApplication
@pytest.fixture
def qt_app():
    """Provide QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestHeaderWidget:
    """Tests for HeaderWidget."""

    def test_header_widget_creates_title_and_author(self, qt_app):
        """Test that HeaderWidget creates title and author labels."""
        widget = HeaderWidget()

        assert widget.title_label.text() == "ProFiles"
        assert widget.author_label.text() == "by F. Albany"


class TestDirectoryBar:
    """Tests for DirectoryBar."""

    def test_directory_bar_emits_signals_on_change(self):
        """Test that DirectoryBar emits signals when values change."""
        bar = DirectoryBar()

        # Mock the signals
        with (
            patch.object(bar, "directory_changed") as mock_dir,
            patch.object(bar, "extension_changed") as mock_ext,
            patch.object(bar, "filter_changed") as mock_filter,
        ):
            bar._on_dir_changed("/test/path")
            bar._on_ext_changed(".py")
            bar._on_filter_changed("test")

            mock_dir.emit.assert_called_once_with("/test/path")
            mock_ext.emit.assert_called_once_with(".py")
            mock_filter.emit.assert_called_once_with("test")

    def test_directory_bar_properties(self, qt_app):
        """Test DirectoryBar property accessors."""
        bar = DirectoryBar()
        # Add items to combo boxes before setting text
        bar.dir_combo.addItem("/test")
        bar.ext_combo.addItem(".txt")
        bar.filter_combo.addItem("keyword")
        # Now set the current text
        bar.set_dir_text("/test")
        bar.set_ext_text(".txt")
        bar.set_filter_text("keyword")

        assert bar.dir_text == "/test"
        assert bar.ext_text == ".txt"
        assert bar.filter_text == "keyword"


class TestActionBar:
    """Tests for ActionBar."""

    def test_action_bar_scan_button_emits_signal(self, qt_app):
        """Test that scan button emits scan_requested signal."""
        bar = ActionBar()

        # Connect to the actual signal instead of mocking
        emitted = []
        bar.scan_requested.connect(lambda: emitted.append(True))
        bar.scan_button.click()

        assert len(emitted) == 1

    def test_action_bar_execute_button_emits_signal(self, qt_app):
        """Test that execute button emits execute_requested signal."""
        bar = ActionBar()

        # Connect to the actual signal instead of mocking
        emitted = []
        bar.execute_requested.connect(lambda: emitted.append(True))
        bar.execute_button.click()

        assert len(emitted) == 1

    def test_action_bar_set_scanning_disables_buttons(self):
        """Test that set_scanning disables buttons during scan."""
        bar = ActionBar()

        bar.set_scanning(True)
        assert not bar._scan_button.isEnabled()
        assert not bar._execute_button.isEnabled()

        bar.set_scanning(False)
        assert bar._scan_button.isEnabled()
        assert bar._execute_button.isEnabled()


class TestFileTree:
    """Tests for FileTree."""

    def test_file_tree_creates_tree_view(self):
        """Test that FileTree creates QTreeView."""
        tree = FileTree()

        assert tree.tree_view is not None
        assert tree.tree_view.alternatingRowColors()

    def test_file_tree_emits_selection_on_double_click(self):
        """Test that double click emits selection_changed signal."""
        tree = FileTree()

        with patch.object(tree, "selection_changed") as mock_signal:
            # Create a mock index
            mock_index = MagicMock()
            tree._on_double_click(mock_index)
            mock_signal.emit.assert_called_once_with([mock_index])


class TestStatusBar:
    """Tests for StatusBar."""

    def test_status_bar_initial_message(self):
        """Test that status bar starts with 'Ready' message."""
        bar = StatusBar()

        assert bar._message_label.text() == "Ready"

    def test_status_bar_set_message(self):
        """Test that set_message updates the message."""
        bar = StatusBar()

        bar.set_message("Processing...")
        assert bar._message_label.text() == "Processing..."

    def test_status_bar_set_scanning_updates_message(self):
        """Test that set_scanning updates the message."""
        bar = StatusBar()

        bar.set_scanning(True)
        assert bar._message_label.text() == "Scanning..."

        bar.set_scanning(False)
        assert bar._message_label.text() == "Ready"


class TestContextMenu:
    """Tests for ContextMenu."""

    def test_context_menu_creates_actions(self):
        """Test that ContextMenu creates expected actions."""
        mock_tree = MagicMock()
        logger = logging.getLogger("test")

        menu = ContextMenu(mock_tree, logger)

        assert menu.copy_path_action is not None
        assert menu.copy_name_action is not None
        assert menu.open_action is not None
        assert menu.refresh_action is not None


class TestMainWindow:
    """Integration tests for MainWindow."""

    def test_main_window_scan_button_triggers_worker(self, qt_app):
        """Integration test: scan button triggers worker via controller."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)

            # Mock the controller's start_scan
            window._controller = MagicMock()

            # Click scan button
            window.action_bar.scan_button.click()

            # Verify controller was called
            window._controller.start_scan.assert_called_once()

    def test_main_window_directory_change_updates_tree(self, qt_app):
        """Integration test: directory change flow."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)

            # Simulate directory change using the setter
            window.directory_bar.set_dir_text("/new/path")

            # Verify the text was set
            assert window.directory_bar.dir_text == "/new/path"

    def test_main_window_context_menu_shows_actions(self, qt_app):
        """Integration test: context menu shows expected actions."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)

            # Verify context menu exists and has actions
            assert window.context_menu is not None
            assert window.context_menu.copy_path_action.text() == "Copy Path"
            assert window.context_menu.copy_name_action.text() == "Copy Name"
            assert window.context_menu.open_action.text() == "Open"
            assert window.context_menu.refresh_action.text() == "Refresh"

    def test_main_window_scan_finished_updates_ui(self, qt_app):
        """Integration test: scan finished updates UI state."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._controller = MagicMock()

            # Simulate scan finished
            window._on_scan_finished([MagicMock(), MagicMock()])

            # Verify UI state
            assert window.action_bar._scan_button.isEnabled()
            assert window.status_bar._message_label.text() == "Scan complete: 2 items"

    def test_main_window_scan_failed_shows_error(self, qt_app):
        """Integration test: scan failed shows error dialog."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._controller = MagicMock()

            # Mock QMessageBox to avoid actual dialog
            with patch("profiles.gui.qt.main_window.QMessageBox.critical"):
                # Simulate scan failed
                window._on_scan_failed("Test error")

                # Verify UI state
                assert window.action_bar._scan_button.isEnabled()
                assert "Test error" in window.status_bar._message_label.text()

    def test_main_window_close_stops_scan(self, qt_app):
        """Integration test: close event stops scan."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._controller = MagicMock()

            # Simulate close event
            from PySide6.QtGui import QCloseEvent

            event = MagicMock(spec=QCloseEvent)
            window.closeEvent(event)

            # Verify controller stop was called
            window._controller.stop_scan.assert_called_once()
            event.accept.assert_called_once()


class TestShortcuts:
    """Tests for keyboard shortcuts."""

    def test_shortcut_f5_triggers_scan(self, qt_app):
        """Test that F5 triggers scan/refresh."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._controller = MagicMock()
            # Manually setup shortcuts (avoid show() which causes access violations in tests)
            window._setup_shortcuts()

            # Trigger F5 shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "F5":
                    shortcut.activated.emit()
                    break

            # Verify controller start_scan was called
            window._controller.start_scan.assert_called_once()

    def test_shortcut_ctrl_r_triggers_scan(self, qt_app):
        """Test that Ctrl+R triggers scan/refresh."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._controller = MagicMock()
            window._setup_shortcuts()

            # Trigger the Ctrl+R shortcut directly
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Ctrl+R":
                    shortcut.activated.emit()
                    break

            window._controller.start_scan.assert_called_once()

    def test_shortcut_return_executes_file(self, qt_app):
        """Test that Return key triggers execute."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Mock the execute method
            with patch.object(window, "_on_execute_clicked") as mock_execute:
                # Trigger Return shortcut
                for shortcut in window.findChildren(QShortcut):
                    if shortcut.key().toString() == "Return":
                        shortcut.activated.emit()
                        break

                mock_execute.assert_called_once()

    def test_shortcut_delete_clears_filter(self, qt_app):
        """Test that Delete key clears filter."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Set a filter value
            window.directory_bar.filter_combo.setEditText("test")
            assert window.directory_bar.filter_text == "test"

            # Trigger Delete shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Delete":
                    shortcut.activated.emit()
                    break

            # Verify filter was cleared
            assert window.directory_bar.filter_text == ""

    def test_shortcut_escape_clears_filter(self, qt_app):
        """Test that Escape key clears filter."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Set a filter value
            window.directory_bar.filter_combo.setEditText("test")
            assert window.directory_bar.filter_text == "test"

            # Trigger Escape shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Escape":
                    shortcut.activated.emit()
                    break

            # Verify filter was cleared
            assert window.directory_bar.filter_text == ""

    def test_shortcut_ctrl_f_focuses_filter(self, qt_app):
        """Test that Ctrl+F focuses filter field."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Trigger Ctrl+F shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Ctrl+F":
                    shortcut.activated.emit()
                    break

            # Verify filter combo has focus
            assert window.directory_bar.filter_combo.hasFocus()

    def test_shortcut_ctrl_e_focuses_extension(self, qt_app):
        """Test that Ctrl+E focuses extension field."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Trigger Ctrl+E shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Ctrl+E":
                    shortcut.activated.emit()
                    break

            # Verify extension combo has focus
            assert window.directory_bar.ext_combo.hasFocus()

    def test_shortcut_ctrl_l_focuses_tree(self, qt_app):
        """Test that Ctrl+L focuses file tree."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Trigger Ctrl+L shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Ctrl+L":
                    shortcut.activated.emit()
                    break

            # Verify tree view has focus
            assert window.file_tree.tree_view.hasFocus()

    def test_shortcut_ctrl_q_quits(self, qt_app):
        """Test that Ctrl+Q quits the application."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Track if close was called
            close_called = []

            def mock_close():
                close_called.append(True)

            window.close = mock_close

            # Trigger Ctrl+Q shortcut
            for shortcut in window.findChildren(QShortcut):
                if shortcut.key().toString() == "Ctrl+Q":
                    shortcut.activated.emit()
                    break

            assert len(close_called) == 1

    def test_shortcut_ctrl_shift_t_cycles_theme(self, qt_app):
        """Test that Ctrl+Shift+T cycles theme."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Mock the theme toggle
            with patch.object(window, "_on_toggle_theme") as mock_toggle:
                # Trigger Ctrl+Shift+T shortcut
                for shortcut in window.findChildren(QShortcut):
                    if shortcut.key().toString() == "Ctrl+Shift+T":
                        shortcut.activated.emit()
                        break

                mock_toggle.assert_called_once()

    def test_shortcut_ctrl_question_shows_help(self, qt_app):
        """Test that Ctrl+? shows shortcuts help."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Mock QMessageBox to avoid actual dialog
            with patch("profiles.gui.qt.main_window.QMessageBox") as mock_msgbox:
                # Trigger Ctrl+/ shortcut (Ctrl+?)
                for shortcut in window.findChildren(QShortcut):
                    if shortcut.key().toString() == "Ctrl+/":
                        shortcut.activated.emit()
                        break

                # Verify QMessageBox was used
                assert mock_msgbox.called

    def test_shortcut_ctrl_d_executes_file(self, qt_app):
        """Test that Ctrl+D executes selected file."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Mock the execute method
            with patch.object(window, "_on_execute_clicked") as mock_execute:
                # Trigger Ctrl+D shortcut
                for shortcut in window.findChildren(QShortcut):
                    if shortcut.key().toString() == "Ctrl+D":
                        shortcut.activated.emit()
                        break

                mock_execute.assert_called_once()

    def test_shortcut_ctrl_shift_l_launches_with_args(self, qt_app):
        """Test that Ctrl+Shift+L launches with arguments."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Mock the launch_with_args method
            with patch.object(window, "_launch_with_args") as mock_launch:
                # Trigger Ctrl+Shift+L shortcut
                for shortcut in window.findChildren(QShortcut):
                    if shortcut.key().toString() == "Ctrl+Shift+L":
                        shortcut.activated.emit()
                        break

                mock_launch.assert_called_once()

    def test_shortcut_ctrl_comma_opens_preferences(self, qt_app):
        """Test that Ctrl+, opens preferences."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            # Mock the open_preferences method
            with patch.object(window, "_open_preferences") as mock_prefs:
                # Trigger Ctrl+, shortcut
                for shortcut in window.findChildren(QShortcut):
                    if shortcut.key().toString() == "Ctrl+,":
                        shortcut.activated.emit()
                        break

                mock_prefs.assert_called_once()

    def test_all_shortcuts_created(self, qt_app):
        """Test that all expected shortcuts are created."""
        config = AppConfig()
        logger = logging.getLogger("test")

        with patch.object(MainWindow, "_setup_controller"):
            window = MainWindow(config, logger)
            window._setup_shortcuts()

            shortcuts = window.findChildren(QShortcut)
            shortcut_keys = [s.key().toString() for s in shortcuts]

            expected_shortcuts = [
                "F5",
                "Ctrl+R",
                "Ctrl+D",
                "Ctrl+E",
                "Ctrl+L",
                "Return",
                "Delete",
                "Ctrl+Shift+L",
                "Ctrl+,",
                "Ctrl+Shift+T",
                "Ctrl+/",
                "Ctrl+Q",
                "Escape",
                "Ctrl+F",
            ]

            for expected in expected_shortcuts:
                assert expected in shortcut_keys, f"Missing shortcut: {expected}"
