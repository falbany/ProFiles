"""Telemetry subsystem — logging and diagnostic operations.

- :func:`configure_logger` — configure the global ``profiles`` logger
- :func:`get_logger` — get or create the default logger
- :class:`LoggerFactory` — factory for rotating-file loggers
- :class:`SourceFilter` — filter that injects a ``source`` field on records
- :mod:`events` — structured event helpers
"""

from __future__ import annotations

from profiles.core.telemetry.diagnostics import (
    LOG_FORMAT,
    LoggerFactory,
    SourceFilter,
    configure_logger,
    get_logger,
)
from profiles.core.telemetry.events import (
    app_closed,
    app_gui_failed,
    app_launched,
    app_restarting,
    app_started,
    command_exit,
    command_failed,
    command_timeout,
    config_create_failed,
    config_created,
    config_invalid,
    config_loaded,
    config_reload_failed,
    config_reloaded,
    file_delete_failed,
    file_deleted,
    file_launch_failed,
    file_launched,
    file_not_a_file,
    file_not_found,
    file_open_config,
    file_open_log,
    lang_switched,
    processing_failed,
    scan_complete,
    scan_failed,
    theme_switched,
    wcag_contrast_faint,
    workflow_aborted,
    workflow_step,
    workflow_step_failed,
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
    "app_closed",
    "app_gui_failed",
    "app_launched",
    "app_restarting",
    "app_started",
    "command_exit",
    "command_failed",
    "command_timeout",
    "config_create_failed",
    "config_created",
    "config_invalid",
    "config_loaded",
    "config_reload_failed",
    "config_reloaded",
    "file_delete_failed",
    "file_deleted",
    "file_launch_failed",
    "file_launched",
    "file_not_a_file",
    "file_not_found",
    "file_open_config",
    "file_open_log",
    "lang_switched",
    "processing_failed",
    "scan_complete",
    "scan_failed",
    "theme_switched",
    "wcag_contrast_faint",
    "workflow_aborted",
    "workflow_step",
    "workflow_step_failed",
]
