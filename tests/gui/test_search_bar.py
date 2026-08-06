"""Tests for profiles.gui.search_bar.SearchBar without instantiating tk.Tk.

Strategy: patch ``tkinter.ttk`` and the ``tkinter.StringVar`` class so the
constructor runs against in-memory fakes. Capture widget creation calls so tests
can assert widget identity and event bindings.

Production source under test is NOT modified — these tests observe behaviour.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock

import pytest

from profiles.gui.search_bar import SearchBar

# ── In-memory fakes ─────────────────────────────────────────────────────────


class FakeWidget:
    """In-memory ttk widget that records construction and method calls."""

    instances: list[FakeWidget] = []

    def __init__(self, *args, **kwargs) -> None:
        self._args = args
        self._kwargs = kwargs
        self._bindings: dict[str, object] = {}
        self._text: str = kwargs.get("text", "")
        self._command = kwargs.get("command")
        FakeWidget.instances.append(self)

    # Layout no-ops
    def pack(self, *args, **kwargs) -> None:
        return None

    def grid(self, *args, **kwargs) -> None:
        return None

    # Event binding
    def bind(self, event: str, callback, add=None) -> str:  # type: ignore[no-untyped-def]
        self._bindings[event] = callback
        return f"fake-binding-{event}"

    # Configuration
    def configure(self, **kwargs) -> None:
        if "text" in kwargs:
            self._text = kwargs["text"]

    def cget(self, key: str):
        if key == "text":
            return self._text
        return None

    # Misc ttk widget methods
    def focus_set(self) -> None:
        return None

    def invoke(self) -> None:
        if self._command is not None:
            self._command()

    def winfo_height(self) -> int:
        return 36

    def winfo_rootx(self) -> int:
        return 0

    def winfo_rooty(self) -> int:
        return 0

    def update_idletasks(self) -> None:
        return None


class FakeStringVar:
    """In-memory StringVar stand-in."""

    def __init__(self, *args, **kwargs) -> None:
        self._value: str = kwargs.get("value", "")

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class FakeToolTip:
    """No-op ToolTip stand-in. Real ToolTip binds events to widgets."""

    def __init__(self, *args, **kwargs) -> None:
        return None


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_fake_tk_constants() -> types.SimpleNamespace:
    """Build a fake ``tk`` namespace exposing the constants used by SearchBar."""
    return types.SimpleNamespace(
        StringVar=FakeStringVar,
        X="x",
        Y="y",
        BOTH="both",
        LEFT="left",
        RIGHT="right",
        TOP="top",
        BOTTOM="bottom",
        W="w",
        E="e",
        N="n",
        S="s",
        NW="nw",
        NE="ne",
        SW="sw",
        SE="se",
        CENTER="center",
        VERTICAL="vertical",
        HORIZONTAL="horizontal",
        NORMAL="normal",
        DISABLED="disabled",
    )


def _make_fake_ttk() -> types.SimpleNamespace:
    """Build a fake ``ttk`` namespace exposing every widget class used by SearchBar."""
    return types.SimpleNamespace(
        Frame=FakeWidget,
        Label=FakeWidget,
        Combobox=FakeWidget,
        Checkbutton=FakeWidget,
        Button=FakeWidget,
        Separator=FakeWidget,
        Treeview=FakeWidget,
    )


@pytest.fixture
def patched_tk(monkeypatch: pytest.MonkeyPatch) -> FakeWidget:
    """Patch tkinter imports in ``search_bar`` module to in-memory fakes."""
    FakeWidget.instances = []

    monkeypatch.setattr("profiles.gui.search_bar.tk", _make_fake_tk_constants())
    monkeypatch.setattr("profiles.gui.search_bar.ttk", _make_fake_ttk())
    monkeypatch.setattr("profiles.gui.search_bar.ToolTip", FakeToolTip)

    return FakeWidget


@pytest.fixture
def callback_mocks() -> dict[str, MagicMock]:
    """Mock every callback the SearchBar consumes."""
    return {
        "on_directory_changed": MagicMock(),
        "on_directory_enter": MagicMock(),
        "on_directory_double_click": MagicMock(),
        "on_browse": MagicMock(),
        "on_extension_or_filter_select": MagicMock(),
        "on_debounced_refresh_ext": MagicMock(),
        "on_flush_timer_ext": MagicMock(),
        "on_filter_refresh": MagicMock(),
        "on_flush_timer_filter": MagicMock(),
        "on_recursive_toggle": MagicMock(),
        "on_search": MagicMock(),
    }


def _make_search_bar(callbacks: dict[str, MagicMock]) -> SearchBar:
    """Build a SearchBar with the faked Tk environment."""
    parent = FakeWidget()
    recursive_var = MagicMock()
    return SearchBar(
        parent=parent,
        release_version="1.0.0",
        recursive_var=recursive_var,
        config_title="",
        on_directory_changed=callbacks["on_directory_changed"],
        on_directory_enter=callbacks["on_directory_enter"],
        on_directory_double_click=callbacks["on_directory_double_click"],
        on_browse=callbacks["on_browse"],
        on_extension_or_filter_select=callbacks["on_extension_or_filter_select"],
        on_debounced_refresh_ext=callbacks["on_debounced_refresh_ext"],
        on_flush_timer_ext=callbacks["on_flush_timer_ext"],
        on_filter_refresh=callbacks["on_filter_refresh"],
        on_flush_timer_filter=callbacks["on_flush_timer_filter"],
        on_recursive_toggle=callbacks["on_recursive_toggle"],
        on_search=callbacks["on_search"],
    )


# ── Widget construction tests ───────────────────────────────────────────────


class TestSearchBarBuildsWidgets:
    """``SearchBar.__init__`` builds every expected widget."""

    def test_builds_search_frame(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.search_frame is not None
        assert isinstance(bar.search_frame, FakeWidget)

    def test_builds_dir_frame(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.dir_frame is not None
        assert isinstance(bar.dir_frame, FakeWidget)

    def test_builds_filter_frame(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.filter_frame is not None
        assert isinstance(bar.filter_frame, FakeWidget)

    def test_builds_dir_combo(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.dir_combo is not None
        assert isinstance(bar.dir_combo, FakeWidget)

    def test_builds_ext_combo(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.ext_combo is not None
        assert isinstance(bar.ext_combo, FakeWidget)

    def test_builds_filter_combo(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.filter_combo is not None
        assert isinstance(bar.filter_combo, FakeWidget)

    def test_builds_recursive_check(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.recursive_check is not None
        assert isinstance(bar.recursive_check, FakeWidget)

    def test_builds_search_btn(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.search_btn is not None
        assert isinstance(bar.search_btn, FakeWidget)

    def test_builds_browse_btn(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.browse_btn is not None
        assert isinstance(bar.browse_btn, FakeWidget)

    def test_builds_title_label(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert bar.title_label is not None
        assert isinstance(bar.title_label, FakeWidget)


# ── Event binding tests ─────────────────────────────────────────────────────


class TestSearchBarBindingsPresence:
    """Verify the expected event bindings are registered on each widget."""

    def test_dir_combo_binds_combobox_selected(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert "<<ComboboxSelected>>" in bar.dir_combo._bindings

    def test_dir_combo_binds_return(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert "<Return>" in bar.dir_combo._bindings

    def test_dir_combo_binds_double_click(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert "<Double-Button-1>" in bar.dir_combo._bindings

    def test_ext_combo_binds_key_release(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert "<KeyRelease>" in bar.ext_combo._bindings

    def test_filter_combo_binds_key_release(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        assert "<KeyRelease>" in bar.filter_combo._bindings


class TestSearchBarBindingsInvokeCallbacks:
    """Bindings should fire the right callback when invoked."""

    def test_dir_combo_combobox_selected_fires_callback(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.dir_combo._bindings["<<ComboboxSelected>>"]()
        callback_mocks["on_directory_changed"].assert_called_once()

    def test_dir_combo_return_fires_callback(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.dir_combo._bindings["<Return>"]()
        callback_mocks["on_directory_enter"].assert_called_once()

    def test_dir_combo_double_click_fires_callback(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.dir_combo._bindings["<Double-Button-1>"]()
        callback_mocks["on_directory_double_click"].assert_called_once()

    def test_ext_combo_key_release_fires_callback(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.ext_combo._bindings["<KeyRelease>"](None)
        callback_mocks["on_debounced_refresh_ext"].assert_called_once()

    def test_filter_combo_key_release_fires_callback(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.filter_combo._bindings["<KeyRelease>"](None)
        callback_mocks["on_filter_refresh"].assert_called_once()


# ── Search button invoke test ───────────────────────────────────────────────


class TestSearchBarButtonInvoke:
    """The search button's ``invoke()`` should fire the on_search callback."""

    def test_search_btn_invoke_fires_on_search(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.search_btn.invoke()
        callback_mocks["on_search"].assert_called_once()

    def test_browse_btn_invoke_fires_on_browse(self, patched_tk, callback_mocks):
        bar = _make_search_bar(callback_mocks)
        bar.browse_btn.invoke()
        callback_mocks["on_browse"].assert_called_once()
