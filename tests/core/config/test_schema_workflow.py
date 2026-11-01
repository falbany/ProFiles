"""Schema validation tests for workflow steps (command/message split).

Covers the hard breaking change from the overloaded ``content:`` key to the
dedicated ``command:`` / ``message:`` step keys, per-action required-field
errors, and the ``if:`` YAML alias.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from profiles.core.config.schema import AppConfigYaml, HooksConfig, WorkflowStepSchema


def _parse_steps(yaml_text: str) -> AppConfigYaml:
    """Parse a minimal hooks-only YAML document through the root schema."""
    import yaml

    return AppConfigYaml.model_validate(yaml.safe_load(yaml_text))


class TestContentKeyRemoved:
    def test_content_key_is_rejected(self) -> None:
        """A step using the removed ``content:`` key fails with unknown-key error."""
        with pytest.raises(ValidationError) as excinfo:
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: run\n"
                "        content: 'echo hi'\n"
            )
        errors = excinfo.value.errors()
        assert any(e["type"] == "extra_forbidden" and "content" in e["loc"] for e in errors)

    def test_content_key_error_is_generic(self) -> None:
        """The ``content:`` rejection is the generic extra-input error (no alias)."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: notify\n"
                "        content: 'hello'\n"
            )


class TestRequiredFieldErrors:
    def test_notify_without_message_mentions_pattern(self) -> None:
        """``notify`` without ``message`` fails, naming the entry pattern."""
        with pytest.raises(ValidationError, match=r"hooks entry '\*\.mttl'"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: notify\n"
                "        command: 'echo x'\n"
            )

    def test_run_without_command_mentions_pattern(self) -> None:
        """``run`` without ``command`` fails, naming the entry pattern."""
        with pytest.raises(ValidationError, match=r"a 'run' step requires 'command'"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: run\n"
                "        message: 'text only'\n"
            )

    def test_check_without_command_fails(self) -> None:
        """``check`` without ``command`` fails schema validation."""
        with pytest.raises(ValidationError, match=r"a 'check' step requires 'command'"):
            _parse_steps("hooks:\n  entries:\n    '*.pdf':\n      - action: check\n")

    def test_notify_with_command_is_valid(self) -> None:
        """``command`` on a notify step is accepted (ignored at runtime)."""
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: notify\n"
            "        message: 'hello'\n"
            "        command: 'ignored-cmd'\n"
        )
        step = schema.hooks.entries["*.mttl"][0]
        assert step.message == "hello"
        assert step.command == "ignored-cmd"


class TestStepKeys:
    def test_run_with_command_and_message(self) -> None:
        """A command step accepts both keys."""
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: run\n"
            "        command: 'tool {{path}}'\n"
            "        message: '**Preparing** {{stem}}'\n"
            "        ask: 'Execute: {{command}}?'\n"
        )
        step = schema.hooks.entries["*.mttl"][0]
        assert step.command == "tool {{path}}"
        assert step.message == "**Preparing** {{stem}}"
        assert step.ask == "Execute: {{command}}?"

    def test_if_yaml_key_maps_to_if_(self) -> None:
        """The YAML ``if:`` key populates the ``if_`` field."""
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: run\n"
            "        command: 'echo deploy'\n"
            "        if: 'env:SITE=FACTORY'\n"
        )
        assert schema.hooks.entries["*.mttl"][0].if_ == "env:SITE=FACTORY"

    def test_unknown_key_is_rejected(self) -> None:
        """Any unknown step key (not just ``content``) is rejected."""
        with pytest.raises(ValidationError, match="bogus"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: run\n"
                "        command: 'echo hi'\n"
                "        bogus_key: 42\n"
            )

    def test_programmatic_hooks_construction_enforces_required_fields(self) -> None:
        """HooksConfig enforces per-action required fields programmatically."""
        with pytest.raises(ValidationError, match="requires 'command'"):
            HooksConfig(
                entries={"*.mttl": [WorkflowStepSchema(action="run", message="no command")]}
            )
        hooks = HooksConfig(
            entries={"*.mttl": [WorkflowStepSchema(action="run", command="echo hi")]}
        )
        assert hooks.entries["*.mttl"][0].command == "echo hi"


class TestOutputKey:
    """The ``output:`` key controls command output display.

    Valid values: ``hide`` (default), ``show``, ``fail_only``; anything else
    is a schema validation error.
    """

    def test_output_defaults_to_hide(self) -> None:
        schema = _parse_steps(
            "hooks:\n  entries:\n    '*.mttl':\n      - action: run\n        command: 'echo hi'\n"
        )
        assert schema.hooks.entries["*.mttl"][0].output == "hide"

    def test_output_accepts_show(self) -> None:
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: check\n"
            "        command: 'probe.exe'\n"
            "        output: show\n"
        )
        assert schema.hooks.entries["*.mttl"][0].output == "show"

    def test_output_accepts_fail_only(self) -> None:
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: check\n"
            "        command: 'probe.exe'\n"
            "        output: fail_only\n"
        )
        assert schema.hooks.entries["*.mttl"][0].output == "fail_only"

    def test_output_invalid_value_rejected(self) -> None:
        with pytest.raises(ValidationError, match="output"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: run\n"
                "        command: 'echo hi'\n"
                "        output: always\n"
            )


class TestPhaseKey:
    """The ``phase:`` step key (#9): pre default, post accepted, replace+post rejected."""

    def test_phase_defaults_to_pre(self) -> None:
        schema = _parse_steps(
            "hooks:\n  entries:\n    '*.mttl':\n      - action: run\n        command: 'echo hi'\n"
        )
        assert schema.hooks.entries["*.mttl"][0].phase == "pre"

    def test_phase_post_accepted(self) -> None:
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: notify\n"
            "        message: 'Launched {{filename}}'\n"
            "        phase: post\n"
        )
        assert schema.hooks.entries["*.mttl"][0].phase == "post"

    def test_phase_invalid_value_rejected(self) -> None:
        with pytest.raises(ValidationError, match="phase"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: run\n"
                "        command: 'echo hi'\n"
                "        phase: mid\n"
            )

    def test_replace_with_post_phase_rejected(self) -> None:
        """A replace step can never be post: replace *is* the launch (#9)."""
        with pytest.raises(ValidationError, match="replace.*cannot use 'phase: post'"):
            _parse_steps(
                "hooks:\n"
                "  entries:\n"
                "    '*.mttl':\n"
                "      - action: replace\n"
                "        command: 'special.exe {{path}}'\n"
                "        phase: post\n"
            )

    def test_replace_with_default_phase_is_valid(self) -> None:
        schema = _parse_steps(
            "hooks:\n"
            "  entries:\n"
            "    '*.mttl':\n"
            "      - action: replace\n"
            "        command: 'special.exe {{path}}'\n"
        )
        assert schema.hooks.entries["*.mttl"][0].action == "replace"
