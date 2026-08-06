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
from pathlib import Path

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
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(self._log_path),
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(self._level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(source_filter)
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
