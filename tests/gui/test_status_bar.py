"""Tests for the StatusBar component."""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock

import pytest

from profiles.gui.status_bar import StatusBar


@pytest.fixture
def mock_callbacks():
    """Create mock callback functions."""
    return {
        "on_config_click": MagicMock(),
        "on_refresh_click": MagicMock(),
        "on_log_click": MagicMock(),
        "on_theme_toggle": MagicMock(),
    }


@pytest.fixture
def status_bar(mock_callbacks):
    """Create a StatusBar instance for testing.

    Creates a fresh Tkinter environment for each test to avoid
    race conditions and resource conflicts between tests.
    """
    root = None
    frame = None
    max_retries = 3

    for attempt in range(max_retries):
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the window
            frame = ttk.Frame(root)
            frame.pack()

            bar = StatusBar(
                parent=frame,
                on_config_click=mock_callbacks["on_config_click"],
                on_refresh_click=mock_callbacks["on_refresh_click"],
                on_log_click=mock_callbacks["on_log_click"],
                on_theme_toggle=mock_callbacks["on_theme_toggle"],
                theme_label="☀ Light",
            )

            yield bar

            # Clean up in reverse order
            root.destroy()
            return

        except (tk.TclError, OSError) as e:
            # Clean up partial resources
            if frame:
                with contextlib.suppress(Exception):
                    frame.pack_forget()
            if root:
                with contextlib.suppress(Exception):
                    root.destroy()

            # If this was the last attempt, re-raise the error
            if attempt == max_retries - 1:
                pytest.skip(f"Tkinter initialization failed after {max_retries} attempts: {e}")
            # Otherwise, retry with a small delay
            import time

            time.sleep(0.1)


class TestStatusBarInit:
    """Tests for StatusBar initialization."""

    def test_creates_status_frame(self, status_bar):
        """Verify status frame is created."""
        assert status_bar._status_frame is not None
        assert isinstance(status_bar._status_frame, ttk.Frame)

    def test_creates_all_labels(self, status_bar):
        """Verify all label widgets are created."""
        assert status_bar._user_label is not None
        assert status_bar._host_label is not None
        assert status_bar._ip_label is not None
        assert status_bar._count_label is not None
        assert status_bar._dir_status_label is not None

    def test_creates_all_buttons(self, status_bar):
        """Verify all button widgets are created."""
        assert status_bar._config_link is not None
        assert status_bar._refresh_btn is not None
        assert status_bar._log_link is not None
        assert status_bar._theme_btn is not None

    def test_initial_theme_label(self, status_bar):
        """Verify initial theme label is set."""
        assert status_bar._theme_btn.cget("text") == "☀ Light"


class TestStatusBarProperties:
    """Tests for StatusBar property accessors."""

    def test_status_frame_property(self, status_bar):
        """Verify status_frame property returns correct frame."""
        assert status_bar.status_frame is status_bar._status_frame

    def test_status_inner_property(self, status_bar):
        """Verify status_inner property returns correct frame."""
        assert status_bar.status_inner is status_bar._status_inner

    def test_widget_properties(self, status_bar):
        """Verify all widget properties return correct instances."""
        assert status_bar.config_link is status_bar._config_link
        assert status_bar.refresh_btn is status_bar._refresh_btn
        assert status_bar.log_link is status_bar._log_link
        assert status_bar.theme_btn is status_bar._theme_btn
        assert status_bar.user_label is status_bar._user_label
        assert status_bar.host_label is status_bar._host_label
        assert status_bar.ip_label is status_bar._ip_label
        assert status_bar.count_label is status_bar._count_label
        assert status_bar.dir_status_label is status_bar._dir_status_label


class TestStatusBarCallbacks:
    """Tests for StatusBar callback bindings."""

    def test_config_button_calls_callback(self, status_bar, mock_callbacks):
        """Verify config button triggers callback."""
        status_bar._config_link.invoke()
        mock_callbacks["on_config_click"].assert_called_once()

    def test_refresh_button_calls_callback(self, status_bar, mock_callbacks):
        """Verify refresh button triggers callback."""
        status_bar._refresh_btn.invoke()
        mock_callbacks["on_refresh_click"].assert_called_once()

    def test_log_button_calls_callback(self, status_bar, mock_callbacks):
        """Verify log button triggers callback."""
        status_bar._log_link.invoke()
        mock_callbacks["on_log_click"].assert_called_once()

    def test_theme_button_calls_callback(self, status_bar, mock_callbacks):
        """Verify theme button triggers callback."""
        status_bar._theme_btn.invoke()
        mock_callbacks["on_theme_toggle"].assert_called_once()


class TestStatusBarUpdateThemeLabel:
    """Tests for StatusBar theme label update."""

    def test_update_theme_label(self, status_bar):
        """Verify theme label can be updated."""
        status_bar.update_theme_label("🌙 Dark")
        assert status_bar._theme_btn.cget("text") == "🌙 Dark"

    def test_update_theme_label_with_different_text(self, status_bar):
        """Verify theme label update with various texts."""
        test_labels = ["Light", "Dark", "Custom Theme", "☀ Light", "🌙 Dark"]
        for label in test_labels:
            status_bar.update_theme_label(label)
            assert status_bar._theme_btn.cget("text") == label


class TestStatusBarTooltips:
    """Tests for StatusBar tooltip functionality."""

    def test_user_label_has_tooltip(self, status_bar):
        """Verify user label has tooltip bound."""
        # ToolTip binds events, so we check if events are present
        events = status_bar._user_label.bind()
        assert "<Enter>" in events or len(events) > 0

    def test_host_label_has_tooltip(self, status_bar):
        """Verify host label has tooltip bound."""
        events = status_bar._host_label.bind()
        assert "<Enter>" in events or len(events) > 0

    def test_ip_label_has_tooltip(self, status_bar):
        """Verify IP label has tooltip bound."""
        events = status_bar._ip_label.bind()
        assert "<Enter>" in events or len(events) > 0

    def test_count_label_has_tooltip(self, status_bar):
        """Verify count label has tooltip bound."""
        events = status_bar._count_label.bind()
        assert "<Enter>" in events or len(events) > 0

    def test_dir_status_label_has_tooltip(self, status_bar):
        """Verify directory status label has tooltip bound."""
        events = status_bar._dir_status_label.bind()
        assert "<Enter>" in events or len(events) > 0


class TestStatusBarUpdateThemeLabelMutation:
    """update_theme_label mutates the theme button text."""

    def test_button_text_mutates_to_supplied_value(self, status_bar):
        initial = status_bar._theme_btn.cget("text")
        new_label = "🌙 Dark"
        assert initial != new_label
        status_bar.update_theme_label(new_label)
        assert status_bar._theme_btn.cget("text") == new_label

    def test_button_text_mutates_back_and_forth(self, status_bar):
        status_bar.update_theme_label("🌙 Dark")
        assert status_bar._theme_btn.cget("text") == "🌙 Dark"
        status_bar.update_theme_label("☀ Light")
        assert status_bar._theme_btn.cget("text") == "☀ Light"


class TestStatusBarShortcutsBranch:
    """The ``on_shortcuts_click is None`` branch leaves shortcuts_btn as None."""

    def test_shortcuts_btn_is_none_when_callback_missing(self, status_bar):
        """status_bar fixture omits on_shortcuts_click → defaults to None."""
        assert status_bar._on_shortcuts_click is None
        assert status_bar._shortcuts_btn is None

    def test_other_widgets_still_pack_when_shortcuts_missing(self, status_bar):
        """Every non-shortcuts widget must still exist when shortcuts is None."""
        assert status_bar._status_frame is not None
        assert status_bar._status_inner is not None
        assert status_bar._config_link is not None
        assert status_bar._refresh_btn is not None
        assert status_bar._log_link is not None
        assert status_bar._theme_btn is not None
        assert status_bar._user_label is not None
        assert status_bar._host_label is not None
        assert status_bar._ip_label is not None
        assert status_bar._count_label is not None
        assert status_bar._dir_status_label is not None

    def test_shortcuts_property_returns_none_when_callback_missing(self, status_bar):
        """Public shortcuts_btn property reflects the None branch."""
        assert status_bar.shortcuts_btn is None


class TestStatusBarLanguageBranch:
    """The ``on_language_toggle is None`` branch leaves language_btn as None."""

    def test_language_btn_is_none_when_callback_missing(self, status_bar):
        """status_bar fixture omits on_language_toggle → defaults to None."""
        assert status_bar._on_language_toggle is None
        assert status_bar._language_btn is None
        assert status_bar.language_btn is None

    def test_language_btn_created_when_callback_provided(self, mock_callbacks):
        """Providing on_language_toggle creates the language button."""
        root = tk.Tk()
        root.withdraw()
        try:
            frame = ttk.Frame(root)
            frame.pack()
            bar = StatusBar(
                parent=frame,
                on_config_click=mock_callbacks["on_config_click"],
                on_refresh_click=mock_callbacks["on_refresh_click"],
                on_log_click=mock_callbacks["on_log_click"],
                on_theme_toggle=mock_callbacks["on_theme_toggle"],
                on_language_toggle=MagicMock(),
            )
            assert bar.language_btn is not None
            assert bar._language_tooltip is not None
        finally:
            root.destroy()

    def test_update_language_label_reflects_current_language(self, mock_callbacks):
        """update_language_label sets the button text from LANGUAGE_LABELS."""
        from profiles.gui.i18n import LANGUAGE_LABELS, set_current_language

        root = tk.Tk()
        root.withdraw()
        try:
            frame = ttk.Frame(root)
            frame.pack()
            bar = StatusBar(
                parent=frame,
                on_config_click=mock_callbacks["on_config_click"],
                on_refresh_click=mock_callbacks["on_refresh_click"],
                on_log_click=mock_callbacks["on_log_click"],
                on_theme_toggle=mock_callbacks["on_theme_toggle"],
                on_language_toggle=MagicMock(),
            )
            set_current_language("fr")
            bar.update_language_label()
            assert bar.language_btn.cget("text") == LANGUAGE_LABELS["fr"]
            set_current_language("en")
            bar.update_language_label()
            assert bar.language_btn.cget("text") == LANGUAGE_LABELS["en"]
        finally:
            root.destroy()

    def test_apply_text_relabels_widgets(self, mock_callbacks):
        """_apply_text re-labels buttons and tooltips from the catalog."""
        from profiles.gui.i18n import set_current_language, t

        root = tk.Tk()
        root.withdraw()
        try:
            frame = ttk.Frame(root)
            frame.pack()
            bar = StatusBar(
                parent=frame,
                on_config_click=mock_callbacks["on_config_click"],
                on_refresh_click=mock_callbacks["on_refresh_click"],
                on_log_click=mock_callbacks["on_log_click"],
                on_theme_toggle=mock_callbacks["on_theme_toggle"],
                on_language_toggle=MagicMock(),
            )
            set_current_language("fr")
            bar._apply_text()
            assert bar.config_link.cget("text") == t("status.config", lang="fr")
            assert bar.refresh_btn.cget("text") == t("status.refresh", lang="fr")
            assert bar.log_link.cget("text") == t("status.log", lang="fr")
            assert bar.language_btn.cget("text") == "\U0001f310 FR"
            set_current_language("en")
        finally:
            root.destroy()
