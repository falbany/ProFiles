"""Tests for ``MainWindow._on_show_shortcuts`` — deprecated Tkinter GUI.

Lives under ``tests/gui`` so the directory-wide deprecation skip applies;
removed together with the Tkinter frontend in phase 2.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from profiles.gui.main_window import MainWindow


class TestShortcutsDialog:
    """The shortcuts dialog exposes both Keyboard and Mouse sections."""

    def test_shortcuts_dialog_has_mouse_section(self) -> None:
        """Render the dialog on a minimal host and confirm both section headers."""

        class _Host:
            """Minimal duck-typed host with the surface _on_show_shortcuts touches."""

            def __init__(self, root: tk.Tk) -> None:
                self._root = root
                # Stubs for attributes _shortcut_entries references at build time.
                self._refresh_file_list = lambda: None
                self._on_refresh = lambda: None
                self._on_open_log = lambda: None
                self._on_open_config = lambda: None
                self._on_toggle_theme = lambda: None
                self._on_close = lambda: None
                self._on_execute = lambda: None
                self._dir_combo = tk.Entry(root)
                self._ext_combo = tk.Entry(root)
                self._filter_combo = tk.Entry(root)
                self._tree = ttk.Treeview(root)
                self._filter_var = tk.StringVar(root)

            _shortcut_entries = MainWindow._shortcut_entries
            _mouse_entries = MainWindow._mouse_entries
            _on_show_shortcuts = MainWindow._on_show_shortcuts

        root = tk.Tk()
        try:
            host = _Host(root)
            host._on_show_shortcuts()
            root.update_idletasks()

            toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            assert toplevels, "Expected _on_show_shortcuts to create a Toplevel dialog"
            dlg = toplevels[-1]

            def _text_of(widget: tk.Misc) -> str | None:
                if not isinstance(widget, (tk.Widget, ttk.Widget)):
                    return None
                try:
                    return str(widget.cget("text"))
                except (tk.TclError, AttributeError):
                    return None

            labels_text = [t for t in (_text_of(w) for w in dlg.winfo_children()) if t]
            labels_text += [
                t
                for child in dlg.winfo_children()
                if isinstance(child, (tk.Frame, ttk.Frame))
                for t in (_text_of(w) for w in child.winfo_children())
                if t
            ]
            assert "Keyboard Shortcuts" in labels_text
            assert "Mouse Actions" in labels_text
        finally:
            root.destroy()
