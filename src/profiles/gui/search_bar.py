"""Search bar component for ProFiles.

Provides a dedicated search/filter bar with controls for directory selection,
extension filtering, keyword filtering, and search options.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from profiles.gui.i18n import register, t
from profiles.gui.styles import ToolTip


class SearchBar:
    """Search bar component for the main window.

    Contains app title, directory selection, extension filter, keyword filter,
    recursive option, and search button.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        release_version: str,
        recursive_var: tk.BooleanVar,
        on_directory_changed: Callable[[], None],
        on_directory_enter: Callable[[], None],
        on_directory_double_click: Callable[[], None],
        on_browse: Callable[[], None],
        on_extension_or_filter_select: Callable[[], None],
        on_debounced_refresh_ext: Callable[[], None],
        on_flush_timer_ext: Callable[[], None],
        on_filter_refresh: Callable[[], None],
        on_flush_timer_filter: Callable[[], None],
        on_recursive_toggle: Callable[[], None],
        on_search: Callable[[], None],
        config_title: str = "",
    ) -> None:
        """Initialize the search bar.

        Args:
            parent: Parent frame to attach the search bar to.
            release_version: Application version string.
            recursive_var: BooleanVar for recursive search checkbox.
            on_directory_changed: Callback for directory combobox selection.
            on_directory_enter: Callback for directory Enter key.
            on_directory_double_click: Callback for directory double-click.
            on_browse: Callback for browse button.
            on_extension_or_filter_select: Callback for extension/filter selection.
            on_debounced_refresh_ext: Callback for extension debounced refresh.
            on_flush_timer_ext: Callback for extension timer flush.
            on_filter_refresh: Callback for filter refresh.
            on_flush_timer_filter: Callback for filter timer flush.
            on_recursive_toggle: Callback for recursive checkbox toggle.
            on_search: Callback for search button.
        """
        self._parent = parent
        self._release_version = release_version
        self._config_title = config_title
        self._recursive_var = recursive_var
        self._on_directory_changed = on_directory_changed
        self._on_directory_enter = on_directory_enter
        self._on_directory_double_click = on_directory_double_click
        self._on_browse = on_browse
        self._on_extension_or_filter_select = on_extension_or_filter_select
        self._on_debounced_refresh_ext = on_debounced_refresh_ext
        self._on_flush_timer_ext = on_flush_timer_ext
        self._on_filter_refresh = on_filter_refresh
        self._on_flush_timer_filter = on_flush_timer_filter
        self._on_recursive_toggle = on_recursive_toggle
        self._on_search = on_search

        # String variables
        self._dir_var: tk.StringVar
        self._ext_var: tk.StringVar
        self._filter_var: tk.StringVar

        # Widget references
        self._search_frame: ttk.Frame
        self._title_frame: ttk.Frame
        self._title_label: ttk.Label
        self._title_author: ttk.Label
        self._controls_frame: ttk.Frame
        self._dir_frame: ttk.Frame
        self._dir_combo: ttk.Combobox
        self._browse_btn: ttk.Button
        self._filter_frame: ttk.Frame
        self._recursive_check: ttk.Checkbutton
        self._search_btn: ttk.Button
        self._ext_combo: ttk.Combobox
        self._filter_combo: ttk.Combobox

        # Translatable widget refs (set in _build, updated in _apply_text)
        self._dir_label: ttk.Label | None = None
        self._ext_label: ttk.Label | None = None
        self._filter_label: ttk.Label | None = None
        self._dir_tooltip: ToolTip | None = None
        self._browse_tooltip: ToolTip | None = None
        self._recursive_tooltip: ToolTip | None = None
        self._search_btn_tooltip: ToolTip | None = None
        self._ext_tooltip: ToolTip | None = None
        self._filter_tooltip: ToolTip | None = None
        self._title_tooltip: ToolTip | None = None

        self._build()
        register(self._apply_text)

    def _build(self) -> None:
        """Build the search bar widgets."""
        self._search_frame = ttk.Frame(self._parent)
        self._search_frame.pack(fill=tk.X, side=tk.TOP)

        # ── Title stacked vertically above directory/filters ─────────
        self._title_frame = ttk.Frame(self._search_frame, padding=(16, 14, 16, 0))
        self._title_frame.pack(side=tk.TOP, fill=tk.X)

        title_text = f"ProFiles — {self._config_title}" if self._config_title else "ProFiles"
        self._title_label = ttk.Label(
            self._title_frame,
            text=title_text,
            style="Title.TLabel",
        )
        self._title_label.pack(side=tk.LEFT, anchor=tk.W)

        self._title_author = ttk.Label(
            self._title_frame,
            text=f"By Florent ALBANY - v{self._release_version}",
            style="TitleAuthor.TLabel",
        )
        self._title_author.pack(side=tk.LEFT, anchor=tk.W, padx=(12, 0), pady=(6, 0))

        self._title_tooltip = ToolTip(self._title_frame, t("title.tooltip"))

        # ── Controls below the title ─────────────────────────
        self._controls_frame = ttk.Frame(self._search_frame, padding=(16, 10, 16, 14))
        self._controls_frame.pack(side=tk.TOP, fill=tk.X, expand=True)

        # --- Row 1: Directory ---
        self._dir_frame = ttk.Frame(self._controls_frame)
        self._dir_frame.pack(fill=tk.X, pady=(0, 10))

        self._dir_label = ttk.Label(
            self._dir_frame,
            text=t("search.dir_label"),
            width=9,
            anchor=tk.W,
        )
        self._dir_label.pack(side=tk.LEFT, padx=(0, 4))

        self._dir_var = tk.StringVar()
        self._dir_combo = ttk.Combobox(
            self._dir_frame,
            textvariable=self._dir_var,
            state="normal",
            width=60,
        )
        self._dir_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self._dir_combo.bind("<<ComboboxSelected>>", lambda _e=None: self._on_directory_changed())
        self._dir_combo.bind("<Return>", lambda _e=None: self._on_directory_enter())
        self._dir_combo.bind("<Double-Button-1>", lambda _e=None: self._on_directory_double_click())
        self._dir_tooltip = ToolTip(self._dir_combo, t("search.dir.tooltip"))

        self._browse_btn = ttk.Button(
            self._dir_frame,
            text=t("search.browse"),
            style="SearchBar.TButton",
            width=12,
            command=self._on_browse,
        )
        self._browse_btn.pack(side=tk.RIGHT, padx=(0, 0))
        self._browse_tooltip = ToolTip(self._browse_btn, t("search.browse.tooltip"))

        # --- Row 2: Extension + Filter + Search ---
        self._filter_frame = ttk.Frame(self._controls_frame)
        self._filter_frame.pack(fill=tk.X)

        # Right-aligned group: Recursive check + Search button
        right_group = ttk.Frame(self._filter_frame)
        right_group.pack(side=tk.RIGHT)

        self._recursive_check = ttk.Checkbutton(
            right_group,
            text=t("search.recursive"),
            variable=self._recursive_var,
            command=self._on_recursive_toggle,
        )
        self._recursive_check.pack(side=tk.LEFT, padx=(0, 12))
        self._recursive_tooltip = ToolTip(
            self._recursive_check,
            t("search.recursive.tooltip"),
        )

        self._search_btn = ttk.Button(
            right_group,
            text=t("search.search_btn"),
            style="SearchBar.TButton",
            width=12,
            command=self._on_search,
        )
        self._search_btn.pack(side=tk.LEFT, padx=(0, 0))
        self._search_btn_tooltip = ToolTip(self._search_btn, t("search.search_btn.tooltip"))

        # Extension label + combobox
        self._ext_label = ttk.Label(
            self._filter_frame,
            text=t("search.ext_label"),
            width=9,
            anchor=tk.W,
        )
        self._ext_label.pack(side=tk.LEFT, padx=(0, 4))

        self._ext_var = tk.StringVar()
        self._ext_combo = ttk.Combobox(
            self._filter_frame,
            textvariable=self._ext_var,
            state="normal",
            width=20,
        )
        self._ext_combo.pack(side=tk.LEFT, padx=(0, 24))
        self._ext_combo.bind(
            "<<ComboboxSelected>>", lambda _e=None: self._on_extension_or_filter_select()
        )
        self._ext_combo.bind("<KeyRelease>", lambda _e=None: self._on_debounced_refresh_ext())
        self._ext_combo.bind("<<FocusOut>>", lambda _e=None: self._on_flush_timer_ext())
        self._ext_tooltip = ToolTip(self._ext_combo, t("search.ext.tooltip"))

        # Filter label + expanding combobox
        self._filter_label = ttk.Label(
            self._filter_frame,
            text=t("search.filter_label"),
        )
        self._filter_label.pack(side=tk.LEFT, padx=(0, 4))

        self._filter_var = tk.StringVar()
        self._filter_combo = ttk.Combobox(
            self._filter_frame,
            textvariable=self._filter_var,
            state="normal",
        )
        self._filter_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 24))
        self._filter_combo.bind(
            "<<ComboboxSelected>>", lambda _e=None: self._on_extension_or_filter_select()
        )
        self._filter_combo.bind("<KeyRelease>", lambda _e=None: self._on_filter_refresh())
        self._filter_combo.bind("<<FocusOut>>", lambda _e=None: self._on_flush_timer_filter())
        self._filter_tooltip = ToolTip(self._filter_combo, t("search.filter.tooltip"))

    def _apply_text(self, lang: str | None = None) -> None:
        """Re-label all translatable widgets in the search bar.

        Args:
            lang: Ignored; ``t()`` reads the current language. Present so
                this method matches the i18n registry callback signature.
        """
        with contextlib.suppress(tk.TclError):
            if self._dir_label is not None:
                self._dir_label.configure(text=t("search.dir_label"))
            if self._ext_label is not None:
                self._ext_label.configure(text=t("search.ext_label"))
            if self._filter_label is not None:
                self._filter_label.configure(text=t("search.filter_label"))
            self._browse_btn.configure(text=t("search.browse"))
            self._recursive_check.configure(text=t("search.recursive"))
            self._search_btn.configure(text=t("search.search_btn"))
            if self._dir_tooltip is not None:
                self._dir_tooltip.set_text(t("search.dir.tooltip"))
            if self._browse_tooltip is not None:
                self._browse_tooltip.set_text(t("search.browse.tooltip"))
            if self._recursive_tooltip is not None:
                self._recursive_tooltip.set_text(t("search.recursive.tooltip"))
            if self._search_btn_tooltip is not None:
                self._search_btn_tooltip.set_text(t("search.search_btn.tooltip"))
            if self._ext_tooltip is not None:
                self._ext_tooltip.set_text(t("search.ext.tooltip"))
            if self._filter_tooltip is not None:
                self._filter_tooltip.set_text(t("search.filter.tooltip"))
            if self._title_tooltip is not None:
                self._title_tooltip.set_text(t("title.tooltip"))

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    @property
    def search_frame(self) -> ttk.Frame:
        """Get the outer search bar frame."""
        return self._search_frame

    @property
    def title_frame(self) -> ttk.Frame:
        """Get the title frame."""
        return self._title_frame

    @property
    def title_label(self) -> ttk.Label:
        """Get the title label."""
        return self._title_label

    @property
    def title_author(self) -> ttk.Label:
        """Get the title author label."""
        return self._title_author

    @property
    def controls_frame(self) -> ttk.Frame:
        """Get the controls frame."""
        return self._controls_frame

    @property
    def dir_frame(self) -> ttk.Frame:
        """Get the directory frame."""
        return self._dir_frame

    @property
    def dir_var(self) -> tk.StringVar:
        """Get the directory variable."""
        return self._dir_var

    @property
    def dir_combo(self) -> ttk.Combobox:
        """Get the directory combobox."""
        return self._dir_combo

    @property
    def browse_btn(self) -> ttk.Button:
        """Get the browse button."""
        return self._browse_btn

    @property
    def filter_frame(self) -> ttk.Frame:
        """Get the filter frame."""
        return self._filter_frame

    @property
    def recursive_var(self) -> tk.BooleanVar:
        """Get the recursive variable."""
        return self._recursive_var

    @property
    def recursive_check(self) -> ttk.Checkbutton:
        """Get the recursive checkbox."""
        return self._recursive_check

    @property
    def search_btn(self) -> ttk.Button:
        """Get the search button."""
        return self._search_btn

    @property
    def ext_var(self) -> tk.StringVar:
        """Get the extension variable."""
        return self._ext_var

    @property
    def ext_combo(self) -> ttk.Combobox:
        """Get the extension combobox."""
        return self._ext_combo

    @property
    def filter_var(self) -> tk.StringVar:
        """Get the filter variable."""
        return self._filter_var

    @property
    def filter_combo(self) -> ttk.Combobox:
        """Get the filter combobox."""
        return self._filter_combo
