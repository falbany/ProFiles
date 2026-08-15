"""UI building helpers for MainWindow."""

# pylint: disable=protected-access

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from profiles.gui.search_bar import SearchBar
from profiles.gui.status_bar import StatusBar
from profiles.gui.styles import ToolTip

if TYPE_CHECKING:
    from profiles.gui.main_window import MainWindow


class MainWindowUI:
    """Helper class to construct the layout and widgets of MainWindow."""

    def __init__(self, window: MainWindow) -> None:
        """Initialize the UI builder.

        Args:
            window: The parent MainWindow instance to populate.
        """
        self.window = window

    def build(self) -> None:
        """Build all UI components."""
        self._build_header()
        self._build_search_bar()
        self._build_file_list()
        self._build_action_bar()
        self._build_status_bar()

    def _build_status_bar(self) -> None:
        """Build the status bar with tooltips.

        Creates a StatusBar instance and assigns widget references
        to the window for access.
        """
        from profiles.gui.theme import THEME_LABELS

        self.window._status_bar = StatusBar(
            parent=self.window._root,
            on_config_click=self.window._on_open_config,
            on_refresh_click=self.window._on_refresh,
            on_log_click=self.window._on_open_log,
            on_theme_toggle=self.window._on_toggle_theme,
            on_shortcuts_click=self.window._on_show_shortcuts,
            on_language_toggle=self.window._on_toggle_language,
            theme_label=THEME_LABELS.get(self.window._theme_name, "\u2600 Light"),
        )

        # Assign widget references
        self.window._status_frame = self.window._status_bar.status_frame
        self.window._status_inner = self.window._status_bar.status_inner
        self.window._config_link = self.window._status_bar.config_link
        self.window._refresh_btn = self.window._status_bar.refresh_btn
        self.window._log_link = self.window._status_bar.log_link
        self.window._shortcuts_btn = self.window._status_bar.shortcuts_btn
        self.window._theme_btn = self.window._status_bar.theme_btn
        self.window._user_label = self.window._status_bar.user_label
        self.window._host_label = self.window._status_bar.host_label
        self.window._ip_label = self.window._status_bar.ip_label
        self.window._count_label = self.window._status_bar.count_label
        self.window._dir_status_label = self.window._status_bar.dir_status_label
        self.window._dir_status_tooltip = self.window._status_bar.dir_status_tooltip

    def _build_header(self) -> None:
        """Build the application header separator."""
        # Horizontal outline-colored separator line using a standard Frame or Separator
        self.window._header_frame = ttk.Separator(
            self.window._root,
            orient="horizontal",
        )
        self.window._header_frame.pack(fill=tk.X, side=tk.TOP, pady=(4, 0))

    def _build_search_bar(self) -> None:
        """Build the search/filter bar with app title, directory, extension, and filter controls."""
        self.window._search_bar = SearchBar(
            parent=self.window._root,
            release_version=self.window._config.release,
            recursive_var=self.window._recursive_var,
            on_directory_changed=self.window._on_directory_changed,
            on_directory_enter=self.window._on_directory_enter,
            on_directory_double_click=self.window._on_directory_double_click,
            on_browse=self.window._on_browse,
            on_extension_or_filter_select=self.window._on_extension_or_filter_select,
            on_debounced_refresh_ext=lambda: self.window._debounced_refresh("_ext_timer"),
            on_flush_timer_ext=lambda: self.window._flush_timer("_ext_timer"),
            on_filter_refresh=lambda: self.window._debounced_refresh("_filter_timer"),
            on_flush_timer_filter=lambda: self.window._flush_timer("_filter_timer"),
            on_recursive_toggle=self.window._on_recursive_toggle,
            on_search=self.window._refresh_file_list,
            config_title=self.window._config.title,
        )

        # Assign widget references
        self.window._search_frame = self.window._search_bar.search_frame
        self.window._title_frame = self.window._search_bar.title_frame
        self.window._title_label = self.window._search_bar.title_label
        self.window._title_author = self.window._search_bar.title_author
        self.window._controls_frame = self.window._search_bar.controls_frame
        self.window._dir_frame = self.window._search_bar.dir_frame
        self.window._dir_var = self.window._search_bar.dir_var
        self.window._dir_combo = self.window._search_bar.dir_combo
        self.window._browse_btn = self.window._search_bar.browse_btn
        self.window._filter_frame = self.window._search_bar.filter_frame
        self.window._recursive_var = self.window._search_bar.recursive_var
        self.window._recursive_check = self.window._search_bar.recursive_check
        self.window._search_btn = self.window._search_bar.search_btn
        self.window._ext_var = self.window._search_bar.ext_var
        self.window._ext_combo = self.window._search_bar.ext_combo
        self.window._filter_var = self.window._search_bar.filter_var
        self.window._filter_combo = self.window._search_bar.filter_combo

    def _build_file_list(self) -> None:
        """Build the file list treeview with scrollbars, focus ring, and empty state placeholder."""
        list_frame = ttk.Frame(self.window._root, padding=(16, 0))
        list_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP, pady=(0, 8))

        # Outer container needs background & outline styling via ttk
        self.window._list_container = ttk.Frame(
            list_frame,
            style="TFrame",
        )
        self.window._list_container.pack(fill=tk.BOTH, expand=True)

        # Treeview
        self.window._tree = ttk.Treeview(
            self.window._list_container,
            columns=self.window._config.column_names,
            show="headings",
            selectmode="extended",
            style="FileList.Treeview",
        )

        # Sort state: tracks current sort column and direction
        self.window._sort_state = {}

        # Configure columns with stretch control and sort-on-click
        for i, (header, width, stretch) in enumerate(
            zip(
                self.window._config.column_headers,
                self.window._config.column_widths,
                self.window._config.column_stretches,
                strict=True,
            )
        ):
            self.window._tree.heading(
                i,
                text=header,
                anchor=tk.W,
                command=lambda idx=i: self.window._sort_treeview(idx),
            )
            self.window._tree.column(
                i,
                width=width,
                minwidth=50,
                anchor=tk.W,
                stretch=stretch,  # Apply per-column stretch behavior
            )

        # Scrollbars
        self.window._v_scroll = ttk.Scrollbar(
            self.window._list_container,
            orient=tk.VERTICAL,
            command=self.window._tree.yview,
        )
        self.window._h_scroll = ttk.Scrollbar(
            self.window._list_container,
            orient=tk.HORIZONTAL,
            command=self.window._tree.xview,
        )
        self.window._tree.configure(
            yscrollcommand=self.window._v_scroll.set,
            xscrollcommand=self.window._h_scroll.set,
        )

        self.window._tree.grid(row=0, column=0, sticky="nsew")
        self.window._v_scroll.grid(row=0, column=1, sticky="ns")
        self.window._h_scroll.grid(row=1, column=0, sticky="ew")

        self.window._list_container.grid_rowconfigure(0, weight=1)
        self.window._list_container.grid_columnconfigure(0, weight=1)

        # Bind events
        self.window._tree.bind("<Double-1>", self.window._on_execute)
        self.window._tree.bind("<Return>", self.window._on_execute)
        self.window._tree.bind("<Key-Up>", self.window._on_key_up)
        self.window._tree.bind("<Key-Down>", self.window._on_key_down)
        # Right-click context menu (Button-3 = right click, Button-2 = middle click on macOS)
        self.window._tree.bind("<Button-3>", self.window._on_tree_right_click)
        self.window._tree.bind("<Button-2>", self.window._on_tree_right_click)

        # On macOS, one-button mice use Control+Click. Button-3 doesn't fire.
        if sys.platform == "darwin":
            self.window._tree.bind("<Control-Button-1>", self.window._on_tree_right_click)

        # ── Smooth mouse-wheel scrolling ─────────────────────────────
        def _on_mousewheel(event: tk.Event) -> str:
            # macOS sends delta in multiples of 1; Windows/Linux in 120s
            if event.delta:
                units = -1 * (event.delta // (1 if abs(event.delta) < 10 else 120))
            elif event.num == 4:  # Linux scroll up
                units = -3
            elif event.num == 5:  # Linux scroll down
                units = 3
            else:
                units = 0
            self.window._tree.yview_scroll(units, "units")
            return "break"

        self.window._tree.bind("<MouseWheel>", _on_mousewheel)  # macOS / Windows
        self.window._tree.bind("<Button-4>", _on_mousewheel)  # Linux scroll up
        self.window._tree.bind("<Button-5>", _on_mousewheel)  # Linux scroll down

        # ── Horizontal pan (Shift+scroll / trackpad swipe) ───────────
        def _on_mousewheel_h(event: tk.Event) -> str:
            if event.delta:
                units = -1 * (event.delta // (1 if abs(event.delta) < 10 else 120))
            else:
                units = 0
            self.window._tree.xview_scroll(units, "units")
            return "break"

        self.window._tree.bind("<Shift-MouseWheel>", _on_mousewheel_h)

        # ── Page / Home / End navigation ─────────────────────────────
        def _nav_page(direction: int) -> str:
            children = self.window._tree.get_children()
            if not children:
                return "break"
            sel = self.window._tree.selection()
            idx = children.index(sel[0]) if sel and sel[0] in children else 0
            # Approximate visible rows from widget height and row height
            visible = max(1, self.window._tree.winfo_height() // 36)
            target = max(0, min(len(children) - 1, idx + direction * visible))
            item = children[target]
            self.window._tree.selection_set(item)
            self.window._tree.focus(item)
            self.window._tree.see(item)
            return "break"

        def _nav_edge(end: bool) -> str:
            children = self.window._tree.get_children()
            if not children:
                return "break"
            item = children[-1] if end else children[0]
            self.window._tree.selection_set(item)
            self.window._tree.focus(item)
            self.window._tree.see(item)
            return "break"

        self.window._tree.bind("<Prior>", lambda e: _nav_page(-1))  # Page Up
        self.window._tree.bind("<Next>", lambda e: _nav_page(1))  # Page Down
        self.window._tree.bind("<Home>", lambda e: _nav_edge(False))
        self.window._tree.bind("<End>", lambda e: _nav_edge(True))

        # Tag configuration for colored rows is applied dynamically per
        # active configuration's row_colors — see MainWindow._configure_row_colors.

        self._install_focus_ring()

    def _install_focus_ring(self) -> None:
        """Wire FocusIn/FocusOut to swap combobox style to Focus.TCombobox."""

        def _on_focus_in(_event: tk.Event, combo: ttk.Combobox) -> None:
            combo.configure(style="Focus.TCombobox")

        def _on_focus_out(_event: tk.Event, combo: ttk.Combobox) -> None:
            combo.configure(style="TCombobox")

        combos = (
            self.window._dir_combo,
            self.window._ext_combo,
            self.window._filter_combo,
        )
        for combo in combos:
            combo.bind("<FocusIn>", lambda e, c=combo: _on_focus_in(e, c), add="+")
            combo.bind("<FocusOut>", lambda e, c=combo: _on_focus_out(e, c), add="+")

    def _build_action_bar(self) -> None:
        """Build the action bar with execute button and options."""
        self.window._action_frame = ttk.Frame(self.window._root, padding=(16, 0))
        self.window._action_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 8))

        # Close after execution checkbox
        self.window._close_var = tk.BooleanVar(value=self.window._config.close_after_execute)
        self.window._close_check = ttk.Checkbutton(
            self.window._action_frame,
            text="Close after execution",
            variable=self.window._close_var,
            command=self.window._on_close_toggle,
        )
        self.window._close_check.pack(side=tk.LEFT, padx=(0, 20))
        ToolTip(self.window._close_check, "Close ProFiles after launching a file")

        # Indeterminate progressbar — shown only during long scans, hidden by default
        self.window._progress_bar = ttk.Progressbar(
            self.window._action_frame,
            mode="indeterminate",
        )
        self.window._progress_bar.pack(side=tk.LEFT, padx=(0, 12))
        self.window._progress_bar.pack_forget()

        # Execute button (prominent accent button)
        self.window._execute_btn = ttk.Button(
            self.window._action_frame,
            text="▶ Execute",
            command=self.window._on_execute,
            style="Execute.Accent.TButton",
        )
        self.window._execute_btn.pack(side=tk.RIGHT)
        ToolTip(self.window._execute_btn, "Launch the selected test program")
