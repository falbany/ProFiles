"""Centralized styling for ProFiles GUI.

All colour themes are defined in ``theme.py``. This module re-exports
the ``ToolTip`` utility class and provides the ``configure_styles()``
entry point for applying a Material Design 3 theme to the Tkinter
application.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk

from profiles.gui.theme import THEMES, Md3Theme

# ── Current theme tracking ──────────────────────────────────────────────────

_current_theme: Md3Theme = THEMES["light"]


# ── Convenience accessors (for dynamic use) ─────────────────────────────────


def current_theme() -> Md3Theme:
    """Return the currently active theme."""
    return _current_theme


def configure_styles(theme_name: str = "light") -> Md3Theme:
    """Configure ttk styles for the application.

    Applies the named Material Design 3 theme to all ttk widgets and
    updates the internal theme reference.

    Args:
        theme_name: One of ``"light"`` or ``"dark"``.

    Returns:
        The applied Md3Theme instance.
    """
    global _current_theme
    theme = THEMES.get(theme_name, THEMES["light"])
    _current_theme = theme
    return theme


# ── Tooltip ─────────────────────────────────────────────────────────────────


class ToolTip:
    """A hover tooltip attached to any tkinter widget.

    Usage::

        ToolTip(widget, "Helpful text")
    """

    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 400) -> None:
        self._widget = widget
        self._text = text
        self.delay_ms = delay_ms
        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None
        widget.bind("<Enter>", self._schedule_show, add=True)
        widget.bind("<Leave>", self._hide, add=True)
        widget.bind("<ButtonPress>", self._hide, add=True)

    def _schedule_show(self, _event: tk.Event | None = None) -> None:
        if self._after_id is not None:
            with contextlib.suppress(tk.TclError):
                self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._after_id = self._widget.after(self.delay_ms, self._show)

    def _show(self, _event: tk.Event | None = None) -> None:
        self._after_id = None
        if self._tip is not None or not self._text:
            return
        x = self._widget.winfo_rootx() + 16
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(
            self._tip,
            text=self._text,
            style="Tooltip.TLabel",
        )
        label.pack()

    def _hide(self, _event: tk.Event | None = None) -> None:
        if self._after_id is not None:
            with contextlib.suppress(tk.TclError):
                self._widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def set_text(self, text: str) -> None:
        """Update the tooltip text. Refreshes an already-visible tip."""
        self._text = text
        if self._tip is not None:
            for child in self._tip.winfo_children():
                with contextlib.suppress(tk.TclError):
                    child.configure(text=text)
