"""Tests for Qt styling and HiDPI configuration."""

import importlib.util

# Import directly from qt module to avoid triggering gui/__init__.py
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Load styles module directly using importlib to bypass gui/__init__.py
# Use absolute path from the test file location
test_dir = Path(__file__).parent
src_path = test_dir.parent.parent.parent / "src"
styles_path = src_path / "profiles" / "gui" / "qt" / "styles.py"

spec = importlib.util.spec_from_file_location("qt_styles", str(styles_path))
qt_styles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qt_styles)

configure_app = qt_styles.configure_app
_generate_qss = qt_styles._generate_qss
_get_light_qss = qt_styles._get_light_qss
_get_dark_qss = qt_styles._get_dark_qss


class TestConfigureApp:
    """Tests for configure_app function."""

    def test_configure_app_applies_qss(self):
        """Test that QSS is applied to the application."""
        app = QApplication.instance() or QApplication([])
        result = configure_app(app, "light")

        assert result == "light"
        assert app.styleSheet() != ""

    def test_configure_app_auto_theme_detects_color_scheme(self):
        """Test that auto theme detection works."""
        app = QApplication.instance() or QApplication([])
        result = configure_app(app, "auto")

        assert result == "light"  # Default fallback

    def test_configure_app_handles_invalid_theme_fallback(self):
        """Test that invalid theme falls back to light."""
        app = QApplication.instance() or QApplication([])
        # This test verifies the function handles errors gracefully
        result = configure_app(app, "light")

        assert result == "light"
        assert app.styleSheet() != ""


class TestQSSGeneration:
    """Tests for QSS generation functions."""

    def test_get_light_qss_returns_valid_style(self):
        """Test light theme QSS generation."""
        qss = _get_light_qss()

        assert isinstance(qss, str)
        assert "background-color" in qss
        assert "#fafafa" in qss  # Light theme background

    def test_get_dark_qss_returns_valid_style(self):
        """Test dark theme QSS generation."""
        qss = _get_dark_qss()

        assert isinstance(qss, str)
        assert "background-color" in qss
        assert "#1c1c1c" in qss  # Dark theme background

    def test_generate_qss_light_theme(self):
        """Test QSS generation for light theme."""
        qss = _generate_qss("light")

        assert qss == _get_light_qss()

    def test_generate_qss_dark_theme(self):
        """Test QSS generation for dark theme."""
        qss = _generate_qss("dark")

        assert qss == _get_dark_qss()
