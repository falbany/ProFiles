"""Qt main window with decomposed widgets and signal wiring."""

from __future__ import annotations

import logging
from typing import Any

try:
    from typing import override
except ImportError:
    from typing_extensions import override

from PySide6.QtCore import Qt, QTimer, QEvent, Signal, QCoreApplication
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

# Sort indicator arrows (matching Tkinter behavior)
_SORT_ASC = " \u25b2"  # Up arrow ▲
_SORT_DESC = " \u25bc"  # Down arrow ▼

from profiles.core.actions import ActionStatus
from profiles.core.actions import launch_selected_file as actions_launch_file
from profiles.core.config.models import AppConfig
from profiles.core.processing.scanner import ScannedFileDynamic
from profiles.gui.qt.controllers.chunked_file_list_controller import (
    ChunkedFileListController,
)
from profiles.gui.qt.controllers.scan_controller import ScanController
from profiles.gui.qt.ui import create_horizontal_layout, create_vertical_layout
from profiles.gui.theme import DARK_THEME, LIGHT_THEME, THEME_LABELS, to_qss_tokens, resolve_theme_name_qt

# ── Sub-widgets ──────────────────────────────────────────────────


class HeaderWidget(QWidget):
    """Application header with title and author label."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = create_vertical_layout(self, spacing=4, margin=12)

        self._title_label = QLabel("ProFiles")
        self._title_label.setStyleSheet("font-size: 18px; font-weight: bold;")

        self._author_label = QLabel("by F. Albany")
        self._author_label.setStyleSheet("font-size: 12px; color: #666;")

        layout.addWidget(self._title_label)
        layout.addWidget(self._author_label)
        layout.addStretch()

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    @property
    def author_label(self) -> QLabel:
        return self._author_label


class DirectoryBar(QWidget):
    """Directory, extension, and filter comboboxes."""

    directory_changed = Signal(str)
    extension_changed = Signal(str)
    filter_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._install_focus_ring()

    def _install_focus_ring(self) -> None:
        """Install event filter on comboboxes for focus ring styling."""
        for combo in (self._dir_combo, self._ext_combo, self._filter_combo):
            combo.installEventFilter(self)

    def _setup_ui(self) -> None:
        layout = create_vertical_layout(self, spacing=6, margin=8)

        # Directory combobox
        dir_layout = create_horizontal_layout(spacing=6, margin=0)
        dir_label = QLabel("Directory:")
        self._dir_combo = QComboBox()
        self._dir_combo.setMinimumHeight(28)
        self._dir_combo.currentTextChanged.connect(self._on_dir_changed)
        
        # Browse button
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._on_browse_directory)
        
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self._dir_combo, 1)
        dir_layout.addWidget(browse_btn)
        
        layout.addLayout(dir_layout)

        # Extension combobox
        ext_layout = create_horizontal_layout(spacing=6, margin=0)
        ext_label = QLabel("Extension:")
        self._ext_combo = QComboBox()
        self._ext_combo.setMinimumHeight(28)
        self._ext_combo.currentTextChanged.connect(self._on_ext_changed)
        ext_layout.addWidget(ext_label)
        ext_layout.addWidget(self._ext_combo, 1)
        layout.addLayout(ext_layout)

        # Filter combobox
        filter_layout = create_horizontal_layout(spacing=6, margin=0)
        filter_label = QLabel("Filter:")
        self._filter_combo = QComboBox()
        self._filter_combo.setMinimumHeight(28)
        self._filter_combo.setEditable(True)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self._filter_combo, 1)
        layout.addLayout(filter_layout)

    def _on_dir_changed(self, text: str) -> None:
        self.directory_changed.emit(text)

    def _on_browse_directory(self) -> None:
        """Open directory picker dialog and update combobox."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Launcher Directory", ""
        )
        if directory:
            self.set_dir_text(directory)
            self.directory_changed.emit(directory)

    def _on_ext_changed(self, text: str) -> None:
        self.extension_changed.emit(text)

    def _on_filter_changed(self, text: str) -> None:
        self.filter_changed.emit(text)

    @property
    def dir_combo(self) -> QComboBox:
        return self._dir_combo

    @property
    def ext_combo(self) -> QComboBox:
        return self._ext_combo

    @property
    def filter_combo(self) -> QComboBox:
        return self._filter_combo

    @property
    def dir_text(self) -> str:
        return self._dir_combo.currentText()

    @property
    def ext_text(self) -> str:
        return self._ext_combo.currentText()

    @property
    def filter_text(self) -> str:
        return self._filter_combo.currentText()

    def set_dir_text(self, text: str) -> None:
        """Set directory text, adding item if not present."""
        idx = self._dir_combo.findText(text)
        if idx < 0:
            self._dir_combo.addItem(text)
            idx = self._dir_combo.count() - 1
        self._dir_combo.setCurrentIndex(idx)

    def set_ext_text(self, text: str) -> None:
        """Set extension text, adding item if not present."""
        idx = self._ext_combo.findText(text)
        if idx < 0:
            self._ext_combo.addItem(text)
            idx = self._ext_combo.count() - 1
        self._ext_combo.setCurrentIndex(idx)

    def set_filter_text(self, text: str) -> None:
        """Set filter text, adding item if not present."""
        idx = self._filter_combo.findText(text)
        if idx < 0:
            self._filter_combo.addItem(text)
            idx = self._filter_combo.count() - 1
        self._filter_combo.setCurrentIndex(idx)

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        """Event filter for focus ring styling on comboboxes."""
        if event.type() == QEvent.FocusIn:
            if isinstance(obj, QComboBox):
                obj.setStyleSheet(
                    "QComboBox {"
                    "    border: 2px solid #005fb8;"
                    "    border-radius: 4px;"
                    "    padding: 4px 8px;"
                    "}"
                )
        elif event.type() == QEvent.FocusOut:
            if isinstance(obj, QComboBox):
                obj.setStyleSheet(
                    "QComboBox {"
                    "    border: 1px solid #888;"
                    "    border-radius: 4px;"
                    "    padding: 4px 8px;"
                    "}"
                )
        return super().eventFilter(obj, event)


class ActionBar(QWidget):
    """Recursive checkbox and scan/execute buttons with progress indicator."""

    scan_requested = Signal()
    execute_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._scan_timer: QTimer | None = None

    def _setup_ui(self) -> None:
        layout = create_horizontal_layout(self, spacing=12, margin=8)

        self._recursive_check = QCheckBox("Recursive")
        self._recursive_check.setChecked(True)

        self._scan_button = QPushButton("Scan")
        self._scan_button.setMinimumHeight(28)
        self._scan_button.clicked.connect(self.scan_requested.emit)

        self._execute_button = QPushButton("Execute")
        self._execute_button.setMinimumHeight(28)
        self._execute_button.clicked.connect(self.execute_requested.emit)

        # Progress bar (indeterminate, hidden by default)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimumHeight(28)
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 0)  # Indeterminate mode

        layout.addWidget(self._recursive_check)
        layout.addStretch()
        layout.addWidget(self._scan_button)
        layout.addWidget(self._execute_button)
        layout.addWidget(self._progress_bar)

    @property
    def recursive_check(self) -> QCheckBox:
        return self._recursive_check

    @property
    def scan_button(self) -> QPushButton:
        return self._scan_button

    @property
    def execute_button(self) -> QPushButton:
        return self._execute_button

    @property
    def progress_bar(self) -> QProgressBar:
        return self._progress_bar

    def set_scanning(self, scanning: bool) -> None:
        self._scan_button.setEnabled(not scanning)
        self._execute_button.setEnabled(not scanning)
        if scanning:
            # Start progress bar after 200ms delay to avoid flicker on quick scans
            self._scan_timer = QTimer()
            self._scan_timer.setSingleShot(True)
            self._scan_timer.timeout.connect(self._start_progress)
            self._scan_timer.start(200)
        else:
            # Stop progress bar
            if self._scan_timer:
                self._scan_timer.stop()
                self._scan_timer = None
            self._progress_bar.setVisible(False)

    def _start_progress(self) -> None:
        """Start the indeterminate progress bar."""
        self._progress_bar.setVisible(True)


class FileTree(QWidget):
    """QTableWidget with dynamic columns from AppConfig."""

    selection_changed = Signal(list)
    reset_filters_requested = Signal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._empty_state_widget: QWidget | None = None
        self._sort_column: int = -1
        self._sort_direction: str = "asc"
        self._setup_ui()

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        """Event filter for header double-click auto-fit."""
        if event.type() == QEvent.Type.MouseButtonDblClick:
            header = self._table_widget.horizontalHeader()
            if obj == header:
                # Get the column under the cursor
                pos = event.position()
                logical_index = header.logicalIndexAt(int(pos.x()))
                if logical_index >= 0:
                    # Auto-fit the clicked column
                    header.resizeSectionToContents(logical_index)
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        """Handle keyboard navigation: PageUp, PageDown, Home, End."""
        table = self._table_widget
        row_count = table.rowCount()
        
        if row_count == 0:
            super().keyPressEvent(event)
            return
            
        current_row = table.currentRow()
        
        if event.key() == 16777234:  # PageUp
            visible_rows = table.viewport().height() // table.rowHeight(0) if row_count > 0 else 10
            new_row = max(0, current_row - visible_rows)
            table.setCurrentCell(new_row, 0)
        elif event.key() == 16777235:  # PageDown
            visible_rows = table.viewport().height() // table.rowHeight(0) if row_count > 0 else 10
            new_row = min(row_count - 1, current_row + visible_rows)
            table.setCurrentCell(new_row, 0)
        elif event.key() == 16777232:  # Home
            table.setCurrentCell(0, 0)
        elif event.key() == 16777233:  # End
            table.setCurrentCell(row_count - 1, 0)
        else:
            super().keyPressEvent(event)

    def _setup_ui(self) -> None:
        layout = create_vertical_layout(self, spacing=0, margin=0)

        self._table_widget = QTableWidget()
        self._table_widget.setAlternatingRowColors(True)
        self._table_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table_widget.doubleClicked.connect(self._on_double_click)

        # Install event filter on header for double-click auto-fit
        header = self._table_widget.horizontalHeader()
        header.setSectionsMovable(True)
        header.installEventFilter(self)
        
        # Connect sort signal for click handling
        header.sectionClicked.connect(self._on_header_clicked)

        # Build columns dynamically from config
        self._setup_columns()

        # Empty state overlay widget (initially hidden)
        self._empty_state_widget = self._create_empty_state_widget()
        self._empty_state_widget.setVisible(False)

        layout.addWidget(self._table_widget)
        layout.addWidget(self._empty_state_widget)

    def _setup_columns(self) -> None:
        """Configure table columns from AppConfig."""
        column_names = self._config.column_names or ("File",)
        column_headers = self._config.column_headers or column_names
        column_widths = self._config.column_widths or (200,) * len(column_names)
        column_stretches = self._config.column_stretches or (False,) * len(column_names)

        # Ensure all tuples have matching lengths
        num_columns = len(column_names)
        if len(column_headers) != num_columns:
            column_headers = column_names
        if len(column_widths) != num_columns:
            column_widths = (200,) * num_columns
        if len(column_stretches) != num_columns:
            column_stretches = (False,) * num_columns

        # Set column count and headers
        self._table_widget.setColumnCount(num_columns)
        for i, header in enumerate(column_headers):
            self._table_widget.setHorizontalHeaderItem(i, QTableWidgetItem(header))

        # Configure column widths and stretches
        header = self._table_widget.horizontalHeader()
        for i, (width, stretch) in enumerate(zip(column_widths, column_stretches, strict=False)):
            if stretch:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                self._table_widget.setColumnWidth(i, width)
    
    def _on_header_clicked(self, logical_index: int) -> None:
        """Handle header click for sorting (matching Tkinter behavior)."""
        self._sort_by_column(logical_index)
    
    def _sort_by_column(self, col_index: int) -> None:
        """Sort the table rows by column index, toggling direction.
        
        Matches Tkinter _sort_treeview behavior:
        - First click: ascending (▲)
        - Second click on same column: descending (▼)
        - Click on different column: reset to ascending
        """
        table = self._table_widget
        row_count = table.rowCount()
        if row_count == 0:
            return
        
        # Determine sort direction
        if col_index == self._sort_column:
            # Toggle direction on same column
            self._sort_direction = "desc" if self._sort_direction == "asc" else "asc"
        else:
            # New column, start with ascending
            self._sort_column = col_index
            self._sort_direction = "asc"
        
        reverse = self._sort_direction == "desc"
        
        # Collect all rows with sort values
        items_data = []
        for row in range(row_count):
            item = table.item(row, col_index)
            val = item.text() if item else ""
            sort_val = val.lower()
            items_data.append((sort_val, row))
        
        # Sort the data
        items_data.sort(key=lambda x: x[0], reverse=reverse)
        
        # Reorder rows using takeItem/setItem to preserve data
        # Store all row data first
        row_data = []
        for row in range(row_count):
            row_items = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                row_items.append(item.text() if item else "")
            row_data.append(row_items)
        
        # Clear table and repopulate in sorted order
        table.setRowCount(0)
        table.setRowCount(row_count)
        
        for new_row, (_, old_row) in enumerate(items_data):
            for col in range(table.columnCount()):
                text = row_data[old_row][col]
                if text:
                    item = QTableWidgetItem(text)
                    table.setItem(new_row, col, item)
        
        # Update header indicators
        self._update_sort_indicators()
    
    def _update_sort_indicators(self) -> None:
        """Update column header text with sort arrows (matching Tkinter)."""
        column_names = self._config.column_names or ("File",)
        column_headers = self._config.column_headers or column_names
        
        for i, base_header in enumerate(column_headers):
            # Remove any existing arrow
            clean_header = base_header.rstrip(" ▲▼\u25b2\u25bc")
            
            # Add arrow for sorted column
            if i == self._sort_column:
                arrow = _SORT_ASC if self._sort_direction == "asc" else _SORT_DESC
                final_header = clean_header + arrow
            else:
                final_header = clean_header
            
            # Update header item
            item = QTableWidgetItem(final_header)
            self._table_widget.setHorizontalHeaderItem(i, item)
    
    def clear_sort_state(self) -> None:
        """Reset sort state when data is repopulated."""
        self._sort_column = -1
        self._sort_direction = "asc"
        # Clear arrows from all headers
        column_names = self._config.column_names or ("File",)
        column_headers = self._config.column_headers or column_names
        for i, header in enumerate(column_headers):
            clean_header = header.rstrip(" ▲▼\u25b2\u25bc")
            item = QTableWidgetItem(clean_header)
            self._table_widget.setHorizontalHeaderItem(i, item)
    
    def _create_empty_state_widget(self) -> QWidget:
        """Create the empty state overlay widget with banner and reset button."""
        container = QWidget()
        container.setStyleSheet(
            "QWidget {"
            "    background-color: transparent;"
            "}"
        )
        
        layout = create_vertical_layout(container, spacing=12, margin=0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Banner label
        banner_label = QLabel("📂 No matching files")
        banner_label.setStyleSheet(
            "font-size: 16px;"
            "font-weight: bold;"
            "color: #999;"
            "padding: 20px;"
        )
        banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(banner_label)
        
        # Reset filters button
        reset_button = QPushButton("Reset filters")
        reset_button.setStyleSheet(
            "QPushButton {"
            "    background-color: #1976D2;"
            "    color: white;"
            "    border: none;"
            "    padding: 8px 16px;"
            "    border-radius: 4px;"
            "    font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #1565C0;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #0D47A1;"
            "}"
        )
        reset_button.clicked.connect(lambda: self.reset_filters_requested.emit())
        layout.addWidget(reset_button)
        
        layout.addStretch()
        
        return container

    def _update_empty_state(self, show: bool) -> None:
        """Show or hide the empty state overlay."""
        if self._empty_state_widget:
            self._empty_state_widget.setVisible(show)
            self._table_widget.setVisible(not show)

    def _on_double_click(self, index: Any) -> None:
        self.selection_changed.emit([index])

    @property
    def table_widget(self) -> QTableWidget:
        return self._table_widget

    def set_model(self, model: Any) -> None:
        """Placeholder for compatibility - not used with QTableWidget."""
        pass

    def set_row_colors(self, rules: Any, theme: Any = None) -> None:
        """Configure row colour rules using row_colors module.
        
        Args:
            rules: RowColorRules instance or raw list of (pattern, color) tuples.
            theme: Md3Theme instance for WCAG contrast fallback (optional).
        """
        from profiles.gui.presentation.row_colors import RowColorRules

        if isinstance(rules, RowColorRules):
            self._row_rules = rules
        else:
            self._row_rules = rules
        self._theme = theme
        self._apply_row_colors()

    def _apply_row_colors(self) -> None:
        """Apply row colors to all existing rows using theme-aware colors with WCAG fallback."""
        if not hasattr(self, '_row_rules') or self._row_rules is None:
            return
        if self._theme is None:
            return
            
        from profiles.gui.theme import contrast_ratio
        
        table = self._table_widget
        row_count = table.rowCount()
        
        # Get row color rules - they should be (pattern, color) tuples
        rules = self._row_rules
        if hasattr(rules, '_compiled'):
            # RowColorRules instance - use its compiled rules
            compiled_rules = rules._compiled
        else:
            # Raw list of (pattern, color) tuples
            compiled_rules = [(p.lower(), c) for p, c in rules if p and c]
        
        for row_idx in range(row_count):
            # Get filename from first column
            first_item = table.item(row_idx, 0)
            if not first_item:
                continue
            filename = first_item.text()
            
            # Find matching rule (first match wins)
            matched_color = None
            for pattern_lower, color in compiled_rules:
                if pattern_lower in filename.lower():
                    matched_color = color
                    break
            
            if matched_color is None:
                # No match - use default text color
                continue
                
            # WCAG contrast check: if color has poor contrast against surface, use on_surface
            bg_color = self._theme.surface
            if contrast_ratio(matched_color, bg_color) < 4.5:
                # Use theme's on_surface color for readability
                apply_color = self._theme.on_surface
            else:
                apply_color = matched_color
            
            # Apply color to all items in this row
            col_count = table.columnCount()
            for col_idx in range(col_count):
                item = table.item(row_idx, col_idx)
                if item:
                    from PySide6.QtGui import QColor
                    color = QColor(apply_color)
                    item.setForeground(color)

    def populate(self, items: list) -> None:
        """Populate the table with scanned file items.

        Args:
            items: List of ScannedFileDynamic objects with column_values.
        """
        # Clear existing rows
        self._table_widget.setRowCount(0)

        if not items:
            self._update_empty_state(True)
            return

        self._update_empty_state(False)

        # Get column names from config
        column_names = self._config.column_names or ("File",)

        # Set row count
        self._table_widget.setRowCount(len(items))

        # Populate rows
        for row_idx, scanned_file in enumerate(items):
            for col_idx, col_name in enumerate(column_names):
                value = scanned_file.column_values.get(col_name, "")
                item = QTableWidgetItem(str(value) if value else "")
                self._table_widget.setItem(row_idx, col_idx, item)


class StatusBar(QStatusBar):
    """Status bar with config/log/shortcuts/theme links."""

    config_clicked = Signal()
    log_clicked = Signal()
    shortcuts_clicked = Signal()
    theme_toggled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self._message_label = QLabel("Ready")
        self.addWidget(self._message_label, 1)

        # Action links
        self._config_link = QLabel("<a href='#'>Config</a>")
        self._config_link.mousePressEvent = lambda e: self.config_clicked.emit()

        self._log_link = QLabel("<a href='#'>Log</a>")
        self._log_link.mousePressEvent = lambda e: self.log_clicked.emit()

        self._shortcuts_link = QLabel("<a href='#'>Shortcuts</a>")
        self._shortcuts_link.mousePressEvent = lambda e: self.shortcuts_clicked.emit()

        self._theme_link = QLabel("<a href='#'>Theme</a>")
        self._theme_link.mousePressEvent = lambda e: self.theme_toggled.emit()

        links_layout = create_horizontal_layout(spacing=12, margin=0)
        links_widget = QWidget()
        links_widget.setLayout(links_layout)
        links_layout.addWidget(self._config_link)
        links_layout.addWidget(self._log_link)
        links_layout.addWidget(self._shortcuts_link)
        links_layout.addWidget(self._theme_link)
        links_layout.setContentsMargins(10, 0, 10, 0)

        self.addPermanentWidget(links_widget)

    def set_message(self, message: str) -> None:
        self._message_label.setText(message)

    def set_scanning(self, scanning: bool) -> None:
        if scanning:
            self._message_label.setText("Scanning...")
        else:
            self._message_label.setText("Ready")


class ContextMenu:
    """Right-click context menu for the file table."""

    def __init__(self, table_widget: QTableWidget, logger: logging.Logger) -> None:
        self._table_widget = table_widget
        self._logger = logger
        self._menu = QMenu()
        self._setup_menu()

    def _setup_menu(self) -> None:
        self._copy_path_action = self._menu.addAction("Copy Path")
        self._copy_name_action = self._menu.addAction("Copy Name")
        self._menu.addSeparator()
        self._open_action = self._menu.addAction("Open")
        self._menu.addSeparator()
        self._refresh_action = self._menu.addAction("Refresh")

    def show_event(self, event: Any) -> None:
        """Show context menu at event position."""
        index = self._table_widget.indexAt(event.pos())
        if index.isValid():
            self._menu.exec(event.globalPos())

    @property
    def copy_path_action(self) -> Any:
        return self._copy_path_action

    @property
    def copy_name_action(self) -> Any:
        return self._copy_name_action

    @property
    def open_action(self) -> Any:
        return self._open_action

    @property
    def refresh_action(self) -> Any:
        return self._refresh_action


# ── Main Window ──────────────────────────────────────────────────


class MainWindow(QMainWindow):
    """Main window orchestrator with full signal wiring."""

    def __init__(self, config: AppConfig, logger: logging.Logger) -> None:
        super().__init__()
        self._config = config
        self._logger = logger
        self._context_menu: ContextMenu | None = None
        self._shortcuts_setup: bool = False
        self._theme_name: str = config.theme if hasattr(config, 'theme') else "light"
        self._setup_ui()
        self._setup_controller()
        self._apply_theme(self._theme_name)

    @override
    def showEvent(self, event) -> None:
        """Override showEvent to defer shortcut creation until window is shown."""
        super().showEvent(event)
        if not self._shortcuts_setup:
            self._setup_shortcuts()
            self._shortcuts_setup = True

    def _setup_ui(self) -> None:
        self.setWindowTitle("ProFiles")
        self.resize(1024, 768)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = create_vertical_layout(central_widget, spacing=0, margin=0)

        # Header
        self._header = HeaderWidget()
        main_layout.addWidget(self._header)

        # Directory bar
        self._directory_bar = DirectoryBar()
        main_layout.addWidget(self._directory_bar)

        # Action bar
        self._action_bar = ActionBar()
        main_layout.addWidget(self._action_bar)

        # Wire up action bar signals
        self._action_bar.scan_button.clicked.connect(self._on_scan_clicked)
        self._action_bar.execute_button.clicked.connect(self._on_execute_clicked)

        # File tree
        self._file_tree = FileTree(self._config)
        main_layout.addWidget(self._file_tree, 1)
        
        # Wire up empty state reset signal
        self._file_tree.reset_filters_requested.connect(self._on_reset_filters_requested)

        # Status bar
        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)
        
        # Wire up status bar theme toggle signal
        self._status_bar.theme_toggled.connect(self._on_toggle_theme)
        
        # Wire up directory bar signals for row color re-application
        self._directory_bar.directory_changed.connect(self._on_directory_changed)

        # Context menu
        self._context_menu = ContextMenu(self._file_tree.table_widget, self._logger)
        self._file_tree.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_tree.table_widget.customContextMenuRequested.connect(
            lambda pos: self._context_menu.show_event(
                type("Event", (), {"pos": pos, "globalPos": lambda: self.mapToGlobal(pos)})()
            )
        )

    def _setup_shortcuts(self) -> None:
        """Set up all keyboard shortcuts to match Tkinter behavior.

        Shortcuts are created only when QApplication is available (deferred until
        showEvent to avoid access violations on Windows).
        """
        try:
            from PySide6.QtWidgets import QApplication

            if QApplication.instance() is None:
                return

            # F5 - Scan/Refresh
            f5 = QShortcut(QKeySequence("F5"), self)
            f5.activated.connect(self._on_scan_requested)

            # Ctrl+D - Execute (matches Tkinter's Ctrl+D for execute)
            ctrl_d = QShortcut(QKeySequence("Ctrl+D"), self)
            ctrl_d.activated.connect(self._on_execute_shortcut)

            # Ctrl+E - Filter extension (focus ext field)
            ctrl_e = QShortcut(QKeySequence("Ctrl+E"), self)
            ctrl_e.activated.connect(self._focus_extension)

            # Ctrl+L - Filter folder (focus file tree/list)
            ctrl_l = QShortcut(QKeySequence("Ctrl+L"), self)
            ctrl_l.activated.connect(self._focus_file_tree)

            # Return - Execute selected file
            return_key = QShortcut(QKeySequence("Return"), self)
            return_key.activated.connect(self._on_execute_shortcut)

            # Delete - Clear filter text
            delete_key = QShortcut(QKeySequence("Delete"), self)
            delete_key.activated.connect(self._clear_filter)

            # Ctrl+Shift+L - Launch with args (open log in Tkinter, but we use for launch with args)
            ctrl_shift_l = QShortcut(QKeySequence("Ctrl+Shift+L"), self)
            ctrl_shift_l.activated.connect(self._launch_with_args)

            # Ctrl+Comma - Preferences (open config file)
            ctrl_comma = QShortcut(QKeySequence("Ctrl+,"), self)
            ctrl_comma.activated.connect(self._open_preferences)

            # Ctrl+Shift+T - Terminal (cycle theme in Tkinter)
            ctrl_shift_t = QShortcut(QKeySequence("Ctrl+Shift+T"), self)
            ctrl_shift_t.activated.connect(self._on_toggle_theme)

            # Ctrl+? - Help (show shortcuts dialog)
            ctrl_question = QShortcut(QKeySequence("Ctrl+/"), self)
            ctrl_question.activated.connect(self._show_shortcuts_help)

            # Ctrl+Q - Quit
            ctrl_q = QShortcut(QKeySequence("Ctrl+Q"), self)
            ctrl_q.activated.connect(self.close)

            # Escape - Clear filter (same as Delete)
            escape_key = QShortcut(QKeySequence("Escape"), self)
            escape_key.activated.connect(self._clear_filter)

            # Ctrl+F - Focus filter (already existed, keeping for compatibility)
            ctrl_f = QShortcut(QKeySequence("Ctrl+F"), self)
            ctrl_f.activated.connect(self._focus_filter)

            # Ctrl+R - Scan/Refresh (already existed, keeping for compatibility)
            ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
            ctrl_r.activated.connect(self._on_scan_requested)

        except Exception:
            # QShortcut requires a valid QWidget parent with QApplication
            # Skip shortcuts if QApplication not available (e.g., in tests)
            pass

    def _setup_controller(self) -> None:
        self._controller = ScanController(self._config, self._logger)
        self._chunked_controller = ChunkedFileListController()
        self._scan_items: list[ScannedFileDynamic] = []
        self._row_rules = None

    def _on_directory_changed(self, directory: str) -> None:
        """Handle directory change: re-apply row colors based on new config."""
        # Re-configure row colors for the new directory/config
        self._configure_row_colors()
        
    def _configure_row_colors(self) -> None:
        """Configure row color rules based on active configuration.
        
        Matches Tkinter's _configure_row_colors: uses active config row_colors
        if found, otherwise falls back to [LAUNCHER] row_colors. Applies WCAG
        contrast fallback when colors are invisible against the theme surface.
        """
        from profiles.gui.presentation.row_colors import RowColorRules
        
        # Find active config (matching directory)
        active_config = self._config  # For now, use current config; can be enhanced
        
        # Get row colors from active config or fallback to defaults
        row_colors_to_use = active_config.row_colors if hasattr(active_config, 'row_colors') and active_config.row_colors else self._config.row_colors
        
        # Build RowColorRules engine
        self._row_rules = RowColorRules(row_colors_to_use, "rowcolor")
        
        # Apply colors with current theme
        if hasattr(self._file_tree, '_theme'):
            self._file_tree.set_row_colors(self._row_rules, self._theme)

    def _on_scan_requested(self) -> None:
        self._action_bar.set_scanning(True)
        self._status_bar.set_scanning(True)

        directories = [self._directory_bar.dir_text]
        extension = self._directory_bar.ext_text
        filter_text = self._directory_bar.filter_text
        recursive = self._action_bar.recursive_check.isChecked()
        directory_label = self._directory_bar.dir_text

        self._controller.start_scan(
            directories=directories,
            extension=extension,
            filter_text=filter_text,
            recursive=recursive,
            directory_label=directory_label,
            on_finished=self._on_scan_finished,
            on_failed=self._on_scan_failed,
        )

    def _on_scan_clicked(self) -> None:
        self._on_scan_requested()

    def _on_execute_clicked(self) -> None:
        """Handle file execution on selected row.

        Calls actions.launch_selected_file() with proper parameters,
        handles all ActionResult statuses, closes window after 500ms
        if close_after_execute is set, and emits telemetry events
        (file_launched, file_launch_failed) via the action.
        """
        # Get selected row from table widget
        selected_rows = self._file_tree.table_widget.selectedItems()
        if not selected_rows:
            self._status_bar.set_message("No file selected")
            return

        # Get the selected row index
        row = selected_rows[0].row()

        # Extract filename from first column (File column)
        filename_item = self._file_tree.table_widget.item(row, 0)
        if not filename_item:
            self._status_bar.set_message("Invalid selection")
            return

        filename = filename_item.text()

        # Get directory from directory bar
        directory = self._directory_bar.dir_text

        # Get config values
        release = self._config.release
        username = self._config.title or "unknown"
        close_after = self._config.close_after_execute

        # Call the action
        result = actions_launch_file(
            directory=directory,
            filename=filename,
            release=release,
            username=username,
            config=self._config,
            logger=self._logger,
        )

        # Handle result
        if result.status == ActionStatus.SUCCESS:
            self._status_bar.set_message(f"Launched: {filename}")
        elif result.status == ActionStatus.NOT_FOUND:
            self._status_bar.set_message(f"File not found: {filename}")
            QMessageBox.warning(self, "File Not Found", result.message)
        elif result.status == ActionStatus.FAILED:
            self._status_bar.set_message(f"Launch failed: {filename}")
            QMessageBox.critical(self, "Launch Failed", result.message)

        # Close window after 500ms if configured
        if close_after:
            QTimer.singleShot(500, self.close)

    def _on_scan_finished(self, items: list) -> None:
        """Handle scan completion and start chunked insertion."""
        self._scan_items = items
        column_names = self._config.column_names or ("File",)
        
        # Start chunked insertion
        self._chunked_controller.start_chunked_insert(
            items=items,
            column_names=column_names,
            on_chunk_ready=self._on_chunk_ready,
            on_finished=self._on_chunked_insert_finished,
            on_progress=self._on_chunk_progress,
        )

    def _on_chunk_ready(self, chunk: list[ScannedFileDynamic]) -> None:
        """Handle a chunk of items ready for insertion (called on main thread)."""
        table = self._file_tree.table_widget
        column_names = self._config.column_names or ("File",)
        num_columns = len(column_names)
        
        # Get current row count
        current_row_count = table.rowCount()
        new_row_count = current_row_count + len(chunk)
        
        # Set row count to accommodate new items
        table.setRowCount(new_row_count)
        
        # Insert items into table
        for i, item in enumerate(chunk):
            row = current_row_count + i
            for col in range(num_columns):
                col_name = column_names[col] if col < len(column_names) else ""
                value = item.column_values.get(col_name, "") if item.column_values else ""
                table_item = QTableWidgetItem(str(value) if value else "")
                table.setItem(row, col, table_item)

    def _on_chunk_progress(self, current: int, total: int) -> None:
        """Handle progress update (called on main thread)."""
        self._status_bar.set_message(f"Loading files: {current}/{total}")

    def _on_chunked_insert_finished(self) -> None:
        """Handle completion of chunked insertion (called on main thread)."""
        self._action_bar.set_scanning(False)
        self._status_bar.set_scanning(False)
        total = len(self._scan_items)
        # Clear sort state when new data is loaded
        self._file_tree.clear_sort_state()
        self._status_bar.set_message(f"Scan complete: {total} items")
        self._logger.info(f"Scan finished: {total} items")
        
        # Re-apply row colors after all items are inserted
        if hasattr(self, '_row_rules') and self._row_rules is not None:
            self._file_tree._apply_row_colors()

    def _on_scan_failed(self, error: str) -> None:
        self._action_bar.set_scanning(False)
        self._status_bar.set_scanning(False)
        self._status_bar.set_message(f"Scan failed: {error}")
        self._logger.error(f"Scan failed: {error}")
        QMessageBox.critical(self, "Scan Failed", f"Scan failed: {error}")

    def _focus_filter(self) -> None:
        self._directory_bar.filter_combo.setFocus()

    def _focus_extension(self) -> None:
        """Focus the extension combobox (Ctrl+E)."""
        self._directory_bar.ext_combo.setFocus()

    def _focus_file_tree(self) -> None:
        """Focus the file table (Ctrl+L)."""
        self._file_tree.table_widget.setFocus()

    def _clear_filter(self) -> None:
        """Clear the filter text (Delete or Escape)."""
        self._directory_bar.filter_combo.setCurrentIndex(-1)
        self._directory_bar.filter_combo.setEditText("")

    def _on_reset_filters_requested(self) -> None:
        """Handle reset filters request from empty state banner."""
        # Reset extension and filter to first values
        ext_values = self._directory_bar.ext_combo.currentText()
        filter_values = self._directory_bar.filter_combo.currentText()
        
        # Clear filter text
        self._directory_bar.filter_combo.setCurrentIndex(-1)
        self._directory_bar.filter_combo.setEditText("")
        
        # Trigger a rescan
        self._on_scan_requested()

    def _on_execute_shortcut(self) -> None:
        """Execute selected file (Return or Ctrl+D).

        Same handler as _on_execute_clicked, extracted for shortcut binding.
        """
        self._on_execute_clicked()

    def _launch_with_args(self) -> None:
        """Launch selected file with arguments (Ctrl+Shift+L).

        Prompts for arguments via QMessageBox, then executes with those args.
        """
        from PySide6.QtWidgets import QInputDialog

        # Get selected file
        selected_rows = self._file_tree.table_widget.selectedItems()
        if not selected_rows:
            self._status_bar.set_message("No file selected")
            return

        row = selected_rows[0].row()
        filename_item = self._file_tree.table_widget.item(row, 0)
        if not filename_item:
            self._status_bar.set_message("Invalid selection")
            return

        filename = filename_item.text()
        directory = self._directory_bar.dir_text

        # Prompt for arguments
        args, ok = QInputDialog.getText(
            self,
            "Launch with Arguments",
            f"Arguments for {filename}:",
        )

        if not ok or not args:
            return

        # Get config values
        release = self._config.release
        username = self._config.title or "unknown"
        close_after = self._config.close_after_execute

        # Call the action with args
        result = actions_launch_file(
            directory=directory,
            filename=filename,
            release=release,
            username=username,
            args=args,
            config=self._config,
            logger=self._logger,
        )

        # Handle result
        if result.status == ActionStatus.SUCCESS:
            self._status_bar.set_message(f"Launched: {filename} with args: {args}")
        elif result.status == ActionStatus.NOT_FOUND:
            self._status_bar.set_message(f"File not found: {filename}")
            QMessageBox.warning(self, "File Not Found", result.message)
        elif result.status == ActionStatus.FAILED:
            self._status_bar.set_message(f"Launch failed: {filename}")
            QMessageBox.critical(self, "Launch Failed", result.message)

        # Close window after 500ms if configured
        if close_after:
            QTimer.singleShot(500, self.close)

    def _open_preferences(self) -> None:
        """Open preferences/config file (Ctrl+Comma).

        Opens the config file in the default editor.
        """
        import os
        from pathlib import Path

        config_path = Path(self._config.config_path)
        if config_path.exists():
            try:
                os.startfile(str(config_path))  # Windows
            except AttributeError:
                try:
                    import subprocess

                    subprocess.run(["xdg-open", str(config_path)])  # Linux
                except Exception:
                    self._status_bar.set_message(f"Config file: {config_path}")
        else:
            self._status_bar.set_message("Config file not found")

    def _show_shortcuts_help(self) -> None:
        """Show keyboard shortcuts help dialog (Ctrl+?)."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Keyboard Shortcuts")
        dlg.setIcon(QMessageBox.Icon.Information)

        shortcuts_text = """
F5              : Scan/Refresh
Ctrl+R          : Scan/Refresh
Ctrl+D          : Execute selected file
Return          : Execute selected file
Ctrl+E          : Focus extension field
Ctrl+L          : Focus file tree
Delete/Escape   : Clear filter text
Ctrl+Shift+L    : Launch with arguments
Ctrl+,          : Open preferences/config
Ctrl+Shift+T    : Cycle theme
Ctrl+?          : Show this help
Ctrl+Q          : Quit application
Ctrl+F          : Focus filter field
        """.strip()

        dlg.setText(shortcuts_text)
        dlg.exec()

    def _on_toggle_theme(self) -> None:
        """Toggle between light, dark, and auto themes (matches Tkinter)."""
        if self._theme_name == "light":
            new_name = "dark"
        elif self._theme_name == "dark":
            new_name = "auto"
        else:
            new_name = "light"
        self._apply_theme(new_name)

    def _apply_theme(self, theme_name: str) -> None:
        """Apply the named theme to the entire Qt GUI.
        
        Args:
            theme_name: One of "light", "dark", or "auto".
        """
        # Resolve the actual theme name (auto -> light/dark based on system)
        resolved_name = resolve_theme_name_qt(theme_name)
        theme = DARK_THEME if resolved_name == "dark" else LIGHT_THEME
        self._theme = theme
        self._theme_name = theme_name

        # Convert theme to QSS tokens and apply stylesheet
        qss_tokens = to_qss_tokens(theme)
        
        # Build QSS from tokens - map to Qt properties
        qss = self._build_qss_from_tokens(qss_tokens)
        self.setStyleSheet(qss)

        # Re-apply row colors with new theme
        if hasattr(self, '_row_rules') and self._row_rules is not None:
            self._file_tree.set_row_colors(self._row_rules, theme)
        elif hasattr(self, '_configure_row_colors'):
            # First time: configure row colors
            self._configure_row_colors()

        # Update status bar theme label
        self._status_bar.set_message(f"Theme: {THEME_LABELS.get(theme_name, 'Light')}")

        # Persist to config
        try:
            from profiles.core.config.io.yaml_io import write_value
            write_value(self._config.config_path, "defaults.theme", theme_name)
        except Exception as e:
            self._logger.warning(f"Failed to persist theme: {e}")

    def _build_qss_from_tokens(self, tokens: dict[str, str]) -> str:
        """Build QSS stylesheet from theme tokens.
        
        Args:
            tokens: Dictionary of theme colour values.
            
        Returns:
            QSS stylesheet string.
        """
        # Build QSS with variable substitutions
        qss_parts = []
        
        # Define QSS variables
        qss_parts.append("QMainWindow {")
        qss_parts.append(f"    background-color: {tokens['background']};")
        qss_parts.append(f"    color: {tokens['on_background']};")
        qss_parts.append("}")
        
        qss_parts.append("QWidget {")
        qss_parts.append(f"    background-color: {tokens['surface']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append(f"    border-color: {tokens['outline_variant']};")
        qss_parts.append("}")
        
        qss_parts.append("QPushButton {")
        qss_parts.append(f"    background-color: {tokens['surface_container']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append(f"    border: 1px solid {tokens['outline_variant']};")
        qss_parts.append(f"    border-radius: 4px;")
        qss_parts.append(f"    padding: 6px 12px;")
        qss_parts.append("}")
        
        qss_parts.append("QPushButton:hover {")
        qss_parts.append(f"    background-color: {tokens['hover']};")
        qss_parts.append("}")
        
        qss_parts.append("QPushButton:pressed {")
        qss_parts.append(f"    background-color: {tokens['surface_dim']};")
        qss_parts.append("}")
        
        qss_parts.append("QComboBox {")
        qss_parts.append(f"    background-color: {tokens['surface']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append(f"    border: 1px solid {tokens['outline_variant']};")
        qss_parts.append(f"    border-radius: 4px;")
        qss_parts.append(f"    padding: 4px;")
        qss_parts.append("}")
        
        qss_parts.append("QComboBox::drop-down {")
        qss_parts.append(f"    border: none;")
        qss_parts.append(f"    width: 20px;")
        qss_parts.append("}")
        
        qss_parts.append("QComboBox QAbstractItemView {")
        qss_parts.append(f"    background-color: {tokens['surface']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append(f"    selection-background-color: {tokens['primary']};")
        qss_parts.append(f"    selection-color: {tokens['on_primary']};")
        qss_parts.append("}")
        
        qss_parts.append("QTreeView {")
        qss_parts.append(f"    background-color: {tokens['surface']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append(f"    border: none;")
        qss_parts.append(f"    alternate-background-color: {tokens['surface_container']};")
        qss_parts.append("}")
        
        qss_parts.append("QTreeView::item {")
        qss_parts.append(f"    padding: 8px;")
        qss_parts.append(f"    border: 1px solid transparent;")
        qss_parts.append("}")
        
        qss_parts.append("QTreeView::item:selected {")
        qss_parts.append(f"    background-color: {tokens['primary']};")
        qss_parts.append(f"    color: {tokens['on_primary']};")
        qss_parts.append("}")
        
        qss_parts.append("QTreeView::item:hover {")
        qss_parts.append(f"    background-color: {tokens['hover']};")
        qss_parts.append("}")
        
        qss_parts.append("QHeaderView::section {")
        qss_parts.append(f"    background-color: {tokens['surface_container']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append(f"    padding: 6px;")
        qss_parts.append(f"    border: none;")
        qss_parts.append(f"    border-bottom: 1px solid {tokens['outline_variant']};")
        qss_parts.append("}")
        
        qss_parts.append("QStatusBar {")
        qss_parts.append(f"    background-color: {tokens['status_bg']};")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append("}")
        
        qss_parts.append("QStatusBar QLabel {")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append("}")
        
        qss_parts.append("QStatusBar a {")
        qss_parts.append(f"    color: {tokens['primary']};")
        qss_parts.append("}")
        
        qss_parts.append("QCheckBox {")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append("}")
        
        qss_parts.append("QLabel {")
        qss_parts.append(f"    color: {tokens['on_surface']};")
        qss_parts.append("}")
        
        return "\n".join(qss_parts)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._controller.stop_scan()
        self._chunked_controller.stop_chunked_insert()
        event.accept()

    def run(self) -> int:
        """Run the application.

        Returns:
            Application exit code.
        """
        self.show()
        from PySide6.QtWidgets import QApplication

        return QApplication.instance().exec() if QApplication.instance() else 0

    # Properties for testing
    @property
    def header(self) -> HeaderWidget:
        return self._header

    @property
    def directory_bar(self) -> DirectoryBar:
        return self._directory_bar

    @property
    def action_bar(self) -> ActionBar:
        return self._action_bar

    @property
    def file_tree(self) -> FileTree:
        return self._file_tree

    @property
    def status_bar(self) -> StatusBar:
        return self._status_bar

    @property
    def context_menu(self) -> ContextMenu | None:
        return self._context_menu
