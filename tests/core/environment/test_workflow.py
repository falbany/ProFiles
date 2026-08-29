"""Tests for workflow engine core execution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from profiles.core.config.models import WorkflowStep
from profiles.core.environment.workflow import WorkflowOutcome, run_workflow


def test_workflow_no_steps():
    outcome = run_workflow([], None)
    assert outcome == WorkflowOutcome.CONTINUE


def test_workflow_notify_step():
    notifications = []

    def mock_notify(content: str, wait: bool):
        notifications.append((content, wait))

    steps = [WorkflowStep(action="notify", content="Hello")]
    outcome = run_workflow(steps, None, notify_callback=mock_notify)
    assert outcome == WorkflowOutcome.CONTINUE
    assert len(notifications) == 1
    assert notifications[0][0] == "Hello"


def test_workflow_replace_step(tmp_path: Path):
    steps = [WorkflowStep(action="replace", content="echo test")]
    outcome = run_workflow(steps, tmp_path / "test.txt")
    assert outcome == WorkflowOutcome.SKIP_LAUNCH


def test_workflow_skip_step_over():
    steps = [
        WorkflowStep(action="run", content="echo 1", ask="Skip?"),
        WorkflowStep(action="run", content="echo 2"),
    ]
    outcome = run_workflow(steps, None, user_choice="skip")
    assert outcome == WorkflowOutcome.CONTINUE


def test_timeout_aborts_on_run_failure():
    """A timed-out command on a ``run`` step with on_failure=stop → ABORT."""
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=False
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", content="sleep 10", on_failure="stop")
        ]
        outcome = run_workflow(steps, None, timeout=1)
        assert outcome == WorkflowOutcome.ABORT
        mock_cmd.assert_called_once()
        assert mock_cmd.call_args.kwargs["timeout"] == 1


def test_failmode_abort_triggers_via_unknown_on_failure():
    """An unknown on_failure value falls back to global failmode=abort → ABORT.

    (Python does not enforce Literal at runtime, so we pass a sentinel value.)
    """
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=False
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", content="false", on_failure="unknown_value")
        ]
        outcome = run_workflow(steps, None, failmode="abort")
        assert outcome == WorkflowOutcome.ABORT
        mock_cmd.assert_called_once()


def test_failmode_skip_triggers_via_unknown_on_failure():
    """An unknown on_failure value with failmode=skip → SKIP_LAUNCH."""
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=False
    ):
        steps = [
            WorkflowStep(action="run", content="false", on_failure="unknown_value")
        ]
        outcome = run_workflow(steps, None, failmode="skip")
        assert outcome == WorkflowOutcome.SKIP_LAUNCH


def test_failmode_warn_continues():
    """failmode=warn with on_failure=continue → CONTINUE."""
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=False
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", content="false", on_failure="continue")
        ]
        outcome = run_workflow(steps, None, failmode="warn")
        assert outcome == WorkflowOutcome.CONTINUE
        mock_cmd.assert_called_once()


def test_on_failure_warn_logs_continue():
    """on_failure=warn logs a warning and continues, ignoring failmode."""
    import logging

    log_records = []
    mock_logger = logging.getLogger("test_warn_logs")
    mock_logger.handlers = [logging.Handler()]
    mock_logger.handlers[0].emit = lambda r: log_records.append(r)
    mock_logger.setLevel(logging.DEBUG)

    with patch(
        "profiles.core.environment.workflow._run_command", return_value=False
    ):
        steps = [
            WorkflowStep(action="run", content="false", on_failure="warn")
        ]
        outcome = run_workflow(steps, None, failmode="abort", logger=mock_logger)
        assert outcome == WorkflowOutcome.CONTINUE
        assert any("on_failure=warn" in r.msg % r.args for r in log_records)


def test_username_hostname_token_substitution():
    """{username} and {hostname} tokens are substituted in content."""
    captured = []

    with patch(
        "profiles.core.environment.workflow._run_command",
        side_effect=lambda cmd, **kw: captured.append(cmd) or True,
    ):
        steps = [
            WorkflowStep(action="run", content="echo {username}@{hostname}")
        ]
        run_workflow(steps, None, username="alice", hostname="box.local")

    assert "echo alice@box.local" in captured[0]


def test_date_token_substitution():
    """The {date} token is substituted with today's ISO date."""
    import datetime as dt

    captured = []
    with patch(
        "profiles.core.environment.workflow._run_command",
        side_effect=lambda cmd, **kw: captured.append(cmd) or True,
    ):
        steps = [WorkflowStep(action="run", content="echo {date}")]
        run_workflow(steps, None)

    expected = dt.date.today().isoformat()
    assert f"echo {expected}" in captured[0]


def test_username_in_ask_guard():
    """{username} token is substituted in ask prompts."""
    with patch(
        "profiles.core.environment.workflow.confirm_dialog_3way",
        return_value="yes",
    ) as mock_ask, patch(
        "profiles.core.environment.workflow._run_command", return_value=True
    ):
        steps = [
            WorkflowStep(
                action="run",
                content="echo hello",
                ask="Run for {username}?",
            )
        ]
        run_workflow(steps, None, username="bob")
        mock_ask.assert_called_once_with("Run for bob?", headless=False)


def test_per_step_timeout_override():
    """A per-step timeout overrides the global timeout."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=True,
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", content="echo hi", timeout=3),
        ]
        run_workflow(steps, None, timeout=30)
        mock_cmd.assert_called_once_with(
            "echo hi", wait=True, timeout=3, logger=None,
        )


def test_if_env_var_set_condition_met():
    """if_=env:VAR passes when VAR is set in environment."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DEPLOY_ENV", "production")
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=True,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run", content="echo deploy", if_="env:DEPLOY_ENV",
                ),
            ]
            run_workflow(steps, None)
            mock_cmd.assert_called_once()
    finally:
        monkeypatch.undo()


def test_if_env_var_set_condition_not_met():
    """if_=env:VAR skips the step when VAR is not set."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=True,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run", content="echo deploy", if_="env:DEPLOY_ENV",
                ),
            ]
            outcome = run_workflow(steps, None)
            mock_cmd.assert_not_called()
            assert outcome == WorkflowOutcome.CONTINUE
    finally:
        monkeypatch.undo()


def test_if_env_var_equals_condition_met():
    """if_=env:VAR=value passes when VAR matches the expected value."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("MODE", "release")
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=True,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run", content="echo build", if_="env:MODE=release",
                ),
            ]
            run_workflow(steps, None)
            mock_cmd.assert_called_once()
    finally:
        monkeypatch.undo()


def test_if_env_var_equals_condition_not_met():
    """if_=env:VAR=value skips the step when VAR has a different value."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("MODE", "debug")
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=True,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run", content="echo build", if_="env:MODE=release",
                ),
            ]
            run_workflow(steps, None)
            mock_cmd.assert_not_called()
    finally:
        monkeypatch.undo()


def test_failure_context_populated_on_abort():
    """failure_context is populated with step content when a hook aborts."""
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=False,
    ):
        steps = [
            WorkflowStep(
                action="run",
                content="echo failing-step",
                on_failure="stop",
            ),
        ]
        failure_context: list[str] = []
        outcome = run_workflow(
            steps, None, failure_context=failure_context,
        )
        assert outcome == WorkflowOutcome.ABORT
        assert len(failure_context) > 0
        assert "echo failing-step" in failure_context[0]
