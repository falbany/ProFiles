"""Smoke tests for FileContextMenu — verify each action emits the right event."""

from __future__ import annotations

import hashlib
import logging
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from profiles.core.actions import ActionResult, ActionStatus
from profiles.gui.context_menu import FileContextMenu


@pytest.fixture
def mock_window(tmp_path: Path) -> MagicMock:
    """Build a minimal MainWindow mock that the context menu can talk to."""
    root = tk.Tk()
    root.withdraw()  # don't show window during tests
    window = MagicMock()
    window._root = root
    window._logger = logging.getLogger("test_context_menu")
    window._config = MagicMock()
    window._config.release = "2026.8.0"
    window._close_var = MagicMock(get=MagicMock(return_value=False))
    window._dir_var = MagicMock(get=MagicMock(return_value=str(tmp_path)))
    window._dir_manager = MagicMock()
    window._dir_manager.resolve = MagicMock(return_value=[str(tmp_path)])
    window._ext_var = MagicMock(set=MagicMock())
    window._tree = MagicMock()
    window._tree_to_path = {}
    window._theme = MagicMock(
        surface="white", on_surface="black", primary="blue", on_primary="white"
    )
    window._refresh_file_list = MagicMock()
    window._apply_config_overrides = MagicMock()
    window._on_close = MagicMock()
    window._action_launch_with_args = MagicMock()
    yield window
    root.destroy()


def test_action_reveal_success_emits_event(caplog, mock_window, tmp_path):
    """action_reveal emits FILE_REVEALED status=ok on success."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("x")
    caplog.set_level(logging.DEBUG, logger="test_context_menu")

    with patch(
        "profiles.gui.context_menu.reveal_in_file_manager",
        return_value=ActionResult(status=ActionStatus.SUCCESS, message="ok"),
    ):
        FileContextMenu(mock_window).action_reveal(file_path)

    assert any("FILE_REVEALED" in r.message and 'status="ok"' in r.message for r in caplog.records)


def test_action_open_folder_success_emits_event(caplog, mock_window, tmp_path):
    """action_open_folder emits EXTERNAL_OPENED kind=folder status=ok on success."""
    subdir = tmp_path / "sub"
    subdir.mkdir()
    file_path = subdir / "test.txt"
    file_path.write_text("x")
    caplog.set_level(logging.DEBUG, logger="test_context_menu")

    with patch(
        "profiles.gui.context_menu.open_file_explorer",
        return_value=True,
    ):
        FileContextMenu(mock_window).action_open_folder(file_path)

    assert any(
        "EXTERNAL_OPENED" in r.message
        and 'kind="folder"' in r.message
        and 'status="ok"' in r.message
        for r in caplog.records
    )


def test_action_filter_to_folder_emits_event(caplog, mock_window, tmp_path):
    """action_filter_to_folder emits FILTER_CHANGED kind=folder on success."""
    target = tmp_path / "other"
    target.mkdir()
    file_path = target / "test.txt"
    file_path.write_text("x")
    # Mock resolve to return a *different* path so "already_active" does not fire.
    mock_window._dir_manager.resolve = MagicMock(return_value=[str(tmp_path / "different")])
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_filter_to_folder(file_path)

    assert any(
        "FILTER_CHANGED" in r.message and 'kind="folder"' in r.message for r in caplog.records
    )


def test_action_filter_by_extension_emits_event(caplog, mock_window, tmp_path):
    """action_filter_by_extension emits FILTER_CHANGED kind=extension on success."""
    file_path = tmp_path / "test.mttl"
    file_path.write_text("x")
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_filter_by_extension(file_path)

    assert any(
        "FILTER_CHANGED" in r.message and 'kind="extension"' in r.message for r in caplog.records
    )


def test_action_hash_success_emits_event(caplog, mock_window, tmp_path):
    """action_hash emits HASH_COMPUTED status=ok with duration_ms on success."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_hash(file_path, "md5")

    assert any(
        "HASH_COMPUTED" in r.message and 'status="ok"' in r.message and "duration_ms=" in r.message
        for r in caplog.records
    )


def test_action_verify_hash_match_emits_event(caplog, mock_window, tmp_path):
    """action_verify_hash emits HASH_VERIFIED match=true on a match."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")
    expected = hashlib.md5(b"hello world").hexdigest()
    mock_window._root.clipboard_get = MagicMock(return_value=expected)
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_verify_hash(file_path, "md5")

    assert any("HASH_VERIFIED" in r.message and "match=true" in r.message for r in caplog.records)
