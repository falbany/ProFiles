"""Tests for profiles.gui.qt.status_bar — StatusBar widget."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import directly to avoid circular import from profiles.gui.qt.__init__
from PySide6.QtWidgets import QApplication

from profiles.gui.qt.status_bar import StatusBar


@pytest.fixture
def app():
    """Create QApplication for testing."""
    if not QApplication.instance():
        return QApplication([])
    return QApplication.instance()


class TestStatusBarInit:
    """Tests for StatusBar initialization."""

    def test_creates_without_callbacks(self, app):
        """StatusBar should create with all callbacks optional."""
        status_bar = StatusBar()
        assert status_bar is not None

    def test_creates_with_all_callbacks(self, app):
        """StatusBar should accept all optional callbacks."""
        callbacks = {
            "on_config_click": MagicMock(),
            "on_refresh_click": MagicMock(),
            "on_log_click": MagicMock(),
            "on_shortcuts_click": MagicMock(),
            "on_theme_toggle": MagicMock(),
            "on_language_toggle": MagicMock(),
        }
        status_bar = StatusBar(**callbacks)
        assert status_bar is not None

    def test_system_info_displayed(self, app):
        """System info should be displayed on initialization."""
        with patch("profiles.gui.qt.status_bar.collect_system_info") as mock_info:
            mock_info.return_value.username = "testuser"
            mock_info.return_value.hostname = "testhost"
            mock_info.return_value.ip = "192.168.1.1"

            status_bar = StatusBar()

            # Check labels contain system info
            assert "testuser" in status_bar._user_label.text()
            assert "testhost" in status_bar._host_label.text()
            assert "192.168.1.1" in status_bar._ip_label.text()


class TestStatusBarSignals:
    """Tests for StatusBar signal emissions."""

    def test_config_clicked_emits(self, app):
        """Config link should emit config_clicked signal."""
        emitted = []
        sb = StatusBar()
        sb.config_clicked.connect(lambda: emitted.append(True))
        sb._config_link.linkActivated.emit("#")
        assert len(emitted) == 1

    def test_log_clicked_emits(self, app):
        """Log link should emit log_clicked signal."""
        emitted = []
        sb = StatusBar()
        sb.log_clicked.connect(lambda: emitted.append(True))
        sb._log_link.linkActivated.emit("#")
        assert len(emitted) == 1

    def test_refresh_button_calls_callback(self, app):
        """Refresh button should call on_refresh_click callback."""
        mock_callback = MagicMock()
        status_bar = StatusBar(on_refresh_click=mock_callback)
        status_bar._refresh_btn.click()
        mock_callback.assert_called_once()

    def test_theme_button_calls_callback(self, app):
        """Theme button should call on_theme_toggle callback."""
        mock_callback = MagicMock()
        status_bar = StatusBar(on_theme_toggle=mock_callback)
        status_bar._theme_btn.click()
        mock_callback.assert_called_once()


class TestStatusBarMethods:
    """Tests for StatusBar public methods."""

    def test_update_file_count(self, app):
        """File count should update with flash animation."""
        status_bar = StatusBar()
        status_bar.update_file_count(42, "C:/test")

        assert "Files: 42" in status_bar._count_label.text()
        assert status_bar._dir_status_label.text() == "C:/test"

    def test_set_scanning(self, app):
        """Scanning state should update count label."""
        status_bar = StatusBar()
        status_bar.update_file_count(10)
        status_bar.set_scanning(True)

        assert "Scanning" in status_bar._count_label.text()

        status_bar.set_scanning(False)
        assert "Files: 10" in status_bar._count_label.text()

    def test_set_directory_status(self, app):
        """Directory status should update label."""
        status_bar = StatusBar()
        status_bar.set_directory_status("Ready")
        assert status_bar._dir_status_label.text() == "Ready"

    def test_update_theme_label(self, app):
        """Theme label should update."""
        status_bar = StatusBar()
        status_bar.update_theme_label("🌙 Dark")
        assert status_bar._theme_btn.text() == "🌙 Dark"

    def test_update_language_label(self, app):
        """Language label should update."""
        status_bar = StatusBar(on_language_toggle=lambda: None)
        status_bar.update_language_label()
        assert status_bar._language_btn is not None


class TestStatusBarTooltips:
    """Tests for StatusBar tooltips."""

    def test_all_links_have_tooltips(self, app):
        """All interactive elements should have tooltips."""
        status_bar = StatusBar(
            on_shortcuts_click=lambda: None,
            on_language_toggle=lambda: None,
        )

        assert status_bar._config_link.toolTip() != ""
        assert status_bar._refresh_btn.toolTip() != ""
        assert status_bar._log_link.toolTip() != ""
        assert status_bar._shortcuts_btn.toolTip() != ""
        assert status_bar._theme_btn.toolTip() != ""
        assert status_bar._language_btn.toolTip() != ""

    def test_system_labels_have_tooltips(self, app):
        """System info labels should have tooltips."""
        status_bar = StatusBar()

        assert status_bar._user_label.toolTip() != ""
        assert status_bar._host_label.toolTip() != ""
        assert status_bar._ip_label.toolTip() != ""
        assert status_bar._count_label.toolTip() != ""
        assert status_bar._dir_status_label.toolTip() != ""


class TestStatusBarI18n:
    """Tests for StatusBar internationalization."""

    def test_apply_text_updates_labels(self, app):
        """_apply_text should update all translatable labels."""
        status_bar = StatusBar()

        # Store original texts
        original_config = status_bar._config_link.text()

        # Apply text (should not crash)
        status_bar._apply_text("en")

        # Should still have content
        assert status_bar._config_link.text() != ""

    def test_register_with_i18n(self, app):
        """StatusBar should register with i18n system."""
        # Clear registry for clean test
        from profiles.gui.i18n import _relabel_registry, _reset_for_tests

        _reset_for_tests()

        status_bar = StatusBar()

        # Should be registered
        assert status_bar._apply_text in _relabel_registry
