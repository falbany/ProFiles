"""Tests for profiles.core.config.template — YAML starter template."""

from __future__ import annotations

from profiles.core.config.template import STARTER_CONFIG_TEMPLATE


class TestStarterTemplate:
    def test_is_yaml(self) -> None:
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        assert "version: 1" in body
        assert "defaults:" in body
        assert "configs:" in body

    def test_has_cwd_placeholder(self) -> None:
        assert "{cwd}" in STARTER_CONFIG_TEMPLATE

    def test_formats_cwd(self) -> None:
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/my/dir")
        assert "/my/dir" in body


class TestStarterTemplateWorkflowKeys:
    def test_hooks_examples_use_command_and_message(self) -> None:
        """The starter hooks section documents command:/message: (no content:)."""
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        assert "command:" in body
        assert "message:" in body
        assert "content:" not in body

    def test_hooks_step_tokens_documented(self) -> None:
        """The token docs list {command}/{message}, not {content}."""
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        assert "{command}" in body
        assert "{message}" in body
        assert "{content}" not in body

    def test_commented_examples_validate_against_schema(self) -> None:
        """Uncommenting the example entries yields schema-valid steps."""
        import re

        import yaml

        from profiles.core.config.schema import AppConfigYaml

        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        block = body[body.index("hooks:") : body.index("# =====", body.index("hooks:"))]
        uncommented = re.sub(r"(?m)^(\s*)# ", r"\1", block)
        doc = yaml.safe_load(uncommented)
        schema = AppConfigYaml.model_validate(doc)
        patterns = list(schema.hooks.entries.keys())
        assert patterns == ["*.mttl", ".pdf", "report_?.docx"]
        for steps in schema.hooks.entries.values():
            for step in steps:
                if step.action == "notify":
                    assert step.message
                else:
                    assert step.command
