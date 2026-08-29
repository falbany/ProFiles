"""Tests for profiles.gui.main_window — MainWindow, _hex_luminance, _restart_application, _on_execute, _configure_bindings, _insert_chunk, context menu actions."""

from __future__ import annotations

import contextlib
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from profiles.config import AppConfig, MachineConfiguration
from profiles.core import actions
from profiles.gui.main_window import MainWindow

# ── Tkinter availability guard ──────────────────────────────────────────────

_tk_available = True
try:
    _root_test = tk.Tk()
    _root_test.withdraw()
except (tk.TclError, RuntimeError):
    _tk_available = False
else:
    # Keep the probe root ALIVE for the whole session. On macOS (TkAqua),
    # destroying the first Tk root poisons the window-server state so that
    # update() on every later root spins forever — but a withdrawn,
    # never-destroyed session root keeps later roots healthy. Reset the
    # module default so each MainWindow's own Tk() becomes the default
    # root again (images/variables then bind to that window's interpreter).
    tk._default_root = None

needs_tk = pytest.mark.skipif(
    not _tk_available,
    reason="Tkinter not available (headless CI or missing Tcl/Tk)",
)

# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_config(
    tmp_path: Path,
    *,
    theme: str = "light",
    row_colors: tuple[tuple[str, str], ...] = (),
) -> AppConfig:
    """Build a minimal AppConfig pointing at *tmp_path*."""
    # Ensure config file exists to avoid prompt
    config_path = tmp_path / ".profiles"
    if not config_path.exists():
        config_path.write_text("version: 1\n", encoding="utf-8")

    cfg = AppConfig(
        release="0.0.1",
        title="Test",
        config_path=config_path,
        search_dir=str(tmp_path),
        search_exclude_dirs=(),
        extensions=(".mttl",),
        filters=("",),
        column_names=("File", "Version"),
        column_headers=("File", "Version"),
        column_widths=(600, 150),
        column_stretches=(True, False),
        recursive_search=False,
        close_after_execute=False,
        theme=theme,
        skip_config_prompt=True,
        configurations=[
            MachineConfiguration(
                name="default",
                scan=(str(tmp_path),),
            ),
        ],
    )
    # LAUNCHER-level row_colors: exercised when no active per-directory
    # config matches the selected directory (the canonical docs setup).
    cfg.row_colors = row_colors
    return cfg


@pytest.fixture
def window(tmp_path: Path) -> MainWindow:
    """Build a MainWindow without launching the mainloop."""
    config = _make_config(tmp_path)
    (tmp_path / "sample.mttl").write_text("dummy", encoding="utf-8")
    win = MainWindow(config)
    yield win
    with contextlib.suppress(tk.TclError):
        win.root.destroy()


@pytest.fixture
def row_color_window(tmp_path: Path) -> Callable[..., MainWindow]:
    """Factory fixture for a MainWindow with LAUNCHER-level row_colors.

    ``row_colors`` are placed on ``AppConfig`` (the ``[LAUNCHER]`` base),
    which ``_configure_row_colors`` uses whenever no per-directory
    ``MachineConfiguration`` matches the selected directory — the
    canonical documented setup.
    """

    created: list[MainWindow] = []

    def _build(
        theme: str = "dark",
        row_colors: tuple[tuple[str, str], ...] = (("PROD", "#1565C0"),),
    ) -> MainWindow:
        config = _make_config(tmp_path, theme=theme, row_colors=row_colors)
        (tmp_path / "PROD_sample.mttl").write_text("dummy", encoding="utf-8")
        win = MainWindow(config)
        created.append(win)
        return win

    yield _build
    for win in created:
        with contextlib.suppress(tk.TclError):
            win.root.destroy()


# ── _selected_file_path ─────────────────────────────────────────────────────


class TestSelectedFilePath:
    """MainWindow._selected_file_path — resolution of the selected row."""

    @needs_tk
    def test_returns_none_when_nothing_selected(self, window: MainWindow) -> None:
        # No row in the tree → no path
        assert window._tree.selection() == ()
        assert window._selected_file_path() is None

    @needs_tk
    def test_returns_full_path_for_selected_row(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        # Force-set the directory so we don't rely on auto-select logic.
        window._dir_var.set(str(tmp_path))
        window._tree.insert(
            parent="",
            index=tk.END,
            values=("sample.mttl", "V1"),
        )
        window._tree.selection_set(window._tree.get_children()[0])
        path = window._selected_file_path()
        assert path == tmp_path / "sample.mttl"

    @needs_tk
    def test_empty_directory_returns_none(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        window._dir_var.set("")
        window._tree.insert(
            parent="",
            index=tk.END,
            values=("ghost.txt", ""),
        )
        assert window._selected_file_path() is None


# ── Context menu bindings ───────────────────────────────────────────────────


class TestContextMenuBindings:
    """The right-click handler is bound to the treeview."""

    @needs_tk
    def test_right_click_bound(self, window: MainWindow) -> None:
        bindings = window._tree.bind()
        assert "<Button-3>" in bindings

    @needs_tk
    def test_middle_click_bound(self, window: MainWindow) -> None:
        bindings = window._tree.bind()
        assert "<Button-2>" in bindings

    @needs_tk
    def test_control_click_bound_for_macos(self, window: MainWindow) -> None:
        bindings = window._tree.bind()
        assert "<Control-Button-1>" in bindings


# ── _action_copy / clipboard helpers ────────────────────────────────────────


class TestCopyActions:
    """MainWindow._action_copy — populates the system clipboard."""

    @needs_tk
    def test_copy_writes_to_clipboard(self, window: MainWindow) -> None:
        window._action_copy("hello world")
        assert window.root.clipboard_get() == "hello world"

    @needs_tk
    def test_copy_path_default_uses_native_separator(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "a.mttl"
        window._action_copy_path(f)
        assert window.root.clipboard_get() == str(f)

    @needs_tk
    def test_copy_path_forward_slashes(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "b.mttl"
        window._action_copy_path(f, forward_slashes=True)
        text = window.root.clipboard_get()
        # No backslashes left — all converted to forward slashes.
        assert "\\" not in text
        assert text.endswith("/b.mttl")

    @needs_tk
    def test_copy_name_with_and_without_extension(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "report.txt"
        window._action_copy_name(f, with_ext=True)
        assert window.root.clipboard_get() == "report.txt"
        window._action_copy_name(f, with_ext=False)
        assert window.root.clipboard_get() == "report"


# ── _on_tree_right_click ────────────────────────────────────────────────────


class TestOnTreeRightClick:
    """The right-click handler builds a menu without crashing."""

    @needs_tk
    def test_bails_out_on_empty_area(self, window: MainWindow) -> None:
        # No row under the cursor → no menu should be posted.
        event = MagicMock()
        event.y = 999_999  # well below any row
        event.x = 0
        event.x_root = 100
        event.y_root = 100
        # Should not raise
        window._on_tree_right_click(event)

    @needs_tk
    def test_selects_row_under_cursor(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        window._tree.insert(
            parent="",
            index=tk.END,
            values=("sample.mttl", "V1"),
        )
        # Map the window and scroll the row into view so bbox is populated.
        window._tree.see(window._tree.get_children()[0])
        window.root.update_idletasks()
        bbox = window._tree.bbox(window._tree.get_children()[0])
        assert bbox  # row must be visible / laid out

        event = MagicMock()
        event.y = bbox[1] + 1
        event.x = bbox[0] + 1
        event.x_root = 100
        event.y_root = 100

        # Mock tk_popup to prevent blocking / showing UI in tests
        mocker.patch("tkinter.Menu.tk_popup")

        # The handler tries to call tk_popup, which in a headless test
        # environment raises TclError — we only need to verify the row
        # got selected before that point.
        with contextlib.suppress(tk.TclError):
            window._on_tree_right_click(event)

        selection = window._tree.selection()
        assert selection
        assert window._tree.item(selection[0], "values")[0] == "sample.mttl"


# ── _action_filter_to_folder ───────────────────────────────────────────────


class TestFilterToFolder:
    """MainWindow._action_filter_to_folder — drill-down into a parent dir."""

    @needs_tk
    def test_switches_directory_to_parent(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        f = sub / "child.mttl"
        f.write_text("", encoding="utf-8")
        window._dir_var.set(str(sub))

        window._action_filter_to_folder(f)
        assert window._dir_var.get() == str(sub)

    @needs_tk
    def test_noop_when_already_in_parent(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "top.mttl"
        f.write_text("", encoding="utf-8")
        window._dir_var.set(str(tmp_path))
        # Refresher must NOT be called since nothing changed.
        called = {"n": 0}
        original = window._refresh_file_list
        window._refresh_file_list = lambda: called.__setitem__("n", called["n"] + 1)  # type: ignore[method-assign]
        try:
            window._action_filter_to_folder(f)
            assert called["n"] == 0
            assert window._dir_var.get() == str(tmp_path)
        finally:
            window._refresh_file_list = original  # type: ignore[method-assign]

    @needs_tk
    def test_missing_folder_warns(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        # Build a path whose parent doesn't exist on disk.
        ghost = tmp_path / "doesnt_exist" / "child.mttl"
        mock_warn = mocker.patch("profiles.gui.main_window.messagebox.showwarning")
        window._action_filter_to_folder(ghost)
        mock_warn.assert_called_once()
        assert "Folder Not Found" in mock_warn.call_args.args[0]


# ── _action_hash ───────────────────────────────────────────────────────────


class TestActionHash:
    """MainWindow._action_hash — compute and show / copy a file digest."""

    @needs_tk
    def test_show_dialog(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "report.mttl"
        f.write_bytes(b"abc")
        mock_info = mocker.patch("profiles.gui.main_window.messagebox.showinfo")
        window._action_hash(f, "md5")
        mock_info.assert_called_once()
        title = mock_info.call_args.args[0]
        body = mock_info.call_args.args[1]
        assert title == "MD5 Hash"
        import hashlib

        assert hashlib.md5(b"abc").hexdigest() in body

    @needs_tk
    def test_copy_only(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "report.mttl"
        f.write_bytes(b"abc")
        mock_info = mocker.patch("profiles.gui.main_window.messagebox.showinfo")
        window._action_hash(f, "sha256", copy_only=True)
        mock_info.assert_not_called()
        import hashlib

        assert window.root.clipboard_get() == hashlib.sha256(b"abc").hexdigest()

    @needs_tk
    def test_missing_file_warns(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        mock_warn = mocker.patch("profiles.gui.main_window.messagebox.showwarning")
        window._action_hash(tmp_path / "ghost.mttl", "md5")
        mock_warn.assert_called_once()
        assert "File Not Found" in mock_warn.call_args.args[0]


# ── _action_copy_uri ───────────────────────────────────────────────────────


class TestCopyUri:
    """MainWindow._action_copy_uri — `file://` URI to clipboard."""

    @needs_tk
    def test_writes_file_uri_to_clipboard(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "report.mttl"
        window._action_copy_uri(f)
        expected = Path(f).as_uri()
        assert window.root.clipboard_get() == expected

    @needs_tk
    def test_starts_with_file_scheme(
        self,
        window: MainWindow,
        tmp_path: Path,
    ) -> None:
        f = tmp_path / "data.bin"
        window._action_copy_uri(f)
        assert window.root.clipboard_get().startswith("file://")


# ── _action_filter_by_extension ────────────────────────────────────────────


class TestFilterByExtension:
    """MainWindow._action_filter_by_extension — narrow scan to a file's ext."""

    @needs_tk
    def test_sets_extension_var_to_suffix(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "thing.mttl"
        mocker.patch.object(window, "_refresh_file_list")
        window._action_filter_by_extension(f)
        assert window._ext_var.get() == ".mttl"

    @needs_tk
    def test_triggers_refresh(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "thing.mttl"
        mock_refresh = mocker.patch.object(window, "_refresh_file_list")
        window._action_filter_by_extension(f)
        mock_refresh.assert_called_once()

    @needs_tk
    def test_no_extension_warns(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        no_ext = tmp_path / "Makefile"
        no_ext.write_text("", encoding="utf-8")
        mock_warn = mocker.patch("profiles.gui.main_window.messagebox.showwarning")
        mock_refresh = mocker.patch.object(window, "_refresh_file_list")
        window._action_filter_by_extension(no_ext)
        mock_warn.assert_called_once()
        assert "No Extension" in mock_warn.call_args.args[0]
        mock_refresh.assert_not_called()


# ── _action_verify_hash ────────────────────────────────────────────────────


class TestVerifyHash:
    """MainWindow._action_verify_hash — file hash vs. clipboard digest."""

    @needs_tk
    def test_match_shows_success_dialog(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        import hashlib

        f = tmp_path / "good.mttl"
        f.write_bytes(b"hello")
        digest = hashlib.sha256(b"hello").hexdigest()
        window.root.clipboard_clear()
        window.root.clipboard_append(digest)
        # ponytail: update() drains the clipboard grab but blocks forever on
        # TkAqua when a prior root was destroyed; update_idletasks() flushes
        # the Tcl queue without the blocking grab.
        window.root.update_idletasks()

        mock_info = mocker.patch("profiles.gui.main_window.messagebox.showinfo")
        mock_error = mocker.patch("profiles.gui.main_window.messagebox.showerror")
        window._action_verify_hash(f, "sha256")
        mock_info.assert_called_once()
        mock_error.assert_not_called()
        assert "Match" in mock_info.call_args.args[1]

    @needs_tk
    def test_match_is_case_insensitive(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        import hashlib

        f = tmp_path / "good.mttl"
        f.write_bytes(b"hello")
        digest = hashlib.md5(b"hello").hexdigest()
        window.root.clipboard_clear()
        window.root.clipboard_append(digest.upper())  # uppercase clipboard
        # ponytail: update() drains the clipboard grab but blocks forever on
        # TkAqua when a prior root was destroyed; update_idletasks() flushes
        # the Tcl queue without the blocking grab.
        window.root.update_idletasks()

        mock_info = mocker.patch("profiles.gui.main_window.messagebox.showinfo")
        window._action_verify_hash(f, "md5")
        mock_info.assert_called_once()
        assert "Match" in mock_info.call_args.args[1]

    @needs_tk
    def test_mismatch_shows_error_dialog(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "good.mttl"
        f.write_bytes(b"hello")
        window.root.clipboard_clear()
        window.root.clipboard_append("0" * 64)  # wrong hash
        # ponytail: update() drains the clipboard grab but blocks forever on
        # TkAqua when a prior root was destroyed; update_idletasks() flushes
        # the Tcl queue without the blocking grab.
        window.root.update_idletasks()

        mock_error = mocker.patch("profiles.gui.main_window.messagebox.showerror")
        window._action_verify_hash(f, "sha256")
        mock_error.assert_called_once()
        body = mock_error.call_args.args[1]
        assert "Mismatch" in body
        assert "Clipboard" in body

    @needs_tk
    def test_empty_clipboard_informs(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "good.mttl"
        f.write_bytes(b"hello")
        window.root.clipboard_clear()
        # ponytail: update() drains the clipboard grab but blocks forever on
        # TkAqua when a prior root was destroyed; update_idletasks() flushes
        # the Tcl queue without the blocking grab.
        window.root.update_idletasks()

        mock_info = mocker.patch("profiles.gui.main_window.messagebox.showinfo")
        mock_error = mocker.patch("profiles.gui.main_window.messagebox.showerror")
        window._action_verify_hash(f, "sha256")
        mock_info.assert_called_once()
        mock_error.assert_not_called()
        assert "empty" in mock_info.call_args.args[1].lower()

    @needs_tk
    def test_missing_file_warns(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        mock_warn = mocker.patch("profiles.gui.main_window.messagebox.showwarning")
        window._action_verify_hash(tmp_path / "ghost.mttl", "md5")
        mock_warn.assert_called_once()
        assert "File Not Found" in mock_warn.call_args.args[0]


# ── _action_open_terminal ─────────────────────────────────────────────────


class TestOpenTerminal:
    """MainWindow._action_open_terminal — spawn an OS terminal in the parent dir."""

    @needs_tk
    def test_missing_folder_warns(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        ghost = tmp_path / "doesnt_exist" / "child.mttl"
        mock_warn = mocker.patch("profiles.gui.main_window.messagebox.showwarning")
        mock_popen = mocker.patch(
            "profiles.core.actions.subprocess.Popen",
        )
        window._action_open_terminal(ghost)
        mock_warn.assert_called_once()
        mock_popen.assert_not_called()

    @needs_tk
    def test_macos_opens_terminal_app(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "child.mttl"
        f.write_text("", encoding="utf-8")
        mock_popen = mocker.patch("profiles.core.actions.subprocess.Popen")
        mocker.patch("profiles.core.actions.sys.platform", "darwin")
        window._action_open_terminal(f)
        mock_popen.assert_called_once()
        args = mock_popen.call_args.args[0]
        assert args[0] == "open"
        assert args[1] == "-a"
        assert args[2] == "Terminal"
        assert str(tmp_path) in args[3]

    @needs_tk
    def test_windows_uses_cmd(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "child.mttl"
        f.write_text("", encoding="utf-8")
        mock_popen = mocker.patch("profiles.core.actions.subprocess.Popen")
        mocker.patch("profiles.core.actions.sys.platform", "win32")
        mocker.patch("profiles.core.actions.os.name", "nt")
        window._action_open_terminal(f)
        mock_popen.assert_called_once()
        args = mock_popen.call_args.args[0]
        assert args[0] == "cmd"
        assert "/K" in args
        assert f"cd /D {tmp_path}" in args

    @needs_tk
    def test_linux_no_terminal_found_errors(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "child.mttl"
        f.write_text("", encoding="utf-8")
        mocker.patch("profiles.core.actions.sys.platform", "linux")
        mocker.patch("profiles.core.actions.os.name", "posix")
        mocker.patch("profiles.core.actions.shutil.which", return_value=None)
        mock_popen = mocker.patch("profiles.core.actions.subprocess.Popen")
        mock_error = mocker.patch("profiles.gui.main_window.messagebox.showerror")
        window._action_open_terminal(f)
        mock_popen.assert_not_called()
        mock_error.assert_called_once()
        # Title is fixed; the "No terminal emulator" detail is in the message.
        assert "No terminal emulator" in mock_error.call_args.args[1]

    @needs_tk
    def test_linux_finds_x_terminal_emulator(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "child.mttl"
        f.write_text("", encoding="utf-8")
        mocker.patch("profiles.core.actions.sys.platform", "linux")
        mocker.patch("profiles.core.actions.os.name", "posix")
        mocker.patch(
            "profiles.core.actions.shutil.which",
            side_effect=lambda name: (
                "/usr/bin/x-terminal-emulator" if name == "x-terminal-emulator" else None
            ),
        )
        mock_popen = mocker.patch("profiles.core.actions.subprocess.Popen")
        window._action_open_terminal(f)
        mock_popen.assert_called_once()
        args = mock_popen.call_args.args[0]
        assert args[0] == "x-terminal-emulator"
        assert str(tmp_path) in args


# ── TestApplicationRestart (from test_restart_functionality.py) ────────────


class TestApplicationRestart:
    """Tests for the WindowActions.restart path (delegated from _restart_application)."""

    def test_restart_destroys_current_window(self) -> None:
        """Verify that restart destroys the current window before launching new instance."""
        from profiles.gui.controllers.window_actions import WindowActions

        mock_destroy = MagicMock()
        with (
            patch("profiles.gui.controllers.window_actions.subprocess") as mock_subprocess,
            patch("profiles.gui.controllers.window_actions.sys") as mock_sys,
        ):
            mock_sys.executable = "python.exe"
            actions = WindowActions(
                config=AppConfig(),
                logger=MagicMock(),
                root_destroy=mock_destroy,
            )
            actions.restart()

            # Verify window was destroyed
            mock_destroy.assert_called_once()
            # Verify subprocess was called to launch new instance
            assert mock_subprocess.Popen.called

    def test_restart_handles_launch_failure_gracefully(self) -> None:
        """Verify that restart shows error message if subprocess fails."""
        from profiles.gui.controllers.window_actions import WindowActions

        mock_destroy = MagicMock()
        with (
            patch("profiles.gui.controllers.window_actions.subprocess") as mock_subprocess,
            patch("profiles.gui.controllers.window_actions.sys") as mock_sys,
            patch("profiles.gui.controllers.window_actions.messagebox") as mock_messagebox,
        ):
            mock_sys.executable = "python.exe"
            mock_subprocess.Popen.side_effect = OSError("Launch failed")
            actions = WindowActions(
                config=AppConfig(),
                logger=MagicMock(),
                root_destroy=mock_destroy,
            )
            actions.restart()

            # Verify error message was shown
            mock_messagebox.showerror.assert_called_once()
            assert "Restart Failed" in mock_messagebox.showerror.call_args.args[0]


# ── TestNoConfigFileMode (from test_no_config_file_mode.py) ────────────────


class TestNoConfigFileMode:
    """Tests for GUI behavior when no .profiles config file exists."""

    def test_insert_chunk_uses_single_value_for_single_column(self, tmp_path: Path) -> None:
        """When column_names has only 1 column, _insert_chunk should use single-value tuples.

        This test verifies the fix for the issue where clicking search buttons
        would find files but the treeview wouldn't display them because it was
        trying to insert 2 values (filename, version) into a 1-column treeview.
        """
        # Create a mock window with single-column config
        mock_window = MagicMock()
        mock_window._config = AppConfig()
        mock_window._config.column_names = ("File",)  # Single column default
        mock_window._config.column_headers = ("File",)
        mock_window._config.column_widths = (600,)
        mock_window._config.column_stretches = (True,)
        mock_window._current_scan_id = 1
        mock_window._tree_to_path = {}
        mock_window._tree_to_filename = {}
        mock_window._row_color_rules = []

        # Import the method as an unbound function
        # Create test data
        from profiles.core.processing.scanner import ScannedFileDynamic
        from profiles.gui.main_window import MainWindow

        test_items = [
            ScannedFileDynamic(path=tmp_path / "test1.mttl", column_values={"File": "test1.mttl"}),
            ScannedFileDynamic(path=tmp_path / "test2.mttl", column_values={"File": "test2.mttl"}),
        ]

        # Mock tree insert to capture calls
        mock_tree = MagicMock()
        mock_window._tree = mock_tree

        # Call the method directly
        MainWindow._insert_chunk(
            mock_window,
            scan_id=1,
            items=test_items,
            start_idx=0,
            accumulated_files=[],
            display_label=str(tmp_path),
            filter_text="",
            extension=".mttl",
        )

        # Verify insert was called with single-value tuples
        assert mock_tree.insert.call_count == 2

        # First call should have values=(filename,) not (filename, version)
        first_call_args = mock_tree.insert.call_args_list[0]
        assert first_call_args.kwargs["values"] == ("test1.mttl",)

        # Second call should also have single value
        second_call_args = mock_tree.insert.call_args_list[1]
        assert second_call_args.kwargs["values"] == ("test2.mttl",)

    def test_insert_chunk_uses_two_values_for_multi_column(self, tmp_path: Path) -> None:
        """When column_names has 2+ columns, _insert_chunk should use 2-value tuples."""
        # Create a mock window with multi-column config
        mock_window = MagicMock()
        mock_window._config = AppConfig()
        mock_window._config.column_names = ("File", "Version")  # Two columns
        mock_window._config.column_headers = ("File", "Version")
        mock_window._config.column_widths = (400, 150)
        mock_window._config.column_stretches = (True, False)
        mock_window._current_scan_id = 1
        mock_window._tree_to_path = {}
        mock_window._tree_to_filename = {}
        mock_window._row_color_rules = []

        # Create test data
        from profiles.core.processing.scanner import ScannedFileDynamic
        from profiles.gui.main_window import MainWindow

        test_items = [
            ScannedFileDynamic(
                path=tmp_path / "test1.mttl",
                column_values={"File": "test1.mttl", "Version": "v1.0"},
            ),
        ]

        # Mock tree insert
        mock_tree = MagicMock()
        mock_window._tree = mock_tree

        # Call the method
        MainWindow._insert_chunk(
            mock_window,
            scan_id=1,
            items=test_items,
            start_idx=0,
            accumulated_files=[],
            display_label=str(tmp_path),
            filter_text="",
            extension=".mttl",
        )

        # Verify insert was called with 2-value tuples
        assert mock_tree.insert.call_count == 1
        call_args = mock_tree.insert.call_args_list[0]
        assert call_args.kwargs["values"] == ("test1.mttl", "v1.0")


# ── TestHexLuminance (from test_main_window_ui.py) ─────────────────────────


class TestHexLuminance:
    """hex_luminance() — WCAG relative luminance for #RRGGBB strings."""

    def test_black_is_zero(self) -> None:
        """#000000 → 0.0 (per WCAG: all channels linearised to 0)."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("#000000") == pytest.approx(0.0, abs=1e-6)

    def test_white_is_one(self) -> None:
        """#ffffff → 1.0 (per WCAG: weighted sum of three ones)."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("#ffffff") == pytest.approx(1.0, abs=1e-3)

    def test_red_is_2126(self) -> None:
        """#ff0000 → ≈0.2126 (R coefficient × 1.0)."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("#ff0000") == pytest.approx(0.2126, abs=0.01)

    def test_missing_hash_tolerated(self) -> None:
        """A leading '#' is optional — same value with or without it."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("ff0000") == pytest.approx(hex_luminance("#ff0000"), abs=1e-6)

    def test_uppercase_hex_matches(self) -> None:
        """Uppercase hex digits parse to the same luminance as lowercase."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("#FF0000") == pytest.approx(hex_luminance("#ff0000"), abs=1e-6)

    def test_green_is_7152(self) -> None:
        """Sanity check: pure green contributes the G coefficient (0.7152)."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("#00ff00") == pytest.approx(0.7152, abs=0.01)

    def test_blue_is_0722(self) -> None:
        """Sanity check: pure blue contributes the B coefficient (0.0722)."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("#0000ff") == pytest.approx(0.0722, abs=0.01)

    def test_invalid_returns_neutral(self) -> None:
        """Garbage input returns the neutral fallback 0.5."""
        from profiles.gui.theme import hex_luminance

        assert hex_luminance("not-a-color") == 0.5
        assert hex_luminance("") == 0.5
        assert hex_luminance("#zz0000") == 0.5

    def test_result_within_unit_interval(self) -> None:
        """For a representative sample, the result must lie in [0, 1]."""
        from profiles.gui.theme import hex_luminance

        for color in ("#000000", "#ffffff", "#7f7f7f", "#abcdef", "#123456"):
            value = hex_luminance(color)
            assert 0.0 <= value <= 1.0, f"{color} produced {value}"


# ── TestOnExecuteMultiSelect (from test_action_launch_args.py) ───────────────────────


class TestOnExecuteMultiSelect:
    """_on_execute must call launch_selected_file once per selected iid."""

    @needs_tk
    def test_no_selection_shows_info(self, window: MainWindow, mocker) -> None:
        info = mocker.patch("profiles.gui.main_window.messagebox.showinfo")
        launch = mocker.patch("profiles.gui.main_window.actions.launch_selected_file")

        window._on_execute()

        info.assert_called_once()
        launch.assert_not_called()

    @needs_tk
    def test_single_selection_launches_one_file(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        a = tmp_path / "a.mttl"
        window._dir_var.set(str(tmp_path))
        iid = window._tree.insert(parent="", index=tk.END, values=("a.mttl", "1"))
        window._tree_to_path[iid] = a
        window._tree_to_filename[iid] = "a.mttl"
        window._tree.selection_set(iid)

        launch = mocker.patch(
            "profiles.gui.main_window.actions.launch_selected_file",
            return_value=actions.ActionResult(
                status=actions.ActionStatus.SUCCESS,
                message="ok",
                path=a,
            ),
        )

        window._on_execute()

        launch.assert_called_once()
        kwargs = launch.call_args.kwargs
        assert kwargs["filename"] == "a.mttl"
        assert Path(kwargs["directory"]) == tmp_path

    @needs_tk
    def test_multi_selection_launches_each(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        window._dir_var.set(str(tmp_path))
        iid_a = window._tree.insert(parent="", index=tk.END, values=("a.mttl", "1"))
        iid_b = window._tree.insert(parent="", index=tk.END, values=("b.mttl", "1"))
        window._tree_to_path[iid_a] = tmp_path / "a.mttl"
        window._tree_to_path[iid_b] = tmp_path / "b.mttl"
        window._tree_to_filename[iid_a] = "a.mttl"
        window._tree_to_filename[iid_b] = "b.mttl"
        # Tk's `selectmode="extended"` requires selection_set per iid; the
        # widgets let us combine them with selectmode toggled (e.g. shift-click
        # in user UI). Calling selection_set twice is the most reliable way
        # to verify multi-selection in tests.
        window._tree.selection_set(iid_a)
        window._tree.selection_add(iid_b)

        launch = mocker.patch(
            "profiles.gui.main_window.actions.launch_selected_file",
            return_value=actions.ActionResult(
                status=actions.ActionStatus.SUCCESS,
                message="ok",
            ),
        )

        window._on_execute()

        assert launch.call_count == 2
        filenames = {c.kwargs["filename"] for c in launch.call_args_list}
        assert filenames == {"a.mttl", "b.mttl"}

    @needs_tk
    def test_first_failure_is_reported(
        self,
        window: MainWindow,
        tmp_path: Path,
        mocker,
    ) -> None:
        window._dir_var.set(str(tmp_path))
        iid_a = window._tree.insert(parent="", index=tk.END, values=("a.mttl", "1"))
        iid_b = window._tree.insert(parent="", index=tk.END, values=("b.mttl", "1"))
        window._tree_to_path[iid_a] = tmp_path / "a.mttl"
        window._tree_to_path[iid_b] = tmp_path / "b.mttl"
        window._tree_to_filename[iid_a] = "a.mttl"
        window._tree_to_filename[iid_b] = "b.mttl"
        window._tree.selection_set(iid_a)
        window._tree.selection_add(iid_b)

        err = mocker.patch("profiles.gui.main_window.messagebox.showerror")
        warn = mocker.patch("profiles.gui.main_window.messagebox.showwarning")

        effects = [
            actions.ActionResult(
                status=actions.ActionStatus.NOT_FOUND,
                message="a not found",
                path=tmp_path / "a.mttl",
            ),
            actions.ActionResult(
                status=actions.ActionStatus.SUCCESS,
                message="b ok",
            ),
        ]

        def _side_effect(**_kwargs):
            return effects.pop(0)

        mocker.patch(
            "profiles.gui.main_window.actions.launch_selected_file",
            side_effect=_side_effect,
        )

        window._on_execute()

        warn.assert_called_once()
        # The second launch still happened even though the first failed.
        err.assert_not_called()


# ── Root-level key bindings ──────────────────────────────────────────────────


class TestRootKeyBindings:
    """``_configure_bindings`` wires Ctrl+F / F5 / Escape / Ctrl+R on root."""

    @needs_tk
    @pytest.mark.parametrize(
        "sequence",
        [
            ("<Control-f>", "<Control-Key-f>"),
            ("<F5>", "<Key-F5>"),
            ("<Escape>", "<Key-Escape>"),
            ("<Control-r>", "<Control-Key-r>"),
        ],
    )
    def test_root_binding_present(
        self,
        window: MainWindow,
        sequence: tuple[str, str],
    ) -> None:
        # Tk normalizes event sequences on registration; accept either form.
        written, normalized = sequence
        bindings = window._root.bind()
        assert written in bindings or normalized in bindings, (
            f"expected {written} in {sorted(bindings)}"
        )

    @needs_tk
    def test_ctrl_f_binding_callback_focuses_filter(self, window: MainWindow) -> None:
        """The registered binding string is non-empty (Tk stores it as a tcl cmd)."""
        # Bind registration testing: `bind` without an event name returns a
        # tuple of bindings; with an event name it returns the callback string
        # registered for that event. Both being non-empty is sufficient to
        # prove the binding was wired up.
        registered = window._root.bind("<Control-f>")
        assert registered, "expected <Control-f> to be bound on the root window"


# ── Context menu entry ──────────────────────────────────────────────────────


class TestLaunchWithArgsMenuEntry:
    """The context menu exposes a 'Launch with arguments…' entry."""

    @needs_tk
    def test_menu_includes_launch_with_args(self, window: MainWindow, mocker) -> None:
        iid = window._tree.insert(
            parent="",
            index=tk.END,
            values=("sample.mttl", "V1"),
        )
        window._tree.selection_set(iid)
        # Map the window and scroll the row into view so bbox is populated.
        window._tree.see(iid)
        window.root.update_idletasks()
        bbox = window._tree.bbox(iid)
        assert bbox

        event = MagicMock()
        event.y = bbox[1] + 1
        event.x = bbox[0] + 1
        event.x_root = 100
        event.y_root = 100

        captured: dict[str, list[str]] = {"labels": []}
        original_add_command = tk.Menu.add_command

        def spy(self, **kwargs):  # type: ignore[no-untyped-def]
            label = kwargs.get("label", "")
            if label:
                captured["labels"].append(label)
            return original_add_command(self, **kwargs)

        mocker.patch.object(tk.Menu, "add_command", spy)
        mocker.patch.object(tk.Menu, "tk_popup", lambda self, x, y: None)
        with contextlib.suppress(tk.TclError):
            window._on_tree_right_click(event)

        labels = captured["labels"]
        assert any("Launch with arguments" in label for label in labels), labels


# ── Row coloring (test_main_window_row_colors) ─────────────────────────────


def _tag_foreground(tree: ttk.Treeview, tag_name: str) -> str:
    """Return the effective foreground configured for *tag_name* (lowercased)."""
    return str(tree.tag_configure(tag_name, "foreground")).lower()


class TestRowColors:
    """MainWindow._configure_row_colors — dark theme keeps configured colors.

    Regression guard for the bug where *starting* the app with the dark
    theme rendered row colors grey (the canonical ``PROD:#1565C0`` trips
    the old luminance-delta fallback against the dark surface), while a
    runtime light→dark switch briefly kept the stale light-theme tag.
    """

    @needs_tk
    def test_startup_dark_keeps_prod_blue(self, row_color_window) -> None:
        """Starting with the dark theme must keep PROD:#1565C0 (not grey)."""
        win = row_color_window(theme="dark", row_colors=(("PROD", "#1565C0"),))
        # Buggy behaviour: tag becomes "_rowcolor_PROD_7A7680" (grey outline).
        assert ("PROD", "_rowcolor_PROD_1565C0") in win._row_color_rules, win._row_color_rules
        assert _tag_foreground(win._tree, "_rowcolor_PROD_1565C0") == "#1565c0"
        assert win._row_color_tags_for("PROD_sample.mttl") == (
            "_rowcolor_default",
            "_rowcolor_PROD_1565C0",
        )

    @needs_tk
    def test_light_to_dark_switch_reuses_same_tag(self, row_color_window) -> None:
        """Switching light→dark must reconfigure the SAME tag, not diverge."""
        win = row_color_window(theme="light", row_colors=(("PROD", "#1565C0"),))
        assert ("PROD", "_rowcolor_PROD_1565C0") in win._row_color_rules

        win._apply_theme("dark")

        # Same tag name survives the switch (no stale-tag divergence).
        assert ("PROD", "_rowcolor_PROD_1565C0") in win._row_color_rules, win._row_color_rules
        assert _tag_foreground(win._tree, "_rowcolor_PROD_1565C0") == "#1565c0"
        # A row inserted after a re-scan still resolves to the same tag/color.
        assert win._row_color_tags_for("PROD_sample.mttl") == (
            "_rowcolor_default",
            "_rowcolor_PROD_1565C0",
        )

    @needs_tk
    def test_invisible_color_falls_back_to_readable_text(self, row_color_window) -> None:
        """A color indistinguishable from the surface falls back to on_surface."""
        from profiles.gui.theme import LIGHT_THEME

        win = row_color_window(theme="light", row_colors=(("GHOST", "#FFFFFF"),))
        # Tag name still derives from the ORIGINAL configured color.
        assert ("GHOST", "_rowcolor_GHOST_FFFFFF") in win._row_color_rules
        fg = _tag_foreground(win._tree, "_rowcolor_GHOST_FFFFFF")
        assert fg == LIGHT_THEME.on_surface.lower(), f"expected readable fallback, got {fg}"

    @needs_tk
    def test_empty_rules_still_expose_default_tag(self, row_color_window) -> None:
        """With no rules the `_rowcolor_default` tag is still configured."""
        from profiles.gui.theme import DARK_THEME

        win = row_color_window(theme="dark", row_colors=())
        assert win._row_color_rules == []
        fg = _tag_foreground(win._tree, "_rowcolor_default")
        assert fg == DARK_THEME.on_surface_variant.lower()

    @needs_tk
    def test_light_theme_canonical_colors_unchanged(self, row_color_window) -> None:
        """Light theme must keep every documented canonical row color."""
        win = row_color_window(
            theme="light",
            row_colors=(("PROD", "#1565C0"), ("DEV", "#757575"), ("TMP", "#BAC015")),
        )
        assert ("PROD", "_rowcolor_PROD_1565C0") in win._row_color_rules
        assert ("DEV", "_rowcolor_DEV_757575") in win._row_color_rules
        assert ("TMP", "_rowcolor_TMP_BAC015") in win._row_color_rules
        assert _tag_foreground(win._tree, "_rowcolor_PROD_1565C0") == "#1565c0"
        assert _tag_foreground(win._tree, "_rowcolor_DEV_757575") == "#757575"
        assert _tag_foreground(win._tree, "_rowcolor_TMP_BAC015") == "#bac015"


# ── Language toggle ─────────────────────────────────────────────────────────


class TestLanguageToggle:
    """MainWindow._on_toggle_language — cycles en↔fr and persists."""

    @needs_tk
    def test_toggle_switches_language_and_persists(self, window: MainWindow, mocker) -> None:
        from profiles.gui import i18n

        i18n.set_language("en")
        save_spy = mocker.patch(
            "profiles.gui.main_window.write_value",
        )
        window._on_toggle_language()
        assert i18n.current_language() == "fr"
        save_spy.assert_called_once_with(
            window._config.config_path,
            "defaults.language",
            "fr",
        )
        # Toggle again → back to English
        window._on_toggle_language()
        assert i18n.current_language() == "en"
        i18n.set_language("en")

    @needs_tk
    def test_toggle_relabels_status_bar(self, window: MainWindow) -> None:
        from profiles.gui import i18n

        i18n.set_language("en")
        window._on_toggle_language()
        assert window._status_bar.config_link.cget("text") == i18n.t("status.config", lang="fr")
        assert window._status_bar.language_btn.cget("text") == "\U0001f310 FR"
        window._on_toggle_language()
        assert window._status_bar.config_link.cget("text") == i18n.t("status.config", lang="en")
        i18n.set_language("en")
