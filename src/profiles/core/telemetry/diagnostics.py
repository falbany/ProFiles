"""Logging subsystem for ProFiles.

Provides a rotating file logger that produces log entries with the log format::

    YYYY-MM-DD HH:MM:SS - Level  - Source: Message

Uses Python's RotatingFileHandler to manage log file growth,
keeping the log directory clean and bounded in size.

Lives in ``core`` because logging is a cross-cutting domain concern
shared by every front-end (GUI, CLI, TUI) and has zero dependency
on Tkinter.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import types
from pathlib import Path

from profiles.core.telemetry.events import log_rotated, uncaught_exception

# log format
LOG_FORMAT = "%(asctime)s - %(levelname)-4s - %(source)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file
_DEFAULT_BACKUP_COUNT = 5  # Keep 5 rotated files


class SourceFilter(logging.Filter):
    """Custom filter that injects a 'source' field into log records."""

    def __init__(self, source: str = "") -> None:
        super().__init__()
        self.source = source

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the source field to every log record."""
        record.source = self.source
        return True


class TelemetryRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler that emits a LOG_ROTATED event on rollover.

    The event is written just before the rotation, so it lands as the
    first line of the freshly opened log file.
    """

    def __init__(
        self,
        filename: str,
        mode: str = "a",
        maxBytes: int = 0,  # noqa: N803 — matches logging.handlers signature
        backupCount: int = 0,  # noqa: N803 — matches logging.handlers signature
        encoding: str | None = None,
        delay: bool = False,
    ) -> None:
        self.event_logger: logging.Logger | None = None
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

    def doRollover(self) -> None:  # noqa: N802 — overrides stdlib method name
        """Emit LOG_ROTATED as the first line of the fresh log, then rotate."""
        try:
            old_size = os.path.getsize(self.baseFilename)
        except OSError:
            old_size = 0
        super().doRollover()
        if self.event_logger is None or old_size == 0:
            return
        # Guard against recursion: a temporary maxBytes of 0 disables
        # shouldRollover while the event is emitted through this handler.
        original_max = self.maxBytes
        self.maxBytes = 0
        try:
            log_rotated(self.event_logger, old_size_bytes=old_size)
        finally:
            self.maxBytes = original_max


def install_crash_hook(logger: logging.Logger) -> None:
    """Route uncaught exceptions into the log as UNCAUGHT_EXCEPTION (CRITICAL).

    Chains the previously installed ``sys.excepthook`` so default crash
    reporting is preserved after the event is logged.

    Args:
        logger: The "profiles" logger to receive the CRITICAL event.
    """
    previous_hook = sys.excepthook

    def _log_crash(
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        type_name = getattr(exc_type, "__name__", "Unknown")
        uncaught_exception(logger, type_name=str(type_name), error=str(exc_value))
        previous_hook(exc_type, exc_value, traceback)

    sys.excepthook = _log_crash  # type: ignore[assignment]


class LoggerFactory:
    """Factory for creating configured ProFiles loggers.

    The factory honors the requested *level* for both the logger and
    every handler it installs — DEBUG, INFO, WARNING, ERROR, CRITICAL
    are all supported. The rotating file handler captures everything
    at or above the configured level; the console handler mirrors it.

    Usage::

        factory = LoggerFactory("profiles.log", source="ST-244", level=logging.DEBUG)
        logger = factory.create_logger()
        logger.debug("verbose detail")
        logger.info("Application started")
        logger.warning("something to watch")
        logger.error("launch failed: %s", exc)
    """

    def __init__(
        self,
        log_path: Path | str = "profiles.log",
        source: str = "ProFiles",
        level: int | str = logging.INFO,
        max_bytes: int = _DEFAULT_MAX_BYTES,
        backup_count: int = _DEFAULT_BACKUP_COUNT,
    ) -> None:
        """Initialize the logger factory.

        Args:
            log_path: Path to the log file.
            source: Default source identifier (e.g., hostname).
            level: Logging level — DEBUG / INFO / WARNING / ERROR /
                CRITICAL, by name (str) or numeric constant.
            max_bytes: Maximum size per log file before rotation.
            backup_count: Number of rotated log files to keep.
        """
        self._log_path = Path(log_path)
        self._source = source
        self._level = level
        self._max_bytes = max_bytes
        self._backup_count = backup_count

    def _ensure_log_dir(self) -> None:
        """Create the log directory if it doesn't exist."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def create_logger(self) -> logging.Logger:
        """Create and return a configured logger instance.

        The logger uses a RotatingFileHandler and writes entries
        in the log format.

        Returns:
            A configured logging.Logger instance.
        """
        self._ensure_log_dir()

        logger = logging.getLogger("profiles")
        logger.setLevel(self._level)

        # Remove any existing handlers to avoid duplicates on re-creation
        # Close handlers properly to release file handles
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        source_filter = SourceFilter(source=self._source)

        # --- File handler with rotation ---
        file_handler = TelemetryRotatingFileHandler(
            filename=str(self._log_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(self._level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(source_filter)
        file_handler.event_logger = logger
        logger.addHandler(file_handler)

        # --- Console handler (stderr) — mirrors the configured level ---
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self._level)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(source_filter)
        logger.addHandler(console_handler)

        return logger

    def update_source(self, source: str) -> None:
        """Update the source identifier on all handlers.

        Allows changing the source (e.g., to the detected hostname)
        after the logger has been created.
        """
        self._source = source
        logger = logging.getLogger("profiles")
        for handler in logger.handlers:
            for log_filter in handler.filters:
                if isinstance(log_filter, SourceFilter):
                    log_filter.source = source


# Module-level convenience
_DEFAULT_LOGGER: logging.Logger | None = None  # noqa: N816


def get_logger() -> logging.Logger:
    """Get or create the default ProFiles logger.

    Returns:
        A configured logging.Logger instance.
    """
    global _DEFAULT_LOGGER  # noqa: PLW0603
    if _DEFAULT_LOGGER is None:
        factory = LoggerFactory()
        _DEFAULT_LOGGER = factory.create_logger()
    return _DEFAULT_LOGGER


def configure_logger(
    log_path: Path | str = "profiles.log",
    source: str = "ProFiles",
    level: int | str = logging.INFO,
) -> logging.Logger:
    """Configure the global logger with the given settings.

    The *level* parameter accepts any standard logging level — DEBUG,
    INFO, WARNING, ERROR, CRITICAL — as either a numeric constant or
    its string name. Both the rotation file handler and the console
    handler honor this level.

    Args:
        log_path: Path to the log file.
        source: Source identifier (e.g., hostname).
        level: Logging level (numeric constant or case-insensitive
            string like ``"DEBUG"``, ``"WARNING"``, ``"ERROR"``).

    Returns:
        The configured logger.
    """
    global _DEFAULT_LOGGER  # noqa: PLW0603
    # Accept string level names like "DEBUG" / "WARNING" — stdlib already
    # normalizes them through logging.getLevelName, but normalize explicit
    # numeric coercion failures up-front for a clearer error.
    normalized_level: int | str = level
    if isinstance(level, str):
        numeric = logging.getLevelName(level.upper())
        if isinstance(numeric, int):
            normalized_level = numeric
    factory = LoggerFactory(
        log_path=log_path,
        source=source,
        level=normalized_level,
    )
    _DEFAULT_LOGGER = factory.create_logger()
    return _DEFAULT_LOGGER
