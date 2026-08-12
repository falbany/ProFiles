"""Context menu helper for MainWindow."""

# pylint: disable=protected-access

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from functools import partial
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING

from profiles.core import actions
from profiles.core.actions import ActionStatus
from profiles.core.processing.file_classifier import ensure_trailing_separator
from profiles.gui.i18n import t
from profiles.utils.file_utils import hash_file, open_file_explorer
from profiles.utils.network import get_username

if TYPE_CHECKING:
    from profiles.gui.main_window import MainWindow


class FileContextMenu:
    """Helper class to build and manage the context menu for MainWindow."""

    def __init__(self, window: MainWindow) -> None:
        """Initialize the context menu helper.

        Args:
            window: The parent MainWindow instance.
        """
        self.window = window

    def _make_menu(self, parent: tk.Misc) -> tk.Menu:
        """Build a tk.Menu themed to match the active palette.

        Args:
            parent: Parent widget (root for the top menu, parent menu for submenus).

        Returns:
            A themed ``tk.Menu`` instance.
        """
        theme = self.window._theme
        return tk.Menu(
            parent,
            tearoff=0,
            bg=theme.surface,
            fg=theme.on_surface,
            activebackground=theme.primary,
            activeforeground=theme.on_primary,
            bd=1,
            relief="flat",
        )

    def selected_file_path(self) -> Path | None:
        """Resolve the full filesystem path of the currently selected file.

        Returns:
            The full path to the selected file, or None if the selection
            is empty or the directory has not been populated.
        """
        selection = self.window._tree.selection()
        if not selection:
            return None
        values = self.window._tree.item(selection[0], "values")
        if not values or len(values) < 2:
            return None
        directory = self.window._dir_var.get().strip()
        if not directory:
            return None
        return Path(ensure_trailing_separator(directory)) / values[0]

    def on_tree_right_click(self, event: tk.Event) -> None:
        """Show the right-click context menu for the row under the cursor.

        Args:
            event: The Tkinter event triggering the context menu.
        """
        row = self.window._tree.identify_row(event.y)
        if row:
            # Select the row that was right-clicked (without clearing the
            # current multi-selection if multi-select is ever enabled).
            self.window._tree.selection_set(row)
            self.window._tree.focus(row)
        else:
            # Right-clicked empty area → bail out, do not show a menu.
            return

        file_path = self.selected_file_path()
        if file_path is None:
            return

        menu = self._make_menu(self.window._root)

        # --- Top: primary action ------------------------------------
        menu.add_command(
            label=f"▶  {t('menu.launch')} {file_path.name}",
            command=partial(self.action_launch, file_path),
        )
        menu.add_command(
            label=f"🚀  {t('menu.launch_args')}",
            command=partial(self.action_launch_with_args, file_path),
        )
        menu.add_separator()

        # --- Open folder --------------------------------------------
        menu.add_command(
            label=f"📂  {t('menu.reveal')}",
            command=partial(self.action_reveal, file_path),
        )
        menu.add_command(
            label=f"📁  {t('menu.open_folder')}",
            command=partial(self.action_open_folder, file_path),
        )
        menu.add_command(
            label=f"🖥  {t('menu.terminal')}",
            command=partial(self.action_open_terminal, file_path),
        )
        menu.add_separator()

        # --- Filter  --------------------------------------------
        menu.add_command(
            label=f"🔎  {t('menu.filter_folder')}",
            command=partial(self.action_filter_to_folder, file_path),
        )
        menu.add_command(
            label=f"🔎  {t('menu.filter_extension')}",
            command=partial(self.action_filter_by_extension, file_path),
        )
        menu.add_separator()

        # --- Copy actions -------------------------------------------
        copy_menu = self._make_menu(menu)
        copy_menu.add_command(
            label=t("menu.copy.full"),
            command=partial(self.action_copy_path, file_path),
        )
        copy_menu.add_command(
            label=t("menu.copy.forward"),
            command=partial(self.action_copy_path, file_path, forward_slashes=True),
        )
        copy_menu.add_command(
            label=t("menu.copy.name_w_ext"),
            command=partial(self.action_copy_name, file_path, with_ext=True),
        )
        copy_menu.add_command(
            label=t("menu.copy.name_wo_ext"),
            command=partial(self.action_copy_name, file_path, with_ext=False),
        )
        copy_menu.add_command(
            label=t("menu.copy.directory"),
            command=partial(self.action_copy, str(file_path.parent)),
        )
        copy_menu.add_separator()
        copy_menu.add_command(
            label=f"🔗  {t('menu.copy.uri')}",
            command=partial(self.action_copy_uri, file_path),
        )
        menu.add_cascade(label=f"📋  {t('menu.copy')}", menu=copy_menu)

        # --- Hash (compute + show + verify) --------------------------
        hash_menu = self._make_menu(menu)
        hash_menu.add_command(
            label=t("menu.hash.md5"),
            command=partial(self.action_hash, file_path, "md5"),
        )
        hash_menu.add_command(
            label=t("menu.hash.sha256"),
            command=partial(self.action_hash, file_path, "sha256"),
        )
        hash_menu.add_separator()
        hash_menu.add_command(
            label=t("menu.hash.copy_md5"),
            command=partial(self.action_hash, file_path, "md5", copy_only=True),
        )
        hash_menu.add_command(
            label=t("menu.hash.copy_sha256"),
            command=partial(self.action_hash, file_path, "sha256", copy_only=True),
        )
        hash_menu.add_separator()
        hash_menu.add_command(
            label=f"✅  {t('menu.hash.verify_md5')}",
            command=partial(self.action_verify_hash, file_path, "md5"),
        )
        hash_menu.add_command(
            label=f"✅  {t('menu.hash.verify_sha256')}",
            command=partial(self.action_verify_hash, file_path, "sha256"),
        )
        menu.add_cascade(label=f"#  {t('menu.hash')}", menu=hash_menu)
        menu.add_separator()

        # --- Info + utility ------------------------------------------
        menu.add_command(
            label=f"ℹ  {t('menu.properties')}",
            command=partial(self.action_properties, file_path),
        )
        menu.add_command(
            label=f"🗑  {t('menu.delete')}",
            command=partial(self.action_clear_file, file_path),
        )
        menu.add_command(
            label=f"🔄 {t('menu.refresh_list')}",
            command=self.window._refresh_file_list,
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def action_launch(self, file_path: Path) -> None:
        """Launch the given file using the OS default association."""
        result = actions.launch_selected_file(
            directory=str(file_path.parent),
            filename=file_path.name,
            release=self.window._config.release,
            username=get_username(),
            logger=self.window._logger,
            config=self.window._config,
        )
        if result.status is ActionStatus.NOT_FOUND:
            messagebox.showwarning(
                "File Not Found",
                f"The selected file does not exist:\n{file_path}",
            )
            return
        if result.status is ActionStatus.SUCCESS:
            if self.window._close_var.get():
                self.window._root.after(500, self.window._on_close)
            return
        messagebox.showerror("Execution Error", result.message)

    def action_launch_with_args(self, file_path: Path) -> None:
        """Prompt for arguments then launch *file_path* with them.

        Delegates to :meth:`MainWindow._action_launch_with_args` so the
        dialog and action-result presentation stay consistent with the
        rest of the GUI.
        """
        self.window._action_launch_with_args(file_path)

    def action_open_folder(self, file_path: Path) -> None:
        """Open the directory that contains *file_path*."""
        parent = file_path.parent
        if not parent.is_dir():
            messagebox.showwarning(
                "Folder Not Found",
                f"The folder does not exist:\n{parent}",
            )
            return
        if not open_file_explorer(parent):
            messagebox.showerror(
                "Open Folder Error",
                f"Failed to open folder:\n{parent}",
            )

    def action_reveal(self, file_path: Path) -> None:
        """Reveal the file in the OS file explorer."""
        if not file_path.exists():
            messagebox.showwarning(
                "File Not Found",
                f"The selected file does not exist:\n{file_path}",
            )
            return
        try:
            if sys.platform == "darwin":
                with subprocess.Popen(["open", "-R", str(file_path)]) as proc:
                    proc.wait()
            elif os.name == "nt":
                with subprocess.Popen(["explorer", f"/select,{file_path}"]) as proc:
                    proc.wait()
            else:
                open_file_explorer(file_path.parent)
        except OSError as exc:
            self.window._logger.error("Reveal failed: %s", exc)
            open_file_explorer(file_path.parent)

    def action_copy(self, value: str) -> None:
        """Copy *value* to the system clipboard."""
        self.window._root.clipboard_clear()
        self.window._root.clipboard_append(value)

    def action_copy_path(self, file_path: Path, *, forward_slashes: bool = False) -> None:
        """Copy the full file path to the clipboard."""
        text = str(file_path)
        if forward_slashes:
            text = text.replace("\\", "/")
        self.action_copy(text)

    def action_copy_name(self, file_path: Path, *, with_ext: bool = True) -> None:
        """Copy the file name (with or without extension) to the clipboard."""
        self.action_copy(file_path.name if with_ext else file_path.stem)

    def action_properties(self, file_path: Path) -> None:
        """Show a properties dialog for the file (size, dates, path)."""
        if not file_path.exists():
            messagebox.showwarning(
                "File Not Found",
                f"The selected file does not exist:\n{file_path}",
            )
            return
        try:
            stat = file_path.stat()
            size_kb = stat.st_size / 1024
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError as exc:
            messagebox.showerror("Properties Error", f"Failed to read file info:\n{exc}")
            return

        text = (
            f"File: {file_path.name}\n"
            f"Path: {file_path}\n\n"
            f"Size: {stat.st_size:,} bytes ({size_kb:.1f} KB)\n"
            f"Modified: {modified}\n"
            f"Created: {created}"
        )
        messagebox.showinfo("File Properties", text)

    def action_filter_to_folder(self, file_path: Path) -> None:
        """Switch the directory combobox to the file's parent folder."""
        parent = file_path.parent
        current_dir = self.window._dir_var.get()
        current = Path(current_dir) if current_dir else None
        if current is not None and parent == current:
            return
        if not parent.is_dir():
            messagebox.showwarning(
                "Folder Not Found",
                f"The folder does not exist:\n{parent}",
            )
            return
        self.window._dir_var.set(str(parent))
        self.window._apply_config_overrides()
        self.window._refresh_file_list()
        self.window._logger.info("Filtered list to folder: %s", parent)

    def action_hash(self, file_path: Path, algorithm: str, *, copy_only: bool = False) -> None:
        """Compute the file's hash, show a dialog, and optionally copy it."""
        if not file_path.exists():
            messagebox.showwarning(
                "File Not Found",
                f"The selected file does not exist:\n{file_path}",
            )
            return
        try:
            digest = hash_file(file_path, algorithm)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Hash Error", f"Failed to hash file:\n{exc}")
            return

        if copy_only:
            self.action_copy(digest)
            return

        messagebox.showinfo(
            f"{algorithm.upper()} Hash",
            f"File: {file_path.name}\nPath: {file_path}\n\n{algorithm.upper()}: {digest}",
        )

    def action_copy_uri(self, file_path: Path) -> None:
        """Copy a ``file://`` URI to the clipboard for the file."""
        try:
            uri = file_path.as_uri()
        except ValueError as exc:
            messagebox.showerror("URI Error", f"Cannot build URI:\n{exc}")
            return
        self.action_copy(uri)

    def action_filter_by_extension(self, file_path: Path) -> None:
        """Set the extension filter to ``.<ext>`` and re-scan the current folder."""
        ext = file_path.suffix
        if not ext:
            messagebox.showwarning(
                "No Extension",
                f"Selected file has no extension:\n{file_path.name}",
            )
            return
        self.window._ext_var.set(ext)
        self.window._refresh_file_list()
        self.window._logger.info("Filtered list by extension: %s", ext)

    def action_verify_hash(self, file_path: Path, algorithm: str) -> None:
        """Compute the file's *algorithm* hash and compare it to the clipboard."""
        if not file_path.exists():
            messagebox.showwarning(
                "File Not Found",
                f"The selected file does not exist:\n{file_path}",
            )
            return
        try:
            expected_clip = self.window._root.clipboard_get().strip()
        except tk.TclError:
            expected_clip = ""
        if not expected_clip:
            messagebox.showinfo(
                f"Verify {algorithm.upper()}",
                "Clipboard is empty — copy a hash first, then try again.",
            )
            return
        try:
            digest = hash_file(file_path, algorithm)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Hash Error", f"Failed to hash file:\n{exc}")
            return

        match = digest.casefold() == expected_clip.casefold()
        if match:
            messagebox.showinfo(
                f"Verify {algorithm.upper()}",
                f"✅  Match!\n\n{algorithm.upper()}: {digest}",
            )
        else:
            messagebox.showerror(
                f"Verify {algorithm.upper()}",
                f"❌  Mismatch\n\nFile:    {digest}\nClipboard: {expected_clip}",
            )

    def action_open_terminal(self, file_path: Path) -> None:
        """Open a terminal session in the file's parent directory."""
        parent = file_path.parent
        if not parent.is_dir():
            messagebox.showwarning(
                "Folder Not Found",
                f"The folder does not exist:\n{parent}",
            )
            return
        try:
            if sys.platform == "darwin":
                with subprocess.Popen(["open", "-a", "Terminal", str(parent)]):
                    pass
            elif os.name == "nt":
                with subprocess.Popen(
                    ["cmd", "/c", "start", "cmd", "/K", f"cd /D {parent}"],
                ):
                    pass
            else:
                # Best-effort: try a few common Linux terminals in order.
                opener = None
                for cmd in (
                    ["x-terminal-emulator", "--working-directory", str(parent)],
                    ["gnome-terminal", "--working-directory", str(parent)],
                    ["konsole", "--workdir", str(parent)],
                    ["xfce4-terminal", "--working-directory", str(parent)],
                ):
                    if shutil.which(cmd[0]):
                        opener = cmd
                        break
                if opener is None:
                    messagebox.showerror(
                        "No Terminal Found",
                        f"Could not find a terminal emulator.\nFolder: {parent}",
                    )
                    return
                with subprocess.Popen(opener):
                    pass
        except OSError as exc:
            self.window._logger.error("Open terminal failed: %s", exc)
            messagebox.showerror(
                "Open Terminal Error",
                f"Failed to open terminal:\n{exc}",
            )

    def action_clear_file(self, file_path: Path) -> None:
        """Delete the given file from the filesystem."""
        if not file_path.exists():
            messagebox.showwarning(
                "File Not Found",
                f"The selected file does not exist:\n{file_path}",
            )
            return

        # Confirm before deleting
        if not messagebox.askyesno(
            "Delete File",
            f"Are you sure you want to delete this file?\n\n"
            f"{file_path}\n\n"
            f"This action cannot be undone.",
        ):
            return

        try:
            file_path.unlink()
            self.window._logger.info("File deleted: %s", file_path)
            messagebox.showinfo(
                "File Deleted",
                f"File deleted successfully:\n{file_path}",
            )
            self.window._refresh_file_list()
        except OSError as exc:
            self.window._logger.error("Failed to delete file %s: %s", file_path, exc)
            messagebox.showerror(
                "Delete File Error",
                f"Failed to delete file:\n{file_path}\n\n{exc}",
            )
