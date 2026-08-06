"""Tests for profiles.app — ProFileApp, main(), init_default_config.

Also tests profiles.__init__ package metadata and __main__ entry point.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

import pytest

import profiles
from profiles.app import ProFileApp, init_default_config, main
from profiles.gui.main_window import MainWindow

# ── Tkinter availability guard ──────────────────────────────────────────────

_tk_available = True
try:
    _tk_root = tk.Tk()
    _tk_root.destroy()
except (tk.TclError, RuntimeError):
    _tk_available = False

needs_tk = pytest.mark.skipif(
    not _tk_available,
    reason="Tkinter not available (headless CI or missing Tcl/Tk)",
)

# ── Package metadata (__init__.py) ──────────────────────────────────────────


class TestPackageMetadata:
    """profiles.__init__ exports version, author, license."""

    def test_version(self) -> None:
        assert profiles.__version__ == "2026.7.0"

    def test_author(self) -> None:
        assert profiles.__author__ == "Florent ALBANY"

    def test_license(self) -> None:
        assert profiles.__license__ == "MIT"


# ── ProFileApp.__init__ ──────────────────────────────────────────────────


class TestProFileAppInit:
    """ProFileApp constructor with various arguments."""

    def test_default_construction(self) -> None:
        app = ProFileApp()
        assert app._config_path is None
        assert app._log_path == Path("profiles.log")
        assert app._headless is False
        assert app._config is None
        assert app._window is None
        assert app._logger is None

    def test_custom_config_path(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        app = ProFileApp(config_path=conf)
        assert app._config_path == conf

    def test_custom_log_path(self) -> None:
        app = ProFileApp(log_path="custom/log.txt")
        assert app._log_path == Path("custom/log.txt")

    def test_headless_mode(self) -> None:
        app = ProFileApp(headless=True)
        assert app._headless is True

    def test_config_path_str_conversion(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        app = ProFileApp(config_path=str(conf))
        assert app._config_path == conf


# ── ProFileApp._setup_logging ────────────────────────────────────────────


class TestSetupLogging:
    """_setup_logging configures and returns a logger."""

    def test_returns_logger(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.get_hostname", return_value="HOST")
        mock_configure = mocker.patch("profiles.app.configure_logger")
        app = ProFileApp()
        app._setup_logging()
        mock_configure.assert_called_once()
        args, kwargs = mock_configure.call_args
        assert kwargs["source"] == "HOST"
        assert kwargs["level"] == 20  # logging.INFO


# ── ProFileApp._load_configuration ───────────────────────────────────────


class TestLoadConfiguration:
    """_load_configuration loads config or exits on error."""

    def test_loads_config_successfully(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_load = mocker.patch("profiles.app.load_config")
        app = ProFileApp()
        mock_logger = mocker.MagicMock()
        app._load_configuration(mock_logger)
        mock_load.assert_called_once_with(None)

    def test_oserror_exits(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mocker.patch("profiles.app.load_config", side_effect=OSError("bad file"))
        app = ProFileApp()
        mock_logger = mocker.MagicMock()
        with pytest.raises(SystemExit) as exc:
            app._load_configuration(mock_logger)
        assert exc.value.code == 1

    def test_valueerror_exits(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mocker.patch("profiles.app.load_config", side_effect=ValueError("bad value"))
        app = ProFileApp()
        mock_logger = mocker.MagicMock()
        with pytest.raises(SystemExit) as exc:
            app._load_configuration(mock_logger)
        assert exc.value.code == 1


# ── ProFileApp.run_headless ──────────────────────────────────────────────


class TestRunHeadless:
    """ProFileApp.run_headless — headless file launching."""

    def test_with_valid_file(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        mocker.patch("profiles.app.configure_logger")
        mocker.patch("profiles.app.load_config")
        mocker.patch(
            "profiles.core.actions.launch_selected_file",
            return_value=mocker.MagicMock(
                status=profiles.core.actions.ActionStatus.SUCCESS,
                message="ok",
                path=f,
            ),
        )

        app = ProFileApp()
        app._logger = mocker.MagicMock()
        app._config = mocker.MagicMock()
        exit_code = app.run_headless(file_path=f)
        assert exit_code == 0

    def test_file_not_found(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mocker.patch("profiles.app.load_config")

        app = ProFileApp()
        app._logger = mocker.MagicMock()
        app._config = mocker.MagicMock()
        exit_code = app.run_headless(file_path=Path("C:/nonexistent_xyz.mttl"))
        assert exit_code == 1

    def test_launch_fails(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        f = tmp_path / "fail.mttl"
        f.write_text("", encoding="utf-8")
        mocker.patch("profiles.app.configure_logger")
        mocker.patch("profiles.app.load_config")
        mocker.patch(
            "profiles.core.actions.launch_selected_file",
            return_value=mocker.MagicMock(
                status=profiles.core.actions.ActionStatus.FAILED,
                message="boom",
                path=f,
            ),
        )

        app = ProFileApp()
        app._logger = mocker.MagicMock()
        app._config = mocker.MagicMock()
        exit_code = app.run_headless(file_path=f)
        assert exit_code == 1

    def test_without_file_scans_directories(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mocker.patch("profiles.app.load_config")
        from profiles.core.processing.scanner import ScannedFile

        mocker.patch(
            "profiles.app.scan_and_process",
            return_value=[
                ScannedFile("a.mttl", "1.0", Path("a.mttl")),
                ScannedFile("b.mttl", "2.0", Path("b.mttl")),
            ],
        )
        mocker.patch(
            "profiles.core.actions.launch_selected_file",
            return_value=mocker.MagicMock(
                status=profiles.core.actions.ActionStatus.SUCCESS,
                message="ok",
                path=None,
            ),
        )

        app = ProFileApp()
        app._logger = mocker.MagicMock()
        app._config = mocker.MagicMock()
        app._config.configurations = [
            mocker.MagicMock(directory="M:/tests"),
        ]
        app._config.extensions = [".mttl"]
        exit_code = app.run_headless()
        assert exit_code == 0

    def test_without_file_empty_configs(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")

        app = ProFileApp()
        app._logger = mocker.MagicMock()
        app._config = mocker.MagicMock()
        app._config.configurations = []
        app._config.extensions = []
        exit_code = app.run_headless()
        assert exit_code == 0


# ── ProFileApp.run (GUI mode) ────────────────────────────────────────────


class TestRun:
    """ProFileApp.run — lifecycle orchestration."""

    def test_gui_mode_creates_window(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mock_main_window = mocker.patch("profiles.app.MainWindow")
        mock_window_instance = mocker.MagicMock()
        mock_main_window.return_value = mock_window_instance

        app = ProFileApp()
        app.run()
        mock_main_window.assert_called_once()
        mock_window_instance.run.assert_called_once()

    def test_headless_branch_calls_run_headless(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mock_run_headless = mocker.patch.object(ProFileApp, "run_headless", return_value=0)

        app = ProFileApp(headless=True)
        with pytest.raises(SystemExit):
            app.run()
        mock_run_headless.assert_called_once()

    def test_tk_runtime_error_handling(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mocker.patch("profiles.app.MainWindow", side_effect=RuntimeError("no screen available"))

        app = ProFileApp()
        with pytest.raises(SystemExit):
            app.run()

    def test_tk_tcl_error_handling(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        import tkinter

        mocker.patch("profiles.app.MainWindow", side_effect=tkinter.TclError("display error"))

        app = ProFileApp()
        with pytest.raises(SystemExit):
            app.run()

    def test_gui_non_display_error(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """RuntimeError without 'screen'/'display' keyword uses generic message."""
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mocker.patch("profiles.app.MainWindow", side_effect=RuntimeError("Tcl error"))

        app = ProFileApp()
        with pytest.raises(SystemExit):
            app.run()


# ── init_default_config ─────────────────────────────────────────────────────


class TestInitDefaultConfig:
    """init_default_config — generates default .profiles file."""

    def test_creates_file_from_template(self, tmp_path: Path) -> None:
        """Uses the canonical YAML template from config_template module."""
        dest = tmp_path / "output"
        dest.mkdir()
        result = init_default_config(dest)
        assert result.exists()
        assert result.name == ".profiles"
        content = result.read_text(encoding="utf-8")
        # Verify the canonical template content
        assert "ProFiles" in content
        assert "configs:" in content

    def test_existing_file_exits(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("existing", encoding="utf-8")
        with pytest.raises(SystemExit):
            init_default_config(dest=tmp_path)

    def test_default_dest_is_cwd(self, tmp_path: Path, monkeypatch) -> None:
        """Default dest (dest=None) uses CWD."""
        monkeypatch.chdir(tmp_path)
        result = init_default_config()
        assert result == tmp_path / ".profiles"
        assert result.exists()


# ── main() ──────────────────────────────────────────────────────────────────


class TestMain:
    """main() entry point — argument parsing."""

    def test_init_flag(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("sys.argv", ["profiles", "--init"])
        mock_init = mocker.patch("profiles.app.init_default_config")
        main()
        mock_init.assert_called_once()

    def test_headless_flag(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("sys.argv", ["profiles", "--headless"])
        mock_app = mocker.patch("profiles.app.ProFileApp")
        main()
        mock_app.assert_called_once_with(config_path=None, headless=True)
        mock_app.return_value.run.assert_called_once_with(file=None)

    def test_config_and_headless(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("sys.argv", ["profiles", "--config", "custom/.profiles", "--headless"])
        mock_app = mocker.patch("profiles.app.ProFileApp")
        main()
        mock_app.assert_called_once()
        args, kwargs = mock_app.call_args
        assert str(kwargs["config_path"]) == "custom/.profiles"
        assert kwargs["headless"] is True

    def test_file_argument(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("sys.argv", ["profiles", "file.mttl"])
        mock_app = mocker.patch("profiles.app.ProFileApp")
        main()
        mock_app.return_value.run.assert_called_once_with(file="file.mttl")

    def test_default_no_args(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("sys.argv", ["profiles"])
        mock_app = mocker.patch("profiles.app.ProFileApp")
        main()
        mock_app.assert_called_once_with(config_path=None, headless=False)


# ── __main__.py ─────────────────────────────────────────────────────────────


class TestMainModule:
    """profiles.__main__ calls app.main()."""

    def test_main_module_has_module_level_call(self) -> None:
        """The ``main()`` call in ``__main__.py`` is the last statement."""
        import ast

        source = (Path(profiles.__file__).parent / "__main__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        last = tree.body[-1]
        assert isinstance(last, ast.Expr)
        assert isinstance(last.value, ast.Call)
        assert isinstance(last.value.func, ast.Name)
        assert last.value.func.id == "main"


# ── Shortcuts dialog (MainWindow._on_show_shortcuts) ─────────────────────────


@needs_tk
class TestShortcutsDialog:
    """The shortcuts dialog exposes both Keyboard and Mouse sections."""

    def test_shortcuts_dialog_has_mouse_section(self) -> None:
        """Render the dialog on a minimal host and confirm both section headers."""

        class _Host:
            """Minimal duck-typed host with the surface _on_show_shortcuts touches."""

            def __init__(self, root: tk.Tk) -> None:
                self._root = root
                # Stubs for attributes _shortcut_entries references at build time.
                self._refresh_file_list = lambda: None
                self._on_refresh = lambda: None
                self._on_open_log = lambda: None
                self._on_open_config = lambda: None
                self._on_toggle_theme = lambda: None
                self._on_close = lambda: None
                self._on_execute = lambda: None
                self._dir_combo = tk.Entry(root)
                self._ext_combo = tk.Entry(root)
                self._filter_combo = tk.Entry(root)
                self._tree = ttk.Treeview(root)
                self._filter_var = tk.StringVar(root)

            _shortcut_entries = MainWindow._shortcut_entries
            _mouse_entries = MainWindow._mouse_entries
            _on_show_shortcuts = MainWindow._on_show_shortcuts

        root = tk.Tk()
        try:
            host = _Host(root)
            host._on_show_shortcuts()
            root.update_idletasks()

            toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            assert toplevels, "Expected _on_show_shortcuts to create a Toplevel dialog"
            dlg = toplevels[-1]

            def _text_of(widget: tk.Misc) -> str | None:
                if not isinstance(widget, (tk.Widget, ttk.Widget)):
                    return None
                try:
                    return str(widget.cget("text"))
                except (tk.TclError, AttributeError):
                    return None

            labels_text = [t for t in (_text_of(w) for w in dlg.winfo_children()) if t]
            labels_text += [
                t
                for child in dlg.winfo_children()
                if isinstance(child, (tk.Frame, ttk.Frame))
                for t in (_text_of(w) for w in child.winfo_children())
                if t
            ]
            assert "Keyboard Shortcuts" in labels_text
            assert "Mouse Actions" in labels_text
        finally:
            root.destroy()
