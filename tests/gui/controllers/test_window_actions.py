"""Tests for the WindowActions controller."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from profiles.core.actions import ActionResult, ActionStatus
from profiles.core.config.models import AppConfig
from profiles.gui.controllers.window_actions import WindowActions


def _actions() -> tuple[WindowActions, MagicMock]:
    destroy = MagicMock()
    return (
        WindowActions(
            config=AppConfig(),
            logger=MagicMock(),
            root_destroy=destroy,
        ),
        destroy,
    )


class TestRestart:
    """restart() destroys the window then spawns a new Python process."""

    def test_destroy_called(self) -> None:
        acts, destroy = _actions()
        with (
            patch("profiles.gui.controllers.window_actions.subprocess"),
            patch("profiles.gui.controllers.window_actions.sys") as sys_mock,
        ):
            sys_mock.executable = "python.exe"
            acts.restart()
        destroy.assert_called_once()

    def test_popen_receives_module_flag(self) -> None:
        acts, _ = _actions()
        with (
            patch("profiles.gui.controllers.window_actions.subprocess") as popen_mock,
            patch("profiles.gui.controllers.window_actions.sys") as sys_mock,
        ):
            sys_mock.executable = "python.exe"
            acts.restart()
        args = popen_mock.Popen.call_args.args[0]
        assert args[0] == "python.exe"
        assert "-m" in args
        assert "profiles" in args

    def test_oserror_shows_messagebox(self) -> None:
        acts, _ = _actions()
        with (
            patch("profiles.gui.controllers.window_actions.subprocess") as popen_mock,
            patch("profiles.gui.controllers.window_actions.sys") as sys_mock,
            patch("profiles.gui.controllers.window_actions.messagebox") as msg_mock,
        ):
            sys_mock.executable = "python.exe"
            popen_mock.Popen.side_effect = OSError("nope")
            acts.restart()
        msg_mock.showerror.assert_called_once()
        assert "Restart Failed" in msg_mock.showerror.call_args.args[0]


class TestOpenLog:
    """open_log() delegates to core.actions and shows a dialog on failure."""

    def test_success_no_dialog(self) -> None:
        acts, _ = _actions()
        with (
            patch("profiles.gui.controllers.window_actions.actions.open_log_file") as open_log_mock,
            patch("profiles.gui.controllers.window_actions.messagebox") as msg_mock,
        ):
            open_log_mock.return_value = ActionResult(status=ActionStatus.SUCCESS, message="ok")
            acts.open_log(Path("logs/profiles.log"))
        msg_mock.showerror.assert_not_called()

    def test_failure_shows_dialog(self) -> None:
        acts, _ = _actions()
        with (
            patch("profiles.gui.controllers.window_actions.actions.open_log_file") as open_log_mock,
            patch("profiles.gui.controllers.window_actions.messagebox") as msg_mock,
        ):
            open_log_mock.return_value = ActionResult(status=ActionStatus.FAILED, message="missing")
            acts.open_log(Path("logs/profiles.log"))
        msg_mock.showerror.assert_called_once()
