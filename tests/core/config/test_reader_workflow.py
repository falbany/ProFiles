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
    mock_entry.command = ""
    mock_entry.message = "Hello"
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
    assert step.message == "Hello"


def test_notify_with_command_logs_debug(caplog):
    """A notify step carrying 'command' is valid; the key is debug-logged."""
    import logging

    from profiles.core.config.schema import AppConfigYaml

    schema = AppConfigYaml.model_validate(
        {
            "hooks": {
                "entries": {
                    "*.mttl": [
                        {
                            "action": "notify",
                            "message": "hello",
                            "command": "ignored-cmd",
                        }
                    ]
                }
            }
        }
    )
    config = AppConfig()
    reader = ConfigReader(config_path="memory")
    with caplog.at_level(logging.DEBUG, logger="profiles.core.config.reader"):
        reader._apply_hooks(config, schema)

    step = config.launch_hooks["*.mttl"][0]
    assert step.message == "hello"
    assert step.command == "ignored-cmd"
    assert any("'command' is ignored" in r.message for r in caplog.records)
