"""Test backend selection gateway in ProFiles app."""

from __future__ import annotations

import os
from unittest.mock import patch

from profiles.app import ProFileApp
from profiles.core.config.models import AppConfig


def test_backend_selection_default_web() -> None:
    with patch.dict(os.environ, {}, clear=True):
        app = ProFileApp(headless=False)
        backend = app.resolve_gui_backend()
        assert backend == "web"


def test_backend_selection_env_tk() -> None:
    with patch.dict(os.environ, {"PROFILES_GUI_BACKEND": "tk"}):
        app = ProFileApp(headless=False)
        backend = app.resolve_gui_backend()
        assert backend == "tk"


def test_launch_web_backend_calls_desktop() -> None:
    app = ProFileApp(headless=False)
    app._config = AppConfig(title="Test Bench")
    with patch("profiles.desktop.launcher.launch_desktop_window") as mock_launch:
        app._run_web_gui()
        mock_launch.assert_called_once_with(app._config, port=8088, host="127.0.0.1")
