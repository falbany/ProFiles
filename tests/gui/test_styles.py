"""Tests for profiles.gui.styles — configure_styles, ToolTip class.

Note: Tests that require a Tk root widget use ``pytest.mark.skipif``
when Tkinter is unavailable (headless CI, missing Tcl/Tk). The ToolTip
class is tested for binding setup only — never calls mainloop().
"""

from __future__ import annotations

import tkinter as tk

import pytest

from profiles.gui.styles import ToolTip, configure_styles, current_theme
from profiles.gui.theme import (
    DARK_THEME,
    FONT_FAMILY,
    FONT_SIZE_LARGE,
    FONT_SIZE_NORMAL,
    FONT_SIZE_SMALL,
    LIGHT_THEME,
)

# ── Tkinter availability guard ──────────────────────────────────────────────

_tk_available = True
try:
    _root_test = tk.Tk()
    _root_test.destroy()
except (tk.TclError, RuntimeError):
    _tk_available = False

needs_tk = pytest.mark.skipif(
    not _tk_available,
    reason="Tkinter not available (headless CI or missing Tcl/Tk)",
)


# ── current_theme ────────────────────────────────────────────────────────────


class TestCurrentTheme:
    """current_theme() accessor."""

    def test_returns_md3_theme(self) -> None:
        theme = current_theme()
        assert theme is LIGHT_THEME  # default before configure_styles call

    def test_reimported(self) -> None:
        """Re-import from theme.py matches."""
        from profiles.gui.theme import LIGHT_THEME as LT  # noqa: PLC0415

        assert current_theme() is LT


# ── configure_styles ────────────────────────────────────────────────────────


class TestConfigureStyles:
    """configure_styles() function — no Tkinter required."""

    def test_configure_light(self) -> None:
        theme = configure_styles("light")
        assert theme is LIGHT_THEME
        assert current_theme() is LIGHT_THEME

    def test_configure_dark(self) -> None:
        theme = configure_styles("dark")
        assert theme is DARK_THEME
        assert current_theme() is DARK_THEME

    def test_unknown_theme_falls_back_to_light(self) -> None:
        theme = configure_styles("unknown")
        assert theme is LIGHT_THEME


# ── Font constants ──────────────────────────────────────────────────────────


class TestFontConstants:
    """Font configuration values are sensible (re-exported from theme.py)."""

    def test_font_family_is_string(self) -> None:
        assert isinstance(FONT_FAMILY, str)
        assert len(FONT_FAMILY) > 0

    def test_font_sizes_positive(self) -> None:
        assert FONT_SIZE_SMALL > 0
        assert FONT_SIZE_NORMAL > 0
        assert FONT_SIZE_LARGE > 0

    def test_font_size_ordering(self) -> None:
        assert FONT_SIZE_SMALL < FONT_SIZE_NORMAL < FONT_SIZE_LARGE


# ── ToolTip (requires Tk root, no mainloop) ─────────────────────────────────


@needs_tk
class TestToolTip:
    """ToolTip binding setup — no main loop required."""

    @pytest.fixture
    def root(self) -> tk.Tk:
        """Create a temporary Tk root for widget creation."""
        r = tk.Tk()
        yield r
        r.destroy()

    def test_binds_enter_leave_buttonpress(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "Helpful text")  # noqa: F841
        # Verify bindings were added
        assert widget.bind("<Enter>") != ""
        assert widget.bind("<Leave>") != ""
        assert widget.bind("<ButtonPress>") != ""

    def test_default_delay_ms_is_400(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "x")
        assert tip.delay_ms == 400

    def test_custom_delay_ms(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "x", delay_ms=50)
        assert tip.delay_ms == 50

    def test_light_dark_tooltip_bg_differ(self) -> None:
        assert LIGHT_THEME.tooltip_bg != DARK_THEME.tooltip_bg

    def test_empty_text_skips_show(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "")
        assert tip._tip is None
        # _show should not create a Toplevel for empty text
        tip._show()
        assert tip._tip is None

    def test_show_creates_toplevel(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "Some info")
        tip._show()
        assert tip._tip is not None
        assert isinstance(tip._tip, tk.Toplevel)
        tip._hide()
        assert tip._tip is None

    def test_double_show_does_not_duplicate(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "Info")
        tip._show()
        first_tip = tip._tip
        tip._show()  # should be no-op (tip is not None and not empty)
        assert tip._tip is first_tip
        tip._hide()

    def test_hide_destroyed_tip_graceful(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "Info")
        tip._show()
        assert tip._tip is not None
        tip._hide()
        assert tip._tip is None
        # Hiding again should not error
        tip._hide()
        assert tip._tip is None

    def test_set_text_updates_when_tip_hidden(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "Initial")
        tip.set_text("Updated")
        assert tip._text == "Updated"
        assert tip._tip is None

    def test_set_text_refreshes_visible_tip(self, root: tk.Tk) -> None:
        widget = tk.Label(root, text="test")
        tip = ToolTip(widget, "Initial")
        tip._show()
        assert tip._tip is not None
        tip.set_text("Updated")
        assert tip._text == "Updated"
        labels = tip._tip.winfo_children()
        assert labels[0].cget("text") == "Updated"
