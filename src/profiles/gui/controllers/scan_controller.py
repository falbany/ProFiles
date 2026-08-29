"""Background scan worker — pure, no Tk, no widgets.

Owns the thread-side logic for a single scan: invoke
``scanner.scan_and_process_dynamic`` and push the result (or error) to
a queue. The main thread drains the queue.

Splitting this out lets us unit-test the worker without instantiating
Tk. The MainWindow still owns the queue, scan_id bookkeeping, and the
chunked main-thread insert.
"""

from __future__ import annotations

import logging
import queue
from typing import Any

from profiles.core.config import service as config_service
from profiles.core.config.models import AppConfig
from profiles.core.processing import scanner
from profiles.core.processing.scanner import ScannedFileDynamic

# Tuple pushed onto the result queue:
#   ("ok", scan_id, [ScannedFileDynamic, ...])
#   ("error", scan_id, None)
ScanResult = tuple[str, int, list[ScannedFileDynamic] | None]


def run_scan(
    *,
    config: AppConfig,
    directory_label: str,
    scan_paths: list[str],
    extension: str,
    filter_text: str,
    recursive: bool,
    queue_: queue.Queue[ScanResult],
    scan_id: int,
    logger: logging.Logger,
) -> None:
    """Execute a single scan off the main thread; push result to ``queue_``.

    Intended to be the target of a ``threading.Thread``. Pure: reads
    only ``config`` and the captured ``scan_paths``/``filter_text``/
    etc. Writes only to ``queue_`` and ``logger``.

    Args:
        config: The application configuration (read for exclude lists).
        directory_label: Captured at request time; used to pick the
            active machine config (which contributes per-config excludes).
        scan_paths: Directories to scan (multiple supported).
        extension: Extension filter expression.
        filter_text: Keyword filter.
        recursive: Whether to recurse into subdirectories.
        queue_: Shared queue drained by the main thread.
        scan_id: Identifies this scan; the main thread discards results
            whose scan_id has been superseded.
        logger: Standard logger for diagnostics.
    """
    try:
        active = config_service.find_active_config(config, directory_label)
        exclude_files = (
            active.search_exclude_files if active is not None else config.search_exclude_files
        )
        items = scanner.scan_and_process_dynamic(
            scan_paths,
            extension=extension,
            filter_text=filter_text,
            recursive=recursive,
            exclude_dirs=config.search_exclude_dirs,
            exclude_files=exclude_files,
            column_names=config.column_names,
            columns=config.columns,
            config=config,
        )
        queue_.put(("ok", scan_id, items))
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error during background file scan: %s", exc)
        queue_.put(("error", scan_id, None))


class ScanQueue:
    """Thin wrapper around ``queue.Queue`` with a typed ``try_dequeue``.

    Extracted so tests can substitute a fake queue without touching the
    real threading primitives.
    """

    def __init__(self) -> None:
        self._q: queue.Queue[ScanResult] = queue.Queue()

    def put(self, result: ScanResult) -> None:
        self._q.put(result)

    def try_dequeue(self) -> tuple[bool, ScanResult | None]:
        """Return ``(True, item)`` if available, else ``(False, None)``."""
        try:
            return True, self._q.get_nowait()
        except queue.Empty:
            return False, None


# Silence unused-import lint for Any (kept for forward-compat typing).
_ = Any
__all__ = ["run_scan", "ScanQueue", "ScanResult"]
