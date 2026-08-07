"""Tests for profiles.gui.ui — MainWindowUI widget construction, build, progress bar, show/hide."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import MagicMock

import pytest

from profiles.gui.ui import MainWindowUI

# ── MainWindowUI construction ───────────────────────────────────────────────


def _make_window_mock() -> MagicMock:
    """Build a MagicMock that quacks enough like MainWindow for the UI builder."""
    window = MagicMock()
    window._theme_name = "light"
    window._config = MagicMock()
    window._config.title = ""
    window._config.release = "1.0.0"
    window._config.column_names = ["File"]
    window._config.column_headers = ["File"]
    window._config.column_widths = [100]
    window._config.column_stretches = [True]
    window._config.close_after_execute = False
    return window


class TestMainWindowUIInit:
    """``__init__`` stores the window reference."""

    def test_init_stores_window(self) -> None:
        window = _make_window_mock()
        ui = MainWindowUI(window)
        assert ui.window is window


class TestMainWindowUIBuild:
    """``build()`` invokes every sub-builder exactly once."""

    def _instrumented_ui(self) -> tuple[MainWindowUI, list[str]]:
        window = _make_window_mock()
        ui = MainWindowUI(window)

        log: list[str] = []

        def _record(name: str):
            def _fn() -> None:
                log.append(name)

            return _fn

        ui._build_header = _record("header")
        ui._build_search_bar = _record("search_bar")
        ui._build_file_list = _record("file_list")
        ui._build_action_bar = _record("action_bar")
        ui._build_status_bar = _record("status_bar")
        return ui, log

    def test_build_invokes_all_sub_builders_once(self) -> None:
        ui, log = self._instrumented_ui()
        ui.build()
        assert log.count("header") == 1
        assert log.count("search_bar") == 1
        assert log.count("file_list") == 1
        assert log.count("action_bar") == 1
        assert log.count("status_bar") == 1

    def test_build_invokes_each_sub_builder_exactly_once(self) -> None:
        ui, log = self._instrumented_ui()
        ui.build()
        assert sorted(log) == [
            "action_bar",
            "file_list",
            "header",
            "search_bar",
            "status_bar",
        ]
        assert len(log) == 5

    def test_build_invokes_sub_builders_in_expected_order(self) -> None:
        ui, log = self._instrumented_ui()
        ui.build()
        assert log == [
            "header",
            "search_bar",
            "file_list",
            "action_bar",
            "status_bar",
        ]


# ── _build_action_bar — indeterminate progressbar ────────────────────────


class TestActionBarProgressbar:
    """``_build_action_bar`` creates an indeterminate progressbar and hides it."""

    def _make_window_with_action_frame(self) -> MagicMock:
        """Window mock with the minimum surface ``_build_action_bar`` needs."""
        window = _make_window_mock()
        window._action_frame = MagicMock()
        window._root = MagicMock()
        return window

    def test_build_action_bar_creates_progressbar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An indeterminate progressbar is created, packed, then immediately hidden."""
        progressbar_mock = MagicMock(name="Progressbar")
        monkeypatch.setattr("profiles.gui.ui.ttk.Progressbar", progressbar_mock)

        window = self._make_window_with_action_frame()
        # Provide the ttk.Frame / ttk.Button / ttk.Checkbutton stubs so the
        # surrounding widgets are no-ops on the mock.
        monkeypatch.setattr("profiles.gui.ui.ttk.Frame", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.ttk.Button", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.ttk.Checkbutton", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.ToolTip", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.tk.BooleanVar", MagicMock())

        ui = MainWindowUI(window)
        ui._build_action_bar()

        progressbar_mock.assert_called_once()
        kwargs = progressbar_mock.call_args.kwargs
        assert kwargs.get("mode") == "indeterminate"

        progress_instance = progressbar_mock.return_value
        progress_instance.pack.assert_called()
        progress_instance.pack_forget.assert_called_once()

    def test_build_action_bar_stores_progressbar_reference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The progressbar instance is stored as ``window._progress_bar``."""
        progressbar_mock = MagicMock(name="Progressbar")
        monkeypatch.setattr("profiles.gui.ui.ttk.Progressbar", progressbar_mock)
        monkeypatch.setattr("profiles.gui.ui.ttk.Frame", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.ttk.Button", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.ttk.Checkbutton", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.ToolTip", MagicMock())
        monkeypatch.setattr("profiles.gui.ui.tk.BooleanVar", MagicMock())

        window = self._make_window_with_action_frame()
        ui = MainWindowUI(window)
        ui._build_action_bar()

        assert window._progress_bar is progressbar_mock.return_value


# ── Scan-progress lifecycle ──────────────────────────────────────────────


class TestShowHideProgress:
    """``_show_progress`` and ``_hide_progress`` are safe without a progressbar."""

    def _make_main_window_attrs(self) -> MagicMock:
        """Build a MagicMock that quacks like the parts of ``MainWindow`` the helpers use."""
        window = MagicMock()
        window._progress_bar = MagicMock()
        return window

    def test_show_progress_packs_and_starts(self) -> None:
        """When a progressbar exists, ``_show_progress`` packs and starts it."""
        from profiles.gui.main_window import MainWindow

        window = self._make_main_window_attrs()
        MainWindow._show_progress(window)

        window._progress_bar.pack.assert_called_once_with(side=tk.LEFT, padx=(0, 12))
        window._progress_bar.start.assert_called_once_with(10)

    def test_hide_progress_stops_and_forgets(self) -> None:
        """When a progressbar exists, ``_hide_progress`` stops and forgets it."""
        from profiles.gui.main_window import MainWindow

        window = self._make_main_window_attrs()
        MainWindow._hide_progress(window)

        window._progress_bar.stop.assert_called_once()
        window._progress_bar.pack_forget.assert_called_once()

    def test_show_progress_is_noop_without_progressbar(self) -> None:
        """Legacy callers without ``_progress_bar`` do not crash."""
        from profiles.gui.main_window import MainWindow

        window = MagicMock(spec=[])  # no _progress_bar attribute
        MainWindow._show_progress(window)

    def test_hide_progress_is_noop_without_progressbar(self) -> None:
        """Legacy callers without ``_progress_bar`` do not crash."""
        from profiles.gui.main_window import MainWindow

        window = MagicMock(spec=[])
        MainWindow._hide_progress(window)
