"""Status bar management for ProFiles.

Provides a dedicated status bar component with tooltips for user,
hostname, IP, directory, and file count information.
"""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk

from profiles.gui.i18n import LANGUAGE_LABELS, current_language, register, t
from profiles.gui.styles import ToolTip


class StatusBar:
    """Status bar component for the main window.

    Displays system information (user, host, IP) and scan status
    (directory, file count) with hover tooltips for each label.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        on_config_click: tk.Callable[[], None],
        on_refresh_click: tk.Callable[[], None],
        on_log_click: tk.Callable[[], None],
        on_theme_toggle: tk.Callable[[], None],
        theme_label: str = "☀ Light",
        on_shortcuts_click: tk.Callable[[], None] | None = None,
        on_language_toggle: tk.Callable[[], None] | None = None,
    ) -> None:
        """Initialize the status bar.

        Args:
            parent: Parent frame to attach the status bar to.
            on_config_click: Callback for config button.
            on_refresh_click: Callback for refresh button.
            on_log_click: Callback for log button.
            on_theme_toggle: Callback for theme toggle button.
            theme_label: Initial text for theme button.
            on_shortcuts_click: Optional callback for shortcuts button.
            on_language_toggle: Optional callback for language toggle button.
        """
        self._parent = parent
        self._on_config_click = on_config_click
        self._on_refresh_click = on_refresh_click
        self._on_log_click = on_log_click
        self._on_theme_toggle = on_theme_toggle
        self._on_shortcuts_click = on_shortcuts_click
        self._on_language_toggle = on_language_toggle
        self._theme_label = theme_label

        # Widget references
        self._status_frame: ttk.Frame
        self._status_inner: ttk.Frame
        self._config_link: ttk.Button
        self._refresh_btn: ttk.Button
        self._log_link: ttk.Button
        self._shortcuts_btn: ttk.Button | None
        self._theme_btn: ttk.Button
        self._language_btn: ttk.Button | None
        self._user_label: ttk.Label
        self._host_label: ttk.Label
        self._ip_label: ttk.Label
        self._count_label: ttk.Label
        self._dir_status_label: ttk.Label

        # Translatable widget refs (set in _build, updated in _apply_text)
        self._user_label_text: ttk.Label | None = None
        self._host_label_text: ttk.Label | None = None
        self._ip_label_text: ttk.Label | None = None
        self._config_tooltip: ToolTip | None = None
        self._refresh_tooltip: ToolTip | None = None
        self._log_tooltip: ToolTip | None = None
        self._shortcuts_tooltip: ToolTip | None = None
        self._theme_tooltip: ToolTip | None = None
        self._language_tooltip: ToolTip | None = None
        self._user_tooltip: ToolTip | None = None
        self._host_tooltip: ToolTip | None = None
        self._ip_tooltip: ToolTip | None = None
        self._count_tooltip: ToolTip | None = None
        self._dir_status_tooltip: ToolTip | None = None

        self._build()
        register(self._apply_text)

    def _build(self) -> None:
        """Build the status bar widgets."""
        # Outer frame
        self._status_frame = ttk.Frame(
            self._parent,
            style="Status.TFrame",
        )
        self._status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_inner = ttk.Frame(
            self._status_frame,
            style="Status.TFrame",
            padding=(10, 4),
        )
        self._status_inner.pack(fill=tk.X)

        # Config link
        self._config_link = ttk.Button(
            self._status_inner,
            text=t("status.config"),
            style="Theme.TButton",
            command=self._on_config_click,
        )
        self._config_link.pack(side=tk.LEFT, padx=(0, 4))
        self._config_tooltip = ToolTip(self._config_link, t("status.config.tooltip"))

        # Refresh button
        self._refresh_btn = ttk.Button(
            self._status_inner,
            text=t("status.refresh"),
            style="Theme.TButton",
            command=self._on_refresh_click,
        )
        self._refresh_btn.pack(side=tk.LEFT, padx=(4, 8))
        self._refresh_tooltip = ToolTip(self._refresh_btn, t("status.refresh.tooltip"))

        # Log link
        self._log_link = ttk.Button(
            self._status_inner,
            text=t("status.log"),
            style="Theme.TButton",
            command=self._on_log_click,
        )
        self._log_link.pack(side=tk.LEFT, padx=(0, 10))
        self._log_tooltip = ToolTip(self._log_link, t("status.log.tooltip"))

        # Shortcuts button (optional)
        self._shortcuts_btn = None
        if self._on_shortcuts_click is not None:
            self._shortcuts_btn = ttk.Button(
                self._status_inner,
                text=t("status.shortcuts"),
                style="Theme.TButton",
                command=self._on_shortcuts_click,
            )
            self._shortcuts_btn.pack(side=tk.LEFT, padx=(0, 4))
            self._shortcuts_tooltip = ToolTip(
                self._shortcuts_btn,
                t("status.shortcuts.tooltip"),
            )
        else:
            self._shortcuts_tooltip = None

        # Theme toggle button
        self._theme_btn = ttk.Button(
            self._status_inner,
            text=self._theme_label,
            style="Theme.TButton",
            command=self._on_theme_toggle,
        )
        self._theme_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._theme_tooltip = ToolTip(self._theme_btn, t("status.theme.tooltip"))

        # Language toggle button (optional)
        self._language_btn = None
        if self._on_language_toggle is not None:
            self._language_btn = ttk.Button(
                self._status_inner,
                text=LANGUAGE_LABELS.get(current_language(), "\U0001f310"),
                style="Theme.TButton",
                command=self._on_language_toggle,
            )
            self._language_btn.pack(side=tk.LEFT, padx=(0, 12))
            self._language_tooltip = ToolTip(
                self._language_btn,
                t("status.language.tooltip"),
            )
        else:
            self._language_tooltip = None

        # Separator
        ttk.Separator(self._status_inner, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # User label with tooltip
        self._user_label_text = ttk.Label(
            self._status_inner,
            text=t("status.user"),
            style="Info.TLabel",
        )
        self._user_label_text.pack(side=tk.LEFT, padx=(4, 2))
        self._user_label = ttk.Label(
            self._status_inner,
            text="...",
            style="Value.TLabel",
            anchor=tk.W,
        )
        self._user_label.pack(side=tk.LEFT, padx=(0, 8))
        self._user_tooltip = ToolTip(self._user_label, t("status.user.tooltip"))

        # Host label with tooltip
        self._host_label_text = ttk.Label(
            self._status_inner,
            text=t("status.host"),
            style="Info.TLabel",
        )
        self._host_label_text.pack(side=tk.LEFT, padx=(4, 2))
        self._host_label = ttk.Label(
            self._status_inner,
            text="...",
            style="Value.TLabel",
            anchor=tk.W,
        )
        self._host_label.pack(side=tk.LEFT, padx=(0, 8))
        self._host_tooltip = ToolTip(self._host_label, t("status.host.tooltip"))

        # IP label with tooltip
        self._ip_label_text = ttk.Label(
            self._status_inner,
            text=t("status.ip"),
            style="Info.TLabel",
        )
        self._ip_label_text.pack(side=tk.LEFT, padx=(0, 8))
        self._ip_label = ttk.Label(
            self._status_inner,
            text="...",
            style="Value.TLabel",
            anchor=tk.W,
        )
        self._ip_label.pack(side=tk.LEFT, padx=(0, 8))
        self._ip_tooltip = ToolTip(self._ip_label, t("status.ip.tooltip"))

        # File count label with tooltip
        self._count_label = ttk.Label(
            self._status_inner,
            text="Files: 0",
            style="Info.TLabel",
        )
        self._count_label.pack(side=tk.RIGHT, padx=(10, 0))
        self._count_tooltip = ToolTip(self._count_label, t("status.count.tooltip"))

        # Directory status label with tooltip
        self._dir_status_label = ttk.Label(
            self._status_inner,
            text="",
            style="Info.TLabel",
        )
        self._dir_status_label.pack(side=tk.RIGHT, padx=(10, 10))
        self._dir_status_tooltip = ToolTip(
            self._dir_status_label,
            t("status.dir_status.tooltip"),
        )

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    @property
    def status_frame(self) -> ttk.Frame:
        """Get the outer status bar frame."""
        return self._status_frame

    @property
    def status_inner(self) -> ttk.Frame:
        """Get the inner status bar container."""
        return self._status_inner

    @property
    def config_link(self) -> ttk.Button:
        """Get the config button."""
        return self._config_link

    @property
    def refresh_btn(self) -> ttk.Button:
        """Get the refresh button."""
        return self._refresh_btn

    @property
    def log_link(self) -> ttk.Button:
        """Get the log button."""
        return self._log_link

    @property
    def theme_btn(self) -> ttk.Button:
        """Get the theme toggle button."""
        return self._theme_btn

    @property
    def language_btn(self) -> ttk.Button | None:
        """Get the language toggle button, if created."""
        return self._language_btn

    @property
    def shortcuts_btn(self) -> ttk.Button | None:
        """Get the shortcuts button, if created."""
        return self._shortcuts_btn

    @property
    def user_label(self) -> ttk.Label:
        """Get the user label."""
        return self._user_label

    @property
    def host_label(self) -> ttk.Label:
        """Get the host label."""
        return self._host_label

    @property
    def ip_label(self) -> ttk.Label:
        """Get the IP label."""
        return self._ip_label

    @property
    def count_label(self) -> ttk.Label:
        """Get the file count label."""
        return self._count_label

    @property
    def dir_status_label(self) -> ttk.Label:
        """Get the directory status label."""
        return self._dir_status_label

    @property
    def dir_status_tooltip(self) -> ToolTip | None:
        """Get the directory status tooltip."""
        return self._dir_status_tooltip

    def update_theme_label(self, label: str) -> None:
        """Update the theme button label.

        Args:
            label: New text for the theme button.
        """
        self._theme_btn.configure(text=label)
        self._theme_btn.update_idletasks()

    def update_language_label(self) -> None:
        """Refresh the language button label from the current language."""
        if self._language_btn is not None:
            self._language_btn.configure(
                text=LANGUAGE_LABELS.get(current_language(), "\U0001f310"),
            )
            self._language_btn.update_idletasks()

    def _apply_text(self, lang: str | None = None) -> None:
        """Re-label all translatable widgets in the status bar.

        Args:
            lang: Ignored; ``t()`` reads the current language. Present so
                this method matches the i18n registry callback signature.
        """
        with contextlib.suppress(tk.TclError):
            self._config_link.configure(text=t("status.config"))
            self._refresh_btn.configure(text=t("status.refresh"))
            self._log_link.configure(text=t("status.log"))
            if self._shortcuts_btn is not None:
                self._shortcuts_btn.configure(text=t("status.shortcuts"))
            if self._user_label_text is not None:
                self._user_label_text.configure(text=t("status.user"))
            if self._host_label_text is not None:
                self._host_label_text.configure(text=t("status.host"))
            if self._ip_label_text is not None:
                self._ip_label_text.configure(text=t("status.ip"))
            if self._config_tooltip is not None:
                self._config_tooltip.set_text(t("status.config.tooltip"))
            if self._refresh_tooltip is not None:
                self._refresh_tooltip.set_text(t("status.refresh.tooltip"))
            if self._log_tooltip is not None:
                self._log_tooltip.set_text(t("status.log.tooltip"))
            if self._shortcuts_tooltip is not None:
                self._shortcuts_tooltip.set_text(t("status.shortcuts.tooltip"))
            if self._theme_tooltip is not None:
                self._theme_tooltip.set_text(t("status.theme.tooltip"))
            if self._language_tooltip is not None:
                self._language_tooltip.set_text(t("status.language.tooltip"))
            if self._user_tooltip is not None:
                self._user_tooltip.set_text(t("status.user.tooltip"))
            if self._host_tooltip is not None:
                self._host_tooltip.set_text(t("status.host.tooltip"))
            if self._ip_tooltip is not None:
                self._ip_tooltip.set_text(t("status.ip.tooltip"))
            if self._count_tooltip is not None:
                self._count_tooltip.set_text(t("status.count.tooltip"))
            if self._dir_status_tooltip is not None:
                self._dir_status_tooltip.set_text(t("status.dir_status.tooltip"))
            self.update_language_label()
