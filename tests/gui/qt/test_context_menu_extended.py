"""Tests for Qt context menu with all Tkinter-matching actions."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from profiles.gui.qt.context_menu import ContextMenu, build_context_menu, open_terminal_in_directory


@pytest.fixture
def qt_app():
    """Create QApplication for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        temp_path = f.name
    yield temp_path
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_clipboard():
    """Mock clipboard to avoid headless environment issues."""
    with patch.object(QClipboard, "setText") as mock_set:
        with patch.object(QClipboard, "text", return_value=""):
            yield mock_set


class TestContextMenuActions:
    """Tests for context menu action count and presence."""

    def test_context_menu_has_all_tkinter_actions(self, qt_app):
        """Verify context menu has all 20+ Tkinter actions."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        # Get all action texts (including submenus)
        all_actions = []
        for action in menu.all_actions():
            if action.text():
                all_actions.append(action.text())
            elif action.menu():
                for sub_action in action.menu().actions():
                    if sub_action.text():
                        all_actions.append(sub_action.text())

        # Primary actions
        assert "▶  Launch" in all_actions
        assert "🚀  Launch with args" in all_actions

        # Open/Reveal/Terminal
        assert "📂  Reveal in Explorer" in all_actions
        assert "📁  Open folder" in all_actions
        assert "🖥  Open terminal" in all_actions

        # Filter actions
        assert "🔎  Filter to folder" in all_actions
        assert "🔎  Filter by extension" in all_actions

        # Copy submenu actions
        assert "Full path" in all_actions
        assert "Forward slashes" in all_actions
        assert "Name with extension" in all_actions
        assert "Name without extension" in all_actions
        assert "Directory" in all_actions
        assert "URI (file://)" in all_actions

        # Hash submenu actions
        assert "MD5 (show)" in all_actions
        assert "SHA256 (show)" in all_actions
        assert "Copy MD5" in all_actions
        assert "Copy SHA256" in all_actions
        assert "✅ Verify MD5" in all_actions
        assert "✅ Verify SHA256" in all_actions

        # Info/Utility
        assert "ℹ  Properties" in all_actions
        assert "🗑  Delete" in all_actions
        assert "🔄 Refresh" in all_actions

        # Should have 20+ actions
        assert len(all_actions) >= 20

    def test_context_menu_creates_submenus(self, qt_app):
        """Verify Copy and Hash submenus are created."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        # Find Copy and Hash menu actions by checking all top-level actions
        copy_menu_action = None
        hash_menu_action = None
        for action in QMenu.actions(menu):
            if action.text() == "📋  Copy":
                copy_menu_action = action
            elif action.text() == "#  Hash":
                hash_menu_action = action

        assert copy_menu_action is not None
        assert hash_menu_action is not None
        assert copy_menu_action.menu() is not None
        assert hash_menu_action.menu() is not None


class TestCopyActions:
    """Tests for copy-related actions."""

    def test_copy_path_copies_full_path(self, qt_app, temp_file, mock_clipboard):
        """Test Copy Path action copies full path."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        menu._on_copy_path()

        mock_clipboard.assert_called_with(temp_file)

    def test_copy_path_forward_slashes(self, qt_app, mock_clipboard):
        """Test forward slashes copy converts backslashes."""
        # Use Windows-style path
        win_path = "C:\\test\\file.txt"
        menu = ContextMenu()
        menu.build_for_file(
            file_path=win_path,
            filename="test.txt",
            directory="C:\\test",
        )

        menu._on_copy_path_forward_slashes()

        # Should convert to forward slashes
        called_text = mock_clipboard.call_args[0][0]
        assert "\\" not in called_text
        assert "/" in called_text

    def test_copy_name_with_extension(self, qt_app, mock_clipboard):
        """Test copy name with extension."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        menu._on_copy_name_with_ext()

        mock_clipboard.assert_called_with("file.txt")

    def test_copy_name_without_extension(self, qt_app, mock_clipboard):
        """Test copy name without extension."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        menu._on_copy_name_without_ext()

        mock_clipboard.assert_called_with("file")

    def test_copy_directory(self, qt_app, mock_clipboard):
        """Test copy directory path."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        menu._on_copy_directory()

        mock_clipboard.assert_called_with("C:/test")

    def test_copy_uri(self, qt_app, mock_clipboard):
        """Test copy file URI."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        menu._on_copy_uri()

        # Should start with file://
        called_text = mock_clipboard.call_args[0][0]
        assert called_text.startswith("file://")


class TestLaunchActions:
    """Tests for launch-related actions."""

    def test_launch_emits_signal(self, qt_app, temp_file):
        """Test launch action emits signal."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        emitted_dir = None
        emitted_filename = None

        def capture(directory, filename):
            nonlocal emitted_dir, emitted_filename
            emitted_dir = directory
            emitted_filename = filename

        menu.launch_triggered.connect(capture)

        with patch("profiles.gui.qt.context_menu.launch_file", return_value=True):
            menu._on_launch()

        assert emitted_dir is not None
        assert emitted_filename == "test.txt"

    def test_launch_with_args_prompts_and_emits(self, qt_app, temp_file):
        """Test launch with args prompts for arguments."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        emitted_args = None

        def capture(directory, filename, args):
            nonlocal emitted_args
            emitted_args = args

        menu.launch_with_args_triggered.connect(capture)

        with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("--help", True)):
            with patch("subprocess.Popen"):
                menu._on_launch_with_args()

        assert emitted_args == "--help"


class TestFilterActions:
    """Tests for filter-related actions."""

    def test_filter_to_folder_emits_signal(self, qt_app, temp_file):
        """Test filter to folder emits signal."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        emitted_folder = None

        def capture(folder):
            nonlocal emitted_folder
            emitted_folder = folder

        menu.filter_folder_triggered.connect(capture)
        menu._on_filter_to_folder()

        assert emitted_folder is not None

    def test_filter_by_extension_emits_signal(self, qt_app):
        """Test filter by extension emits signal."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        emitted_ext = None

        def capture(ext):
            nonlocal emitted_ext
            emitted_ext = ext

        menu.filter_extension_triggered.connect(capture)
        menu._on_filter_by_extension()

        assert emitted_ext == ".txt"

    def test_filter_by_extension_no_extension_warning(self, qt_app):
        """Test filter by extension shows warning for files without extension."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/README",
            filename="README",
            directory="C:/test",
        )

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warning:
            menu._on_filter_by_extension()

        mock_warning.assert_called_once()


class TestHashActions:
    """Tests for hash-related actions."""

    def test_hash_md5_shows_dialog(self, qt_app, temp_file):
        """Test MD5 hash shows dialog with digest."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            menu._on_hash("md5", show=True)

        mock_info.assert_called_once()

    def test_hash_copy_only_copies_to_clipboard(self, qt_app, temp_file):
        """Test copy-only hash copies to clipboard without dialog."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            menu._on_hash("sha256", copy_only=True)

        mock_info.assert_not_called()
        # Note: clipboard may not be accessible in headless test environment
        # Just verify no exception was raised

    def test_verify_hash_matches(self, qt_app, temp_file):
        """Test hash verification when clipboard matches."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        # First compute the hash
        from profiles.utils.file_utils import hash_file

        expected_hash = hash_file(temp_file, "md5")

        with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            with patch.object(QClipboard, "text", return_value=expected_hash):
                with patch.object(QClipboard, "setText"):
                    menu._on_verify_hash("md5")

        mock_info.assert_called_once()
        # call_args[0] = (self, title, message), check message contains the hash
        message = mock_info.call_args[0][2]
        assert expected_hash in message

    def test_verify_hash_mismatch(self, qt_app, temp_file):
        """Test hash verification when clipboard doesn't match."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_critical:
            with patch.object(QClipboard, "text", return_value="wronghash123"):
                with patch.object(QClipboard, "setText"):
                    menu._on_verify_hash("md5")

        mock_critical.assert_called_once()
        # Check that the message mentions mismatch
        message = mock_critical.call_args[0][2]
        assert "wronghash123" in message

    def test_verify_hash_empty_clipboard(self, qt_app, temp_file):
        """Test hash verification with empty clipboard."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            with patch.object(QClipboard, "text", return_value=""):
                menu._on_verify_hash("md5")

        mock_info.assert_called_once()
        # Check that the message mentions empty clipboard
        message = mock_info.call_args[0][2]
        assert "empty" in message.lower()


class TestUtilityActions:
    """Tests for utility actions."""

    def test_properties_shows_dialog(self, qt_app, temp_file):
        """Test properties action shows file info dialog."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
            menu._on_properties()

        mock_info.assert_called_once()
        # call_args[0] = (self, title, message), check message contains the file path
        message = mock_info.call_args[0][2]
        # The temp file name will be like tmpXXXXXX.txt, check it contains the path
        assert temp_file in message or Path(temp_file).name in message

    def test_delete_prompts_for_confirmation(self, qt_app, temp_file):
        """Test delete action prompts for confirmation."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.Yes):
            with patch("profiles.gui.qt.context_menu.QMessageBox.information"):
                menu._on_delete()

        # File should be deleted
        assert not os.path.exists(temp_file)

    def test_delete_cancelled(self, qt_app, temp_file):
        """Test delete action cancelled when user says no."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=QMessageBox.No):
            menu._on_delete()

        # File should still exist
        assert os.path.exists(temp_file)

    def test_refresh_emits_signal(self, qt_app):
        """Test refresh action emits signal."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path="C:/test/file.txt",
            filename="file.txt",
            directory="C:/test",
        )

        refresh_called = False

        def on_refresh():
            nonlocal refresh_called
            refresh_called = True

        menu.refresh_triggered.connect(on_refresh)
        menu._on_refresh()

        assert refresh_called


class TestOpenFolderActions:
    """Tests for open folder and reveal actions."""

    def test_open_folder_emits_signal(self, qt_app, temp_file):
        """Test open folder action emits signal."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        emitted_path = None

        def capture(path):
            nonlocal emitted_path
            emitted_path = path

        menu.open_folder_triggered.connect(capture)

        with patch("profiles.gui.qt.context_menu.open_file_explorer", return_value=True):
            menu._on_open_folder()

        assert emitted_path is not None

    def test_reveal_emits_signal(self, qt_app, temp_file):
        """Test reveal action emits signal on success."""
        menu = ContextMenu()
        menu.build_for_file(
            file_path=temp_file,
            filename="test.txt",
            directory=str(Path(temp_file).parent),
        )

        emitted_path = None

        def capture(path):
            nonlocal emitted_path
            emitted_path = path

        menu.reveal_triggered.connect(capture)

        with patch("profiles.gui.qt.context_menu.reveal_in_file_manager") as mock_reveal:
            mock_result = MagicMock()
            mock_result.status.value = "success"
            mock_reveal.return_value = mock_result
            menu._on_reveal()

        assert emitted_path == temp_file


class TestFactoryFunction:
    """Tests for build_context_menu factory."""

    def test_build_context_menu_creates_menu(self, qt_app):
        """Test factory function creates configured menu."""
        menu = build_context_menu(
            file_path="C:/test/file.txt",
            filename="file.txt",
        )

        assert isinstance(menu, ContextMenu)

        # Should have all actions
        actions = [a.text() for a in menu.all_actions() if a.text()]
        assert len(actions) >= 20
        assert "▶  Launch" in actions
        assert "🔄 Refresh" in actions


class TestOpenTerminalHelper:
    """Tests for open_terminal_in_directory helper."""

    def test_open_terminal_nonexistent_directory(self):
        """Test opening terminal in non-existent directory returns False."""
        result = open_terminal_in_directory(Path("/nonexistent/path"))
        assert result is False
