"""Test backend selection gateway in ProFiles app."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

from profiles.app import ProFileApp, main
from profiles.core.config.models import AppConfig


def _resolved_backend(argv: list[str]) -> str:
    """Run ``main()`` with *argv* and return the backend it constructs."""
    with patch.object(sys, "argv", argv), patch("profiles.app.ProFileApp") as mock_app:
        main()
    call = mock_app.call_args
    assert call is not None, "main() must construct ProFileApp"
    return call.kwargs["gui_backend"]


def test_backend_selection_default_web() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert _resolved_backend(["profiles"]) == "web"


def test_backend_selection_cli_tk() -> None:
    with patch.dict(os.environ, {}, clear=True):
        assert _resolved_backend(["profiles", "--tkinter"]) == "tk"


def test_launch_web_backend_calls_desktop() -> None:
    app = ProFileApp(headless=False)
    app._config = AppConfig(title="Test Bench")
    with patch("profiles.desktop.launcher.launch_desktop_window") as mock_launch:
        app._run_web_gui()
        mock_launch.assert_called_once_with(app._config, port=8088, host="127.0.0.1")
