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
    """Verify context menu has all 5 expected actions."""
    menu = ContextMenu()
    menu.build_for_file(
        file_path="C:/test/file.txt",
        filename="file.txt",
        directory="C:/test",
    )

    actions = menu.actions()
    # Filter out separator actions
    text_actions = [a.text() for a in actions if a.text()]

    assert len(text_actions) == 5
    assert "Copy Path" in text_actions
    assert "Copy Name" in text_actions
    assert "Open" in text_actions
    assert "Reveal in Explorer" in text_actions
    assert "Refresh" in text_actions


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

    # Trigger copy name
    menu._on_copy_name()

    # Verify clipboard content
    clipboard = QApplication.clipboard()
    assert clipboard.text() == "file.txt"


def test_context_menu_open_emits_signal(qt_app):
    """Test that Open action emits signal with correct parameters."""
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

    menu.open_triggered.connect(capture)

    # Trigger open
    menu._on_open()

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
