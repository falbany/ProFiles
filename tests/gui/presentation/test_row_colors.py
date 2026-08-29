"""Tests for profiles.gui.presentation.row_colors — pure rule engine."""

from __future__ import annotations

from profiles.gui.presentation.row_colors import (
    RowColorRules,
    default_tag_name,
    make_rule_tag_name,
)


def _rules() -> RowColorRules:
    return RowColorRules(
        rules=[("prod", "#005fb8"), ("dev", "#757575")],
        tag_prefix="rc",
    )


class TestDefaultTagName:
    """default_tag_name produces a stable, prefix-based identifier."""

    def test_includes_prefix(self) -> None:
        assert default_tag_name("rc") == "rc_default"

    def test_distinct_prefixes_are_distinct(self) -> None:
        assert default_tag_name("a") != default_tag_name("b")


class TestMakeRuleTagName:
    """make_rule_tag_name strips the # and replaces spaces."""

    def test_strips_hash(self) -> None:
        assert make_rule_tag_name("rc", "prod", "#005fb8") == "rc_prod_005fb8"

    def test_replaces_spaces(self) -> None:
        assert make_rule_tag_name("rc", "my prod", "#fff") == "rc_my_prod_fff"

    def test_no_hash(self) -> None:
        assert make_rule_tag_name("rc", "prod", "005fb8") == "rc_prod_005fb8"


class TestRowColorRulesTagsFor:
    """The engine returns the right tags for a given filename."""

    def test_empty_rules_returns_default_only(self) -> None:
        rules = RowColorRules(rules=[], tag_prefix="rc")
        assert rules.tags_for("anything.txt") == ("rc_default",)

    def test_no_match_returns_default_only(self) -> None:
        assert _rules().tags_for("test.txt") == ("rc_default",)

    def test_first_match_wins(self) -> None:
        tags = _rules().tags_for("myprod_file.mttl")
        assert tags == ("rc_default", "rc_prod_005fb8")

    def test_matching_is_case_insensitive(self) -> None:
        assert _rules().tags_for("PROD_file") == ("rc_default", "rc_prod_005fb8")
        assert _rules().tags_for("dev_file") == ("rc_default", "rc_dev_757575")

    def test_skips_empty_patterns_and_colors(self) -> None:
        rules = RowColorRules(
            rules=[("", "#000000"), ("prod", ""), ("prod", "#005fb8")],
            tag_prefix="rc",
        )
        assert rules.tags_for("prod_file") == ("rc_default", "rc_prod_005fb8")

    def test_default_tag_always_present(self) -> None:
        for name in ("", "anything", "PROD_thing", "totally_unrelated"):
            tags = _rules().tags_for(name)
            assert tags[0] == "rc_default", f"default missing for {name!r}"
