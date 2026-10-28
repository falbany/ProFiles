"""Tests for workflow command output capture (``output:`` key + ``{{output}}``)."""

from __future__ import annotations

import logging
import subprocess
from unittest.mock import patch

from profiles.core.config.models import WorkflowStep
from profiles.core.environment.workflow import (
    CommandResult,
    WorkflowOutcome,
    _run_command,
    _substitute_variables,
    run_workflow,
)

_RESULT_OK = CommandResult(code=0, output="")
_RESULT_FAIL = CommandResult(code=1, output="")


def _runner(code: int, output: str):
    def run(command: str, wait: bool, **kwargs):
        return CommandResult(code=code, output=output)

    return run


def _quiet_logger():
    """Return a logger capturing debug records like the other engine tests."""
    records = []
    mock_logger = logging.getLogger("test_workflow_output")
    mock_logger.handlers = [logging.Handler()]
    mock_logger.handlers[0].emit = lambda r: records.append(r)
    mock_logger.setLevel(logging.DEBUG)
    return mock_logger, records


class TestCommandResult:
    """The internal runner returns typed results, not bare bools."""

    def test_run_command_captures_stdout_and_stderr(self):
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 2, stdout=b"probe out\n", stderr=b"probe err\n"
            )
            res = _run_command("probe.exe", True)
        assert res.code == 2
        assert res.output == "probe out\nprobe err\n"
        assert not res.success

    def test_run_command_success(self):
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 0, stdout=b"all good\n", stderr=b""
            )
            res = _run_command("probe.exe", True)
        assert res.success
        assert res.code == 0
        assert res.output == "all good\n"

    def test_run_command_tail_bounded_at_4kb(self):
        """Output is cut to the last 4096 characters with a leading ellipsis."""
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 0, stdout=b"a" * 5000, stderr=b""
            )
            res = _run_command("probe.exe", True)
        assert len(res.output) == 4097  # 1 ellipsis marker + 4096 tail chars
        assert res.output.startswith("…")
        assert res.output.endswith("a" * 4096)

    def test_run_command_under_limit_not_marked(self):
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 0, stdout=b"small", stderr=b""
            )
            res = _run_command("probe.exe", True)
        assert res.output == "small"
        assert not res.output.startswith("…")

    def test_run_command_decodes_invalid_bytes_with_replace(self):
        """Arbitrary byte output is decoded with the locale encoding, errors replaced."""
        with (
            patch(
                "profiles.core.environment.workflow.locale.getpreferredencoding",
                return_value="ascii",
            ),
            patch("profiles.core.environment.workflow.subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 0, stdout=b"bad: \xff ok", stderr=b""
            )
            res = _run_command("probe.exe", True)
        assert res.output == "bad: \ufffd ok"

    def test_run_command_async_spawn_no_capture(self):
        """A detached spawn yields code 0 with empty output."""
        with patch("profiles.core.environment.workflow.subprocess.Popen") as mock_popen:
            res = _run_command("spy.exe", False)
        mock_popen.assert_called_once()
        assert res.success
        assert res.code == 0
        assert res.output == ""

    def test_run_command_timeout_returns_nonzero(self):
        with patch(
            "profiles.core.environment.workflow.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="slow.exe", timeout=1),
        ):
            res = _run_command("slow.exe", True, timeout=1)
        assert not res.success
        assert res.output == ""

    def test_run_command_exception_returns_nonzero(self):
        with patch(
            "profiles.core.environment.workflow.subprocess.run",
            side_effect=OSError("boom"),
        ):
            res = _run_command("crash.exe", True)
        assert not res.success
        assert res.output == ""


class TestOutputToken:
    """``{{output}}`` substitutes the previous blocking step's captured output."""

    def test_next_step_message_substitutes_output(self):
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(0, "probe ok"),
        ):
            steps = [
                WorkflowStep(action="check", command="probe.exe", output="fail_only"),
                WorkflowStep(action="run", command="prepare.exe", message="Got: {{output}}"),
            ]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append(m))
        assert "Got: probe ok" in notices

    def test_next_step_command_substitutes_output(self):
        commands = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: (
                commands.append(cmd),
                CommandResult(code=0, output="probe ok"),
            )[1],
        ):
            steps = [
                WorkflowStep(action="check", command="probe.exe"),
                WorkflowStep(action="run", command="log.exe --text {output}"),
            ]
            run_workflow(steps, None, failmode="warn")
        assert commands == ["probe.exe", "log.exe --text probe ok"]

    def test_output_token_empty_before_any_command(self):
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: _RESULT_OK,
        ):
            steps = [WorkflowStep(action="notify", message="Out: {{output}}")]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append(m))
        assert notices == ["Out: "]

    def test_output_token_refers_to_most_recent_command(self):
        """A later command's output replaces the earlier one."""
        outputs = iter(
            [CommandResult(code=0, output="first"), CommandResult(code=0, output="second")]
        )
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: next(outputs),
        ):
            steps = [
                WorkflowStep(action="check", command="probe1.exe"),
                WorkflowStep(action="notify", message="After first: {{output}}"),
                WorkflowStep(action="check", command="probe2.exe"),
                WorkflowStep(action="notify", message="After second: {{output}}"),
            ]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append(m))
        assert "After first: first" in notices
        assert "After second: second" in notices

    def test_substitute_variables_output_token(self):
        res = _substitute_variables("Out: {{output}}", None, output="blob")
        assert res == "Out: blob"
        res2 = _substitute_variables("Out: {output}", None, output="blob")
        assert res2 == "Out: blob"


class TestOutputDisplay:
    """Per-step ``output:`` controls whether captured output is shown."""

    def test_output_show_displays_after_success(self):
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(0, "hello stdout"),
        ):
            steps = [WorkflowStep(action="run", command="tool.exe", output="show")]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append((m, w)))
        assert ("hello stdout", False) in notices

    def test_output_fail_only_not_displayed_on_success(self):
        notices = []

        def notifier(msg: str, wait: bool) -> None:
            notices.append(msg or "")

        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(0, "secret blob"),
        ):
            steps = [WorkflowStep(action="run", command="tool.exe", output="fail_only")]
            run_workflow(steps, None, notify_callback=notifier)
        assert "secret blob" not in notices

    def test_output_hide_never_displayed_on_success(self):
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(0, "quiet blob"),
        ):
            steps = [WorkflowStep(action="run", command="tool.exe", output="hide")]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append(m))
        assert notices == []

    def test_fail_mode_only_shown_on_failure(self):
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(2, "ERROR: bad probe"),
        ):
            steps = [
                WorkflowStep(
                    action="check",
                    command="env_check.exe",
                    output="fail_only",
                    on_failure="continue",
                )
            ]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append(m))
        joined = "\n".join(notices)
        assert "rc=2" in joined
        assert "ERROR: bad probe" in joined

    def test_show_also_displayed_on_failure(self):
        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(3, "traceback text"),
        ):
            steps = [
                WorkflowStep(
                    action="run",
                    command="tool.exe",
                    output="show",
                    on_failure="continue",
                )
            ]
            run_workflow(steps, None, notify_callback=lambda m, w: notices.append(m))
        joined = "\n".join(notices)
        assert "rc=3" in joined
        assert "traceback text" in joined


class TestFailureNoticeEnrichment:
    """Failure context entries carry the exit code, and output when applicable."""

    def test_failure_context_includes_exit_code(self):
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(2, "probe details"),
        ):
            steps = [WorkflowStep(action="check", command="env_check.exe", output="hide")]
            ctx: list[str] = []
            outcome = run_workflow(steps, None, failure_context=ctx)
        assert outcome == WorkflowOutcome.ABORT
        assert ctx
        assert "rc=2" in ctx[0]
        assert "env_check.exe" in ctx[0]
        # hide mode: no captured output in the failure entry
        assert "probe details" not in ctx[0]

    def test_failure_context_includes_output_when_fail_only(self):
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(2, "ERROR: missing PROD license"),
        ):
            steps = [
                WorkflowStep(
                    action="check",
                    command="env_check.exe --verify",
                    output="fail_only",
                )
            ]
            ctx: list[str] = []
            outcome = run_workflow(steps, None, failure_context=ctx)
        assert outcome == WorkflowOutcome.ABORT
        assert ctx
        assert "rc=2" in ctx[0]
        assert "Last output" in ctx[0]
        assert "ERROR: missing PROD license" in ctx[0]

    def test_show_mode_failure_entry_includes_output(self):
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(1, "trace lines"),
        ):
            steps = [WorkflowStep(action="run", command="tool.exe", output="show")]
            ctx: list[str] = []
            outcome = run_workflow(steps, None, failure_context=ctx)
        assert outcome == WorkflowOutcome.ABORT
        assert "trace lines" in ctx[0]

    def test_aborted_status_code_recorded_without_output_config(self):
        """Exit code is recorded for every failing step, even output: hide."""
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(7, "data"),
        ):
            steps = [WorkflowStep(action="check", command="bogus.exe")]
            ctx: list[str] = []
            outcome = run_workflow(steps, None, failure_context=ctx)
        assert outcome == WorkflowOutcome.ABORT
        assert "rc=7" in ctx[0]


class TestOutputOnNonBlockingSteps:
    """``output:`` on detached steps is ignored, with a debug-level log."""

    def test_run_after_ignores_output(self):
        notices = []
        mock_logger, records = _quiet_logger()
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: _RESULT_OK,
        ):
            steps = [WorkflowStep(action="run_after", command="logger.exe", output="show")]
            run_workflow(
                steps,
                None,
                notify_callback=lambda m, w: notices.append(m),
                logger=mock_logger,
            )
        assert notices == []
        assert any("'output' is ignored" in str(r.msg % r.args) for r in records)

    def test_run_wait_false_ignores_output(self):
        notices = []
        mock_logger, records = _quiet_logger()
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: _RESULT_OK,
        ):
            steps = [WorkflowStep(action="run", command="logger.exe", wait=False, output="show")]
            run_workflow(
                steps,
                None,
                notify_callback=lambda m, w: notices.append(m),
                logger=mock_logger,
            )
        assert notices == []
        assert any("'output' is ignored" in str(r.msg % r.args) for r in records)

    def test_async_step_does_not_update_output_token(self):
        commands = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: commands.append(cmd) or _RESULT_OK,
        ):
            steps = [
                WorkflowStep(action="run_after", command="detached.exe", output="show"),
                WorkflowStep(action="run", command="echo {{output}}"),
            ]
            run_workflow(steps, None)
        assert commands == ["detached.exe", "echo "]


class TestOutputThroughHeadless:
    """Headless mode gets the captured output through the print channel."""

    def test_output_show_prints_in_headless(self, capsys):
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_runner(0, "headless blob"),
        ):
            steps = [WorkflowStep(action="run", command="tool.exe", output="show")]
            run_workflow(steps, None, headless=True)
        out = capsys.readouterr().out
        assert "headless blob" in out


class TestReplaceOutputShow:
    """``output: show`` also applies to replace (blocking) steps."""

    def test_replace_display_output_and_stash_token(self):
        notices = []
        commands = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=lambda cmd, **kw: (
                commands.append(cmd),
                CommandResult(code=0, output="replace blob"),
            )[1],
        ):
            steps = [
                WorkflowStep(action="replace", command="tool.exe", output="show"),
            ]
            outcome = run_workflow(
                steps,
                None,
                notify_callback=lambda m, w: notices.append(m if isinstance(m, str) else ""),
            )
        assert outcome == WorkflowOutcome.SKIP_LAUNCH
        assert "replace blob" in " ".join(notices)


class TestRunnerLogging:
    """_run_command emits telemetry events and debug traces via *logger*."""

    def test_blocking_logs_command_exit(self):
        mock_logger, records = _quiet_logger()
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(["x"], 0, stdout=b"", stderr=b"")
            _run_command("ok.exe", True, logger=mock_logger)
        assert any("COMMAND_EXIT" in str(r.msg % r.args) for r in records)

    def test_spawn_logs_debug(self):
        mock_logger, records = _quiet_logger()
        with patch("profiles.core.environment.workflow.subprocess.Popen"):
            _run_command("spy.exe", False, logger=mock_logger)
        assert any("spawned in background" in str(r.msg % r.args) for r in records)

    def test_timeout_logs_event(self):
        mock_logger, records = _quiet_logger()
        with patch(
            "profiles.core.environment.workflow.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="slow.exe", timeout=1),
        ):
            _run_command("slow.exe", True, timeout=1, logger=mock_logger)
        assert any("COMMAND_TIMEOUT" in str(r.msg % r.args) for r in records)

    def test_error_logs_event(self):
        mock_logger, records = _quiet_logger()
        with patch(
            "profiles.core.environment.workflow.subprocess.run",
            side_effect=OSError("boom"),
        ):
            _run_command("crash.exe", True, logger=mock_logger)
        assert any("COMMAND_FAILED" in str(r.msg % r.args) for r in records)

    def test_blocking_logs_command_output(self):
        mock_logger, records = _quiet_logger()
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 0, stdout=b"line one\nline two\n", stderr=b""
            )
            _run_command("loud.exe", True, logger=mock_logger)
        logged = [str(r.msg % r.args) for r in records if "COMMAND_OUTPUT" in str(r.msg % r.args)]
        assert len(logged) == 1
        assert logged[0].startswith("COMMAND_OUTPUT code=0")
        assert 'output="line one\\nline two\\n"' in logged[0]

    def test_failing_command_output_logged_at_warning(self):
        mock_logger, records = _quiet_logger()
        with patch("profiles.core.environment.workflow.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                ["x"], 3, stdout=b"", stderr=b"boom\n"
            )
            _run_command("failing.exe", True, logger=mock_logger)
        logged = [r for r in records if "COMMAND_OUTPUT" in str(r.msg % r.args)]
        assert len(logged) == 1
        assert logged[0].levelno == logging.WARNING

    def test_spawn_does_not_log_command_output(self):
        mock_logger, records = _quiet_logger()
        with patch("profiles.core.environment.workflow.subprocess.Popen"):
            _run_command("spy.exe", False, logger=mock_logger)
        assert not any("COMMAND_OUTPUT" in str(r.msg % r.args) for r in records)


class TestUnknownRcFailure:
    """When no rc is known, the failure text keeps the plain form."""

    def test_resolve_failure_without_rc(self):
        from profiles.core.environment.workflow import _resolve_failure

        ctx: list[str] = []
        outcome = _resolve_failure("stop", "abort", step_command="x.exe", failure_context=ctx)
        assert outcome == WorkflowOutcome.ABORT
        assert ctx == ["Step failed: x.exe"]
