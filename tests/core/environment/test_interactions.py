"""Tests for profiles.core.environment.interactions — confirmation dialogs."""

from unittest.mock import MagicMock, patch

import pytest

from profiles.core.environment.interactions import confirm_dialog


class TestConfirmDialog:
    """Test confirm_dialog() in GUI and headless modes."""

    @patch("tkinter.messagebox.askyesno")
    def test_gui_mode_yes(self, mock_yesno: MagicMock) -> None:
        """Returns True when user clicks Yes."""
        mock_yesno.return_value = True

        result = confirm_dialog("Launch this file?", "Confirmation")

        assert result is True
        mock_yesno.assert_called_once()

    @patch("tkinter.messagebox.askyesno")
    def test_gui_mode_no(self, mock_yesno: MagicMock) -> None:
        """Returns False when user clicks No."""
        mock_yesno.return_value = False

        result = confirm_dialog("Launch?", "Confirm")

        assert result is False

    @patch("builtins.input", return_value="y")
    def test_headless_mode_yes(self, mock_input: MagicMock) -> None:
        """Headless mode: returns True on 'y' input."""
        # Force headless: patch tkinter to fail
        with patch("builtins.__import__", side_effect=ImportError):
            result = confirm_dialog("Launch?", "Confirm")

        assert result is True
        mock_input.assert_called_once()

    @patch("builtins.input", return_value="n")
    def test_headless_mode_no(self, mock_input: MagicMock) -> None:
        """Headless mode: returns False on 'n' input."""
        with patch("builtins.__import__", side_effect=ImportError):
            result = confirm_dialog("Launch?", "Confirm")

        assert result is False

    @patch("builtins.input", return_value="invalid")
    def test_headless_mode_yes_after_invalid(self, mock_input: MagicMock) -> None:
        """Headless mode: 'invalid' returns False (not yes)."""
        with patch("builtins.__import__", side_effect=ImportError):
            result = confirm_dialog("Launch?", "Confirm")

        assert result is False  # Only "y"/"yes" returns True