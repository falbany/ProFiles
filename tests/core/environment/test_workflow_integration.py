"""Integration tests for the step-based workflow launch hooks engine."""

from pathlib import Path
from unittest.mock import patch

from profiles.core.actions import ActionStatus, launch_selected_file
from profiles.core.config.models import AppConfig, WorkflowStep


def test_full_workflow_notify_then_replace(tmp_path: Path):
    file_path = tmp_path / "test.mttl"
    file_path.write_text("content")

    config = AppConfig()
    config.launch_hooks["*.mttl"] = (
        WorkflowStep(action="notify", content="Starting processing for {filename}"),
        WorkflowStep(action="replace", content="echo replaced", wait=True),
    )

    with patch("profiles.core.actions.run_workflow") as mock_run:
        from profiles.core.environment.workflow import WorkflowOutcome

        mock_run.return_value = WorkflowOutcome.SKIP_LAUNCH

        res = launch_selected_file(str(tmp_path), "test.mttl", "v1.0", "user1", config=config)

        assert res.status == ActionStatus.SUCCESS
        assert "handled by workflow" in res.message
        mock_run.assert_called_once()


def test_workflow_glob_pattern_specificity(tmp_path: Path):
    file_path = tmp_path / "special.mttl"
    file_path.write_text("content")

    config = AppConfig()
    config.launch_hooks["*.mttl"] = (WorkflowStep(action="notify", content="Generic"),)
    config.launch_hooks["special.mttl"] = (WorkflowStep(action="notify", content="Specific"),)

    with patch("profiles.core.actions.run_workflow") as mock_run:
        from profiles.core.environment.workflow import WorkflowOutcome

        mock_run.return_value = WorkflowOutcome.CONTINUE

        with patch("profiles.core.actions.launch_file", return_value=True):
            res = launch_selected_file(
                str(tmp_path), "special.mttl", "v1.0", "user1", config=config
            )

        assert res.status == ActionStatus.SUCCESS
        # Verify specific step was selected
        executed_steps = mock_run.call_args[0][0]
        assert len(executed_steps) == 1
        assert executed_steps[0].content == "Specific"
