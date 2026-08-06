"""Tests for profiles.core.environment.system — SystemInfo, collect_system_info, apply_source_to_logger."""

from __future__ import annotations

import logging

from profiles.core.environment.system import SystemInfo, apply_source_to_logger, collect_system_info
from profiles.core.telemetry.diagnostics import SourceFilter


class TestCollectSystemInfo:
    """Tests for collect_system_info()."""

    def test_returns_strings(self) -> None:
        """All three fields should be non-empty strings."""
        info = collect_system_info()
        assert isinstance(info, SystemInfo)
        assert isinstance(info.hostname, str) and info.hostname
        assert isinstance(info.username, str) and info.username
        assert isinstance(info.ip, str) and info.ip


class TestApplySourceToLogger:
    """Tests for apply_source_to_logger()."""

    def test_updates_source_filter(self) -> None:
        """The SourceFilter on every handler is updated."""
        logger = logging.getLogger("profile_test_source")
        logger.setLevel(logging.DEBUG)
        handler = logging.NullHandler()
        handler.addFilter(SourceFilter(source="old"))
        logger.handlers.clear()
        logger.addHandler(handler)

        apply_source_to_logger(logger, "new-host")
        for h in logger.handlers:
            for f in h.filters:
                if isinstance(f, SourceFilter):
                    assert f.source == "new-host"

    def test_no_source_filter_no_error(self) -> None:
        """Handlers without a SourceFilter are silently skipped."""
        logger = logging.getLogger("profile_test_noop")
        logger.setLevel(logging.DEBUG)
        handler = logging.NullHandler()
        logger.handlers.clear()
        logger.addHandler(handler)

        # Should not raise
        apply_source_to_logger(logger, "any-host")

    def test_empty_handlers_no_error(self) -> None:
        """A logger with no handlers is silently handled."""
        logger = logging.getLogger("profile_test_empty")
        logger.handlers.clear()
        apply_source_to_logger(logger, "any-host")
