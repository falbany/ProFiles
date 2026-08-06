"""Tests for workflow engine core execution."""

from pathlib import Path

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
