"""Tests for profiles.core.config.diagnostics — the editor's issue report.

The YAML editor's Problems panel must list EVERY problem in a draft, not
just the first: unknown keys, bad ``extends`` references, cycles and
schema violations are all collected. Only YAML *syntax* errors are
necessarily single-issue — the parser stops at the first one.
"""

from __future__ import annotations

from profiles.core.config.diagnostics import collect_config_issues

#: Minimal content that parses, passes semantic validation and the schema.
VALID_YAML = 'defaults:\n  search_dir: "C:/data"\n'


def messages(issues: list[dict[str, str]]) -> list[str]:
    """Extract the message list from an issue report."""
    return [issue["message"] for issue in issues]


def test_valid_content_reports_no_issues() -> None:
    assert collect_config_issues(VALID_YAML) == []


def test_empty_content_reports_single_issue() -> None:
    issues = collect_config_issues("")
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert "empty" in issues[0]["message"].lower()


def test_syntax_error_reports_single_error_issue() -> None:
    issues = collect_config_issues("defaults: [unclosed\n")
    assert len(issues) == 1
    assert issues[0]["severity"] == "error"
    assert issues[0]["message"]


def test_reports_every_unknown_top_level_key() -> None:
    content = 'typo_a: 1\ntypo_b: 2\ndefaults:\n  search_dir: "C:/data"\n'
    issues = collect_config_issues(content)
    found = messages(issues)
    assert any("unknown top-level key 'typo_a'" in message for message in found)
    assert any("unknown top-level key 'typo_b'" in message for message in found)


def test_reports_schema_violations_with_dotted_paths() -> None:
    content = "defaults:\n  search_dir: 42\n  theme: midnight\nversion: not-a-number\n"
    issues = collect_config_issues(content)
    found = messages(issues)
    assert len(issues) >= 3
    assert any(message.startswith("defaults.search_dir:") for message in found)
    assert any(message.startswith("defaults.theme:") for message in found)
    assert any(message.startswith("version:") for message in found)


def test_reports_semantic_and_schema_issues_together() -> None:
    content = "typo_key: 1\ndefaults:\n  search_dir: 42\n  bogus_extra: true\n"
    issues = collect_config_issues(content)
    found = messages(issues)
    assert any("unknown top-level key 'typo_key'" in message for message in found)
    assert any(message.startswith("defaults.search_dir:") for message in found)
    assert len(issues) >= 3


def test_all_issues_carry_error_severity() -> None:
    content = "typo_key: 1\ndefaults:\n  search_dir: 42\n"
    issues = collect_config_issues(content)
    assert issues
    assert all(issue["severity"] == "error" for issue in issues)


def test_non_mapping_root_reports_error() -> None:
    issues_scalar = collect_config_issues("42\n")
    assert any("root must be a mapping" in i["message"] for i in issues_scalar)

    issues_list = collect_config_issues("- item1\n- item2\n")
    assert any("root must be a mapping" in i["message"] for i in issues_list)


def test_non_hashable_extends_reports_error_without_crash() -> None:
    issues = collect_config_issues("configs: {a: {extends: [b]}}\n")
    assert any("configs.a.extends" in i["message"] for i in issues)


def test_invalid_regex_pattern_reports_issue() -> None:
    yaml_text = """
version: 1
configs:
  prod:
    match:
      hostname: ["re:([unclosed"]
"""
    issues = collect_config_issues(yaml_text)
    assert any("configs.prod.match.hostname" in i["message"] for i in issues)
    assert any("invalid regex pattern" in i["message"] for i in issues)


def test_deprecation_warning_for_defaults() -> None:
    """``defaults.recursive_search`` surfaces a warning, not an error (#240)."""
    issues = collect_config_issues("defaults:\n  recursive_search: true\n")
    assert {
        "severity": "warning",
        "message": "defaults: recursive_search is deprecated — use max_search_depth",
    } in issues


def test_deprecation_warning_for_config_entry() -> None:
    """A per-config ``recursive_search`` surfaces a warning naming the config."""
    issues = collect_config_issues(
        "defaults: {}\nconfigs:\n  prod:\n    match: {hostname: ['*']}\n"
        "    recursive_search: true\n"
    )
    assert any(
        i["severity"] == "warning" and i["message"].startswith("configs.prod:") for i in issues
    )


def test_no_deprecation_warning_when_absent() -> None:
    """No warning is appended when ``recursive_search`` is not used."""
    issues = collect_config_issues("defaults: {}\n")
    assert all(i["severity"] != "warning" for i in issues)
