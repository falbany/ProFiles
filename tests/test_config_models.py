from profiles.core.config.models import WorkflowStep

def test_workflow_step_defaults():
    """Test WorkflowStep with default values."""
    step = WorkflowStep(action="run", content="echo hello")
    assert step.wait is True
    assert step.on_failure == "stop"
    assert step.ask is None

def test_workflow_step_custom_values():
    """Test WorkflowStep with custom values."""
    step = WorkflowStep(
        action="notify",
        content="# Title",
        wait=False,
        on_failure="continue",
        ask="Confirm?"
    )
    assert step.wait is False
    assert step.on_failure == "continue"
    assert step.ask == "Confirm?"
