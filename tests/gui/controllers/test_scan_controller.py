"""Tests for the scan controller worker.

Covers the pure background-scan function and the queue wrapper. The
rest of the scan lifecycle (chunked insert, queue polling) stays in
MainWindow and is tested there.
"""

from __future__ import annotations

import logging
import queue
from unittest.mock import MagicMock, patch

from profiles.core.config.models import AppConfig
from profiles.gui.controllers.scan_controller import (
    ScanQueue,
    ScanResult,
    run_scan,
)


def _config() -> AppConfig:
    """Minimal AppConfig stub — the real one is complex and not relevant."""
    # Plain MagicMock — AppConfig attributes are set externally, not declared
    # at class scope, so spec= would reject them. Set the iteration
    # attribute explicitly.
    return MagicMock(configurations=[])


def _logger() -> logging.Logger:
    return logging.getLogger("test_scan_controller")


class TestRunScan:
    """run_scan() is the off-main-thread worker."""

    def test_pushes_ok_with_items(self) -> None:
        cfg = _config()
        q: queue.Queue[ScanResult] = queue.Queue()
        items = [MagicMock(name="sf1"), MagicMock(name="sf2")]

        with patch(
            "profiles.gui.controllers.scan_controller.scanner.scan_and_process_dynamic",
            return_value=items,
        ):
            run_scan(
                config=cfg,
                directory_label="d",
                scan_paths=["/tmp"],
                extension=".txt",
                filter_text="",
                recursive=True,
                queue_=q,
                scan_id=7,
                logger=_logger(),
            )

        status, sid, got = q.get_nowait()
        assert status == "ok"
        assert sid == 7
        assert got is items

    def test_pushes_error_on_exception(self) -> None:
        cfg = _config()
        q: queue.Queue[ScanResult] = queue.Queue()

        with patch(
            "profiles.gui.controllers.scan_controller.scanner.scan_and_process_dynamic",
            side_effect=RuntimeError("boom"),
        ):
            run_scan(
                config=cfg,
                directory_label="d",
                scan_paths=["/tmp"],
                extension=".txt",
                filter_text="",
                recursive=True,
                queue_=q,
                scan_id=8,
                logger=_logger(),
            )

        status, sid, got = q.get_nowait()
        assert status == "error"
        assert sid == 8
        assert got is None

    def test_uses_active_config_excludes_when_available(self) -> None:
        cfg = _config()
        active = MagicMock(search_exclude_files=("active",))
        q: queue.Queue[ScanResult] = queue.Queue()
        with (
            patch(
                "profiles.gui.controllers.scan_controller.scanner.scan_and_process_dynamic",
                return_value=[],
            ) as scan_mock,
            patch(
                "profiles.gui.controllers.scan_controller.config_service.find_active_config",
                return_value=active,
            ),
        ):
            run_scan(
                config=cfg,
                directory_label="d",
                scan_paths=["/tmp"],
                extension=".txt",
                filter_text="",
                recursive=True,
                queue_=q,
                scan_id=9,
                logger=_logger(),
            )

        kwargs = scan_mock.call_args.kwargs
        assert kwargs["exclude_files"] == ("active",)

    def test_falls_back_to_base_excludes_when_no_active(self) -> None:
        cfg = _config()
        cfg.search_exclude_files = ("base",)
        q: queue.Queue[ScanResult] = queue.Queue()
        with (
            patch(
                "profiles.gui.controllers.scan_controller.scanner.scan_and_process_dynamic",
                return_value=[],
            ) as scan_mock,
            patch(
                "profiles.gui.controllers.scan_controller.config_service.find_active_config",
                return_value=None,
            ),
        ):
            run_scan(
                config=cfg,
                directory_label="d",
                scan_paths=["/tmp"],
                extension=".txt",
                filter_text="",
                recursive=True,
                queue_=q,
                scan_id=10,
                logger=_logger(),
            )

        kwargs = scan_mock.call_args.kwargs
        assert kwargs["exclude_files"] == ("base",)


class TestScanQueue:
    """ScanQueue wraps queue.Queue with a typed try_dequeue."""

    def test_empty_returns_false(self) -> None:
        q = ScanQueue()
        has, item = q.try_dequeue()
        assert has is False
        assert item is None

    def test_put_then_dequeue(self) -> None:
        q = ScanQueue()
        q.put(("ok", 1, []))
        has, item = q.try_dequeue()
        assert has is True
        assert item == ("ok", 1, [])

    def test_try_dequeue_is_non_blocking(self) -> None:
        q = ScanQueue()
        # Should return (False, None) without raising or blocking.
        has, item = q.try_dequeue()
        assert has is False
        assert item is None
