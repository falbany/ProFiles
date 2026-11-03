"""Test the ``--host`` CLI option and its validation."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from profiles.app import ProFileApp, host_error, main


def test_host_error_accepts_wildcard_loopback_and_ipv4() -> None:
    assert host_error("0.0.0.0") is None
    assert host_error("127.0.0.1") is None
    assert host_error("172.16.41.65") is None


def test_host_error_rejects_hostname_and_ipv6() -> None:
    assert host_error("st-465") is not None
    assert host_error("::1") is not None


def test_default_host_is_loopback() -> None:
    """The app launches loopback-only; LAN is an opt-in via the status bar."""
    app = ProFileApp(headless=False)
    assert app._host == "127.0.0.1"


def test_explicit_loopback_host_is_kept() -> None:
    app = ProFileApp(headless=False, host="127.0.0.1")
    assert app._host == "127.0.0.1"


def test_main_rejects_hostname() -> None:
    with (
        patch.object(sys, "argv", ["profiles", "--host", "st-465"]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 2


def test_main_rejects_ipv6() -> None:
    with (
        patch.object(sys, "argv", ["profiles", "--host", "::1"]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 2


def test_main_passes_host_argument() -> None:
    """``--host`` flows from argv into the constructed ProFileApp."""
    argv = ["profiles", "--host", "127.0.0.1"]
    with patch.object(sys, "argv", argv), patch("profiles.app.ProFileApp") as mock_app:
        main()
    call = mock_app.call_args
    assert call is not None, "main() must construct ProFileApp"
    assert call.kwargs["host"] == "127.0.0.1"


def test_main_default_host_is_loopback() -> None:
    argv = ["profiles"]
    with patch.object(sys, "argv", argv), patch("profiles.app.ProFileApp") as mock_app:
        main()
    call = mock_app.call_args
    assert call is not None
    assert call.kwargs["host"] == "127.0.0.1"
