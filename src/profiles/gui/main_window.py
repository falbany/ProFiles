"""Main window for ProFiles.

Provides the primary GUI interface: a file browser with filtering
capabilities for selecting and launching production test programs.
"""

from __future__ import annotations

import contextlib
import importlib.resources
import logging
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from profiles.core import actions
from profiles.core.config import service as config_service
from profiles.core.config.io.yaml_io import write_value
from profiles.core.config.loader import load_config
from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.core.environment import system
from profiles.core.processing import scanner
from profiles.core.processing.file_classifier import directory_exists
from profiles.gui.context_menu import FileContextMenu
from profiles.gui.controllers.directory_manager import (
    DirectoryManager,
    format_dir_entry,
)
from profiles.gui.controllers.scan_controller import run_scan
from profiles.gui.i18n import set_language
from profiles.gui.presentation.row_colors import RowColorRules, default_tag_name
from profiles.gui.status_bar import StatusBar
from profiles.gui.styles import ToolTip, configure_styles
from profiles.gui.theme import (
    THEME_LABELS,
    THEMES,
    Md3Theme,
    contrast_ratio,
    resolve_theme_name,
)
from profiles.gui.ui import MainWindowUI
from profiles.utils.file_utils import open_file_explorer

#: Minimum WCAG contrast ratio for a row-colour foreground against the
#: theme surface. Below this the text is effectively unreadable, so the
#: configured colour is replaced with the theme's standard text colour.
_MIN_ROW_COLOR_CONTRAST = 1.5


class MainWindow:
    """Main application window for ProFiles.

    Provides a treeview-based file browser with filtering, directory
    selection, and one-click execution of production test programs.
    """

    # Widgets and variables (built by MainWindowUI)
    _header_frame: ttk.Frame
    _search_frame: ttk.Frame
    _title_frame: ttk.Frame
    _title_label: ttk.Label
    _title_author: ttk.Label
    _controls_frame: ttk.Frame
    _dir_frame: ttk.Frame
    _dir_var: tk.StringVar
    _dir_combo: ttk.Combobox
    _browse_btn: ttk.Button
    _filter_frame: ttk.Frame
    _recursive_check: ttk.Checkbutton
    _search_btn: ttk.Button
    _ext_var: tk.StringVar
    _ext_combo: ttk.Combobox
    _filter_var: tk.StringVar
    _filter_combo: ttk.Combobox
    _list_container: ttk.Frame
    _tree: ttk.Treeview
    _sort_state: dict[int, str]
    _v_scroll: ttk.Scrollbar
    _h_scroll: ttk.Scrollbar
    _action_frame: ttk.Frame
    _close_var: tk.BooleanVar
    _close_check: ttk.Checkbutton
    _execute_btn: ttk.Button
    _status_frame: ttk.Frame
    _status_inner: ttk.Frame
    _config_link: ttk.Button
    _refresh_btn: ttk.Button
    _log_link: ttk.Button
    _shortcuts_btn: ttk.Button | None
    _theme_btn: ttk.Button
    _user_label: ttk.Label
    _host_label: ttk.Label
    _ip_label: ttk.Label
    _count_label: ttk.Label
    _dir_status_label: ttk.Label
    _dir_status_tooltip: ToolTip | None

    _row_color_rules: list[tuple[str, str]]
    _row_color_pattern_cache: list[tuple[re.Pattern, str]]  # Compiled regex patterns
    _status_bar: StatusBar  # Set dynamically by ui.py _build_status_bar()
    _row_color_tag_prefix: str

    def __init__(self, config: AppConfig) -> None:
        """Initialize the main window.

        Args:
            config: The application configuration.
        """
        self._config = config
        self._logger = logging.getLogger("profiles")
        self._current_scan_id: int = 0
        self._scan_in_progress: bool = False
        self._filter_timer: str | None = None  # Debounce timer for filter field
        self._ext_timer: str | None = None  # Debounce timer for extension field
        self._row_color_rules: list[tuple[str, str]] = []
        self._row_color_tag_prefix = "_rowcolor"
        self._tree_to_path: dict[str, Path] = {}  # iid -> filesystem path
        self._tree_to_filename: dict[str, str] = {}  # iid -> filename (for log)

        # Build window
        self._root = tk.Tk()
        self._recursive_var = tk.BooleanVar(value=self._config.recursive_search)
        self._root.title(f"ProFiles - {config.title}" if config.title else "ProFiles")
        self._root.geometry("1000x700")
        self._root.minsize(800, 500)

        # Try to set icon
        self._try_set_icon()

        # Theme initialisation
        self._theme_name: str = self._config.theme
        resolved_name = resolve_theme_name(self._theme_name)
        self._theme: Md3Theme = THEMES.get(resolved_name, THEMES["light"])
        configure_styles(self._root, resolved_name)

        # Language initialisation (before UI build so widgets are created
        # in the configured language)
        set_language(self._config.language)

        # Initialize helpers
        self._ui = MainWindowUI(self)
        self._context_menu = FileContextMenu(self)

        # Build the UI
        self._ui.build()

        # Configure keyboard shortcuts
        self._configure_bindings()

        # Populate initial data
        self._load_system_info()  # sets self._hostname early
        self._dir_manager = DirectoryManager(view=self, hostname=self._hostname)
        self._populate_directories()
        self._populate_extensions()
        self._populate_filters()
        self._auto_select_directory()
        self._apply_config_overrides()
        self._configure_row_colors()
        self._refresh_file_list()

        # Check if config file exists, propose creation if not
        if not self._config.skip_config_prompt:
            self._check_config_file()

        # Center on screen
        self._center_window()

        # Protocol for window close
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------------
    # Window setup
    # ----------------------------------------------------------------

    def _try_set_icon(self) -> None:
        """Try to set the window icon from available resources.

        Checks the current working directory first, then falls back to
        packaged assets (when the package is installed with bundled
        ``img/`` resources).
        """
        cwd_ico = Path.cwd() / "img" / "launcher.ico"
        cwd_png = Path.cwd() / "img" / "launcher.png"
        if cwd_ico.exists():
            with contextlib.suppress(tk.TclError):
                self._root.iconbitmap(str(cwd_ico))
                return
        if cwd_png.exists():
            with contextlib.suppress(tk.TclError):
                self._root.iconphoto(True, tk.PhotoImage(file=str(cwd_png)))
            return

        # Fallback: look for packaged assets (no img/ shipped today; safe no-op)
        try:
            pkg_img = importlib.resources.files("profiles").joinpath("img")
            pkg_ico = pkg_img.joinpath("launcher.ico")
            if pkg_ico.is_file():
                with contextlib.suppress(tk.TclError):
                    self._root.iconbitmap(str(pkg_ico))
                    return
            pkg_png = pkg_img.joinpath("launcher.png")
            if pkg_png.is_file():
                with contextlib.suppress(tk.TclError):
                    self._root.iconphoto(True, tk.PhotoImage(file=str(pkg_png)))
        except (ImportError, AttributeError, OSError, TypeError):
            pass

    def _center_window(self) -> None:
        """Center the window on the screen."""
        self._root.update_idletasks()
        width = self._root.winfo_width()
        height = self._root.winfo_height()
        screen_width = self._root.winfo_screenwidth()
        screen_height = self._root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self._root.geometry(f"{width}x{height}+{x}+{y}")

    # ----------------------------------------------------------------
    # Sorting
    # ----------------------------------------------------------------

    def _sort_treeview(self, col_index: int) -> None:
        """Sort the treeview rows by *col_index* (0=File, 1=Version).

        Optimized version: batch delete and reinsert using move for better performance
        with large file lists (1000+ items).
        """
        children = list(self._tree.get_children(""))
        if not children:
            return

        # Collect all items with their sort values before sorting
        items_data = []
        for item_id in children:
            val = self._tree.set(item_id, col_index)
            sort_val = val.lower() if val else ""
            items_data.append((sort_val, item_id))

        # Determine direction
        reverse = self._sort_state.get(col_index) == "asc"
        self._sort_state[col_index] = "desc" if reverse else "asc"

        # Sort the collected data
        items_data.sort(key=lambda x: x[0], reverse=reverse)

        # Batch move/reattach items in sorted order (much faster than delete + insert)
        for _, item_id in items_data:
            self._tree.move(item_id, "", tk.END)

        # Update heading indicators
        for i, header in enumerate(self._config.column_headers):
            arrow = ""
            if i == col_index:
                arrow = " \u25b2" if not reverse else " \u25bc"
            self._tree.heading(i, text=header + arrow)

    # ----------------------------------------------------------------
    # Theme switching
    # ----------------------------------------------------------------

    def _on_toggle_theme(self) -> None:
        """Toggle between light, dark, and auto themes."""
        if self._theme_name == "light":
            new_name = "dark"
        elif self._theme_name == "dark":
            new_name = "auto"
        else:
            new_name = "light"
        self._apply_theme(new_name)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the named theme to the entire GUI."""
        resolved_name = resolve_theme_name(theme_name)
        theme = THEMES.get(resolved_name, THEMES["light"])
        self._theme = theme
        self._theme_name = theme_name

        # 1. Apply ttk styles + tk palette (single entry point)
        configure_styles(self._root, resolved_name)

        # 2. Reconfigure row color tags against the (possibly new) theme palette
        self._configure_row_colors()

        # 3. Update theme button text via status bar
        if self._status_bar:
            self._status_bar.update_theme_label(THEME_LABELS.get(theme_name, "\u2600 Light"))

        # 4. Persist to config
        write_value(
            self._config.config_path,
            "defaults.theme",
            theme_name,
        )

        self._logger.info("Theme switched to: %s", theme_name)

    def _on_toggle_language(self) -> None:
        """Toggle the GUI language between English and French."""
        from profiles.gui.i18n import current_language

        new_lang = "fr" if current_language() == "en" else "en"
        set_language(new_lang)

        # Persist to config
        write_value(
            self._config.config_path,
            "defaults.language",
            new_lang,
        )

        self._logger.info("Language switched to: %s", new_lang)

    # ----------------------------------------------------------------
    # Data population
    # ----------------------------------------------------------------

    def _populate_directories(self) -> None:
        """Populate the directory combobox from configurations.

        Delegates to :class:`DirectoryManager` for the actual logic.
        """
        self._dir_manager.populate()

    @staticmethod
    def _format_dir_entry(entry: config_service.DirectoryEntry) -> str:
        """Format a DirectoryEntry as a combobox display string."""
        return format_dir_entry(entry)

    def _resolve_dir_selection(self, label: str) -> list[str]:
        """Resolve a combobox selection label to the list of scan paths."""
        return self._dir_manager.resolve(label)

    def _set_dir_selection(self, label: str) -> None:
        """Set the combobox to the entry matching *label*, or ``label`` itself."""
        self._dir_manager.set_selection(label)

    def _populate_extensions(self) -> None:
        """Populate the extension combobox."""
        self._ext_combo["values"] = self._config.extensions
        self._ext_var.set(self._config.extensions[0] if self._config.extensions else "")

    def _populate_filters(self) -> None:
        """Populate the filter combobox."""
        self._filter_combo["values"] = self._config.filters
        self._filter_var.set(self._config.filters[0] if self._config.filters else "")

    # ponytail: only consumer is tests/test_extension_filter.py; delete when
    # those tests move to the core module.
    @staticmethod
    def _is_simple_extension(ext: str) -> bool:
        """Check whether *ext* is a simple extension (no search operators)."""
        return scanner.is_simple_extension(ext)

    def _load_system_info(self) -> None:
        """Load and display system information in the status bar."""
        info = system.collect_system_info()
        self._hostname = info.hostname
        self._user_label.config(text=info.username)
        self._host_label.config(text=info.hostname)
        self._ip_label.config(text=info.ip)

        # Update logger source with actual hostname
        system.apply_source_to_logger(self._logger, info.hostname)

    def _auto_select_directory(self) -> None:
        """Auto-select the directory matching the current hostname.

        Delegates to :class:`DirectoryManager`.
        """
        self._dir_manager.auto_select()

    def _current_dir_label(self) -> str:
        """Return the current combobox selection with icon prefix stripped."""
        return self._dir_manager.current_label()

    def _find_active_config(self) -> MachineConfiguration | None:
        """Find the configuration matching the currently selected directory."""
        return self._dir_manager.find_active_config()

    def _apply_config_overrides(self) -> None:
        """Merge per-config extensions/filters with the generic [LAUNCHER] defaults."""
        self._dir_manager.apply_config_overrides()

    # ----------------------------------------------------------------
    # Row coloring (per-config `row_colors`)
    # ----------------------------------------------------------------

    def _configure_row_colors(self) -> None:
        """Reconfigure treeview tags to match the active configuration's row_colors.

        Each ``(pattern, color)`` rule from the active MachineConfiguration
        becomes a unique treeview tag. Pattern matching is case-insensitive
        substring against each filename. If no configuration matches the
        selected directory, fall back to [LAUNCHER].row_colors.

        Configured colours are used as-is on both light and dark themes;
        only colours whose WCAG contrast ratio against ``self._theme.surface``
        is below ``_MIN_ROW_COLOR_CONTRAST`` (effectively invisible) are
        replaced with the theme's ``on_surface`` text colour so the row
        stays readable. Tag names derive from the *original* configured
        colour, keeping tags stable across theme switches. A
        ``_rowcolor_default`` tag is always configured with the theme's
        ``on_surface_variant`` foreground so empty rules still produce a
        visible tag (it is not auto-applied to rows).
        """
        self._row_color_rules = []

        active = self._find_active_config()

        # Use active config row_colors if found, otherwise fall back to [LAUNCHER] row_colors
        row_colors_to_use = active.row_colors if active is not None else self._config.row_colors

        for pattern, color in row_colors_to_use:
            if not pattern or not color:
                continue
            # Contrast-based fallback: if the configured foreground is
            # indistinguishable from the active surface it would be
            # invisible on the background, so substitute the standard
            # readable text colour. Legitimate tints (e.g. PROD:#1565C0
            # on the dark surface) keep their colour in both themes.
            effective_color = color
            if contrast_ratio(color, self._theme.surface) < _MIN_ROW_COLOR_CONTRAST:
                effective_color = self._theme.on_surface
            # Tag names disallow spaces; replace them so the tag can be applied.
            safe_pattern = pattern.replace(" ", "_")
            safe_color = color.lstrip("#").replace(" ", "_")
            tag_name = f"{self._row_color_tag_prefix}_{safe_pattern}_{safe_color}"
            try:
                self._tree.tag_configure(tag_name, foreground=effective_color)
            except tk.TclError as exc:
                self._logger.warning("Skipping invalid row_color '%s:%s': %s", pattern, color, exc)
                continue
            self._row_color_rules.append((pattern, tag_name))

        # Build the engine for fast per-row tag lookup
        self._row_color_rules_engine = RowColorRules(row_colors_to_use, self._row_color_tag_prefix)

        # Always expose a default tag so empty rule lists still produce a
        # visible colour that tests can inspect. The tag is intentionally
        # not auto-applied to rows — this preserves the unchanged row
        # colouring behaviour when no rules are configured.
        try:
            self._tree.tag_configure(
                default_tag_name(self._row_color_tag_prefix),
                foreground=self._theme.on_surface_variant,
            )
        except tk.TclError as exc:
            self._logger.warning("Could not configure default row color tag: %s", exc)

    def _row_color_tags_for(self, filename: str) -> tuple[str, ...]:
        """Return tags for *filename*: the default variant tag (always
        applied) plus the first matching row_color rule, if any.

        Delegates to :class:`RowColorRules` for the matching — this
        method only exists to keep the original call sites stable.
        """
        if self._row_color_rules_engine is None:
            return (default_tag_name(self._row_color_tag_prefix),)
        return self._row_color_rules_engine.tags_for(filename)

    # ----------------------------------------------------------------
    # File list operations
    # ----------------------------------------------------------------

    def _refresh_file_list(self) -> None:
        """Scan the selected directory and populate the file list."""
        directory_label = self._current_dir_label()
        extension = self._ext_var.get()
        filter_text = self._filter_var.get().strip()

        # Resolve the combobox label to scan paths (multiple for configs)
        scan_paths = self._resolve_dir_selection(directory_label)

        # Cancel any ongoing scan/insert by incrementing the ID
        self._current_scan_id += 1
        scan_id = self._current_scan_id

        # Clear the tree (batch delete for performance)
        children = self._tree.get_children()
        if children:
            self._tree.delete(*children)
        self._tree_to_path.clear()
        self._tree_to_filename.clear()

        # Reset sort state and heading indicators
        self._sort_state.clear()
        for i, header in enumerate(self._config.column_headers):
            self._tree.heading(i, text=header)

        # Check that at least one scan path exists
        if not scan_paths or not any(directory_exists(p) for p in scan_paths):
            self._count_label.config(text="Files: 0")
            self._dir_status_label.config(text="Directory not found", style="Status.Error.TLabel")
            self._update_empty_state(True)
            return

        self._update_empty_state(False)

        if len(scan_paths) > 1:
            self._dir_status_label.config(
                text=f"Scanning {len(scan_paths)} paths", style="Status.Info.TLabel"
            )
            if self._dir_status_tooltip:
                self._dir_status_tooltip.set_text(
                    "Paths:\n" + "\n".join(f"• {p}" for p in scan_paths)
                )
        else:
            self._dir_status_label.config(text="Scanning...", style="Status.Info.TLabel")
            if self._dir_status_tooltip:
                self._dir_status_tooltip.set_text("Current search directory")

        self._count_label.config(text="Files: 0")
        self._root.update_idletasks()
        self._scan_in_progress = True
        self._root.after(200, self._show_progress)

        # Start scanning in a background thread
        # NOTE: tkinter variables MUST be read on the main thread, so the
        # worker only performs pure computation and pushes its result into
        # _scan_queue; _poll_scan_queue drains it on the main thread.
        threading.Thread(
            target=self._bg_scan_and_process,
            args=(
                scan_id,
                scan_paths,
                extension,
                filter_text,
                bool(self._recursive_var.get()),
                directory_label,
            ),
            daemon=True,
        ).start()
        self._root.after(
            50, self._poll_scan_queue, scan_id, directory_label, filter_text, extension
        )

    def _bg_scan_and_process(
        self,
        scan_id: int,
        directories: list[str],
        extension: str,
        filter_text: str,
        recursive: bool,
        directory_label: str,
    ) -> None:
        """Scan directories and process files in a background thread.

        Thin wrapper around :func:`run_scan` (which owns the pure
        worker logic). Kept as a method so existing
        ``threading.Thread(target=self._bg_scan_and_process, args=...)``
        call sites continue to work without churn.
        """
        # If this scan has already been superseded, skip the work entirely.
        if scan_id != self._current_scan_id:
            return
        run_scan(
            config=self._config,
            directory_label=directory_label,
            scan_paths=directories,
            extension=extension,
            filter_text=filter_text,
            recursive=recursive,
            queue_=self._scan_queue,
            scan_id=scan_id,
            logger=self._logger,
        )

    def _poll_scan_queue(
        self,
        scan_id: int,
        display_label: str,
        filter_text: str,
        extension: str,
    ) -> None:
        """Drain a finished scan result on the main thread.

        Called repeatedly via ``after()`` while a background scan is in
        flight. When the worker pushes a result for *scan_id*, the chunked
        insertion (which touches the Treeview) is started here, on the
        main thread. Stale results for superseded scans are discarded.
        """
        while True:
            try:
                status, queued_scan_id, items = self._scan_queue.get_nowait()
            except queue.Empty:
                # Scan still running: keep polling if this scan is still current
                if scan_id == self._current_scan_id:
                    self._root.after(
                        50,
                        self._poll_scan_queue,
                        scan_id,
                        display_label,
                        filter_text,
                        extension,
                    )
                return

            if queued_scan_id != scan_id:
                continue  # Result belongs to a superseded scan — discard

            # Result for the scan we are waiting for
            self._scan_in_progress = False
            if status == "error":
                self._dir_status_label.config(text="Scan failed", style="Status.Error.TLabel")
                self._hide_progress()
            else:
                self._start_chunked_insert(scan_id, items, display_label, filter_text, extension)
            return

    def _start_chunked_insert(
        self,
        scan_id: int,
        items: list[scanner.ScannedFileDynamic],
        display_label: str,
        filter_text: str,
        extension: str,
    ) -> None:
        """Initialize the chunked insertion on the main thread."""
        if scan_id != self._current_scan_id:
            return

        self._insert_chunk(scan_id, items, 0, [], display_label, filter_text, extension)

    def _insert_chunk(
        self,
        scan_id: int,
        items: list[scanner.ScannedFileDynamic],
        start_idx: int,
        accumulated_files: list[Path],
        display_label: str,
        filter_text: str,
        extension: str,
    ) -> None:
        """Insert a chunk of files into the Treeview and schedule the next chunk.

        Values are built from ``self._config.column_names`` — the single
        source of truth for the tree columns — so one code path handles
        the single-column layout, the default File/Version layout, and
        fully custom column sets.

        Args:
            scan_id: Current scan ID for validation.
            items: List of scanned files with dynamic column values.
            start_idx: Starting index for this chunk.
            accumulated_files: Accumulated list of file paths.
            display_label: Display label for the scanned directory/config.
            filter_text: Keyword filter used by the scan (for logging).
            extension: Extension expression used by the scan (for logging).
        """
        if scan_id != self._current_scan_id:
            return

        # Adaptive chunk size: render initial 200 items immediately for fast first paint,
        # then scale up to 1000 items per chunk for fast background completion.
        chunk_size = 200 if start_idx == 0 else 1000
        end_idx = min(start_idx + chunk_size, len(items))
        column_names = self._config.column_names

        # Insert this chunk
        for i in range(start_idx, end_idx):
            scanned_file = items[i]
            filename = scanned_file.column_values.get("File", "")
            row_tags = self._row_color_tags_for(filename)

            # Build values tuple from column values in order
            values = tuple(
                scanned_file.column_values.get(col_name, "") for col_name in column_names
            )

            iid = f"{scan_id}_{i}"
            self._tree.insert(
                parent="",
                index=tk.END,
                iid=iid,
                values=values,
                tags=row_tags,
            )
            self._tree_to_path[iid] = scanned_file.path
            self._tree_to_filename[iid] = filename
            accumulated_files.append(scanned_file.path)

        # Update temporary count label
        self._count_label.config(text=f"Files: {end_idx}")

        if end_idx < len(items):
            # Schedule next chunk with minimal delay
            self._root.after(
                1,  # Reduced from 10ms for faster insertion
                self._insert_chunk,
                scan_id,
                items,
                end_idx,
                accumulated_files,
                display_label,
                filter_text,
                extension,
            )
        else:
            # Finalize
            count = len(accumulated_files)
            self._count_label.config(text=f"Files: {count}")
            self._hide_progress()
            self._flash_count_label()
            self._update_empty_state(count == 0)

            scan_paths = self._resolve_dir_selection(display_label)
            if count == 0:
                self._dir_status_label.config(text="No matching files found", style="Info.TLabel")
            elif len(scan_paths) > 1:
                self._dir_status_label.config(
                    text=f"Scanned {len(scan_paths)} paths",
                    style="Info.TLabel",
                )
                if self._dir_status_tooltip:
                    self._dir_status_tooltip.set_text(
                        "Scanned paths:\n" + "\n".join(f"• {p}" for p in scan_paths)
                    )
            else:
                self._dir_status_label.config(
                    text=f"Directory: {display_label}", style="Info.TLabel"
                )
                if self._dir_status_tooltip:
                    self._dir_status_tooltip.set_text(f"Directory: {display_label}")

            self._logger.info(
                "Scanned directory: %s | Extension: %s | Filter: '%s' | Files found: %d",
                display_label,
                extension,
                filter_text,
                count,
            )

    # ----------------------------------------------------------------
    # Event handlers
    # ----------------------------------------------------------------

    def _on_recursive_toggle(self) -> None:
        """Handle Recursive checkbox toggle: persist to config and refresh."""
        write_value(
            self._config.config_path,
            "defaults.recursive_search",
            self._recursive_var.get(),
        )
        self._refresh_file_list()

    def _on_close_toggle(self) -> None:
        """Handle Close after execution toggle: persist to config."""
        write_value(
            self._config.config_path,
            "defaults.close_after_execute",
            self._close_var.get(),
        )

    def _on_directory_changed(self, _event: tk.Event | None = None) -> None:
        """Handle directory selection change."""
        self._apply_config_overrides()
        self._configure_row_colors()
        self._refresh_file_list()

    def _on_directory_enter(self, _event: tk.Event | None = None) -> None:
        """Handle Enter key in directory field: start search."""
        self._apply_config_overrides()
        self._configure_row_colors()
        self._refresh_file_list()

    def _on_directory_double_click(self, _event: tk.Event | None = None) -> None:
        """Handle double-click on directory: open in file explorer."""
        label = self._current_dir_label()
        paths = self._resolve_dir_selection(label)
        # Open the first valid path
        for path in paths:
            if directory_exists(path):
                open_file_explorer(path)
                return
        messagebox.showwarning(
            "Directory Not Found",
            f"The selected directory does not exist:\n{label}",
        )

    def _on_browse(self) -> None:
        """Open a directory picker and refresh the file list."""
        directory = filedialog.askdirectory(title="Select Launcher Directory")
        if directory:
            self._dir_var.set(directory)
            self._apply_config_overrides()
            self._configure_row_colors()
            self._refresh_file_list()

    def _on_open_config(self) -> None:
        """Open the configuration file with the default text editor.

        When the expected ``.profiles`` file does not exist, the user
        is informed and offered the choice to generate a documented
        starter file at the resolved config path (typically CWD) and
        open it. Refusal simply closes the dialog without changes.
        """
        config_path = self._config.config_path

        if not config_path.exists():
            cwd_label = str(Path.cwd())
            prompt = (
                f"No configuration file was found at:\n{config_path}\n\n"
                "Would you like to generate a starter .profiles file in the\n"
                f"current working directory ({cwd_label})?\n\n"
                "The starter is fully commented and ready to edit."
            )
            if not messagebox.askyesno(
                "Configuration File Missing",
                prompt,
                default=messagebox.YES,
            ):
                return

            write_result = actions.write_starter_config(
                config_path,
                logger=self._logger,
            )
            if write_result.status is not actions.ActionStatus.SUCCESS:
                messagebox.showerror(
                    self._result_title(write_result),
                    write_result.message,
                )
                return

            messagebox.showinfo(
                "Starter Configuration Created",
                write_result.message,
            )

        result = actions.open_config_file(
            config_path,
            logger=self._logger,
        )
        if result.status is not actions.ActionStatus.SUCCESS:
            messagebox.showerror(self._result_title(result), result.message)

    def _on_open_log(self) -> None:
        """Open the log file with the default text editor.

        The log path is resolved relative to the current working
        directory (wherever ``profiles`` was launched from). If the
        file or its parent directory is missing, it is created on
        demand so the user can always open it.
        """
        result = actions.open_log_file(
            Path.cwd() / "profiles.log",
            logger=self._logger,
        )
        if result.status is not actions.ActionStatus.SUCCESS:
            messagebox.showerror(self._result_title(result), result.message)

    @staticmethod
    def _result_title(result: actions.ActionResult) -> str:
        """Map an ``ActionResult`` to a messagebox title."""
        return {
            actions.ActionStatus.NOT_FOUND: "Not Found",
            actions.ActionStatus.FAILED: "Open Failed",
        }.get(result.status, "Error")

    def _debounced_refresh(self, timer_attr: str, delay_ms: int = 1000) -> None:
        """Schedule a debounced refresh, cancelling any pending one."""
        if (prev := getattr(self, timer_attr)) is not None:
            self._root.after_cancel(prev)
        setattr(self, timer_attr, self._root.after(delay_ms, self._refresh_file_list))

    def _flush_timer(self, timer_attr: str) -> None:
        """Cancel any pending debounced refresh and trigger one immediately."""
        if (prev := getattr(self, timer_attr)) is not None:
            self._root.after_cancel(prev)
            setattr(self, timer_attr, None)
            self._refresh_file_list()

    def _on_extension_or_filter_select(self, _event: tk.Event | None = None) -> None:
        """Handle extension or filter combobox selection - immediate refresh."""
        self._refresh_file_list()

    def _on_refresh(self) -> None:
        """Handle refresh button: reload config and refresh list."""
        try:
            fresh_config = load_config(self._config.config_path)
            self._config = fresh_config
            self._populate_directories()
            self._auto_select_directory()
            self._apply_config_overrides()
            self._configure_row_colors()
            self._logger.info("Configuration reloaded")
        except (FileNotFoundError, OSError) as exc:
            self._logger.error("Failed to reload configuration: %s", exc)
            messagebox.showerror(
                "Configuration Error",
                f"Failed to reload configuration:\n{exc}",
            )
        self._refresh_file_list()

    def _on_execute(self, _event: tk.Event | None = None) -> None:
        """Handle file execution on one or many selected rows.

        With ``selectmode="extended"`` the treeview may carry any number
        of selected iids.  Each selection is launched independently via
        :func:`actions.launch_selected_file`; the first failure surfaces
        as a messagebox while subsequent launches keep going.
        """
        selection = self._tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a file from the list.")
            return

        username = self._user_label.cget("text")
        first_failure: actions.ActionResult | None = None

        for iid in selection:
            file_path = self._tree_to_path.get(iid)
            if file_path is None:
                continue
            result = actions.launch_selected_file(
                directory=str(file_path.parent),
                filename=file_path.name,
                release=self._config.release,
                username=username,
                config=self._config,
                logger=self._logger,
            )
            if result.status is not actions.ActionStatus.SUCCESS and first_failure is None:
                first_failure = result

        if first_failure is not None:
            title = self._result_title(first_failure)
            if first_failure.status is actions.ActionStatus.NOT_FOUND:
                messagebox.showwarning(title, first_failure.message)
            elif (
                first_failure.status is actions.ActionStatus.FAILED
                and "aborted by a launch hook" in first_failure.message
            ):
                messagebox.showerror("Launch Aborted", first_failure.message)
            else:
                messagebox.showerror(title, first_failure.message)

        if self._close_var.get():
            self._root.after(500, self._on_close)

    def _on_key_up(self, _event: tk.Event) -> str | None:
        """Handle up arrow key navigation."""
        selection = self._tree.selection()
        if selection:
            prev = self._tree.prev(selection[0])
            if prev:
                self._tree.selection_set(prev)
                self._tree.focus(prev)
                self._tree.see(prev)
        return "break"

    def _on_key_down(self, _event: tk.Event) -> str | None:
        """Handle down arrow key navigation."""
        selection = self._tree.selection()
        if selection:
            next_item = self._tree.next(selection[0])
            if next_item:
                self._tree.selection_set(next_item)
                self._tree.focus(next_item)
                self._tree.see(next_item)
        return "break"

    # ----------------------------------------------------------------
    # Context menu actions delegation
    # ----------------------------------------------------------------

    def _selected_file_path(self) -> Path | None:
        """Resolve the full filesystem path of the currently selected file."""
        return self._context_menu.selected_file_path()

    def _on_tree_right_click(self, event: tk.Event) -> None:
        """Show the right-click context menu for the row under the cursor."""
        self._context_menu.on_tree_right_click(event)

    def _action_launch(self, file_path: Path) -> None:
        """Launch the given file using the OS default association."""
        self._context_menu.action_launch(file_path)

    def _action_launch_with_args(self, file_path: Path) -> None:
        """Prompt for extra arguments, then launch *file_path* with them."""
        from tkinter import simpledialog

        args = simpledialog.askstring(
            "Launch arguments",
            f"Arguments for {file_path.name}:",
            parent=self._root,
        )
        # Cancel button or empty input → no launch (matches GUI convention).
        if args is None or not args.strip():
            return
        result = actions.launch_selected_file(
            directory=str(file_path.parent),
            filename=file_path.name,
            release=self._config.release,
            username=self._user_label.cget("text"),
            args=args,
            config=self._config,
            logger=self._logger,
        )
        title = self._result_title(result)
        if result.status is not actions.ActionStatus.SUCCESS:
            if result.status is actions.ActionStatus.NOT_FOUND:
                messagebox.showwarning(title, result.message)
            else:
                messagebox.showerror(title, result.message)
        elif self._close_var.get():
            self._root.after(500, self._on_close)

    def _action_open_folder(self, file_path: Path) -> None:
        """Open the directory that contains *file_path*."""
        self._context_menu.action_open_folder(file_path)

    def _action_reveal(self, file_path: Path) -> None:
        """Reveal the file in the OS file explorer."""
        self._context_menu.action_reveal(file_path)

    def _action_copy(self, value: str) -> None:
        """Copy *value* to the system clipboard."""
        self._context_menu.action_copy(value)

    def _action_copy_path(self, file_path: Path, *, forward_slashes: bool = False) -> None:
        """Copy the full file path to the clipboard."""
        self._context_menu.action_copy_path(file_path, forward_slashes=forward_slashes)

    def _action_copy_name(self, file_path: Path, *, with_ext: bool = True) -> None:
        """Copy the file name (with or without extension) to the clipboard."""
        self._context_menu.action_copy_name(file_path, with_ext=with_ext)

    def _action_properties(self, file_path: Path) -> None:
        """Show a properties dialog for the file (size, dates, path)."""
        self._context_menu.action_properties(file_path)

    def _action_filter_to_folder(self, file_path: Path) -> None:
        """Switch the directory combobox to the file's parent folder."""
        self._context_menu.action_filter_to_folder(file_path)

    def _action_hash(self, file_path: Path, algorithm: str, *, copy_only: bool = False) -> None:
        """Compute the file's hash, show a dialog, and optionally copy it."""
        self._context_menu.action_hash(file_path, algorithm, copy_only=copy_only)

    def _action_copy_uri(self, file_path: Path) -> None:
        """Copy a ``file://`` URI to the clipboard for the file."""
        self._context_menu.action_copy_uri(file_path)

    def _action_filter_by_extension(self, file_path: Path) -> None:
        """Set the extension filter to ``.<ext>`` and re-scan the current folder."""
        self._context_menu.action_filter_by_extension(file_path)

    def _action_verify_hash(self, file_path: Path, algorithm: str) -> None:
        """Compute the file's *algorithm* hash and compare it to the clipboard."""
        self._context_menu.action_verify_hash(file_path, algorithm)

    def _action_open_terminal(self, file_path: Path) -> None:
        """Open a terminal session in the file's parent directory."""
        self._context_menu.action_open_terminal(file_path)

    def _on_close(self) -> None:
        """Handle window close event."""
        self._logger.info("ProFiles closed")
        self._root.destroy()

    def _configure_bindings(self) -> None:
        """Configure keyboard shortcuts.

        The ``_SHORTCUTS`` table is the single source of truth: each
        entry is ``(display_label, key_spec, bound_callback)`` and is
        also reused by :meth:`_on_show_shortcuts`.
        """
        for _label, key, callback in self._shortcut_entries():
            self._root.bind(key, lambda e, cb=callback: cb())

    def _shortcut_entries(self) -> list[tuple[str, str, Callable[[], None]]]:
        """Return the ordered list of shortcut definitions.

        Returns:
            List of ``(label, key_spec, callback)`` tuples.
        """
        return [
            ("Refresh file list", "<F5>", self._refresh_file_list),
            ("Reload config + refresh", "<Control-r>", self._on_refresh),
            ("Focus directory field", "<Control-d>", lambda: self._dir_combo.focus_set()),
            ("Focus extension field", "<Control-e>", lambda: self._ext_combo.focus_set()),
            ("Focus filter field", "<Control-f>", lambda: self._filter_combo.focus_set()),
            ("Focus file list", "<Control-l>", lambda: self._tree.focus_set()),
            ("Execute selected file", "<Return>", lambda: self._on_execute()),
            (
                "Clear filter text",
                "<Delete>",
                lambda: (self._filter_var.set(""), self._refresh_file_list()),
            ),
            ("Open log file", "<Control-Shift-L>", self._on_open_log),
            ("Open config file", "<Control-comma>", self._on_open_config),
            ("Cycle theme", "<Control-Shift-T>", self._on_toggle_theme),
            ("Show shortcuts", "<Control-question>", self._on_show_shortcuts),
            ("Quit application", "<Control-q>", self._on_close),
            ("Close window", "<Escape>", self._on_close),
        ]

    def _on_show_shortcuts(self) -> None:
        """Open a modal dialog listing all keyboard shortcuts and mouse actions."""
        dlg = tk.Toplevel(self._root)
        dlg.title("Keyboard Shortcuts")
        dlg.transient(self._root)
        dlg.resizable(False, False)

        # Close on Escape *inside* the dialog before it reaches the root
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.focus_set()
        dlg.grab_set()

        header = ttk.Label(dlg, text="Keyboard Shortcuts", style="Title.TLabel")
        header.pack(pady=(12, 6))

        body = ttk.Frame(dlg, padding=(16, 0, 16, 12))
        body.pack(fill="both", expand=True)

        keyboard = self._shortcut_entries()
        for i, (label, key, _cb) in enumerate(keyboard):
            ttk.Label(body, text=key, style="Value.TLabel").grid(
                row=i,
                column=0,
                sticky="w",
                padx=(0, 16),
                pady=2,
            )
            ttk.Label(body, text=label).grid(row=i, column=1, sticky="w", pady=2)

        # ── Mouse Actions section ───────────────────────────────────────
        sep_row = len(keyboard)
        ttk.Separator(body, orient="horizontal").grid(
            row=sep_row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 8),
        )
        mouse_header_row = sep_row + 1
        ttk.Label(body, text="Mouse Actions", style="Header.TLabel").grid(
            row=mouse_header_row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(4, 4),
        )

        mouse = self._mouse_entries()
        for offset, (label, action) in enumerate(mouse):
            row = mouse_header_row + 1 + offset
            ttk.Label(body, text=label, style="Value.TLabel").grid(
                row=row,
                column=0,
                sticky="w",
                padx=(0, 16),
                pady=2,
            )
            ttk.Label(body, text=action).grid(row=row, column=1, sticky="w", pady=2)

        close_btn = ttk.Button(dlg, text="Close", command=dlg.destroy)
        close_btn.pack(pady=(0, 12))

    def _mouse_entries(self) -> list[tuple[str, str]]:
        """Return the ordered list of mouse-action documentation tuples.

        Each entry is ``(label, action)`` where ``label`` describes the
        gesture and ``action`` describes its effect. This is rendered by
        :meth:`_on_show_shortcuts` under a "Mouse Actions" header.
        """
        return [
            ("Double-click row", "Launch selected file"),
            ("Right-click row", "Open context menu"),
            ("Ctrl+Click row (macOS)", "Open context menu"),
            ("Double-click directory field", "Open in file explorer"),
            ("Shift+MouseWheel", "Horizontal scroll"),
            ("Page Up / Page Down", "Jump by visible page"),
            ("Home / End", "Jump to first / last row"),
        ]

    def _on_header_double_click(self, event: tk.Event) -> str | None:
        """Auto-fit column width to content on double-click of separator or heading."""
        region = self._tree.identify_region(event.x, event.y)
        if region in ("separator", "heading"):
            col_id = self._tree.identify_column(event.x)
            if not col_id:
                return None

            import tkinter.font as tkfont

            from profiles.gui.theme import FONT_FAMILY, FONT_SIZE_NORMAL

            font = tkfont.Font(font=(FONT_FAMILY, FONT_SIZE_NORMAL))
            heading_font = tkfont.Font(font=(FONT_FAMILY, FONT_SIZE_NORMAL, "bold"))

            try:
                col_idx = int(col_id.replace("#", "")) - 1
            except ValueError:
                return None

            heading_text = self._tree.heading(col_id, "text")
            max_w = heading_font.measure(heading_text) + 30

            # Optimisation: Sample up to a maximum of 200 items for auto-fit measurement
            # to prevent UI freeze on large directory trees (O(1) instead of O(N))
            children = self._tree.get_children()
            sample_size = min(len(children), 200)
            items_to_measure = children[:sample_size]

            for item in items_to_measure:
                val = str(self._tree.set(item, col_idx))
                w = font.measure(val) + 20
                if w > max_w:
                    max_w = w

            new_width = max(60, min(1000, max_w))
            self._tree.column(col_id, width=new_width)
            return "break"
        return None

    def _update_empty_state(self, show: bool) -> None:
        """Update empty state placeholder overlay.

        ponytail: when ``img/ProFiles_banner.png`` is missing we fall back
        to the original single-label layout — behaviour is identical to
        before. Upgrade path: ship a proper icon asset and design pass
        for the empty state.
        """
        if not hasattr(self, "_empty_label"):
            banner_path = Path.cwd() / "img" / "ProFiles_banner.png"
            if banner_path.is_file():
                # Bind the image to THIS window's interpreter — tk.PhotoImage
                # defaults to the process-global default root, which breaks
                # multi-window sessions (each Tk() owns a private interpreter).
                self._empty_photo = tk.PhotoImage(master=self._root, file=str(banner_path))
                self._empty_photo = self._empty_photo.subsample(3, 5)

                self._empty_label = tk.Frame(self._list_container)
                img_label = tk.Label(self._empty_label, image=self._empty_photo, borderwidth=0)
                img_label.pack(pady=(0, 12))
                ttk.Label(
                    self._empty_label,
                    text="📂 No matching files",
                    style="EmptyState.TLabel",
                    padding=(0, 4),
                ).pack()
                ttk.Button(
                    self._empty_label,
                    text="Reset filters",
                    command=self._reset_filters,
                    style="Link.TButton",
                ).pack(pady=(8, 0))
            else:
                self._empty_label = ttk.Label(
                    self._list_container,
                    text="📂  No matching files found\nTry adjusting your search filters or directory",
                    style="EmptyState.TLabel",
                    padding=20,
                )

        if show:
            self._empty_label.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
            self._empty_label.tkraise()
        else:
            self._empty_label.grid_forget()

    def _reset_filters(self) -> None:
        """Reset extension and filter comboboxes to their first value, then refresh."""
        ext_values = self._ext_combo["values"]
        self._ext_var.set(ext_values[0] if ext_values else "")
        filter_values = self._filter_combo["values"]
        self._filter_var.set(filter_values[0] if filter_values else "")
        self._refresh_file_list()

    def _show_progress(self) -> None:
        """Show the indeterminate progressbar and start its animation.

        Guarded by ``_scan_in_progress`` so a deferred ``after`` callback
        cannot start animating a scan that already finished (which would
        leave a recurring Tcl timer running forever).
        """
        progress_bar = getattr(self, "_progress_bar", None)
        if progress_bar is None:
            return
        if not self._scan_in_progress:
            return
        progress_bar.pack(side=tk.LEFT, padx=(0, 12))
        progress_bar.start(10)

    def _hide_progress(self) -> None:
        """Stop the progressbar animation and hide it."""
        self._scan_in_progress = False
        progress_bar = getattr(self, "_progress_bar", None)
        if progress_bar is None:
            return
        with contextlib.suppress(tk.TclError):
            progress_bar.stop()
        with contextlib.suppress(tk.TclError):
            progress_bar.pack_forget()

    def _flash_count_label(self) -> None:
        """Briefly flash count label with success styling on scan completion."""
        self._count_label.config(style="Status.Success.TLabel")
        self._root.after(600, lambda: self._count_label.config(style="Info.TLabel"))

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    @property
    def root(self) -> tk.Tk:
        """Get the root Tk window."""
        return self._root

    def _check_config_file(self) -> None:
        """Check if a .profiles config file exists, propose creation if not."""
        if not self._config.config_path.exists() and messagebox.askyesno(
            "Configuration File Not Found",
            "No .profiles configuration file was found in the current directory "
            "or its subdirectories (search limited to 5 levels).\n\n"
            "Would you like to create a default configuration file now?\n\n"
            "You can customize it later by clicking the 'Config' button.",
            parent=self._root,
        ):
            self._create_config_file()

    def _create_config_file(self) -> None:
        """Create a default .profiles configuration file."""
        from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME
        from profiles.core.config.template import STARTER_CONFIG_TEMPLATE

        target = Path.cwd() / PRIMARY_CONFIG_NAME

        if target.exists():
            messagebox.showinfo(
                "Configuration File",
                f"A .profiles file already exists at:\n{target}\n\nNo action needed.",
                parent=self._root,
            )
            return

        try:
            body = STARTER_CONFIG_TEMPLATE.format(cwd=str(Path.cwd()))
            target.write_text(body, encoding="utf-8")

            self._logger.info("Configuration file created: %s", target)

            # Ask user if they want to restart to apply the new configuration
            if messagebox.askyesno(
                "Restart Required",
                "Configuration file created successfully!\n\n"
                "To apply the new configuration (including column definitions), "
                "the application must be restarted.\n\n"
                "Would you like to restart now?",
                parent=self._root,
            ):
                self._restart_application()
            else:
                messagebox.showinfo(
                    "Configuration File Created",
                    f"Default configuration file created at:\n{target}\n\n"
                    "The application will continue with the current settings.\n"
                    "Restart the application to load the new configuration.",
                    parent=self._root,
                )

        except OSError as exc:
            messagebox.showerror(
                "Error Creating Configuration",
                f"Failed to create configuration file:\n{exc}",
                parent=self._root,
            )
            self._logger.error("Failed to create config file: %s", exc)

    def _restart_application(self) -> None:
        """Restart the application using the module entry point."""

        self._logger.info("Restarting application...")

        # Destroy the current window
        self._root.destroy()

        # Get the current Python executable
        python_executable = sys.executable

        # Launch a new instance via module entry point
        try:
            subprocess.Popen([str(python_executable), "-m", "profiles"])
            self._logger.info(
                "New instance launched via module: %s -m profiles",
                python_executable,
            )
        except OSError as exc:
            self._logger.error("Failed to restart application: %s", exc)
            # Show error but don't block - user can manually restart
            messagebox.showerror(
                "Restart Failed",
                f"Could not automatically restart the application.\n\n"
                f"Error: {exc}\n\n"
                f"Please restart manually by running ProFiles again.",
                parent=self._root,
            )

    def run(self) -> None:
        """Start the application main loop."""
        self._logger.info("ProFiles started")
        self._root.mainloop()
