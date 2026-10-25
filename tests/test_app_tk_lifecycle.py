"""Tkinter-backend lifecycle tests for ``profiles.app`` — deprecated.

These tests pin the ``gui_backend="tk"`` surface of the app (window
creation, Tcl/Tk error handling, ``--tkinter`` CLI routing). They sit at
the mirrored path of ``src/profiles/app.py`` and carry their own module
skip; delete them together with the Tkinter frontend in phase 2.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from profiles.app import ProFileApp, main

pytestmark = pytest.mark.skip(
    reason=(
        "Tkinter GUI is deprecated — web frontend is the default. "
        "Skipped in preparation for removal (phase 2 deletes src/profiles/gui)."
    )
)

# ── ProFileApp.run (tk GUI mode) ─────────────────────────────────────────


class TestRunTkMode:
    """ProFileApp.run — tk-backend branch (deprecated)."""

    def test_gui_mode_creates_window(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mock_main_window = mocker.patch("profiles.gui.main_window.MainWindow")
        mock_window_instance = mocker.MagicMock()
        mock_main_window.return_value = mock_window_instance

        app = ProFileApp(gui_backend="tk")
        app.run()
        mock_main_window.assert_called_once()
        mock_window_instance.run.assert_called_once()

    def test_tk_runtime_error_handling(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mocker.patch(
            "profiles.gui.main_window.MainWindow",
            side_effect=RuntimeError("no screen available"),
        )

        app = ProFileApp(gui_backend="tk")
        with pytest.raises(SystemExit):
            app.run()

    def test_tk_tcl_error_handling(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        import tkinter

        mocker.patch(
            "profiles.gui.main_window.MainWindow",
            side_effect=tkinter.TclError("display error"),
        )

        app = ProFileApp(gui_backend="tk")
        with pytest.raises(SystemExit):
            app.run()

    def test_gui_non_display_error(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """RuntimeError without 'screen'/'display' keyword uses generic message."""
        mocker.patch("profiles.app.configure_logger")
        mock_config = mocker.MagicMock()
        mock_config.verbose = "INFO"
        mocker.patch("profiles.app.load_config", return_value=mock_config)
        mocker.patch(
            "profiles.gui.main_window.MainWindow",
            side_effect=RuntimeError("Tcl error"),
        )

        app = ProFileApp(gui_backend="tk")
        with pytest.raises(SystemExit):
            app.run()


# ── CLI backend selection (--tkinter, deprecated) ────────────────────────


def test_backend_selection_cli_tk() -> None:
    """``--tkinter`` routes to the deprecated tk backend."""
    with (
        patch.object(sys, "argv", ["profiles", "--tkinter"]),
        patch("profiles.app.ProFileApp") as mock_app,
    ):
        main()
    call = mock_app.call_args
    assert call is not None, "main() must construct ProFileApp"
    assert call.kwargs["gui_backend"] == "tk"
