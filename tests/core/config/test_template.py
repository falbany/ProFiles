"""Tests for profiles.core.config.template — YAML starter template."""

from __future__ import annotations

from profiles.core.config.reader import ConfigReader
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

    def test_output_capture_documented(self) -> None:
        """The starter template documents the output key and {output} token."""
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        assert "output:" in body
        assert "{output}" in body

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


class TestStarterTemplateColumnDefaults:
    """The starter ships Size + Modified columns; Type/Version leave them (#227)."""

    @staticmethod
    def _render() -> str:
        return STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")

    def test_ships_size_and_modified_keywords(self) -> None:
        """Default columns use the size and modified attribute keywords."""
        body = self._render()
        assert "match: size" in body
        assert "match: modified" in body

    def test_type_and_version_regex_columns_removed(self) -> None:
        """The legacy Type/Version regexes are gone from the defaults."""
        body = self._render()
        assert "(PRO|ENG|DEV|TMP|DEBUG)" not in body
        assert "[-_]V(" not in body

    def test_path_column_uses_keyword(self) -> None:
        """Path switches to the path keyword, dropping the parent-dir regex."""
        body = self._render()
        assert "match: path" in body
        assert "match: '(.+" not in body

    def test_keyword_table_documents_new_keywords(self) -> None:
        """The built-in keyword table covers size/modified/created/path rows."""
        body = self._render()
        start = body.index('Built-in "match" keywords:')
        end = body.index("# ====", start)
        table = body[start:end]
        assert "size" in table
        assert "size_bytes" in table
        assert "modified" in table
        assert "created" in table
        assert "path" in table

    def test_keyword_table_keeps_version_and_type(self) -> None:
        """version/type stay documented as available-but-not-default keywords."""
        body = self._render()
        start = body.index('Built-in "match" keywords:')
        end = body.index("# ====", start)
        table = body[start:end]
        assert "version" in table
        assert "type" in table

    def test_modified_column_documents_strftime_transform(self) -> None:
        """The Modified column notes that transform accepts a strftime pattern."""
        body = self._render()
        assert "strftime" in body

    def test_rendered_columns_parse_exactly(self) -> None:
        """The rendered template parses; column keys are exactly the new set."""
        config = ConfigReader.from_content(self._render())
        assert list(config.columns) == ["File", "Path", "FileName", "Size", "Modified"]
        assert config.column_names == ("File", "Path", "FileName", "Size", "Modified")
        assert config.columns["Path"].match == "path"
        assert config.columns["Path"].default == "."
        assert config.columns["Path"].width == 200
        assert config.columns["Path"].stretch is False
        assert config.columns["Size"].match == "size"
        assert config.columns["Size"].width == 110
        assert config.columns["Size"].stretch is False
        assert config.columns["Modified"].match == "modified"
        assert config.columns["Modified"].width == 150
        assert config.columns["Modified"].stretch is False
