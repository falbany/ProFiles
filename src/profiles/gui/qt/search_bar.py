"""Search bar component for ProFiles Qt GUI.

Provides a dedicated search/filter bar with controls for directory selection,
extension filtering, keyword filtering, and search options - matching the
Tkinter implementation.
"""

from __future__ import annotations

import contextlib
import platform
import subprocess

try:
    from typing import override
except ImportError:
    pass

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from profiles.gui.i18n import register, t


class SearchBar(QWidget):
    """Search bar component for the main window.

    Contains app title, directory selection, extension filter, keyword filter,
    recursive option, and search button. Mirrors the Tkinter implementation.
    """

    # Signals emitted for parent to handle
    directory_changed = Signal()
    directory_entered = Signal()
    directory_double_clicked = Signal()
    browse_clicked = Signal()
    extension_or_filter_selected = Signal()
    debounced_refresh_ext = Signal()
    flush_timer_ext = Signal()
    filter_refresh = Signal()
    flush_timer_filter = Signal()
    recursive_toggled = Signal()
    search_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        release_version: str = "0.0.0",
        recursive_checked: bool = True,
        config_title: str = "",
    ) -> None:
        """Initialize the search bar.

        Args:
            parent: Parent widget to attach the search bar to.
            release_version: Application version string.
            recursive_checked: Initial state of recursive checkbox.
            config_title: Configuration title for display.
        """
        super().__init__(parent)
        self._release_version = release_version
        self._config_title = config_title
        self._recursive_checked = recursive_checked

        # String variables
        self._dir_text: str = ""
        self._ext_text: str = ""
        self._filter_text: str = ""

        # Widget references
        self._search_frame: QWidget
        self._title_frame: QWidget
        self._title_label: QLabel
        self._title_author: QLabel
        self._controls_frame: QWidget
        self._dir_frame: QWidget
        self._dir_combo: QComboBox
        self._browse_btn: QPushButton
        self._filter_frame: QWidget
        self._recursive_check: QCheckBox
        self._search_btn: QPushButton
        self._ext_combo: QComboBox
        self._filter_combo: QLineEdit

        # Debounce timers
        self._ext_debounce_timer = QTimer(self)
        self._ext_debounce_timer.setSingleShot(True)
        self._ext_debounce_timer.timeout.connect(self._on_ext_debounce_timeout)

        self._filter_debounce_timer = QTimer(self)
        self._filter_debounce_timer.setSingleShot(True)
        self._filter_debounce_timer.timeout.connect(self._on_filter_debounce_timeout)

        self._build()
        register(self._apply_text)

    def _build(self) -> None:
        """Build the search bar widgets."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ── Title stacked vertically above directory/filters ─────────
        self._title_frame = QWidget(self)
        title_layout = QVBoxLayout(self._title_frame)
        title_layout.setContentsMargins(16, 14, 16, 0)
        title_layout.setSpacing(4)

        title_text = f"ProFiles — {self._config_title}" if self._config_title else "ProFiles"
        self._title_label = QLabel(title_text)
        title_layout.addWidget(self._title_label, alignment=Qt.AlignmentFlag.AlignLeft)

        self._title_author = QLabel(f"By Florent ALBANY - v{self._release_version}")
        title_layout.addWidget(self._title_author, alignment=Qt.AlignmentFlag.AlignLeft)

        # Title tooltip
        self._title_label.setToolTip(t("title.tooltip"))

        main_layout.addWidget(self._title_frame)

        # ── Controls below the title ─────────────────────────
        self._controls_frame = QWidget(self)
        controls_layout = QVBoxLayout(self._controls_frame)
        controls_layout.setContentsMargins(16, 10, 16, 14)
        controls_layout.setSpacing(10)

        # --- Row 1: Directory ---
        self._dir_frame = QWidget(self._controls_frame)
        dir_layout = QHBoxLayout(self._dir_frame)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(4)

        dir_label = QLabel(t("search.dir_label"))
        dir_layout.addWidget(dir_label)

        self._dir_combo = QComboBox()
        self._dir_combo.setEditable(True)
        self._dir_combo.setMinimumHeight(28)
        self._dir_combo.currentTextChanged.connect(self._on_directory_changed)
        # Connect to the lineEdit's returnPressed signal for Enter key handling
        self._dir_combo.lineEdit().returnPressed.connect(self._on_directory_enter)
        dir_layout.addWidget(self._dir_combo, 1)

        # Double-click to open explorer
        self._dir_combo.installEventFilter(self)

        self._dir_combo.setToolTip(t("search.dir.tooltip"))

        self._browse_btn = QPushButton(t("search.browse"))
        self._browse_btn.setMinimumHeight(28)
        self._browse_btn.clicked.connect(self._on_browse)
        self._browse_btn.setToolTip(t("search.browse.tooltip"))
        dir_layout.addWidget(self._browse_btn)

        controls_layout.addWidget(self._dir_frame)

        # --- Row 2: Extension + Filter + Search ---
        self._filter_frame = QWidget(self._controls_frame)
        filter_layout = QHBoxLayout(self._filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        # Extension label + combobox
        ext_label = QLabel(t("search.ext_label"))
        filter_layout.addWidget(ext_label)

        self._ext_combo = QComboBox()
        self._ext_combo.setEditable(True)
        self._ext_combo.setMinimumHeight(28)
        self._ext_combo.currentTextChanged.connect(self._on_extension_or_filter_select)
        self._ext_combo.editTextChanged.connect(self._on_ext_key_release)
        self._ext_combo.setToolTip(t("search.ext.tooltip"))
        filter_layout.addWidget(self._ext_combo, 0)

        # Filter label + expanding entry
        filter_lbl = QLabel(t("search.filter_label"))
        filter_layout.addWidget(filter_lbl)

        self._filter_combo = QLineEdit()
        self._filter_combo.setMinimumHeight(28)
        self._filter_combo.returnPressed.connect(self._on_filter_enter)
        self._filter_combo.textChanged.connect(self._on_filter_key_release)
        self._filter_combo.setToolTip(t("search.filter.tooltip"))
        filter_layout.addWidget(self._filter_combo, 1)

        # Right-aligned group: Recursive check + Search button
        right_group = QWidget(self._filter_frame)
        right_layout = QHBoxLayout(right_group)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self._recursive_check = QCheckBox(t("search.recursive"))
        self._recursive_check.setChecked(self._recursive_checked)
        self._recursive_check.toggled.connect(self._on_recursive_toggle)
        self._recursive_check.setToolTip(t("search.recursive.tooltip"))
        right_layout.addWidget(self._recursive_check)

        self._search_btn = QPushButton(t("search.search_btn"))
        self._search_btn.setMinimumHeight(28)
        self._search_btn.clicked.connect(self._on_search)
        self._search_btn.setToolTip(t("search.search_btn.tooltip"))
        right_layout.addWidget(self._search_btn)

        filter_layout.addWidget(right_group)

        controls_layout.addWidget(self._filter_frame)

        main_layout.addWidget(self._controls_frame)

    def _on_directory_changed(self, _text: str = "") -> None:
        """Handle directory combobox selection change."""
        self._dir_text = self._dir_combo.currentText()
        self.directory_changed.emit()

    def _on_directory_enter(self) -> None:
        """Handle Enter key in directory combobox."""
        self._dir_text = self._dir_combo.currentText()
        self.directory_entered.emit()

    def _on_directory_double_click(self) -> None:
        """Handle double-click on directory combobox."""
        self.directory_double_clicked.emit()

    def _on_browse(self) -> None:
        """Handle browse button click."""
        self.browse_clicked.emit()

    def _on_extension_or_filter_select(self, _text: str = "") -> None:
        """Handle extension/filter selection."""
        self._ext_text = self._ext_combo.currentText()
        self.extension_or_filter_selected.emit()

    def _on_ext_key_release(self, _text: str = "") -> None:
        """Handle key release in extension combobox - debounced."""
        self._ext_text = self._ext_combo.currentText()
        self._ext_debounce_timer.start(300)  # 300ms debounce

    def _on_ext_debounce_timeout(self) -> None:
        """Handle extension debounce timeout."""
        self.debounced_refresh_ext.emit()

    def _on_filter_key_release(self, _text: str = "") -> None:
        """Handle key release in filter entry - debounced."""
        self._filter_text = self._filter_combo.text()
        self._filter_debounce_timer.start(300)  # 300ms debounce

    def _on_filter_enter(self) -> None:
        """Handle Enter key in filter entry."""
        self._filter_text = self._filter_combo.text()
        self.filter_refresh.emit()

    def _on_filter_debounce_timeout(self) -> None:
        """Handle filter debounce timeout."""
        self.filter_refresh.emit()

    def _on_recursive_toggle(self, _checked: bool = False) -> None:
        """Handle recursive checkbox toggle."""
        self.recursive_toggled.emit()

    def _on_search(self) -> None:
        """Handle search button click."""
        self.search_requested.emit()

    def _apply_text(self, _lang: str | None = None) -> None:
        """Re-label all translatable widgets in the search bar."""
        with contextlib.suppress(Exception):
            # Update labels
            for i in range(self._dir_frame.layout().count()):
                widget = self._dir_frame.layout().itemAt(i).widget()
                if isinstance(widget, QLabel) and i == 0:
                    widget.setText(t("search.dir_label"))
                    break

            for i in range(self._filter_frame.layout().count()):
                widget = self._filter_frame.layout().itemAt(i).widget()
                if isinstance(widget, QLabel):
                    if self._filter_frame.layout().itemAt(0).widget() == widget:
                        widget.setText(t("search.ext_label"))
                    elif self._filter_frame.layout().itemAt(2).widget() == widget:
                        widget.setText(t("search.filter_label"))

            self._browse_btn.setText(t("search.browse"))
            self._recursive_check.setText(t("search.recursive"))
            self._search_btn.setText(t("search.search_btn"))

            # Update tooltips
            self._dir_combo.setToolTip(t("search.dir.tooltip"))
            self._browse_btn.setToolTip(t("search.browse.tooltip"))
            self._recursive_check.setToolTip(t("search.recursive.tooltip"))
            self._search_btn.setToolTip(t("search.search_btn.tooltip"))
            self._ext_combo.setToolTip(t("search.ext.tooltip"))
            self._filter_combo.setToolTip(t("search.filter.tooltip"))
            self._title_label.setToolTip(t("title.tooltip"))

    # ── Event filter for double-click detection ──────────────────────

    def eventFilter(self, obj, event) -> bool:
        """Handle event filtering for double-click detection."""
        if obj == self._dir_combo and event.type() == QEvent.Type.MouseButtonDblClick:
            self._on_directory_double_click()
            return True
        return super().eventFilter(obj, event)

    # ── Public API ──────────────────────────────────────────────────

    @property
    def search_frame(self) -> QWidget:
        """Get the outer search bar frame."""
        return self

    @property
    def title_frame(self) -> QWidget:
        """Get the title frame."""
        return self._title_frame

    @property
    def title_label(self) -> QLabel:
        """Get the title label."""
        return self._title_label

    @property
    def title_author(self) -> QLabel:
        """Get the title author label."""
        return self._title_author

    @property
    def controls_frame(self) -> QWidget:
        """Get the controls frame."""
        return self._controls_frame

    @property
    def dir_frame(self) -> QWidget:
        """Get the directory frame."""
        return self._dir_frame

    @property
    def dir_var(self) -> str:
        """Get the directory text."""
        return self._dir_text

    @property
    def dir_combo(self) -> QComboBox:
        """Get the directory combobox."""
        return self._dir_combo

    @property
    def browse_btn(self) -> QPushButton:
        """Get the browse button."""
        return self._browse_btn

    @property
    def filter_frame(self) -> QWidget:
        """Get the filter frame."""
        return self._filter_frame

    @property
    def recursive_var(self) -> bool:
        """Get the recursive checkbox state."""
        return self._recursive_check.isChecked()

    @property
    def recursive_check(self) -> QCheckBox:
        """Get the recursive checkbox."""
        return self._recursive_check

    @property
    def search_btn(self) -> QPushButton:
        """Get the search button."""
        return self._search_btn

    @property
    def ext_var(self) -> str:
        """Get the extension text."""
        return self._ext_text

    @property
    def ext_combo(self) -> QComboBox:
        """Get the extension combobox."""
        return self._ext_combo

    @property
    def filter_var(self) -> str:
        """Get the filter text."""
        return self._filter_text

    @property
    def filter_combo(self) -> QLineEdit:
        """Get the filter entry."""
        return self._filter_combo

    # ── Helper methods ──────────────────────────────────────────────

    def set_directory_text(self, text: str) -> None:
        """Set directory text, adding item if not present."""
        idx = self._dir_combo.findText(text)
        if idx < 0:
            self._dir_combo.addItem(text)
            idx = self._dir_combo.count() - 1
        self._dir_combo.setCurrentIndex(idx)
        self._dir_text = text

    def set_extension_text(self, text: str) -> None:
        """Set extension text, adding item if not present."""
        idx = self._ext_combo.findText(text)
        if idx < 0:
            self._ext_combo.addItem(text)
            idx = self._ext_combo.count() - 1
        self._ext_combo.setCurrentIndex(idx)
        self._ext_text = text

    def set_filter_text(self, text: str) -> None:
        """Set filter text."""
        self._filter_combo.setText(text)
        self._filter_text = text

    def auto_select_directory_by_hostname(self, directories: list[str]) -> None:
        """Auto-select directory by hostname.

        Args:
            directories: List of available directory paths.
        """
        hostname = platform.node().lower()
        for i in range(self._dir_combo.count()):
            path = self._dir_combo.itemText(i).lower()
            if hostname in path:
                self._dir_combo.setCurrentIndex(i)
                self._dir_text = self._dir_combo.currentText()
                return
        # If no match, select first
        if self._dir_combo.count() > 0:
            self._dir_combo.setCurrentIndex(0)
            self._dir_text = self._dir_combo.currentText()

    def open_directory_in_explorer(self, path: str) -> None:
        """Open directory in system file explorer.

        Args:
            path: Directory path to open.
        """
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", path])
            else:  # Linux
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass
