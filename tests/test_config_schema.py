import pytest
from pydantic import ValidationError

from profiles.core.config.schema import WorkflowStepSchema


def test_workflow_step_schema_valid():
    """Test valid WorkflowStepSchema parsing."""
    data = {
        "action": "run",
        "content": "echo {path}",
        "ask": "Confirm?",
        "wait": True,
        "on_failure": "stop",
    }
    step = WorkflowStepSchema(**data)
    assert step.action == "run"
    assert step.content == "echo {path}"
    assert step.ask == "Confirm?"


def test_workflow_step_schema_defaults():
    """Test WorkflowStepSchema default values."""
    data = {"action": "notify", "content": "Hello"}
    step = WorkflowStepSchema(**data)
    assert step.wait is True
    assert step.on_failure == "stop"
    assert step.ask is None


def test_workflow_step_schema_invalid_action():
    """Test that invalid action raises ValidationError."""
    with pytest.raises(ValidationError):
        WorkflowStepSchema(action="invalid", content="test")


def test_workflow_step_schema_all_actions():
    """Test all valid action types."""
    valid_actions = ["notify", "run", "run_after", "replace", "check"]
    for action in valid_actions:
        step = WorkflowStepSchema(action=action, content="test")
        assert step.action == action
