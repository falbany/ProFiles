"""Tests for Qt context menu."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from profiles.gui.qt.context_menu import ContextMenu, build_context_menu


@pytest.fixture
def qt_app():
    """Create QApplication for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_context_menu_shows_expected_actions(qt_app):
    """Verify context menu has all 12 expected actions."""
    menu = ContextMenu()
    menu.build_for_file(
        file_path="C:/test/file.txt",
        filename="file.txt",
        directory="C:/test",
    )

    actions = menu.actions()
    # Filter out separator actions
    text_actions = [a.text() for a in actions if a.text()]

    assert len(text_actions) == 12
    assert "▶  Launch" in text_actions
    assert "🚀  Launch with args" in text_actions
    assert "📂  Reveal in Explorer" in text_actions
    assert "📁  Open folder" in text_actions
    assert "🖥  Open terminal" in text_actions
    assert "🔎  Filter to folder" in text_actions
    assert "📋  Copy" in text_actions
    assert "#  Hash" in text_actions
    assert "ℹ  Properties" in text_actions
    assert "🗑  Delete" in text_actions
    assert "🔄 Refresh" in text_actions


def test_context_menu_copy_path_copies_to_clipboard(qt_app):
    """Test that Copy Path action copies full path to clipboard."""
    menu = ContextMenu()
    menu.build_for_file(
        file_path="C:/test/file.txt",
        filename="file.txt",
        directory="C:/test",
    )

    # Trigger copy path
    menu._on_copy_path()

    # Verify clipboard content
    clipboard = QApplication.clipboard()
    assert clipboard.text() == "C:/test/file.txt"


def test_context_menu_copy_name_copies_to_clipboard(qt_app):
    """Test that Copy Name action copies filename to clipboard."""
    menu = ContextMenu()
    menu.build_for_file(
        file_path="C:/test/file.txt",
        filename="file.txt",
        directory="C:/test",
    )

    # Trigger copy name (with extension)
    menu._on_copy_name_with_ext()

    # Verify clipboard content
    clipboard = QApplication.clipboard()
    assert clipboard.text() == "file.txt"


def test_context_menu_open_emits_signal(qt_app):
    """Test that Launch action emits signal with correct parameters."""
    from unittest.mock import patch
    
    menu = ContextMenu()
    menu.build_for_file(
        file_path="C:/test/file.txt",
        filename="file.txt",
        directory="C:/test",
    )

    # Track emitted signal
    emitted_dir = None
    emitted_filename = None

    def capture(directory, filename):
        nonlocal emitted_dir, emitted_filename
        emitted_dir = directory
        emitted_filename = filename

    menu.launch_triggered.connect(capture)

    # Mock launch_file to return True (simulating successful launch)
    with patch("profiles.gui.qt.context_menu.launch_file", return_value=True):
        # Trigger launch
        menu._on_launch()

    # Verify signal was emitted with correct parameters
    assert emitted_dir == "C:/test"
    assert emitted_filename == "file.txt"


def test_build_context_menu_factory(qt_app):
    """Test the build_context_menu factory function."""
    menu = build_context_menu(
        file_path="C:/test/file.txt",
        filename="file.txt",
    )

    assert isinstance(menu, ContextMenu)
    actions = [a.text() for a in menu.actions() if a.text()]
    assert len(actions) == 5
