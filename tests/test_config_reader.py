"""Tests for config reader integration with workflow steps."""

from unittest.mock import MagicMock
from profiles.core.config.models import AppConfig, WorkflowStep
from profiles.core.config.reader import ConfigReader

def test_apply_workflow_steps(tmp_path):
    reader = ConfigReader(config_path=tmp_path / "config.yaml")
    config = AppConfig()

    mock_schema = MagicMock()
    mock_schema.hooks.failmode = "continue"
    mock_schema.hooks.timeout = 10

    mock_entry = MagicMock()
    mock_entry.action = "notify"
    mock_entry.content = "Hello"
    mock_entry.ask = None
    mock_entry.wait = True
    mock_entry.on_failure = "stop"

    mock_schema.hooks.entries = {"*.mttl": [mock_entry]}

    reader._apply_hooks(config, mock_schema)

    assert config.launch_hook_failmode == "continue"
    assert config.launch_hook_timeout == 10
    assert "*.mttl" in config.launch_hooks
    step = config.launch_hooks["*.mttl"][0]
    assert isinstance(step, WorkflowStep)
    assert step.action == "notify"
    assert step.content == "Hello"
