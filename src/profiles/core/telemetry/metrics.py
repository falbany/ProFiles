"""Telemetry module — scan performance metrics.

Provides timing instrumentation for file scan operations:

- ``ScanMetrics``: dataclass describing one scan (duration, throughput...).
- ``ScanTimer``: context manager that times a scan and logs the metrics.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from profiles.core.telemetry.events import scan_complete

logger = logging.getLogger("profiles")  # Use parent logger directly for proper propagation


@dataclass
class ScanMetrics:
    """Metrics for a file scan operation."""

    directory: str
    file_count: int
    duration_ms: float
    files_per_second: float
    recursive: bool
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "directory": self.directory,
            "file_count": self.file_count,
            "duration_ms": self.duration_ms,
            "files_per_second": self.files_per_second,
            "recursive": self.recursive,
            "error_count": self.error_count,
        }


class ScanTimer:
    """Context manager for timing scan operations."""

    def __init__(self, directory: str, recursive: bool = False) -> None:
        self.directory = directory
        self.recursive = recursive
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.file_count: int = 0
        self.error_count: int = 0

    def __enter__(self) -> ScanTimer:
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        self.end_time = time.perf_counter()
        if exc_type is not None:
            self.error_count += 1

    def record_files(self, count: int) -> None:
        """Record the number of files found."""
        self.file_count = count

    def get_metrics(self) -> ScanMetrics | None:
        """Get scan metrics if completed."""
        if self.start_time is None or self.end_time is None:
            return None

        duration_ms = (self.end_time - self.start_time) * 1000
        files_per_second = self.file_count / ((self.end_time - self.start_time) or 1)

        return ScanMetrics(
            directory=self.directory,
            file_count=self.file_count,
            duration_ms=duration_ms,
            files_per_second=files_per_second,
            recursive=self.recursive,
            error_count=self.error_count,
        )

    def finish(self, file_count: int, level: int = logging.DEBUG) -> ScanMetrics | None:
        """Record the final file count, stop the timer, and log metrics.

        Convenience wrapper for the common end-of-scan sequence:
        record count, close timer, emit the DEBUG log line.

        Args:
            file_count: Number of files found by the scan.
            level: Logging level (default DEBUG) - reserved for future use.

        Returns:
            The computed ScanMetrics, or ``None`` if the timer was
            never started.
        """
        self.record_files(file_count)
        self.__exit__(None, None, None)
        metrics = self.get_metrics()
        if metrics:
            scan_complete(
                logger,
                directory=metrics.directory,
                extension="*",
                filter_text="",
                files=metrics.file_count,
                recursive=metrics.recursive,
                duration_ms=metrics.duration_ms,
                errors=metrics.error_count,
            )
        return metrics
