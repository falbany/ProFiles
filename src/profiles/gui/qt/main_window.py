"""Qt main window with decomposed widgets and signal wiring."""

from __future__ import annotations

import logging
from typing import Any

try:
    from typing import override
except ImportError:
    from typing_extensions import override

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTreeView,
    QWidget,
)

from profiles.core.actions import ActionStatus
from profiles.core.actions import launch_selected_file as actions_launch_file
from profiles.core.config.models import AppConfig
from profiles.gui.qt.controllers.scan_controller import ScanController
from profiles.gui.qt.ui import create_horizontal_layout, create_vertical_layout

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

    def _setup_ui(self) -> None:
        layout = create_vertical_layout(self, spacing=6, margin=8)

        # Directory combobox
        dir_layout = create_horizontal_layout(spacing=6, margin=0)
        dir_label = QLabel("Directory:")
        self._dir_combo = QComboBox()
        self._dir_combo.setMinimumHeight(28)
        self._dir_combo.currentTextChanged.connect(self._on_dir_changed)
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self._dir_combo, 1)
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


class ActionBar(QWidget):
    """Recursive checkbox and scan/execute buttons."""

    scan_requested = Signal()
    execute_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

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

        layout.addWidget(self._recursive_check)
        layout.addStretch()
        layout.addWidget(self._scan_button)
        layout.addWidget(self._execute_button)

    @property
    def recursive_check(self) -> QCheckBox:
        return self._recursive_check

    @property
    def scan_button(self) -> QPushButton:
        return self._scan_button

    @property
    def execute_button(self) -> QPushButton:
        return self._execute_button

    def set_scanning(self, scanning: bool) -> None:
        self._scan_button.setEnabled(not scanning)
        self._execute_button.setEnabled(not scanning)


class FileTree(QWidget):
    """QTreeView with row colours support."""

    selection_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = create_vertical_layout(self, spacing=0, margin=0)

        self._tree_view = QTreeView()
        self._tree_view.setAlternatingRowColors(True)
        self._tree_view.setRootIsDecorated(True)
        self._tree_view.setHeaderHidden(False)
        self._tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self._tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        self._tree_view.doubleClicked.connect(self._on_double_click)

        layout.addWidget(self._tree_view)

    def _on_double_click(self, index: Any) -> None:
        self.selection_changed.emit([index])

    @property
    def tree_view(self) -> QTreeView:
        return self._tree_view

    def set_model(self, model: Any) -> None:
        self._tree_view.setModel(model)

    def set_row_colors(self, rules: Any) -> None:
        """Configure row colour rules using row_colors module."""
        from profiles.gui.presentation.row_colors import RowColorRules

        if isinstance(rules, RowColorRules):
            self._row_rules = rules
        else:
            self._row_rules = rules


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
    """Right-click context menu for the file tree."""

    def __init__(self, tree_view: QTreeView, logger: logging.Logger) -> None:
        self._tree_view = tree_view
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
        index = self._tree_view.indexAt(event.pos())
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
        self._setup_ui()
        self._setup_controller()

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
        self._file_tree = FileTree()
        main_layout.addWidget(self._file_tree, 1)

        # Status bar
        self._status_bar = StatusBar()
        self.setStatusBar(self._status_bar)

        # Context menu
        self._context_menu = ContextMenu(self._file_tree.tree_view, self._logger)
        self._file_tree.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_tree.tree_view.customContextMenuRequested.connect(
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
        # Get selected index from tree view
        selection = self._file_tree.tree_view.selection()
        if not selection:
            self._status_bar.set_message("No file selected")
            return

        # Get the selected item data
        selected_item = selection[0]
        item_data = self._file_tree.tree_view.item(selected_item)
        values = item_data["values"]

        # Extract filename from first column (File column)
        if not values or len(values) < 1:
            self._status_bar.set_message("Invalid selection")
            return

        filename = values[0]

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
        self._action_bar.set_scanning(False)
        self._status_bar.set_scanning(False)
        self._status_bar.set_message(f"Scan complete: {len(items)} items")
        self._logger.info(f"Scan finished: {len(items)} items")

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
        """Focus the file tree view (Ctrl+L)."""
        self._file_tree.tree_view.setFocus()

    def _clear_filter(self) -> None:
        """Clear the filter text (Delete or Escape)."""
        self._directory_bar.filter_combo.setCurrentIndex(-1)
        self._directory_bar.filter_combo.setEditText("")

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
        selection = self._file_tree.tree_view.selection()
        if not selection:
            self._status_bar.set_message("No file selected")
            return

        selected_item = selection[0]
        item_data = self._file_tree.tree_view.item(selected_item)
        values = item_data["values"]

        if not values or len(values) < 1:
            self._status_bar.set_message("Invalid selection")
            return

        filename = values[0]
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

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._controller.stop_scan()
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
