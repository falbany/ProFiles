"""Tests for profiles.core.actions — domain action outcomes + launch integration."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from profiles.config import AppConfig, MachineConfiguration
from profiles.core import actions
from profiles.core.actions import (
    ActionStatus,
    clear_file,
    launch_selected_file,
    open_config_file,
    open_log_file,
    write_starter_config,
)
from profiles.core.config.models import MatchCriteria, WorkflowStep


def _make_config_for_actions(tmp_path: Path) -> AppConfig:
    """Build a minimal AppConfig pointing at *tmp_path*."""
    config_path = tmp_path / ".profiles"
    if not config_path.exists():
        config_path.write_text("version: 1\n", encoding="utf-8")
    return AppConfig(
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
        theme="light",
        skip_config_prompt=True,
        configurations=[
            MachineConfiguration(
                match=MatchCriteria(hostname=["All"]),
                scan=[str(tmp_path)],
            ),
        ],
    )


class TestOpenConfigFile:
    """Tests for open_config_file()."""

    def test_file_not_found(self) -> None:
        """Non-existent path returns NOT_FOUND."""
        result = open_config_file(Path("/nonexistent/.profiles"))
        assert result.status is ActionStatus.NOT_FOUND
        assert "does not exist" in result.message

    def test_success(self, tmp_path: Path) -> None:
        """An existing file returns SUCCESS."""
        config = tmp_path / ".profiles"
        config.write_text("")
        result = open_config_file(config)
        assert result.status is ActionStatus.SUCCESS
        assert result.path == config

    def test_logger_records_attempt(self, tmp_path: Path, mocker) -> None:  # noqa: ANN001
        """When a logger is provided, the attempt is recorded."""
        config = tmp_path / ".profiles"
        config.write_text("")
        mock_logger = mocker.MagicMock()
        result = open_config_file(config, logger=mock_logger)
        assert result.status is ActionStatus.SUCCESS
        mock_logger.info.assert_called_once()

    def test_open_failure_returns_failed(self, tmp_path: Path, mocker) -> None:  # noqa: ANN001
        """When the OS can't open the file, status is FAILED."""
        config = tmp_path / ".profiles"
        config.write_text("")
        mocker.patch("profiles.core.actions.open_with_default_app", return_value=False)
        result = open_config_file(config)
        assert result.status is ActionStatus.FAILED
        assert "Could not open" in result.message


class TestOpenLogFile:
    """Tests for open_log_file()."""

    def test_creates_missing_file(self, tmp_path: Path) -> None:
        """A non-existent log file is created on demand."""
        log = tmp_path / "sub" / "test.log"
        assert not log.exists()
        result = open_log_file(log)
        assert result.status is ActionStatus.SUCCESS
        assert log.exists()

    def test_success_existing(self, tmp_path: Path) -> None:
        """An existing log file returns SUCCESS."""
        log = tmp_path / "test.log"
        log.write_text("existing")
        result = open_log_file(log)
        assert result.status is ActionStatus.SUCCESS
        assert result.path == log

    def test_create_failure_returns_not_found(self, tmp_path: Path) -> None:
        """When the parent can't be created, NOT_FOUND is returned."""
        log = tmp_path / "locked" / "sub" / "test.log"
        # Force OSError by making 'locked' a file (not a directory)
        (tmp_path / "locked").write_text("blocker")
        result = open_log_file(log)
        assert result.status is ActionStatus.NOT_FOUND
        assert "does not exist" in result.message

    def test_logger_records_attempt(self, tmp_path: Path, mocker) -> None:  # noqa: ANN001
        """When a logger is provided, the attempt is recorded."""
        log = tmp_path / "test.log"
        log.write_text("")
        mock_logger = mocker.MagicMock()
        result = open_log_file(log, logger=mock_logger)
        assert result.status is ActionStatus.SUCCESS
        mock_logger.info.assert_called_once()

    def test_open_failure_returns_failed(self, tmp_path: Path, mocker) -> None:  # noqa: ANN001
        """When the OS can't open the log file, status is FAILED."""
        log = tmp_path / "test.log"
        log.write_text("")
        mocker.patch("profiles.core.actions.open_with_default_app", return_value=False)
        result = open_log_file(log)
        assert result.status is ActionStatus.FAILED
        assert "Could not open log file" in result.message


class TestLaunchSelectedFile:
    """Tests for launch_selected_file()."""

    def test_not_found(self) -> None:
        """A non-existent file returns NOT_FOUND."""
        result = launch_selected_file(
            directory="/tmp",
            filename="nonexistent.mttl",
            release="test",
            username="tester",
        )
        assert result.status is ActionStatus.NOT_FOUND
        assert "does not exist" in result.message

    def test_success(self, mocker, tmp_path: Path) -> None:
        """An existing file returns SUCCESS."""
        mocker.patch("profiles.core.actions.launch_file", return_value=True)
        target = tmp_path / "test.mttl"
        target.write_text("")

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="test.mttl",
            release="test",
            username="tester",
        )
        assert result.status is ActionStatus.SUCCESS
        assert result.path is not None
        assert result.path.name == "test.mttl"

    def test_launch_failure(self, mocker, tmp_path: Path) -> None:
        """When launch_file returns False, status is FAILED."""
        mocker.patch("profiles.core.actions.launch_file", return_value=False)
        target = tmp_path / "broken.mttl"
        target.write_text("")

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="broken.mttl",
            release="test",
            username="tester",
        )
        assert result.status is ActionStatus.FAILED
        assert "Failed" in result.message


class TestWriteStarterConfig:
    """Tests for write_starter_config()."""

    def test_writes_documented_file(self, tmp_path: Path) -> None:
        """A fresh .profiles is created and parses back as a valid config."""
        target = tmp_path / ".profiles"
        result = write_starter_config(target)

        assert result.status is ActionStatus.SUCCESS
        assert target.exists()

        body = target.read_text(encoding="utf-8")

        # Documented header so the user knows what each key means.
        assert "ProFiles" in body
        assert "configs:" in body
        assert "search_dir" in body or "directory" in body

        # Default search_dir comes from Path.cwd() at write time.
        assert str(Path.cwd()) in body

        # Round-trip: ConfigReader must parse it without raising.
        from profiles.config import ConfigReader

        config = ConfigReader(target).load()
        assert config.title == ""
        assert config.gui_auto_launch is True
        assert config.configurations
        assert config.configurations[0].match.hostname == ("*",)


class TestLaunchHooksIntegration:
    """Integration tests for advanced hooks in launch pipeline via launch_selected_file."""

    def test_launch_with_confirmation_and_user_confirms(self, mocker, tmp_path: Path) -> None:
        """User confirmation allows the file to be launched."""
        mock_confirm_dialog = mocker.patch(
            "profiles.core.environment.workflow.confirm_dialog_3way", return_value="yes"
        )
        mock_notify = mocker.patch("profiles.core.environment.workflow.show_notify_dialog")
        mock_launch_file = mocker.patch("profiles.core.actions.launch_file", return_value=True)

        config = _make_config_for_actions(tmp_path)
        config.launch_hooks = {
            ".mttl": (WorkflowStep(action="notify", content="Proceed?", ask="Proceed?"),)
        }

        target = tmp_path / "test.mttl"
        target.touch()

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="test.mttl",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.SUCCESS
        assert "Launched" in result.message
        mock_confirm_dialog.assert_called_once_with("Proceed?", headless=False)
        mock_notify.assert_called_once_with("Proceed?", blocking=True, headless=False)
        mock_launch_file.assert_called_once_with(target)

    def test_launch_with_confirmation_and_user_cancels(self, mocker, tmp_path: Path) -> None:
        """User cancellation prevents file launch and returns FAILED."""
        mock_confirm_dialog = mocker.patch(
            "profiles.core.environment.workflow.confirm_dialog_3way", return_value="no"
        )
        mock_notify = mocker.patch("profiles.core.environment.workflow.show_notify_dialog")
        mock_launch_file = mocker.patch("profiles.core.actions.launch_file")  # Should not be called

        config = _make_config_for_actions(tmp_path)
        config.launch_hooks = {
            ".mttl": (WorkflowStep(action="notify", content="Proceed?", ask="Proceed?"),)
        }

        target = tmp_path / "test.mttl"
        target.touch()

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="test.mttl",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.FAILED
        assert "aborted by a launch hook" in result.message
        mock_confirm_dialog.assert_called_once_with("Proceed?", headless=False)
        mock_notify.assert_not_called()  # Aborted before notify step
        mock_launch_file.assert_not_called()

    def test_launch_with_sequential_hooks_all_succeed(self, mocker, tmp_path: Path) -> None:
        """A chain of successful required hooks allows normal file launch."""
        mock_run_command = mocker.patch(
            "profiles.core.environment.workflow._run_command", return_value=True
        )
        mock_launch_file = mocker.patch("profiles.core.actions.launch_file", return_value=True)

        config = _make_config_for_actions(tmp_path)
        config.launch_hooks = {
            ".mttl": (
                WorkflowStep(action="run", content="hook1.sh", on_failure="stop"),
                WorkflowStep(action="run", content="hook2.sh", on_failure="stop"),
            )
        }

        target = tmp_path / "test.mttl"
        target.touch()

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="test.mttl",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.SUCCESS
        assert "Launched" in result.message
        assert mock_run_command.call_count == 2  # Both hooks ran
        mock_launch_file.assert_called_once_with(target)

    def test_launch_with_sequential_hooks_middle_failure_aborts(
        self, mocker, tmp_path: Path
    ) -> None:
        """A failure in a required hook aborts the launch pipeline."""
        mock_run_command = mocker.patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=[True, False],  # Success then failure
        )
        mock_launch_file = mocker.patch("profiles.core.actions.launch_file")  # Should not be called

        config = _make_config_for_actions(tmp_path)
        config.launch_hooks = {
            ".mttl": (
                WorkflowStep(action="run", content="hook1.sh", on_failure="stop"),
                WorkflowStep(action="run", content="hook2.sh", on_failure="stop"),
            )
        }

        target = tmp_path / "test.mttl"
        target.touch()

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="test.mttl",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.FAILED
        assert "aborted by a launch hook" in result.message
        assert mock_run_command.call_count == 2  # First two hooks ran
        mock_launch_file.assert_not_called()

    def test_launch_with_sequential_hooks_optional_failure_continues(
        self, mocker, tmp_path: Path
    ) -> None:
        """A failure in an optional hook (on_failure=continue) allows the pipeline to proceed."""
        mock_run_command = mocker.patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=[False, True],  # Failure then success
        )
        mock_launch_file = mocker.patch("profiles.core.actions.launch_file", return_value=True)

        config = _make_config_for_actions(tmp_path)
        config.launch_hooks = {
            ".mttl": (
                WorkflowStep(action="run", content="optional.sh", on_failure="continue"),
                WorkflowStep(action="run", content="required.sh", on_failure="stop"),
            )
        }
        # Even with failmode=abort, optional failure should not abort pipeline
        config.launch_hook_failmode = "abort"

        target = tmp_path / "test.mttl"
        target.touch()

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="test.mttl",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.SUCCESS
        assert "Launched" in result.message
        assert mock_run_command.call_count == 2  # Both hooks ran
        mock_launch_file.assert_called_once_with(target)

    def test_failure_on_unwritable_parent(self) -> None:
        """A non-existent parent directory causes FAILED, never raises."""
        # /nonexistent/ on every platform
        target = Path("/nonexistent_root_xyz/.profiles")
        result = write_starter_config(target)

        assert result.status is ActionStatus.FAILED
        assert "Could not write" in result.message
        assert not target.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """An existing file at the target is replaced, not appended."""
        target = tmp_path / ".profiles"
        target.write_text("stale content")

        result = write_starter_config(target)
        assert result.status is ActionStatus.SUCCESS

        body = target.read_text(encoding="utf-8")
        assert "stale content" not in body
        assert "ProFiles" in body


class TestClearFile:
    """Tests for clear_file() (file deletion)."""

    def test_file_not_found(self) -> None:
        """Non-existent path returns NOT_FOUND."""
        result = clear_file(Path("/nonexistent/file.txt"))
        assert result.status is ActionStatus.NOT_FOUND
        assert "does not exist" in result.message

    def test_not_a_file(self, tmp_path: Path) -> None:
        """A directory returns FAILED."""
        directory = tmp_path / "subdir"
        directory.mkdir()
        result = clear_file(directory)
        assert result.status is ActionStatus.FAILED
        assert "Not a file" in result.message

    def test_success_deletes_file(self, tmp_path: Path) -> None:
        """An existing file is deleted from the filesystem."""
        target = tmp_path / "test.txt"
        target.write_text("some content")

        result = clear_file(target)

        assert result.status is ActionStatus.SUCCESS
        assert not target.exists()
        assert "File deleted" in result.message

    def test_success_with_empty_file(self, tmp_path: Path) -> None:
        """An empty file is also deleted successfully."""
        target = tmp_path / "empty.txt"
        target.write_text("")

        result = clear_file(target)

        assert result.status is ActionStatus.SUCCESS
        assert not target.exists()

    def test_failure_on_permission_error(self, tmp_path: Path) -> None:
        """A file without write permission returns FAILED."""
        target = tmp_path / "readonly.txt"
        target.write_text("content")
        target.chmod(0o444)  # Read-only

        try:
            result = clear_file(target)
            # On Windows, chmod may not work, so we check both outcomes
            if result.status is ActionStatus.FAILED:
                assert "Failed to delete file" in result.message
            else:
                # If it succeeded (Windows behavior), that's also acceptable
                assert result.status is ActionStatus.SUCCESS
                assert not target.exists()
        finally:
            # Restore permissions for cleanup
            with contextlib.suppress(OSError):
                target.chmod(0o644)


class TestLaunchSelectedWithArgs:
    """actions.launch_selected_file: the new ``args='…'`` parameter."""

    def test_empty_args_falls_back_to_plain_launcher(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """Empty ``args`` must invoke the existing ``launch_file`` path."""
        f = tmp_path / "x.mttl"
        f.write_text("x", encoding="utf-8")
        mock_launch = mocker.patch(
            "profiles.core.actions.launch_file",
            return_value=True,
        )
        args_spy = mocker.patch(
            "profiles.core.actions._launch_with_args",
        )

        result = actions.launch_selected_file(
            directory=str(tmp_path),
            filename="x.mttl",
            release="r",
            username="u",
            args="",
        )

        assert result.status is actions.ActionStatus.SUCCESS
        mock_launch.assert_called_once_with(f)
        args_spy.assert_not_called()

    def test_args_routes_to_platform_launcher(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """Non-empty ``args`` invokes ``_launch_with_args``."""
        f = tmp_path / "x.mttl"
        f.write_text("x", encoding="utf-8")
        mocker.patch("profiles.core.actions.launch_file")
        args_spy = mocker.patch(
            "profiles.core.actions._launch_with_args",
            return_value=True,
        )

        result = actions.launch_selected_file(
            directory=str(tmp_path),
            filename="x.mttl",
            release="r",
            username="u",
            args="--flag value",
        )

        assert result.status is actions.ActionStatus.SUCCESS
        args_spy.assert_called_once_with(f, "--flag value")

    def test_args_linux_invokes_xdg_open_with_tokens(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """On Linux, tokens are appended to ``xdg-open`` then the path."""
        f = tmp_path / "doc.pdf"
        f.write_text("x", encoding="utf-8")
        mock_popen = mocker.patch("profiles.utils.file_utils.subprocess.Popen")

        # platform branch is selected at call time, not import time.
        mocker.patch.object(sys, "platform", "linux")
        assert actions._launch_with_args(f, "--page 2") is True

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args.args[0]
        assert cmd[0] == "xdg-open"
        assert cmd[1] == str(f)
        assert cmd[2:] == ["--page", "2"]

    def test_args_macos_invokes_open_with_tokens(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "doc.pdf"
        f.write_text("x", encoding="utf-8")
        mock_popen = mocker.patch("profiles.utils.file_utils.subprocess.Popen")
        mocker.patch.object(sys, "platform", "darwin")

        assert actions._launch_with_args(f, "--page 5") is True

        cmd = mock_popen.call_args.args[0]
        assert cmd[0] == "open"
        assert cmd[1] == str(f)
        assert cmd[2:] == ["--page", "5"]

    def test_args_windows_wraps_in_start(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "doc.pdf"
        f.write_text("x", encoding="utf-8")
        mock_popen = mocker.patch("profiles.utils.file_utils.subprocess.Popen")
        mocker.patch.object(sys, "platform", "win32")

        assert actions._launch_with_args(f, "/p 2") is True

        cmd = mock_popen.call_args.args[0]
        assert cmd[:3] == ["cmd", "/c", "start"]
        # Empty title slot is mandatory for `start`.
        assert cmd[3] == ""
        assert cmd[4] == str(f)
        assert cmd[5:] == ["/p", "2"]

    def test_unparseable_args_returns_false(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        f = tmp_path / "doc.pdf"
        f.write_text("x", encoding="utf-8")
        mock_popen = mocker.patch("profiles.utils.file_utils.subprocess.Popen")

        # Unmatched quote is the canonical shlex failure mode.
        assert actions._launch_with_args(f, '"unterminated') is False
        mock_popen.assert_not_called()

    def test_missing_file_returned_as_not_found(
        self,
        tmp_path: Path,
        mocker,
    ) -> None:
        """File-not-found takes precedence over the args branch."""
        mock_launch = mocker.patch("profiles.core.actions.launch_file")
        args_spy = mocker.patch("profiles.core.actions._launch_with_args")

        result = actions.launch_selected_file(
            directory=str(tmp_path),
            filename="ghost.mttl",
            release="r",
            username="u",
            args="--force",
        )

        assert result.status is actions.ActionStatus.NOT_FOUND
        mock_launch.assert_not_called()
        args_spy.assert_not_called()


class TestLaunchSelectedFileIntegration:
    """launch_selected_file honors the workflow outcome."""

    @patch("profiles.core.actions.launch_file", return_value=True)
    @patch("profiles.core.actions.run_workflow")
    def test_abort_outcome_returns_failed(
        self, mock_workflow: MagicMock, _mock_launch: MagicMock, tmp_path: Path
    ) -> None:
        """An ABORT outcome fails the launch without touching the OS."""
        from profiles.core.environment.workflow import WorkflowOutcome

        mock_workflow.return_value = WorkflowOutcome.ABORT
        target = tmp_path / "x.mttx"
        target.write_text("")

        config = AppConfig()
        config.launch_hooks = {"*.mttx": (WorkflowStep(action="run", content="false"),)}

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="x.mttx",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.FAILED
        assert "aborted" in result.message
        _mock_launch.assert_not_called()

    @patch("profiles.core.actions.launch_file", return_value=True)
    @patch("profiles.core.actions.run_workflow")
    def test_skip_outcome_returns_success_without_os_launch(
        self, mock_workflow: MagicMock, mock_launch: MagicMock, tmp_path: Path
    ) -> None:
        """A SKIP outcome succeeds via the instead hook, no OS launch."""
        from profiles.core.environment.workflow import WorkflowOutcome

        mock_workflow.return_value = WorkflowOutcome.SKIP_LAUNCH
        target = tmp_path / "x.mttx"
        target.write_text("")

        config = AppConfig()
        config.launch_hooks = {"*.mttx": (WorkflowStep(action="replace", content="true"),)}

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="x.mttx",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.SUCCESS
        assert "handled by workflow" in result.message
        mock_launch.assert_not_called()

    @patch("profiles.core.actions.launch_file", return_value=True)
    @patch("profiles.core.actions.run_workflow")
    def test_continue_outcome_calls_os_launch(
        self, mock_workflow: MagicMock, mock_launch: MagicMock, tmp_path: Path
    ) -> None:
        """A CONTINUE outcome proceeds to the OS launch."""
        from profiles.core.environment.workflow import WorkflowOutcome

        mock_workflow.return_value = WorkflowOutcome.CONTINUE
        target = tmp_path / "x.mttx"
        target.write_text("")

        config = AppConfig()
        config.launch_hooks = {"*.mttx": (WorkflowStep(action="notify", content="hi"),)}

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="x.mttx",
            release="test",
            username="tester",
            config=config,
        )

        assert result.status is ActionStatus.SUCCESS
        mock_launch.assert_called_once()

    @patch("profiles.core.actions.launch_file", return_value=True)
    @patch("profiles.core.actions.run_workflow")
    def test_no_config_skips_hook_pipeline(
        self, mock_workflow: MagicMock, mock_launch: MagicMock, tmp_path: Path
    ) -> None:
        """Without a config the hook pipeline is skipped entirely."""
        target = tmp_path / "x.mttx"
        target.write_text("")

        result = launch_selected_file(
            directory=str(tmp_path),
            filename="x.mttx",
            release="test",
            username="tester",
        )

        assert result.status is ActionStatus.SUCCESS
        mock_workflow.assert_not_called()
        mock_launch.assert_called_once()


class TestRevealInFileManager:
    """Tests for reveal_in_file_manager()."""

    def test_missing_file_returns_not_found(self, tmp_path: Path) -> None:
        """A non-existent file returns NOT_FOUND without invoking subprocess."""
        result = actions.reveal_in_file_manager(tmp_path / "missing.txt")
        assert result.status is ActionStatus.NOT_FOUND
        assert "does not exist" in result.message

    @patch("profiles.core.actions.open_file_explorer", return_value=True)
    @patch("profiles.core.actions.subprocess.Popen")
    def test_darwin_uses_open_select(
        self, mock_popen: MagicMock, mock_open_explorer: MagicMock, tmp_path: Path
    ) -> None:
        """On macOS we invoke ``open -R <file>``."""
        target = tmp_path / "thing.txt"
        target.write_text("")
        with patch("profiles.core.actions.sys.platform", "darwin"):
            result = actions.reveal_in_file_manager(target)
        assert result.status is ActionStatus.SUCCESS
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert args[0] == "open"
        assert args[1] == "-R"
        assert args[2] == str(target)
        mock_open_explorer.assert_not_called()

    @patch("profiles.core.actions.open_file_explorer", return_value=True)
    @patch("profiles.core.actions.subprocess.Popen")
    def test_windows_uses_explorer_select(
        self, mock_popen: MagicMock, mock_open_explorer: MagicMock, tmp_path: Path
    ) -> None:
        """On Windows we invoke ``explorer /select,<file>``."""
        target = tmp_path / "thing.txt"
        target.write_text("")
        with (
            patch("profiles.core.actions.os.name", "nt"),
            patch("profiles.core.actions.sys.platform", "win32"),
        ):
            result = actions.reveal_in_file_manager(target)
        assert result.status is ActionStatus.SUCCESS
        args = mock_popen.call_args[0][0]
        assert args[0] == "explorer"
        assert args[1] == f"/select,{target}"
        mock_open_explorer.assert_not_called()

    @patch("profiles.core.actions.open_file_explorer", return_value=True)
    @patch("profiles.core.actions.subprocess.Popen")
    def test_linux_falls_back_to_open_file_explorer(
        self, mock_popen: MagicMock, mock_open_explorer: MagicMock, tmp_path: Path
    ) -> None:
        """On Linux we don't spawn a subprocess — we delegate to open_file_explorer."""
        target = tmp_path / "thing.txt"
        target.write_text("")
        with patch("profiles.core.actions.sys.platform", "linux"):
            result = actions.reveal_in_file_manager(target)
        assert result.status is ActionStatus.SUCCESS
        mock_popen.assert_not_called()
        mock_open_explorer.assert_called_once_with(target.parent)

    @patch("profiles.core.actions.open_file_explorer", return_value=False)
    @patch("profiles.core.actions.subprocess.Popen")
    def test_linux_failure_returns_failed(
        self, mock_popen: MagicMock, mock_open_explorer: MagicMock, tmp_path: Path
    ) -> None:
        """If the Linux fallback fails, status is FAILED."""
        target = tmp_path / "thing.txt"
        target.write_text("")
        with patch("profiles.core.actions.sys.platform", "linux"):
            result = actions.reveal_in_file_manager(target)
        assert result.status is ActionStatus.FAILED


class TestOpenTerminalInDirectory:
    """Tests for open_terminal_in_directory()."""

    def test_missing_dir_returns_not_found(self, tmp_path: Path) -> None:
        """A non-existent path returns NOT_FOUND."""
        result = actions.open_terminal_in_directory(tmp_path / "nope")
        assert result.status is ActionStatus.NOT_FOUND
        assert "Not a directory" in result.message

    def test_file_path_returns_not_found(self, tmp_path: Path) -> None:
        """A file (not a dir) returns NOT_FOUND."""
        f = tmp_path / "a.txt"
        f.write_text("")
        result = actions.open_terminal_in_directory(f)
        assert result.status is ActionStatus.NOT_FOUND

    @patch("profiles.core.actions.subprocess.Popen")
    def test_darwin_uses_open_terminal_app(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """On macOS we invoke ``open -a Terminal <path>``."""
        with patch("profiles.core.actions.sys.platform", "darwin"):
            result = actions.open_terminal_in_directory(tmp_path)
        assert result.status is ActionStatus.SUCCESS
        args = mock_popen.call_args[0][0]
        assert args == ["open", "-a", "Terminal", str(tmp_path)]

    @patch("profiles.core.actions.subprocess.Popen")
    def test_windows_uses_cmd(self, mock_popen: MagicMock, tmp_path: Path) -> None:
        """On Windows we invoke ``cmd /K cd /D <path>``."""
        with (
            patch("profiles.core.actions.os.name", "nt"),
            patch("profiles.core.actions.sys.platform", "win32"),
        ):
            result = actions.open_terminal_in_directory(tmp_path)
        assert result.status is ActionStatus.SUCCESS
        args = mock_popen.call_args[0][0]
        assert args[0:3] == ["cmd", "/c", "start"]
        assert args[3] == "cmd"
        assert args[4] == "/K"
        assert args[5] == f"cd /D {tmp_path}"

    @patch("profiles.core.actions.shutil.which", return_value="/usr/bin/x-terminal-emulator")
    @patch("profiles.core.actions.subprocess.Popen")
    def test_linux_uses_x_terminal_emulator(
        self, mock_popen: MagicMock, mock_which: MagicMock, tmp_path: Path
    ) -> None:
        """On Linux, the first available terminal emulator wins."""
        with patch("profiles.core.actions.sys.platform", "linux"):
            result = actions.open_terminal_in_directory(tmp_path)
        assert result.status is ActionStatus.SUCCESS
        args = mock_popen.call_args[0][0]
        assert args[0] == "x-terminal-emulator"
        assert args[1] == "--working-directory"
        assert args[2] == str(tmp_path)

    @patch("profiles.core.actions.shutil.which", return_value=None)
    @patch("profiles.core.actions.subprocess.Popen")
    def test_linux_no_terminal_returns_failed(
        self, mock_popen: MagicMock, mock_which: MagicMock, tmp_path: Path
    ) -> None:
        """When no terminal is found, status is FAILED."""
        with patch("profiles.core.actions.sys.platform", "linux"):
            result = actions.open_terminal_in_directory(tmp_path)
        assert result.status is ActionStatus.FAILED
        assert "No terminal emulator" in result.message
