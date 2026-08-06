"""Telemetry subsystem — logging and diagnostic operations.

- :func:`configure_logger` — configure the global ``profiles`` logger
- :func:`get_logger` — get or create the default logger
- :class:`LoggerFactory` — factory for rotating-file loggers
- :class:`SourceFilter` — filter that injects a ``source`` field on records
"""

from __future__ import annotations

from profiles.core.telemetry.diagnostics import (
    LOG_FORMAT,
    LoggerFactory,
    SourceFilter,
    configure_logger,
    get_logger,
)
from profiles.core.telemetry.metrics import ScanMetrics, ScanTimer

__all__ = [
    "LOG_FORMAT",
    "LoggerFactory",
    "SourceFilter",
    "configure_logger",
    "get_logger",
    "ScanMetrics",
    "ScanTimer",
]
