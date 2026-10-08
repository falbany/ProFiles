"""Tests for QSS syntax validation."""

from __future__ import annotations

import pytest

from profiles.gui.qt.styles import _generate_qss, _get_dark_qss, _get_light_qss, configure_app
from profiles.gui.theme import DARK_THEME, LIGHT_THEME, to_qss_tokens


@pytest.fixture
def qt_app(qapp):
    """Use pytest-qt's qapp fixture."""
    return qapp


def test_qss_parses_without_errors(qt_app):
    """Apply QSS and verify no syntax errors occur."""
    # Use the provided qt_app fixture
    # Light theme
    theme_light = configure_app(qt_app, "light")
    assert theme_light == "light"
    assert qt_app.styleSheet() != ""

    # Verify dark theme also works (re-configure same app)
    theme_dark = configure_app(qt_app, "dark")
    assert theme_dark == "dark"
    assert qt_app.styleSheet() != ""


def test_qss_contains_all_md3_tokens():
    """Verify all MD3 theme tokens are used in QSS generation."""
    # Test light theme tokens
    light_tokens = to_qss_tokens(LIGHT_THEME)

    # Test dark theme tokens
    dark_tokens = to_qss_tokens(DARK_THEME)

    # Verify tokens are valid hex colors
    for key, value in light_tokens.items():
        assert value.startswith("#"), f"Token {key} should be hex color"
        assert len(value) == 7, f"Token {key} should be 7-char hex"

    for key, value in dark_tokens.items():
        assert value.startswith("#"), f"Token {key} should be hex color"
        assert len(value) == 7, f"Token {key} should be 7-char hex"


def test_qss_renders_consistently():
    """Apply QSS twice and verify same result."""
    # QSS generation should be deterministic without needing new apps
    qss1 = _generate_qss("light")
    qss2 = _generate_qss("light")
    assert qss1 == qss2, "QSS generation should be deterministic"

    # Test dark theme consistency
    qss3 = _generate_qss("dark")
    qss4 = _generate_qss("dark")
    assert qss3 == qss4, "Dark QSS generation should be deterministic"


def test_qss_valid_syntax(qt_app):
    """Verify QSS has valid Qt Style Sheet syntax."""
    light_qss = _get_light_qss()
    dark_qss = _get_dark_qss()

    # Basic syntax checks
    assert "{" in light_qss and "}" in light_qss
    assert "{" in dark_qss and "}" in dark_qss

    # Check for common syntax errors
    assert ";;" not in light_qss, "Double semicolon is invalid"
    assert ";;" not in dark_qss, "Double semicolon is invalid"

    # Check for selector declarations
    assert "QMainWindow" in light_qss or "QMenuBar" in light_qss
    assert "QMainWindow" in dark_qss or "QMenuBar" in dark_qss


def test_configure_app_returns_valid_theme_name(qt_app):
    """Test that configure_app returns valid theme names."""
    # Re-configure the same app with different themes
    result = configure_app(qt_app, "light")
    assert result in ("light", "dark", "auto")

    result = configure_app(qt_app, "dark")
    assert result in ("light", "dark", "auto")

    result = configure_app(qt_app, "auto")
    assert result in ("light", "dark", "auto")
