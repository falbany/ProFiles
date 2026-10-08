"""Qt status bar implementation matching Tkinter behavior."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStatusBar,
    QWidget,
)

from profiles.core.environment.system import collect_system_info
from profiles.gui.i18n import LANGUAGE_LABELS, current_language, register, t


class StatusBar(QStatusBar):
    """Status bar with system info, action links, and theme/language toggles.

    Matches Tkinter StatusBar behavior:
    - User/Host/IP labels from system.collect_system_info()
    - Clickable links: Config, Refresh, Log, Shortcuts, Theme
    - File count display with flash animation
    - Theme toggle button
    - Language toggle button (EN/FR)
    - Tooltips on all links
    """

    config_clicked = Signal()
    refresh_clicked = Signal()
    log_clicked = Signal()
    shortcuts_clicked = Signal()
    theme_toggled = Signal()
    language_toggled = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        on_config_click: Callable[[], None] | None = None,
        on_refresh_click: Callable[[], None] | None = None,
        on_log_click: Callable[[], None] | None = None,
        on_shortcuts_click: Callable[[], None] | None = None,
        on_theme_toggle: Callable[[], None] | None = None,
        on_language_toggle: Callable[[], None] | None = None,
        theme_label: str = "☀ Light",
    ) -> None:
        super().__init__(parent)
        self._on_config_click = on_config_click
        self._on_refresh_click = on_refresh_click
        self._on_log_click = on_log_click
        self._on_shortcuts_click = on_shortcuts_click
        self._on_theme_toggle = on_theme_toggle
        self._on_language_toggle = on_language_toggle
        self._theme_label = theme_label

        # Flash animation timer
        self._flash_timer = QTimer()
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)
        self._flash_count = 0

        # Widget references
        self._links_widget: QWidget
        self._system_widget: QWidget
        self._config_link: QLabel
        self._refresh_btn: QPushButton
        self._log_link: QLabel
        self._shortcuts_btn: QPushButton | None
        self._theme_btn: QPushButton
        self._language_btn: QPushButton | None
        self._user_label: QLabel
        self._host_label: QLabel
        self._ip_label: QLabel
        self._count_label: QLabel
        self._dir_status_label: QLabel

        self._setup_ui()
        register(self._apply_text)

    def _setup_ui(self) -> None:
        """Build the status bar widgets."""
        # Links container (left side)
        self._links_widget = QWidget()
        self._links_layout = QHBoxLayout(self._links_widget)
        self._links_layout.setContentsMargins(10, 2, 10, 2)
        self._links_layout.setSpacing(12)

        # Config link
        self._config_link = QLabel("<a href='#'>Config</a>")
        self._config_link.setTextFormat(Qt.RichText)
        self._config_link.linkActivated.connect(lambda: self.config_clicked.emit())
        self._config_link.setToolTip(t("status.config.tooltip"))
        self._links_layout.addWidget(self._config_link)

        # Refresh button
        self._refresh_btn = QPushButton("Refresh")
        if self._on_refresh_click is not None:
            self._refresh_btn.clicked.connect(self._on_refresh_click)
        self._refresh_btn.setToolTip(t("status.refresh.tooltip"))
        self._links_layout.addWidget(self._refresh_btn)

        # Log link
        self._log_link = QLabel("<a href='#'>Log</a>")
        self._log_link.setTextFormat(Qt.RichText)
        self._log_link.linkActivated.connect(lambda: self.log_clicked.emit())
        self._log_link.setToolTip(t("status.log.tooltip"))
        self._links_layout.addWidget(self._log_link)

        # Shortcuts button (optional)
        self._shortcuts_btn = None
        if self._on_shortcuts_click is not None:
            self._shortcuts_btn = QPushButton("Shortcuts")
            self._shortcuts_btn.clicked.connect(self._on_shortcuts_click)
            self._shortcuts_btn.setToolTip(t("status.shortcuts.tooltip"))
            self._links_layout.addWidget(self._shortcuts_btn)

        # Theme toggle button
        self._theme_btn = QPushButton(self._theme_label)
        if self._on_theme_toggle is not None:
            self._theme_btn.clicked.connect(self._on_theme_toggle)
        self._theme_btn.setToolTip(t("status.theme.tooltip"))
        self._links_layout.addWidget(self._theme_btn)

        # Language toggle button (optional)
        self._language_btn = None
        if self._on_language_toggle is not None:
            self._language_btn = QPushButton(LANGUAGE_LABELS.get(current_language(), "🌐"))
            self._language_btn.clicked.connect(self._on_language_toggle)
            self._language_btn.setToolTip(t("status.language.tooltip"))
            self._links_layout.addWidget(self._language_btn)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedWidth(1)
        self._links_layout.addWidget(separator)

        # System info container (right side)
        self._system_widget = QWidget()
        self._system_layout = QHBoxLayout(self._system_widget)
        self._system_layout.setContentsMargins(10, 2, 10, 2)
        self._system_layout.setSpacing(8)
        self._system_layout.addStretch()

        # User label
        self._user_label = QLabel("User: ...")
        self._user_label.setToolTip(t("status.user.tooltip"))
        self._system_layout.addWidget(self._user_label)

        # Host label
        self._host_label = QLabel("Host: ...")
        self._host_label.setToolTip(t("status.host.tooltip"))
        self._system_layout.addWidget(self._host_label)

        # IP label
        self._ip_label = QLabel("IP: ...")
        self._ip_label.setToolTip(t("status.ip.tooltip"))
        self._system_layout.addWidget(self._ip_label)

        # Spacer
        self._system_layout.addWidget(QFrame())

        # File count label
        self._count_label = QLabel("Files: 0")
        self._count_label.setToolTip(t("status.count.tooltip"))
        self._system_layout.addWidget(self._count_label)

        # Directory status label
        self._dir_status_label = QLabel("")
        self._dir_status_label.setToolTip(t("status.dir_status.tooltip"))
        self._system_layout.addWidget(self._dir_status_label)

        # Add permanent widgets
        self.addPermanentWidget(self._system_widget)
        self.addPermanentWidget(self._links_widget)

        # Update system info
        self._update_system_info()

    def _on_refresh_click(self) -> None:
        """Handle refresh button click."""
        if self._on_refresh_click:
            self._on_refresh_click()

    def _on_theme_toggle(self) -> None:
        """Handle theme toggle button click."""
        if self._on_theme_toggle:
            self._on_theme_toggle()

    def _update_system_info(self) -> None:
        """Update system info labels from collect_system_info()."""
        info = collect_system_info()
        self._user_label.setText(f"User: {info.username}")
        self._host_label.setText(f"Host: {info.hostname}")
        self._ip_label.setText(f"IP: {info.ip}")

    def update_file_count(self, count: int, dir_status: str = "") -> None:
        """Update file count display with optional flash animation.

        Args:
            count: Number of files.
            dir_status: Optional directory status text.
        """
        self._count_label.setText(f"Files: {count}")
        if dir_status:
            self._dir_status_label.setText(dir_status)
        self._flash_count = count
        self._trigger_flash()

    def _trigger_flash(self) -> None:
        """Trigger flash animation on count label."""
        self._count_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self._flash_timer.start(300)

    def _clear_flash(self) -> None:
        """Clear flash animation."""
        self._count_label.setStyleSheet("")

    def set_scanning(self, scanning: bool) -> None:
        """Set scanning state.

        Args:
            scanning: True if scanning, False otherwise.
        """
        if scanning:
            self._count_label.setText(t("count_patterns.scanning"))
        else:
            self._count_label.setText(f"Files: {self._flash_count}")

    def set_directory_status(self, status: str) -> None:
        """Set directory status text.

        Args:
            status: Status text to display.
        """
        self._dir_status_label.setText(status)

    def update_theme_label(self, label: str) -> None:
        """Update the theme button label.

        Args:
            label: New text for the theme button.
        """
        self._theme_btn.setText(label)

    def update_language_label(self) -> None:
        """Refresh the language button label from the current language."""
        if self._language_btn is not None:
            self._language_btn.setText(LANGUAGE_LABELS.get(current_language(), "🌐"))

    def _apply_text(self, lang: str | None = None) -> None:
        """Re-label all translatable widgets in the status bar.

        Args:
            lang: Ignored; t() reads the current language. Present so
                this method matches the i18n registry callback signature.
        """
        del lang  # Intentionally unused - matches i18n callback signature

        # Update link/button texts
        self._config_link.setText(f"<a href='#'>{t('status.config')}</a>")
        self._refresh_btn.setText(t("status.refresh"))
        self._log_link.setText(f"<a href='#'>{t('status.log')}</a>")
        if self._shortcuts_btn is not None:
            self._shortcuts_btn.setText(t("status.shortcuts"))

        # Update tooltips
        self._config_link.setToolTip(t("status.config.tooltip"))
        self._refresh_btn.setToolTip(t("status.refresh.tooltip"))
        self._log_link.setToolTip(t("status.log.tooltip"))
        if self._shortcuts_btn is not None:
            self._shortcuts_btn.setToolTip(t("status.shortcuts.tooltip"))
        self._theme_btn.setToolTip(t("status.theme.tooltip"))
        if self._language_btn is not None:
            self._language_btn.setToolTip(t("status.language.tooltip"))
        self._user_label.setToolTip(t("status.user.tooltip"))
        self._host_label.setToolTip(t("status.host.tooltip"))
        self._ip_label.setToolTip(t("status.ip.tooltip"))
        self._count_label.setToolTip(t("status.count.tooltip"))
        self._dir_status_label.setToolTip(t("status.dir_status.tooltip"))

        # Update labels with system info
        info = collect_system_info()
        self._user_label.setText(f"{t('status.user')} {info.username}")
        self._host_label.setText(f"{t('status.host')} {info.hostname}")
        self._ip_label.setText(f"{t('status.ip')} {info.ip}")

        # Update language button
        self.update_language_label()
