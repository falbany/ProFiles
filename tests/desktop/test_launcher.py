"""Test the desktop window launcher (server-owned window lifecycle)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from profiles.core.config.models import AppConfig
from profiles.desktop.launcher import _make_document_applier, launch_desktop_window
from profiles.desktop.lifecycle import find_available_port
from profiles.server.state import ServerState

_WILDCARD_HOST = "0.0.0.0"
_LOOPBACK_HOST = "127.0.0.1"


@pytest.fixture
def webview_mock(mocker) -> MagicMock:
    """Replace the pywebview module import so no window system is touched."""
    return mocker.patch("profiles.desktop.launcher.webview")


@pytest.fixture
def local_ip_mock(mocker) -> MagicMock:
    """Pin get_local_ip so the Network banner asserts deterministically."""
    return mocker.patch("profiles.utils.network.get_local_ip", return_value="192.0.2.7")


@pytest.fixture
def odoc_handler_mock(mocker) -> MagicMock:
    """Keep window-lifecycle tests hermetic: no real Cocoa class patching."""
    return mocker.patch("profiles.desktop.launcher._install_open_document_handler")


def test_webview_url_uses_loopback_for_wildcard_bind(
    webview_mock: MagicMock, local_ip_mock: MagicMock, odoc_handler_mock: MagicMock, capsys
) -> None:
    """A 0.0.0.0 bind opens the window at 127.0.0.1 and advertises the LAN URL."""
    launch_desktop_window(
        AppConfig(title="t"),
        port=find_available_port(8000),
        host=_WILDCARD_HOST,
    )
    url = webview_mock.create_window.call_args.kwargs["url"]
    assert url.startswith(f"http://{_LOOPBACK_HOST}:"), url
    assert not url.startswith("http://0.0.0.0:")
    out = capsys.readouterr().out
    assert "Network: http://192.0.2.7:" in out
    assert f"Local:   http://{_LOOPBACK_HOST}:" in out


def test_webview_url_and_single_line_for_loopback_bind(
    webview_mock: MagicMock, local_ip_mock: MagicMock, odoc_handler_mock: MagicMock, capsys
) -> None:
    """A loopback bind keeps the URL as-is and prints only the local line."""
    launch_desktop_window(
        AppConfig(title="t"),
        port=find_available_port(8000),
        host=_LOOPBACK_HOST,
    )
    url = webview_mock.create_window.call_args.kwargs["url"]
    assert url.startswith(f"http://{_LOOPBACK_HOST}:")
    out = capsys.readouterr().out
    assert "Local:" in out
    assert "Network:" not in out


def test_webview_window_geometry_fits_status_bar(
    webview_mock: MagicMock, odoc_handler_mock: MagicMock
) -> None:
    """The default window is wide enough for the full status bar in one line."""
    launch_desktop_window(
        AppConfig(title="t"),
        port=find_available_port(8000),
        host=_LOOPBACK_HOST,
    )
    kwargs = webview_mock.create_window.call_args.kwargs
    assert kwargs["width"] == 1200
    assert kwargs["height"] == 700
    assert kwargs["min_size"] == (1000, 500)


def test_launch_installs_open_document_handler(
    webview_mock: MagicMock, local_ip_mock: MagicMock, mocker
) -> None:
    """The running-window odoc handler is installed before webview starts (#188)."""
    install = mocker.patch("profiles.desktop.launcher._install_open_document_handler")

    launch_desktop_window(
        AppConfig(title="t"),
        port=find_available_port(8000),
        host=_LOOPBACK_HOST,
    )

    install.assert_called_once()
    (state,) = install.call_args.args
    assert state.instance_token  # the live server's state was wired


class TestDocumentApplier:
    """The odoc callback shares the handoff route's apply semantics (#188)."""

    def test_applies_config_and_records_notification(self, tmp_path) -> None:
        state = ServerState(config=AppConfig(title="t"))
        config = tmp_path / "b.profiles"
        config.write_text("defaults:\n  title: B\n", encoding="utf-8")

        _make_document_applier(state)([str(config)])

        assert state.config_path == config.resolve()
        events = state.external_events_after(0)
        assert events[-1]["kind"] == "config_handoff"
        assert events[-1]["config_applied"] is True
        assert "b.profiles" in events[-1]["message"]

    def test_rejects_and_reports_a_non_config_file(self, tmp_path) -> None:
        state = ServerState(config=AppConfig(title="t"))
        junk = tmp_path / "junk.txt"
        junk.write_text("nope", encoding="utf-8")

        _make_document_applier(state)([str(junk)])  # must not raise

        events = state.external_events_after(0)
        assert events[-1]["kind"] == "config_handoff_failed"
        assert events[-1]["config_applied"] is False

    def test_reports_a_missing_file_without_raising(self, tmp_path) -> None:
        state = ServerState(config=AppConfig(title="t"))

        _make_document_applier(state)([str(tmp_path / "ghost.profiles")])

        events = state.external_events_after(0)
        assert events[-1]["kind"] == "config_handoff_failed"
