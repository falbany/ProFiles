from profiles.core.config.models import WorkflowStep


def test_workflow_step_defaults():
    """Test WorkflowStep with default values."""
    step = WorkflowStep(action="run", command="echo hello")
    assert step.wait is True
    assert step.on_failure == "stop"
    assert step.ask is None
    assert step.output == "hide"


def test_workflow_step_output_values():
    """The output key accepts hide/show/fail_only."""
    assert WorkflowStep(action="run", command="x", output="show").output == "show"
    assert WorkflowStep(action="check", command="x", output="fail_only").output == "fail_only"


def test_workflow_step_custom_values():
    """Test WorkflowStep with custom values."""
    step = WorkflowStep(
        action="notify", message="# Title", wait=False, on_failure="continue", ask="Confirm?"
    )
    assert step.wait is False
    assert step.on_failure == "continue"
    assert step.ask == "Confirm?"


class TestWorkflowStepRequiredFields:
    """WorkflowStep construction-time validation (mirrors config-load rules)."""

    def test_notify_requires_message(self):
        """A 'notify' step without a message raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="notify.*requires a 'message'"):
            WorkflowStep(action="notify")

    def test_run_requires_command(self):
        """A 'run' step without a command raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="run.*requires a 'command'"):
            WorkflowStep(action="run", message="text only")

    def test_check_requires_command(self):
        """A 'check' step without a command raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="check.*requires a 'command'"):
            WorkflowStep(action="check")

    def test_replace_requires_command(self):
        """A 'replace' step without a command raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="replace.*requires a 'command'"):
            WorkflowStep(action="replace")

    def test_run_after_requires_command(self):
        """A 'run_after' step without a command raises ValueError."""
        import pytest

        with pytest.raises(ValueError, match="run_after.*requires a 'command'"):
            WorkflowStep(action="run_after")

    def test_notify_with_message_and_command_is_valid(self):
        """A 'notify' step with a message is valid; command is accepted too."""
        step = WorkflowStep(action="notify", message="hi", command="ignored")
        assert step.message == "hi"
        assert step.command == "ignored"

    def test_command_step_with_both_fields_is_valid(self):
        """A command step may carry both command and message."""
        step = WorkflowStep(action="run", command="echo hi", message="hello")
        assert step.command == "echo hi"
        assert step.message == "hello"


class TestWorkflowStepPhase:
    """The ``phase`` key (#9): pre default, replace+post rejected."""

    def test_phase_defaults_to_pre(self):
        step = WorkflowStep(action="run", command="echo hi")
        assert step.phase == "pre"

    def test_phase_post_accepted_on_command_actions(self):
        for action in ("run", "run_after", "check", "notify"):
            kwargs = {"command": "x"} if action != "notify" else {"message": "hi"}
            step = WorkflowStep(action=action, phase="post", **kwargs)
            assert step.phase == "post"

    def test_replace_with_post_phase_rejected(self):
        import pytest

        with pytest.raises(ValueError, match="replace.*cannot use 'phase: post'"):
            WorkflowStep(action="replace", command="launch.exe", phase="post")


class TestWorkflowStepEvaluateCondition:
    """evaluate_condition delegates to the shared grammar (#8)."""

    def test_unset_condition_is_true(self):
        assert WorkflowStep(action="run", command="x").evaluate_condition() is True

    def test_env_set(self, monkeypatch):
        monkeypatch.setenv("MODEL_COND", "1")
        step = WorkflowStep(action="run", command="x", if_="env:MODEL_COND")
        assert step.evaluate_condition() is True

    def test_negated_file_condition(self, tmp_path):
        step = WorkflowStep(action="run", command="x", if_=f"!file:{tmp_path / 'nope'}")
        assert step.evaluate_condition() is True

    def test_unknown_syntax_is_false(self):
        step = WorkflowStep(action="run", command="x", if_="bogus")
        assert step.evaluate_condition() is False
