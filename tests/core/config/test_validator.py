"""Tests for profiles.core.config.validator — semantic validation."""

from __future__ import annotations

import pytest

from profiles.core.config.schema import ConfigError
from profiles.core.config.validator import collect_issues, validate


class TestValidate:
    def test_valid_passes(self) -> None:
        raw = {
            "version": 1,
            "configs": {
                "base": {"directory": "/x"},
                "prod": {"extends": "base"},
            },
        }
        validate(raw)  # should not raise

    def test_unknown_extends(self) -> None:
        raw = {"configs": {"prod": {"extends": "ghost"}}}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.prod.extends"
        assert "ghost" in exc.value.message

    def test_cycle(self) -> None:
        raw = {
            "configs": {
                "a": {"extends": "b"},
                "b": {"extends": "a"},
            }
        }
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.b.extends"
        assert "cycle" in exc.value.message.lower()

    def test_unknown_top_level_key(self) -> None:
        raw = {"bogus": 1}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "bogus"


class TestCollectIssues:
    """collect_issues: same checks as validate(), but every problem is
    reported instead of failing fast at the first one (editor diagnostics)."""

    def test_reports_every_unknown_top_level_key(self) -> None:
        raw = {"typo_a": 1, "typo_b": 2, "defaults": {}}
        errors = collect_issues(raw)
        paths = [error.path for error in errors]
        assert paths == ["typo_a", "typo_b"]

    def test_reports_unknown_extends_and_cycle_together(self) -> None:
        raw = {
            "configs": {
                "a": {"extends": "b"},
                "b": {"extends": "a"},
                "c": {"extends": "missing"},
            }
        }
        errors = collect_issues(raw)
        messages = [error.message for error in errors]
        assert len(errors) == 2
        assert any("unknown config 'missing'" in message for message in messages)
        assert any("inheritance cycle" in message for message in messages)

    def test_validate_still_raises_the_first_collected_issue(self) -> None:
        # validate() keeps its fail-fast contract, now implemented on top
        # of collect_issues (DRY): the first unknown key wins.
        raw = {"typo_a": 1, "typo_b": 2}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "typo_a"

    def test_valid_content_collects_nothing(self) -> None:
        raw = {
            "version": 1,
            "defaults": {"search_dir": "/x"},
            "configs": {"prod": {"extends": "base"}, "base": {}},
        }
        assert collect_issues(raw) == []

    def test_non_mapping_root(self) -> None:
        errors = collect_issues(42)  # type: ignore[arg-type]
        assert len(errors) == 1
        assert "root must be a mapping" in errors[0].message

    def test_non_string_extends(self) -> None:
        raw = {"configs": {"a": {"extends": ["b"]}}}
        errors = collect_issues(raw)
        assert any(e.path == "configs.a.extends" for e in errors)

    def test_invalid_regex_match_pattern_collected(self) -> None:
        raw = {
            "configs": {
                "prod": {
                    "match": {
                        "hostname": ["re:([unclosed"],
                        "ip": ["192.168.1.1"],
                    }
                }
            }
        }
        errors = collect_issues(raw)
        assert len(errors) == 1
        assert errors[0].path == "configs.prod.match.hostname[0]"
        assert "invalid regex pattern" in errors[0].message
        assert "re:([unclosed" in errors[0].message

    def test_invalid_regex_match_pattern_scalar(self) -> None:
        raw = {
            "configs": {
                "prod": {
                    "match": {
                        "path": "re:[unclosed",
                    }
                }
            }
        }
        errors = collect_issues(raw)
        assert len(errors) == 1
        assert errors[0].path == "configs.prod.match.path"
        assert "invalid regex pattern" in errors[0].message

    def test_validate_invalid_regex_raises(self) -> None:
        raw = {
            "configs": {
                "prod": {
                    "match": {
                        "hostname": ["re:([unclosed"],
                    }
                }
            }
        }
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.prod.match.hostname[0]"
        assert "invalid regex pattern" in exc.value.message
