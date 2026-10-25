"""Tests for profiles.app — ProFileApp, main(), init_default_config.

Also tests profiles.__init__ package metadata and __main__ entry point.

Tkinter-backend lifecycle tests live under ``tests/gui`` (deprecated
frontend; skipped there in preparation for removal).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

import profiles
from profiles.app import ProFileApp, init_default_config, main
from profiles.core.telemetry.diagnostics import default_log_path
from profiles.desktop.lifecycle import ServerStartError

# ── Package metadata (__init__.py) ──────────────────────────────────────────


def _canonical_version() -> str:
    """Return [project].version — the single source of truth."""
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject["project"]["version"]


class TestPackageMetadata:
    """profiles.__init__ exports version, author, license."""

    def test_version(self) -> None:
        assert profiles.__version__ == _canonical_version()

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
        assert app._log_path == default_log_path()
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
        mocker.patch("profiles.app.get_username", return_value="testuser")
        mock_configure = mocker.patch("profiles.app.configure_logger")
        app = ProFileApp()
        app._setup_logging()
        mock_configure.assert_called_once()
        args, kwargs = mock_configure.call_args
        assert kwargs["source"] == "testuser@HOST"
        assert kwargs["level"] == 20  # logging.INFO

    def test_installs_crash_hook(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """_setup_logging installs the uncaught-exception hook on the logger."""
        import logging as logging_module

        mocker.patch("profiles.app.get_hostname", return_value="HOST")
        mocker.patch("profiles.app.get_username", return_value="testuser")
        logger = logging_module.getLogger("app_test_crash_hook")
        mocker.patch("profiles.app.configure_logger", return_value=logger)
        mock_hook = mocker.patch("profiles.app.install_crash_hook")
        app = ProFileApp()
        result = app._setup_logging()
        mock_hook.assert_called_once_with(result)


# ── ProFileApp._load_configuration ───────────────────────────────────────


class TestLoadConfiguration:
    """_load_configuration loads config or exits on error."""

    def test_loads_config_successfully(self, mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        resolved = tmp_path / ".profiles"
        # The file must exist: launch-time resolution flags a missing file
        # and exits before load_config is ever reached.
        resolved.write_text("", encoding="utf-8")
        mocker.patch("profiles.app.resolve_config_path", return_value=resolved)
        mock_load = mocker.patch("profiles.app.load_config")
        app = ProFileApp()
        mock_logger = mocker.MagicMock()
        app._load_configuration(mock_logger)
        mock_load.assert_called_once_with(resolved)

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
    """ProFileApp.run — lifecycle orchestration (web/headless branches).

    The deprecated tk-backend branch is covered by
    ``tests/gui/test_app_tk_lifecycle.py``.
    """

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

    def test_web_gui_startup_failure_exits_cleanly(self, mocker, capsys) -> None:  # type: ignore[no-untyped-def]
        """A port collision exits 1 with an actionable message, no traceback."""
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mocker.patch(
            "profiles.desktop.launcher.launch_desktop_window",
            side_effect=ServerStartError("ProFiles server failed to start on 127.0.0.1:8088: 3"),
        )

        app = ProFileApp()
        app._config = mock_config
        with pytest.raises(SystemExit) as excinfo:
            app._run_web_gui()

        assert excinfo.value.code == 1
        err = capsys.readouterr().err
        assert "failed to start on 127.0.0.1:8088" in err
        # The fix must be copy-pasteable, not a vague "stop the other instance"
        assert "kill $(lsof -ti:8088 -sTCP:LISTEN)" in err
        assert "another process is already using this port" in err.lower()


class TestStopPortOwnerCommand:
    """_stop_port_owner_command - the advice embedded in startup errors."""

    def test_includes_port_and_a_kill_verb(self) -> None:
        from profiles.app import _stop_port_owner_command

        cmd = _stop_port_owner_command(8088)
        assert "8088" in cmd
        assert cmd.split()[0] in {"kill", "taskkill", "for"}

    def test_filters_to_listeners_only(self) -> None:
        """Client connections are not what blocks a bind - don't invite killing them."""
        from profiles.app import _stop_port_owner_command

        cmd = _stop_port_owner_command(8088)
        if sys.platform != "win32":
            assert "-sTCP:LISTEN" in cmd

    def test_uses_windows_syntax_on_windows(self, mocker) -> None:  # type: ignore[no-untyped-def]
        from profiles.app import _stop_port_owner_command

        mocker.patch("profiles.app.sys.platform", "win32")
        cmd = _stop_port_owner_command(8088)
        assert "netstat" in cmd
        assert "taskkill" in cmd


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
        mock_app.assert_called_once_with(
            config_path=None,
            headless=True,
            server_only=False,
            no_config_propose=False,
            gui_backend="web",
        )
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
        mock_app.assert_called_once_with(
            config_path=None,
            headless=False,
            server_only=False,
            no_config_propose=False,
            gui_backend="web",
        )


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
