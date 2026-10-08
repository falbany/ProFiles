"""Qt context menu builder for ProFiles file list."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QMenu

from profiles.core.actions import reveal_in_file_manager


class ContextMenu(QMenu):
    """Context menu for file list items.

    Provides actions: Copy Path, Copy Name, Open, Refresh, Reveal in Explorer.
    Emits signals for decoupled interaction with MainWindow.
    """

    copy_path_triggered = Signal(str)
    copy_name_triggered = Signal(str)
    open_triggered = Signal(str, str)
    refresh_triggered = Signal()
    reveal_triggered = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._file_path: str = ""
        self._filename: str = ""
        self._directory: str = ""

    def build_for_file(
        self,
        file_path: str,
        filename: str,
        directory: str,
    ) -> ContextMenu:
        """Build context menu for a specific file.

        Args:
            file_path: Full path to the file.
            filename: Name of the file.
            directory: Parent directory path.

        Returns:
            Self for method chaining.
        """
        self.clear()
        self._file_path = file_path
        self._filename = filename
        self._directory = directory

        # Copy Path
        self.addAction("Copy Path", self._on_copy_path)

        # Copy Name
        self.addAction("Copy Name", self._on_copy_name)

        # Separator
        self.addSeparator()

        # Open
        self.addAction("Open", self._on_open)

        # Reveal in Explorer
        self.addAction("Reveal in Explorer", self._on_reveal)

        # Separator
        self.addSeparator()

        # Refresh
        self.addAction("Refresh", self._on_refresh)

        return self

    def _on_copy_path(self) -> None:
        """Copy full file path to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._file_path)
        self.copy_path_triggered.emit(self._file_path)

    def _on_copy_name(self) -> None:
        """Copy filename to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._filename)
        self.copy_name_triggered.emit(self._filename)

    def _on_open(self) -> None:
        """Launch file with OS default association."""
        # Emit signal - MainWindow handles actual launch
        self.open_triggered.emit(self._directory, self._filename)

    def _on_reveal(self) -> None:
        """Reveal file in system file manager."""
        path = Path(self._file_path)
        result = reveal_in_file_manager(path)
        if result.status.value == "success":
            self.reveal_triggered.emit(self._file_path)

    def _on_refresh(self) -> None:
        """Trigger rescan signal."""
        self.refresh_triggered.emit()


def build_context_menu(parent=None, file_path: str = "", filename: str = "") -> ContextMenu:
    """Factory function to create a context menu for a file.

    Args:
        parent: Parent widget for the menu.
        file_path: Full path to the file.
        filename: Name of the file.

    Returns:
        Configured ContextMenu instance.
    """
    menu = ContextMenu(parent)
    # Extract directory from file_path
    path = Path(file_path)
    directory = str(path.parent) if path.parent else ""
    return menu.build_for_file(file_path, filename, directory)
