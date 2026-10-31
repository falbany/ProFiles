"""Tests for workflow engine core execution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from profiles.core.config.models import WorkflowStep
from profiles.core.environment.workflow import CommandResult, WorkflowOutcome, run_workflow

_RESULT_OK = CommandResult(code=0, output="")
_RESULT_FAIL = CommandResult(code=1, output="")


def _record_run(captured):
    """Runner double recording each executed command, succeeding."""

    def run(command, wait=False, **kwargs):
        captured.append(command)
        return _RESULT_OK

    return run


def test_workflow_no_steps():
    outcome = run_workflow([], None)
    assert outcome == WorkflowOutcome.CONTINUE


def test_workflow_notify_step():
    notifications = []

    def mock_notify(content: str, wait: bool):
        notifications.append((content, wait))

    steps = [WorkflowStep(action="notify", message="Hello")]
    outcome = run_workflow(steps, None, notify_callback=mock_notify)
    assert outcome == WorkflowOutcome.CONTINUE
    assert len(notifications) == 1
    assert notifications[0][0] == "Hello"


def test_workflow_replace_step(tmp_path: Path):
    steps = [WorkflowStep(action="replace", command="echo test")]
    outcome = run_workflow(steps, tmp_path / "test.txt")
    assert outcome == WorkflowOutcome.SKIP_LAUNCH


def test_workflow_skip_step_over():
    steps = [
        WorkflowStep(action="run", command="echo 1", ask="Skip?"),
        WorkflowStep(action="run", command="echo 2"),
    ]
    outcome = run_workflow(steps, None, user_choice="skip")
    assert outcome == WorkflowOutcome.CONTINUE


class TestShellQuotedSubstitution:
    """Token values spliced into commands are shell-quoted (#27).

    Filenames come from the scanned tree and ``{{output}}`` from previous
    commands, so a hostile value must never break out into shell syntax.
    """

    def test_quote_for_shell_posix(self):
        from profiles.core.environment import workflow as wf

        assert wf._quote_for_shell("plain.png") == "plain.png"
        assert wf._quote_for_shell("a;b.png") == "'a;b.png'"
        assert wf._quote_for_shell("my file.png") == "'my file.png'"

    def test_quote_for_shell_windows(self, monkeypatch):
        from profiles.core.environment import workflow as wf

        monkeypatch.setattr(wf.os, "name", "nt")
        assert wf._quote_for_shell("plain.png") == "plain.png"
        assert wf._quote_for_shell("my file.png") == '"my file.png"'

    def test_hostile_filename_cannot_inject_shell(self, tmp_path: Path):
        """`x; touch pwned ...` as {{filename}} must run as ONE argument."""
        hostile = "x; touch pwned-27.txt $(touch pwned-27b).png"
        target = tmp_path / hostile
        target.write_text("content")
        out = tmp_path / "out.txt"

        steps = [WorkflowStep(action="run", command=f"printf '%s' {{{{filename}}}} > '{out}'")]
        outcome = run_workflow(steps, target)

        assert outcome == WorkflowOutcome.CONTINUE
        assert not (tmp_path / "pwned-27.txt").exists()
        assert not (tmp_path / "pwned-27b").exists()
        assert out.read_text() == hostile

    def test_quoted_template_is_not_double_quoted(self, tmp_path: Path):
        """A token already wrapped in template quotes consumes its quotes."""
        target = tmp_path / "my file.png"
        target.write_text("content")
        out = tmp_path / "out.txt"

        steps = [WorkflowStep(action="run", command=f"printf '%s' '{{{{path}}}}' > '{out}'")]
        run_workflow(steps, target)

        assert out.read_text() == str(target)

    def test_safe_values_keep_behavior(self, tmp_path: Path):
        """Metachar-free values substitute verbatim (no visible change)."""
        target = tmp_path / "plain.png"
        target.write_text("content")
        captured: list[str] = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_record_run(captured),
        ):
            run_workflow([WorkflowStep(action="run", command="echo {{stem}}")], target)
        assert captured == ["echo plain"]

    def test_output_token_is_shell_quoted(self, tmp_path: Path):
        """Captured {{output}} spliced into the next command is one argument."""
        out = tmp_path / "out.txt"
        steps = [
            WorkflowStep(action="run", command="echo 'a; b'"),
            WorkflowStep(action="run", command=f"printf '%s' {{{{output}}}} > '{out}'"),
        ]
        run_workflow(steps, None)

        assert out.read_text().strip() == "a; b"
        assert not (tmp_path / "b").exists()

    def test_display_text_is_not_quoted(self, tmp_path: Path):
        """`message:` / `ask:` render raw values — quoting is command-only."""
        from profiles.core.environment import workflow as wf

        target = tmp_path / "a;b.png"
        target.write_text("content")
        step = WorkflowStep(
            action="run",
            command="echo {{filename}}",
            message="File: {{filename}}",
        )
        _, message = wf._resolve_step_texts(step, target)
        assert message == "File: a;b.png"


def test_timeout_aborts_on_run_failure():
    """A timed-out command on a ``run`` step with on_failure=stop → ABORT."""
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=_RESULT_FAIL
    ) as mock_cmd:
        steps = [WorkflowStep(action="run", command="sleep 10", on_failure="stop")]
        outcome = run_workflow(steps, None, timeout=1)
        assert outcome == WorkflowOutcome.ABORT
        mock_cmd.assert_called_once()
        assert mock_cmd.call_args.kwargs["timeout"] == 1


def test_failmode_abort_triggers_via_unknown_on_failure():
    """An unknown on_failure value falls back to global failmode=abort → ABORT.

    (Python does not enforce Literal at runtime, so we pass a sentinel value.)
    """
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=_RESULT_FAIL
    ) as mock_cmd:
        steps = [WorkflowStep(action="run", command="false", on_failure="unknown_value")]
        outcome = run_workflow(steps, None, failmode="abort")
        assert outcome == WorkflowOutcome.ABORT
        mock_cmd.assert_called_once()


def test_failmode_skip_triggers_via_unknown_on_failure():
    """An unknown on_failure value with failmode=skip → SKIP_LAUNCH."""
    with patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_FAIL):
        steps = [WorkflowStep(action="run", command="false", on_failure="unknown_value")]
        outcome = run_workflow(steps, None, failmode="skip")
        assert outcome == WorkflowOutcome.SKIP_LAUNCH


def test_failmode_warn_continues():
    """failmode=warn with on_failure=continue → CONTINUE."""
    with patch(
        "profiles.core.environment.workflow._run_command", return_value=_RESULT_FAIL
    ) as mock_cmd:
        steps = [WorkflowStep(action="run", command="false", on_failure="continue")]
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

    with patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_FAIL):
        steps = [WorkflowStep(action="run", command="false", on_failure="warn")]
        outcome = run_workflow(steps, None, failmode="abort", logger=mock_logger)
        assert outcome == WorkflowOutcome.CONTINUE
        assert any("on_failure=warn" in r.msg % r.args for r in log_records)


def test_username_hostname_token_substitution():
    """{username} and {hostname} tokens are substituted in content."""
    captured = []

    with patch(
        "profiles.core.environment.workflow._run_command",
        side_effect=_record_run(captured),
    ):
        steps = [WorkflowStep(action="run", command="echo {username}@{hostname}")]
        run_workflow(steps, None, username="alice", hostname="box.local")

    assert "echo alice@box.local" in captured[0]


def test_date_token_substitution():
    """The {date} token is substituted with today's ISO date."""
    import datetime as dt

    captured = []
    with patch(
        "profiles.core.environment.workflow._run_command",
        side_effect=_record_run(captured),
    ):
        steps = [WorkflowStep(action="run", command="echo {date}")]
        run_workflow(steps, None)

    expected = dt.date.today().isoformat()
    assert f"echo {expected}" in captured[0]


def test_double_brace_token_substitution():
    """Double-brace tokens {{filename}}, {{path}}, etc. are substituted correctly."""
    from pathlib import Path

    from profiles.core.environment.workflow import _substitute_variables

    file_path = Path("/tmp/test_dir/example.pdf")
    res = _substitute_variables(
        "File: {{filename}}, path: {{path}}, dir: {{dir}}, stem: {{stem}}, ext: {{ext}}, user: {{username}}, host: {{hostname}}",
        file_path,
        username="alice",
        hostname="macbook",
    )
    assert (
        res
        == "File: example.pdf, path: /tmp/test_dir/example.pdf, dir: /tmp/test_dir, stem: example, ext: .pdf, user: alice, host: macbook"
    )


def test_username_in_ask_guard():
    """{username} token is substituted in ask prompts."""
    with (
        patch(
            "profiles.core.environment.workflow.confirm_dialog_3way",
            return_value="yes",
        ) as mock_ask,
        patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_OK),
    ):
        steps = [
            WorkflowStep(
                action="run",
                command="echo hello",
                ask="Run for {username}?",
            )
        ]
        run_workflow(steps, None, username="bob")
        mock_ask.assert_called_once_with("Run for bob?", headless=False, pre_message=None)


def test_per_step_timeout_override():
    """A per-step timeout overrides the global timeout."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_OK,
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", command="echo hi", timeout=3),
        ]
        run_workflow(steps, None, timeout=30)
        mock_cmd.assert_called_once_with(
            "echo hi",
            wait=True,
            timeout=3,
            logger=None,
        )


def test_if_env_var_set_condition_met():
    """if_=env:VAR passes when VAR is set in environment."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("DEPLOY_ENV", "production")
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=_RESULT_OK,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run",
                    command="echo deploy",
                    if_="env:DEPLOY_ENV",
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
            return_value=_RESULT_OK,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run",
                    command="echo deploy",
                    if_="env:DEPLOY_ENV",
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
            return_value=_RESULT_OK,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run",
                    command="echo build",
                    if_="env:MODE=release",
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
            return_value=_RESULT_OK,
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run",
                    command="echo build",
                    if_="env:MODE=release",
                ),
            ]
            run_workflow(steps, None)
            mock_cmd.assert_not_called()
    finally:
        monkeypatch.undo()


def test_failure_context_populated_on_abort():
    """failure_context is populated with step content when a hook aborts."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_FAIL,
    ):
        steps = [
            WorkflowStep(
                action="run",
                command="echo failing-step",
                on_failure="stop",
            ),
        ]
        failure_context: list[str] = []
        outcome = run_workflow(
            steps,
            None,
            failure_context=failure_context,
        )
        assert outcome == WorkflowOutcome.ABORT
        assert len(failure_context) > 0
        assert "echo failing-step" in failure_context[0]


def test_per_step_timeout_with_check_action():
    """A per-step timeout applies to check actions too."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_OK,
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="check", command="verify.exe", timeout=7),
        ]
        run_workflow(steps, None, timeout=60)
        mock_cmd.assert_called_once_with(
            "verify.exe",
            wait=True,
            timeout=7,
            logger=None,
        )


def test_global_timeout_used_when_no_per_step_timeout():
    """Global timeout is used when step has no per-step timeout."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_OK,
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", command="echo hi"),
        ]
        run_workflow(steps, None, timeout=45)
        mock_cmd.assert_called_once_with(
            "echo hi",
            wait=True,
            timeout=45,
            logger=None,
        )


def test_no_timeout_when_both_unset():
    """When neither global nor per-step timeout is set, timeout is None."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_OK,
    ) as mock_cmd:
        steps = [
            WorkflowStep(action="run", command="echo hi"),
        ]
        run_workflow(steps, None)
        mock_cmd.assert_called_once_with(
            "echo hi",
            wait=True,
            timeout=None,
            logger=None,
        )


def test_if_condition_skips_run_after():
    """if_ guard skips run_after steps when condition not met."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("SKIP_FLAG", raising=False)
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
        ) as mock_cmd:
            steps = [
                WorkflowStep(
                    action="run_after",
                    command="logger.exe",
                    if_="env:SKIP_FLAG",
                ),
            ]
            run_workflow(steps, None)
            mock_cmd.assert_not_called()
    finally:
        monkeypatch.undo()


def test_if_condition_multiple_steps_skips_only_failed():
    """Steps with unmet if_ are skipped; others still execute."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("RUN_SECOND", "1")
    try:
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=_RESULT_OK,
        ) as mock_cmd:
            steps = [
                WorkflowStep(action="run", command="echo first", if_="env:NOPE"),
                WorkflowStep(action="run", command="echo second", if_="env:RUN_SECOND"),
            ]
            run_workflow(steps, None)
            assert mock_cmd.call_count == 1
            assert "echo second" in mock_cmd.call_args[0][0]
    finally:
        monkeypatch.undo()


def test_failure_context_populated_on_failmode_abort():
    """failure_context is populated when an unknown on_failure triggers failmode=abort."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_FAIL,
    ):
        steps = [
            WorkflowStep(
                action="run",
                command="echo bad-step",
                on_failure="bogus",  # unknown -> falls back to failmode
            ),
        ]
        failure_context: list[str] = []
        outcome = run_workflow(
            steps,
            None,
            failmode="abort",
            failure_context=failure_context,
        )
        assert outcome == WorkflowOutcome.ABORT
        assert len(failure_context) > 0
        assert "echo bad-step" in failure_context[0]


def test_failure_context_empty_when_no_failure():
    """failure_context remains empty when all steps succeed."""
    with patch(
        "profiles.core.environment.workflow._run_command",
        return_value=_RESULT_OK,
    ):
        steps = [
            WorkflowStep(action="run", command="echo ok"),
        ]
        failure_context: list[str] = []
        outcome = run_workflow(steps, None, failure_context=failure_context)
        assert outcome == WorkflowOutcome.CONTINUE
        assert failure_context == []


class TestCommandMessageDispatch:
    """Engine dispatch on the dedicated command/message step keys."""

    def test_notify_renders_message_via_callback(self):
        """notify passes the substituted message to notify_callback."""
        notifications = []

        def mock_notify(content: str, wait: bool):
            notifications.append((content, wait))

        steps = [WorkflowStep(action="notify", message="Hello {username}")]
        outcome = run_workflow(steps, None, notify_callback=mock_notify, username="alice")
        assert outcome == WorkflowOutcome.CONTINUE
        assert notifications == [("Hello alice", True)]

    def test_run_executes_command(self):
        """run executes the substituted command."""
        captured = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_record_run(captured),
        ):
            steps = [WorkflowStep(action="run", command="echo {stem}", message="Running...")]
            run_workflow(steps, Path("/tmp/demo.txt"))
        assert captured == ["echo demo"]

    def test_run_with_message_and_no_ask_shows_nonblocking_notice(self):
        """A run step with message and no ask shows a non-blocking notice."""
        notices = []
        commands = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_record_run(commands),
        ):
            steps = [WorkflowStep(action="run", command="echo hi", message="**Working** on it...")]
            run_workflow(steps, None, notify_callback=lambda msg, wait: notices.append((msg, wait)))
        assert notices == [("**Working** on it...", False)]
        assert commands == ["echo hi"]

    def test_run_with_message_and_ask_composes_dialog(self):
        """message+ask renders the message above the question in one dialog."""
        commands = []
        with (
            patch(
                "profiles.core.environment.workflow.confirm_dialog_3way",
                return_value="yes",
            ) as mock_ask,
            patch(
                "profiles.core.environment.workflow._run_command",
                side_effect=_record_run(commands),
            ),
        ):
            steps = [
                WorkflowStep(
                    action="run",
                    command="special_tool.exe {{path}}",
                    message="# Advanced mode\\n**Special processing** for {{stem}}.",
                    ask="Execute: {command}",
                )
            ]
            run_workflow(steps, Path("/tmp/demo.txt"))

        # The notice must NOT fire separately — the message rode in the dialog
        mock_ask.assert_called_once_with(
            "Execute: special_tool.exe /tmp/demo.txt",
            headless=False,
            pre_message="# Advanced mode\\n**Special processing** for demo.",
        )
        assert commands == ["special_tool.exe /tmp/demo.txt"]

    def test_ask_only_step_passes_no_pre_message(self):
        """An ask guard without a message preserves the prompt-only dialog."""
        with (
            patch(
                "profiles.core.environment.workflow.confirm_dialog_3way",
                return_value="yes",
            ) as mock_ask,
            patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_OK),
        ):
            steps = [WorkflowStep(action="run", command="echo hi", ask="Continue?")]
            run_workflow(steps, None)
        mock_ask.assert_called_once_with("Continue?", headless=False, pre_message=None)

    def test_show_notice_false_suppresses_notice(self):
        """show_notice=False (web session already displayed it) skips the notice."""
        from profiles.core.environment.workflow import _execute_step

        notices = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            return_value=_RESULT_OK,
        ) as mock_cmd:
            step = WorkflowStep(action="run", command="echo hi", message="notice text")
            _execute_step(
                step,
                None,
                notify_callback=lambda msg, wait: notices.append(msg),
                show_notice=False,
            )
            # Same step WITH the flag shows the notice
            _execute_step(
                step,
                None,
                notify_callback=lambda msg, wait: notices.append(msg),
            )
        assert notices == ["notice text"]
        assert mock_cmd.call_count == 2


class TestStepTokenSubstitution:
    """{{command}} / {{message}} tokens; {{content}} is gone."""

    def test_command_token_in_ask_both_brace_forms(self):
        """{{command}} and {command} both resolve in ask prompts."""
        with (
            patch(
                "profiles.core.environment.workflow.confirm_dialog_3way",
                return_value="yes",
            ) as mock_ask,
            patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_OK),
        ):
            steps = [
                WorkflowStep(
                    action="run",
                    command="tool.exe --run",
                    ask="Double: {{command}} Single: {command}",
                )
            ]
            run_workflow(steps, None)
        mock_ask.assert_called_once_with(
            "Double: tool.exe --run Single: tool.exe --run",
            headless=False,
            pre_message=None,
        )

    def test_message_token_cross_substitution(self):
        """A command may reference the step message via {message}."""
        captured = []
        with patch(
            "profiles.core.environment.workflow._run_command",
            side_effect=_record_run(captured),
        ):
            steps = [
                WorkflowStep(
                    action="run",
                    command="log.exe --text {message}",
                    message="all systems go",
                )
            ]
            run_workflow(steps, None, notify_callback=lambda *a: None)
        assert captured == ["log.exe --text all systems go"]

    def test_content_token_no_longer_substitutes(self):
        """{{content}} is not a token anymore — the literal string survives."""
        from profiles.core.environment.workflow import _substitute_variables

        res = _substitute_variables("Execute: {{content}}", None)
        assert res == "Execute: {{content}}"
        res2 = _substitute_variables("Execute: {content}", None)
        assert res2 == "Execute: {content}"

    def test_message_self_reference_stays_literal(self):
        """A {message} reference inside the message itself is not recursive."""
        with (
            patch(
                "profiles.core.environment.workflow.confirm_dialog_3way",
                return_value="yes",
            ) as mock_ask,
            patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_OK),
        ):
            steps = [
                WorkflowStep(
                    action="run",
                    command="echo hi",
                    message="Status: {message}",
                    ask="Proceed?",
                )
            ]
            run_workflow(steps, None)
        mock_ask.assert_called_once_with(
            "Proceed?", headless=False, pre_message="Status: {message}"
        )


class TestHeadlessAskComposition:
    """Headless backend prints the message before the question prompt."""

    def test_headless_ask_prints_message_then_prompt(self, capsys):
        """pre_message renders (Markdown stripped) above the y/s/N prompt."""
        with (
            patch("profiles.core.environment.workflow._run_command", return_value=_RESULT_OK),
            patch("builtins.input", return_value="y") as mock_input,
        ):
            steps = [
                WorkflowStep(
                    action="run",
                    command="echo hi",
                    message="# Preparing\\n**Step 1** of 2.",
                    ask="Proceed with {{stem}}?",
                )
            ]
            run_workflow(steps, Path("/tmp/demo.txt"), headless=True)

        out = capsys.readouterr().out
        # Message first (Markdown stripped, escapes processed)…
        assert out.index("Preparing") < out.index("Step 1")
        assert "**" not in out
        # …then the substituted question with the choice prompt.
        assert "Proceed with demo? [y/s/N]:" in mock_input.call_args[0][0]
