"""Tests for launch_file_with_args — Task 4 (must not block on the child).

The launcher is spawned and never awaited: ``Popen`` without a ``with``
block, so the suite does not wait for the viewer to close.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import profiles.utils.file_utils as file_utils
from profiles.utils.file_utils import launch_file_with_args


class TestLaunchFileWithArgs:
    """Popen is not awaited; empty args short-circuit to False."""

    def test_posix_defaults_to_xdg_open_without_waiting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_popen = MagicMock()
        monkeypatch.setattr(file_utils.subprocess, "Popen", mock_popen)
        monkeypatch.setattr(file_utils, "_IS_WINDOWS", False)
        monkeypatch.setattr(file_utils, "_IS_MACOS", False)

        result = launch_file_with_args(Path("a.pdf"), "--page 2")

        assert result is True
        mock_popen.assert_called_once_with(["xdg-open", "a.pdf", "--page", "2"])
        # The context manager protocol must NOT be used — __exit__ waits
        # for the child process.
        mock_popen.return_value.__enter__.assert_not_called()
        mock_popen.return_value.__exit__.assert_not_called()

    def test_empty_args_returns_false_without_popen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_popen = MagicMock()
        monkeypatch.setattr(file_utils.subprocess, "Popen", mock_popen)
        monkeypatch.setattr(file_utils, "_IS_WINDOWS", False)
        monkeypatch.setattr(file_utils, "_IS_MACOS", False)

        result = launch_file_with_args(Path("a.pdf"), "   ")

        assert result is False
        mock_popen.assert_not_called()
