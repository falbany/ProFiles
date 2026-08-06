"""Tests for 3-way confirmation dialog."""

from unittest.mock import patch

from profiles.core.environment.interactions import confirm_dialog_3way


def test_headless_mode_yes():
    with patch("builtins.input", return_value="y"):
        result = confirm_dialog_3way("Test?", headless=True)
        assert result == "yes"


def test_headless_mode_skip():
    with patch("builtins.input", return_value="s"):
        result = confirm_dialog_3way("Test?", headless=True)
        assert result == "skip"


def test_headless_mode_no():
    with patch("builtins.input", return_value="n"):
        result = confirm_dialog_3way("Test?", headless=True)
        assert result == "no"
