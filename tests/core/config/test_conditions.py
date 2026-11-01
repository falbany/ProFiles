"""Tests for the hook-step ``if:`` condition grammar (#8)."""

import logging

import pytest

from profiles.core.config.conditions import evaluate_hook_condition


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Pin the environment variables the grammar tests rely on."""
    monkeypatch.setenv("HOOK_COND_SET", "hello")
    monkeypatch.delenv("HOOK_COND_UNSET", raising=False)


class TestEmptyConditions:
    """Empty/whitespace conditions are treated as unset (always true)."""

    @pytest.mark.parametrize("condition", [None, "", "   ", "\t"])
    def test_falsy_condition_is_true(self, condition):
        assert evaluate_hook_condition(condition) is True


class TestEnvConditions:
    def test_env_set_any_value(self):
        assert evaluate_hook_condition("env:HOOK_COND_SET") is True

    def test_env_unset(self):
        assert evaluate_hook_condition("env:HOOK_COND_UNSET") is False

    def test_env_equals(self):
        assert evaluate_hook_condition("env:HOOK_COND_SET=hello") is True

    def test_env_equals_wrong_value(self):
        assert evaluate_hook_condition("env:HOOK_COND_SET=world") is False

    def test_env_equals_but_unset(self):
        assert evaluate_hook_condition("env:HOOK_COND_UNSET=hello") is False

    def test_env_differs(self):
        assert evaluate_hook_condition("env:HOOK_COND_SET!=world") is True

    def test_env_differs_same_value_is_false(self):
        assert evaluate_hook_condition("env:HOOK_COND_SET!=hello") is False

    def test_env_differs_but_unset_is_false(self):
        assert evaluate_hook_condition("env:HOOK_COND_UNSET!=hello") is False

    def test_env_differs_value_containing_equals(self):
        """The ``!=`` split takes the first occurrence; the rest is literal."""
        assert evaluate_hook_condition("env:HOOK_COND_SET!=a=b") is True


class TestFileConditions:
    def test_file_exists(self, tmp_path):
        marker = tmp_path / "marker.txt"
        marker.touch()
        assert evaluate_hook_condition(f"file:{marker}") is True

    def test_directory_exists(self, tmp_path):
        assert evaluate_hook_condition(f"file:{tmp_path}") is True

    def test_file_missing(self, tmp_path):
        assert evaluate_hook_condition(f"file:{tmp_path / 'missing.txt'}") is False

    def test_file_empty_path_is_false(self):
        assert evaluate_hook_condition("file:") is False


class TestNegation:
    def test_negate_env_unset(self):
        assert evaluate_hook_condition("!env:HOOK_COND_UNSET") is True

    def test_negate_env_set(self):
        assert evaluate_hook_condition("!env:HOOK_COND_SET") is False

    def test_negate_env_equals(self):
        assert evaluate_hook_condition("!env:HOOK_COND_SET=hello") is False
        assert evaluate_hook_condition("!env:HOOK_COND_SET=world") is True

    def test_negate_env_differs(self):
        assert evaluate_hook_condition("!env:HOOK_COND_SET!=world") is False
        assert evaluate_hook_condition("!env:HOOK_COND_SET!=hello") is True

    def test_negate_file_missing(self, tmp_path):
        assert evaluate_hook_condition(f"!file:{tmp_path / 'missing.txt'}") is True

    def test_negate_file_exists(self, tmp_path):
        marker = tmp_path / "marker.txt"
        marker.touch()
        assert evaluate_hook_condition(f"!file:{marker}") is False

    def test_negate_unknown_syntax(self):
        assert evaluate_hook_condition("!bogus") is True

    def test_double_negation(self):
        assert evaluate_hook_condition("!!env:HOOK_COND_SET") is True


class TestUnknownSyntax:
    def test_unknown_prefix_is_false_and_logged(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="profiles.core.config.conditions"):
            assert evaluate_hook_condition("bogus:value") is False
        assert "Unrecognized hook condition" in caplog.text

    def test_bare_word_is_false_and_logged(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="profiles.core.config.conditions"):
            assert evaluate_hook_condition("DEBUG") is False
        assert "Unrecognized hook condition" in caplog.text


class TestWhitespaceTolerance:
    def test_leading_trailing_whitespace(self, monkeypatch):
        assert evaluate_hook_condition("  env:HOOK_COND_SET  ") is True
        assert evaluate_hook_condition("  !env:HOOK_COND_SET  ") is False

    def test_value_side_is_literal(self):
        """Whitespace after ``=`` is part of the value, not stripped."""
        assert evaluate_hook_condition("env:HOOK_COND_SET= hello") is False
