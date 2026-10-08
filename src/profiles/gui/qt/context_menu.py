"""Qt context menu builder for ProFiles file list.

Extends to match all Tkinter context menu actions:
- Launch with args
- Open folder
- Open terminal
- Filter to folder/ext
- Copy variants (full path, forward slashes, name w/o ext, directory, URI)
- Hash MD5/SHA256, Verify hash
- Properties dialog
- Delete with confirmation
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMenu,
    QMessageBox,
)

from profiles.core.actions import reveal_in_file_manager
from profiles.utils.file_utils import hash_file, launch_file, open_file_explorer


def open_terminal_in_directory(directory: Path) -> bool:
    """Open a terminal in the given directory.

    Args:
        directory: Directory to open terminal in.

    Returns:
        True if successful, False otherwise.
    """
    try:
        if not directory.is_dir():
            return False
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/k", "cd", "/d", str(directory)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        elif sys.platform == "darwin":
            subprocess.run(
                ["open", "-a", "Terminal", str(directory)],
                check=True,
            )
        else:
            # Linux - try common terminals
            for term in ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"]:
                try:
                    subprocess.run([term, "--working-directory", str(directory)], check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except Exception:
        return False


class ContextMenu(QMenu):
    """Context menu for file list items.

    Provides all actions matching Tkinter context menu:
    - Launch, Launch with args
    - Open folder, Reveal in Explorer, Open terminal
    - Filter to folder, Filter by extension
    - Copy: full path, forward slashes, name w/ext, name w/o ext, directory, URI
    - Hash: MD5, SHA256, copy MD5, copy SHA256, verify MD5, verify SHA256
    - Properties, Delete with confirmation, Refresh
    """

    copy_path_triggered = Signal(str)
    copy_name_triggered = Signal(str)
    open_triggered = Signal(str, str)
    refresh_triggered = Signal()
    reveal_triggered = Signal(str)
    delete_triggered = Signal(str)
    filter_folder_triggered = Signal(str)
    filter_extension_triggered = Signal(str)
    open_folder_triggered = Signal(str)
    open_terminal_triggered = Signal(str)
    properties_triggered = Signal(str)
    launch_triggered = Signal(str, str)
    launch_with_args_triggered = Signal(str, str, str)
    hash_triggered = Signal(str, str, str)  # path, algorithm, digest
    verify_hash_triggered = Signal(str, str, bool)  # path, algorithm, match

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
        file_path_obj = Path(file_path)

        # --- Primary action -----------------------------------------
        self.addAction("▶  Launch", self._on_launch)
        self.addAction("🚀  Launch with args", self._on_launch_with_args)
        self.addSeparator()

        # --- Open folder / Reveal / Terminal ------------------------
        self.addAction("📂  Reveal in Explorer", self._on_reveal)
        self.addAction("📁  Open folder", self._on_open_folder)
        self.addAction("🖥  Open terminal", self._on_open_terminal)
        self.addSeparator()

        # --- Filter actions -----------------------------------------
        self.addAction("🔎  Filter to folder", self._on_filter_to_folder)
        self.addAction("🔎  Filter by extension", self._on_filter_by_extension)
        self.addSeparator()

        # --- Copy submenu -------------------------------------------
        copy_menu = QMenu("📋  Copy", self)
        copy_menu.addAction("Full path", self._on_copy_path)
        copy_menu.addAction("Forward slashes", self._on_copy_path_forward_slashes)
        copy_menu.addAction("Name with extension", self._on_copy_name_with_ext)
        copy_menu.addAction("Name without extension", self._on_copy_name_without_ext)
        copy_menu.addAction("Directory", self._on_copy_directory)
        copy_menu.addSeparator()
        copy_menu.addAction("URI (file://)", self._on_copy_uri)
        self.addMenu(copy_menu)
        self.addSeparator()

        # --- Hash submenu -------------------------------------------
        hash_menu = QMenu("#  Hash", self)
        hash_menu.addAction("MD5 (show)", lambda: self._on_hash("md5", show=True))
        hash_menu.addAction("SHA256 (show)", lambda: self._on_hash("sha256", show=True))
        hash_menu.addSeparator()
        hash_menu.addAction("Copy MD5", lambda: self._on_hash("md5", copy_only=True))
        hash_menu.addAction("Copy SHA256", lambda: self._on_hash("sha256", copy_only=True))
        hash_menu.addSeparator()
        hash_menu.addAction("✅ Verify MD5", lambda: self._on_verify_hash("md5"))
        hash_menu.addAction("✅ Verify SHA256", lambda: self._on_verify_hash("sha256"))
        self.addMenu(hash_menu)
        self.addSeparator()

        # --- Info + utility -----------------------------------------
        self.addAction("ℹ  Properties", self._on_properties)
        self.addAction("🗑  Delete", self._on_delete)
        self.addSeparator()
        self.addAction("🔄 Refresh", self._on_refresh)

        return self

    def _on_copy_path(self) -> None:
        """Copy full file path to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._file_path)
        self.copy_path_triggered.emit(self._file_path)

    def _on_copy_path_forward_slashes(self) -> None:
        """Copy full file path with forward slashes to clipboard."""
        path = self._file_path.replace("\\", "/")
        clipboard = QApplication.clipboard()
        clipboard.setText(path)
        self.copy_path_triggered.emit(path)

    def _on_copy_name_with_ext(self) -> None:
        """Copy filename with extension to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._filename)
        self.copy_name_triggered.emit(self._filename)

    def _on_copy_name_without_ext(self) -> None:
        """Copy filename without extension to clipboard."""
        path = Path(self._filename)
        name = path.stem
        clipboard = QApplication.clipboard()
        clipboard.setText(name)
        self.copy_name_triggered.emit(name)

    def _on_copy_directory(self) -> None:
        """Copy directory path to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._directory)
        self.copy_path_triggered.emit(self._directory)

    def _on_copy_uri(self) -> None:
        """Copy file:// URI to clipboard."""
        try:
            uri = Path(self._file_path).as_uri()
            clipboard = QApplication.clipboard()
            clipboard.setText(uri)
        except ValueError:
            QMessageBox.warning(self, "URI Error", "Cannot build URI for this path")

    def _on_launch(self) -> None:
        """Launch file with OS default association."""
        path = Path(self._file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file does not exist:\n{self._file_path}"
            )
            return
        if launch_file(self._file_path):
            self.launch_triggered.emit(self._directory, self._filename)
        else:
            QMessageBox.error(self, "Launch Error", f"Failed to launch file:\n{self._file_path}")

    def _on_launch_with_args(self) -> None:
        """Prompt for arguments then launch file with them."""
        path = Path(self._file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file does not exist:\n{self._file_path}"
            )
            return
        args, ok = QInputDialog.getText(self, "Launch with Arguments", "Enter arguments:")
        if ok and args:
            try:
                import shlex

                tokens = shlex.split(args)
                if sys.platform == "win32":
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", self._file_path] + tokens,
                    )
                else:
                    subprocess.Popen([self._file_path] + tokens)
                self.launch_with_args_triggered.emit(self._directory, self._filename, args)
            except Exception as e:
                QMessageBox.error(self, "Launch Error", f"Failed to launch: {e}")

    def _on_open_folder(self) -> None:
        """Open the file's parent directory in file explorer."""
        parent = Path(self._file_path).parent
        if not parent.is_dir():
            QMessageBox.warning(self, "Folder Not Found", f"The folder does not exist:\n{parent}")
            return
        if open_file_explorer(str(parent)):
            self.open_folder_triggered.emit(str(parent))
        else:
            QMessageBox.error(self, "Open Folder Error", f"Failed to open folder:\n{parent}")

    def _on_reveal(self) -> None:
        """Reveal file in system file manager."""
        result = reveal_in_file_manager(Path(self._file_path))
        if result.status.value == "success":
            self.reveal_triggered.emit(self._file_path)
        elif result.status.value == "not_found":
            QMessageBox.warning(self, "File Not Found", result.message)
        else:
            # Fallback: open parent folder
            open_file_explorer(self._directory)

    def _on_open_terminal(self) -> None:
        """Open terminal in the file's parent directory."""
        parent = Path(self._file_path).parent
        if not parent.is_dir():
            QMessageBox.warning(self, "Folder Not Found", f"The folder does not exist:\n{parent}")
            return
        if open_terminal_in_directory(parent):
            self.open_terminal_triggered.emit(str(parent))
        else:
            QMessageBox.error(self, "Open Terminal Error", "Failed to open terminal")

    def _on_filter_to_folder(self) -> None:
        """Emit signal to filter to the file's parent folder."""
        parent = str(Path(self._file_path).parent)
        self.filter_folder_triggered.emit(parent)

    def _on_filter_by_extension(self) -> None:
        """Emit signal to filter by the file's extension."""
        ext = Path(self._filename).suffix
        if not ext:
            QMessageBox.warning(
                self, "No Extension", f"Selected file has no extension:\n{self._filename}"
            )
            return
        self.filter_extension_triggered.emit(ext)

    def _on_hash(self, algorithm: str, show: bool = False, copy_only: bool = False) -> None:
        """Compute and display/copy file hash."""
        path = Path(self._file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file does not exist:\n{self._file_path}"
            )
            return
        try:
            digest = hash_file(self._file_path, algorithm)
            self.hash_triggered.emit(self._file_path, algorithm, digest)
            if copy_only:
                clipboard = QApplication.clipboard()
                clipboard.setText(digest)
            elif show:
                QMessageBox.information(
                    self,
                    f"{algorithm.upper()} Hash",
                    f"File: {self._filename}\nPath: {self._file_path}\n\n{algorithm.upper()}: {digest}",
                )
        except (OSError, ValueError) as e:
            QMessageBox.error(self, "Hash Error", f"Failed to hash file:\n{e}")

    def _on_verify_hash(self, algorithm: str) -> None:
        """Verify file hash against clipboard content."""
        path = Path(self._file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file does not exist:\n{self._file_path}"
            )
            return
        clipboard = QApplication.clipboard()
        expected = clipboard.text().strip()
        if not expected:
            QMessageBox.information(
                self,
                f"Verify {algorithm.upper()}",
                "Clipboard is empty — copy a hash first, then try again.",
            )
            return
        try:
            digest = hash_file(self._file_path, algorithm)
            match = digest.casefold() == expected.casefold()
            self.verify_hash_triggered.emit(self._file_path, algorithm, match)
            if match:
                QMessageBox.information(
                    self,
                    f"Verify {algorithm.upper()}",
                    f"✅  Match!\n\n{algorithm.upper()}: {digest}",
                )
            else:
                QMessageBox.critical(
                    self,
                    f"Verify {algorithm.upper()}",
                    f"❌  Mismatch\n\nFile:      {digest}\nClipboard: {expected}",
                )
        except (OSError, ValueError) as e:
            QMessageBox.error(self, "Hash Error", f"Failed to hash file:\n{e}")

    def _on_properties(self) -> None:
        """Show file properties dialog."""
        path = Path(self._file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file does not exist:\n{self._file_path}"
            )
            return
        try:
            stat = path.stat()
            size_kb = stat.st_size / 1024
            text = (
                f"File: {path.name}\n"
                f"Path: {self._file_path}\n\n"
                f"Size: {stat.st_size:,} bytes ({size_kb:.1f} KB)\n"
                f"Modified: {stat.st_mtime}\n"
                f"Created: {stat.st_ctime}"
            )
            QMessageBox.information(self, "File Properties", text)
            self.properties_triggered.emit(self._file_path)
        except OSError as e:
            QMessageBox.error(self, "Properties Error", f"Failed to read file info:\n{e}")

    def _on_delete(self) -> None:
        """Delete file after confirmation."""
        path = Path(self._file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found", f"The file does not exist:\n{self._file_path}"
            )
            return
        reply = QMessageBox.question(
            self,
            "Delete File",
            f"Are you sure you want to delete this file?\n\n"
            f"{self._file_path}\n\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                path.unlink()
                self.delete_triggered.emit(self._file_path)
                QMessageBox.information(
                    self, "File Deleted", f"File deleted successfully:\n{self._file_path}"
                )
            except OSError as e:
                QMessageBox.error(self, "Delete Error", f"Failed to delete file:\n{e}")

    def _on_refresh(self) -> None:
        """Trigger refresh signal."""
        self.refresh_triggered.emit()

    def all_actions(self) -> list:
        """Return all actions in the menu (including submenu actions)."""
        result = []
        for action in QMenu.actions(self):
            if action.menu():
                result.extend(action.menu().actions())
            else:
                result.append(action)
        return result


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
    path = Path(file_path)
    directory = str(path.parent) if path.parent else ""
    return menu.build_for_file(file_path, filename, directory)
