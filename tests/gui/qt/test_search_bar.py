"""Tests for the Qt SearchBar widget."""

from __future__ import annotations

import platform
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt

from profiles.gui.i18n import set_language
from profiles.gui.qt.search_bar import SearchBar


@pytest.fixture
def search_bar(qtbot):
    """Create a SearchBar widget for testing."""
    widget = SearchBar(
        release_version="1.0.0",
        recursive_checked=True,
        config_title="Test Config",
    )
    qtbot.addWidget(widget)
    return widget


class TestSearchBarUI:
    """Test SearchBar UI construction."""

    def test_widget_creates_successfully(self, search_bar):
        """Test that SearchBar widget is created without errors."""
        assert search_bar is not None
        assert search_bar.title_label is not None
        assert search_bar.title_author is not None
        assert search_bar.dir_combo is not None
        assert search_bar.ext_combo is not None
        assert search_bar.filter_combo is not None
        assert search_bar.recursive_check is not None
        assert search_bar.search_btn is not None
        assert search_bar.browse_btn is not None

    def test_title_displays_config_title(self, search_bar):
        """Test that title displays config title when provided."""
        assert "Test Config" in search_bar.title_label.text()

    def test_title_displays_default_when_no_config(self, qtbot):
        """Test that title displays default when no config title."""
        widget = SearchBar(release_version="1.0.0", config_title="")
        qtbot.addWidget(widget)
        assert "ProFiles" in widget.title_label.text()

    def test_author_label_displays_version(self, search_bar):
        """Test that author label displays version."""
        assert "v1.0.0" in search_bar.title_author.text()

    def test_recursive_checkbox_initial_state_checked(self, search_bar):
        """Test that recursive checkbox is checked by default."""
        assert search_bar.recursive_check.isChecked() is True

    def test_recursive_checkbox_initial_state_unchecked(self, qtbot):
        """Test that recursive checkbox can be unchecked."""
        widget = SearchBar(release_version="1.0.0", recursive_checked=False)
        qtbot.addWidget(widget)
        assert widget.recursive_check.isChecked() is False

    def test_comboboxes_are_editable(self, search_bar):
        """Test that comboboxes are editable."""
        assert search_bar.dir_combo.isEditable() is True
        assert search_bar.ext_combo.isEditable() is True


class TestSearchBarSignals:
    """Test SearchBar signal emissions."""

    def test_directory_changed_signal_emitted(self, qtbot, search_bar):
        """Test that directory_changed signal is emitted on selection."""
        emitted = False

        def on_dir_changed():
            nonlocal emitted
            emitted = True

        search_bar.directory_changed.connect(on_dir_changed)
        search_bar.dir_combo.setCurrentText("/test/path")

        assert emitted is True

    def test_directory_entered_signal_emitted(self, qtbot, search_bar):
        """Test that directory_entered signal is emitted on Enter key."""
        emitted = False

        def on_dir_entered():
            nonlocal emitted
            emitted = True

        search_bar.directory_entered.connect(on_dir_entered)
        search_bar.dir_combo.lineEdit().returnPressed.emit()

        assert emitted is True

    def test_browse_clicked_signal_emitted(self, qtbot, search_bar):
        """Test that browse_clicked signal is emitted on button click."""
        emitted = False

        def on_browse():
            nonlocal emitted
            emitted = True

        search_bar.browse_clicked.connect(on_browse)
        search_bar.browse_btn.click()

        assert emitted is True

    def test_search_requested_signal_emitted(self, qtbot, search_bar):
        """Test that search_requested signal is emitted on search button."""
        emitted = False

        def on_search():
            nonlocal emitted
            emitted = True

        search_bar.search_requested.connect(on_search)
        search_bar.search_btn.click()

        assert emitted is True

    def test_recursive_toggled_signal_emitted(self, qtbot, search_bar):
        """Test that recursive_toggled signal is emitted on toggle."""
        emitted = False

        def on_recursive():
            nonlocal emitted
            emitted = True

        search_bar.recursive_toggled.connect(on_recursive)
        search_bar.recursive_check.toggle()

        assert emitted is True

    def test_extension_debounce_timer_starts(self, qtbot, search_bar):
        """Test that extension debounce timer starts on text change."""
        search_bar._ext_debounce_timer.setInterval(300)
        search_bar._on_ext_key_release("test")

        assert search_bar._ext_debounce_timer.isActive() is True

    def test_filter_debounce_timer_starts(self, qtbot, search_bar):
        """Test that filter debounce timer starts on text change."""
        search_bar._filter_debounce_timer.setInterval(300)
        search_bar._on_filter_key_release("test")

        assert search_bar._filter_debounce_timer.isActive() is True

    def test_ext_debounce_timeout_emits_signal(self, qtbot, search_bar):
        """Test that debounce timeout emits debounced_refresh_ext signal."""
        emitted = False

        def on_debounced():
            nonlocal emitted
            emitted = True

        search_bar.debounced_refresh_ext.connect(on_debounced)
        search_bar._on_ext_debounce_timeout()

        assert emitted is True

    def test_filter_debounce_timeout_emits_signal(self, qtbot, search_bar):
        """Test that filter debounce timeout emits filter_refresh signal."""
        emitted = False

        def on_refresh():
            nonlocal emitted
            emitted = True

        search_bar.filter_refresh.connect(on_refresh)
        search_bar._on_filter_debounce_timeout()

        assert emitted is True


class TestSearchBarHelperMethods:
    """Test SearchBar helper methods."""

    def test_set_directory_text_adds_item(self, qtbot, search_bar):
        """Test that set_directory_text adds item if not present."""
        search_bar.set_directory_text("/new/path")
        assert search_bar.dir_combo.findText("/new/path") >= 0

    def test_set_directory_text_selects_existing(self, qtbot, search_bar):
        """Test that set_directory_text selects existing item."""
        search_bar.dir_combo.addItem("/existing/path")
        search_bar.set_directory_text("/existing/path")
        assert search_bar.dir_combo.currentText() == "/existing/path"

    def test_set_extension_text_adds_item(self, qtbot, search_bar):
        """Test that set_extension_text adds item if not present."""
        search_bar.set_extension_text(".py")
        assert search_bar.ext_combo.findText(".py") >= 0

    def test_set_filter_text_sets_value(self, qtbot, search_bar):
        """Test that set_filter_text sets the filter value."""
        search_bar.set_filter_text("test_filter")
        assert search_bar.filter_combo.text() == "test_filter"

    def test_auto_select_directory_by_hostname_matches(self, qtbot, search_bar):
        """Test auto-select by hostname when match exists."""
        hostname = platform.node().lower()
        search_bar.dir_combo.addItem(f"/path/to/{hostname}/dir")
        search_bar.dir_combo.addItem("/other/path")

        search_bar.auto_select_directory_by_hostname([])

        assert hostname in search_bar.dir_combo.currentText().lower()

    def test_auto_select_directory_by_hostname_no_match_selects_first(self, qtbot, search_bar):
        """Test auto-select by hostname selects first when no match."""
        search_bar.dir_combo.addItem("/path/one")
        search_bar.dir_combo.addItem("/path/two")

        search_bar.auto_select_directory_by_hostname([])

        assert search_bar.dir_combo.currentIndex() == 0

    @patch("subprocess.Popen")
    def test_open_directory_in_explorer_windows(self, mock_popen, qtbot, search_bar):
        """Test open_directory_in_explorer on Windows."""
        with patch("platform.system", return_value="Windows"):
            search_bar.open_directory_in_explorer("/test/path")
            mock_popen.assert_called_once_with(["explorer", "/test/path"])

    @patch("subprocess.Popen")
    def test_open_directory_in_explorer_macos(self, mock_popen, qtbot, search_bar):
        """Test open_directory_in_explorer on macOS."""
        with patch("platform.system", return_value="Darwin"):
            search_bar.open_directory_in_explorer("/test/path")
            mock_popen.assert_called_once_with(["open", "/test/path"])

    @patch("subprocess.Popen")
    def test_open_directory_in_explorer_linux(self, mock_popen, qtbot, search_bar):
        """Test open_directory_in_explorer on Linux."""
        with patch("platform.system", return_value="Linux"):
            search_bar.open_directory_in_explorer("/test/path")
            mock_popen.assert_called_once_with(["xdg-open", "/test/path"])


class TestSearchBarI18n:
    """Test SearchBar internationalization."""

    def test_labels_display_english_by_default(self, search_bar):
        """Test that labels display English text by default."""
        set_language("en")
        # Trigger re-label
        search_bar._apply_text("en")
        # Check that browse button has English text
        assert "Browse" in search_bar.browse_btn.text()

    def test_labels_display_french_when_switched(self, qtbot, search_bar):
        """Test that labels display French text when language switched."""
        set_language("fr")
        search_bar._apply_text("fr")
        assert "Parcourir" in search_bar.browse_btn.text()

    def test_tooltips_display_english(self, search_bar):
        """Test that tooltips display English text."""
        set_language("en")
        search_bar._apply_text("en")
        tooltip = search_bar.dir_combo.toolTip()
        assert tooltip is not None

    def test_tooltips_display_french(self, qtbot, search_bar):
        """Test that tooltips display French text."""
        set_language("fr")
        search_bar._apply_text("fr")
        tooltip = search_bar.dir_combo.toolTip()
        assert tooltip is not None


class TestSearchBarEventFilter:
    """Test SearchBar event filter for double-click."""

    def test_double_click_emits_signal(self, qtbot, search_bar):
        """Test that double-click on directory combobox emits signal."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QMouseEvent

        emitted = False

        def on_double_click():
            nonlocal emitted
            emitted = True

        search_bar.directory_double_clicked.connect(on_double_click)

        # Create and send double-click event
        event = QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            search_bar.dir_combo.mapToGlobal(search_bar.dir_combo.rect().center()),
            search_bar.dir_combo.rect().center(),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

        search_bar.eventFilter(search_bar.dir_combo, event)

        assert emitted is True


class TestSearchBarProperties:
    """Test SearchBar property accessors."""

    def test_search_frame_returns_self(self, search_bar):
        """Test that search_frame property returns self."""
        assert search_bar.search_frame is search_bar

    def test_dir_var_returns_directory_text(self, qtbot, search_bar):
        """Test that dir_var returns current directory text."""
        search_bar.set_directory_text("/test/path")
        assert search_bar.dir_var == "/test/path"

    def test_ext_var_returns_extension_text(self, qtbot, search_bar):
        """Test that ext_var returns current extension text."""
        search_bar.set_extension_text(".py")
        assert search_bar.ext_var == ".py"

    def test_filter_var_returns_filter_text(self, qtbot, search_bar):
        """Test that filter_var returns current filter text."""
        search_bar.set_filter_text("test")
        assert search_bar.filter_var == "test"

    def test_recursive_var_returns_checkbox_state(self, qtbot, search_bar):
        """Test that recursive_var returns checkbox state."""
        search_bar.recursive_check.setChecked(True)
        assert search_bar.recursive_var is True
        search_bar.recursive_check.setChecked(False)
        assert search_bar.recursive_var is False
