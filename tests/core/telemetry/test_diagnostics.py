"""Tests for profiles.core.telemetry.diagnostics — LoggerFactory, SourceFilter, configure_logger, get_logger."""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
from pathlib import Path

import pytest

from profiles.core.telemetry.diagnostics import (
    LoggerFactory,
    SourceFilter,
    configure_logger,
    get_logger,
)


def _reset_profile_logger() -> None:
    """Reset the 'profiles' logger to a clean state and close all handlers."""
    import profiles.core.telemetry.diagnostics as logger_module

    logger = logging.getLogger("profiles")
    # Close every handler first so file descriptors are released —
    # RotatingFileHandler keeps the log file locked until close().
    for handler in logger.handlers[:]:
        with contextlib.suppress(Exception):
            handler.close()
        logger.removeHandler(handler)
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    # Drop the module-level singleton so get_logger() rebuilds from scratch.
    logger_module._DEFAULT_LOGGER = None


@pytest.fixture(autouse=True)
def _cleanup_logger() -> None:
    """Ensure each test starts and ends with a clean profiles logger."""
    _reset_profile_logger()
    yield
    _reset_profile_logger()


# ── SourceFilter ────────────────────────────────────────────────────────────


class TestSourceFilter:
    """SourceFilter — injects 'source' attribute into log records."""

    def test_default_source_empty(self) -> None:
        f = SourceFilter()
        assert f.source == ""

    def test_custom_source(self) -> None:
        f = SourceFilter(source="TEST-HOST")
        assert f.source == "TEST-HOST"

    def test_filter_injects_source(self) -> None:
        f = SourceFilter(source="MY-PC")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert f.filter(record) is True
        assert record.source == "MY-PC"

    def test_filter_preserves_other_attributes(self) -> None:
        f = SourceFilter(source="SRC")
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert record.levelno == logging.WARNING
        assert record.msg == "test"

    def test_can_change_source(self) -> None:
        f = SourceFilter(source="A")
        f.source = "B"
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        f.filter(record)
        assert record.source == "B"


# ── LoggerFactory ───────────────────────────────────────────────────────────


class TestLoggerFactoryInit:
    """LoggerFactory.__init__ — default and custom values."""

    def test_default_values(self) -> None:
        factory = LoggerFactory()
        assert factory._log_path == Path("profiles.log")
        assert factory._source == "ProFiles"
        assert factory._level == logging.INFO
        assert factory._max_bytes == 5 * 1024 * 1024
        assert factory._backup_count == 5

    def test_custom_values(self) -> None:
        factory = LoggerFactory(
            log_path="custom/log.txt",
            source="CUSTOM",
            level=logging.DEBUG,
            max_bytes=1024,
            backup_count=2,
        )
        assert factory._log_path == Path("custom/log.txt")
        assert factory._source == "CUSTOM"
        assert factory._level == logging.DEBUG
        assert factory._max_bytes == 1024
        assert factory._backup_count == 2

    def test_string_level(self) -> None:
        factory = LoggerFactory(level="WARNING")
        assert factory._level == "WARNING"  # passed through, resolved by logger.setLevel


class TestLoggerFactoryEnsureLogDir:
    """LoggerFactory._ensure_log_dir creates parent directory."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        log_file = tmp_path / "sub" / "dir" / "test.log"
        factory = LoggerFactory(log_path=log_file)
        factory._ensure_log_dir()
        assert log_file.parent.exists()

    def test_existing_directory_does_not_error(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        factory = LoggerFactory(log_path=log_file)
        factory._ensure_log_dir()  # should not raise


class TestLoggerFactoryCreateLogger:
    """LoggerFactory.create_logger() — creates configured logger instances."""

    def test_returns_logger_named_profile(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, source="TEST")
        logger = factory.create_logger()
        assert logger.name == "profiles"
        assert logger.level == logging.INFO

    def test_has_rotating_file_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file)
        logger = factory.create_logger()
        handlers = logger.handlers
        file_handlers = [h for h in handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) >= 1
        assert file_handlers[0].baseFilename == str(log_file.resolve())

    def test_has_stream_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file)
        logger = factory.create_logger()
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_file_handler_has_source_filter(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, source="HOSTNAME")
        logger = factory.create_logger()
        for handler in logger.handlers:
            for filt in handler.filters:
                if isinstance(filt, SourceFilter):
                    assert filt.source == "HOSTNAME"
                    return
        pytest.fail("No SourceFilter found on any handler")

    def test_logger_writes_to_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, source="WRITER")
        logger = factory.create_logger()
        logger.info("Hello, World!")
        # Force flush
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "Hello, World!" in content
        assert "WRITER" in content

    def test_log_format_includes_source(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, source="MYPC-01")
        logger = factory.create_logger()
        logger.info("test message")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        # Format: "YYYY-MM-DD HH:MM:SS - INFO - MYPC-01: test message"
        assert "MYPC-01: test message" in content
        assert " - INFO - " in content

    def test_clears_existing_handlers(self, tmp_path: Path) -> None:
        """create_logger() should clear handlers to avoid duplicates."""
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file)
        logger1 = factory.create_logger()
        count1 = len(logger1.handlers)
        logger2 = factory.create_logger()
        count2 = len(logger2.handlers)
        assert count2 == count1  # Not accumulating duplicates

    def test_logger_respects_level(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, level=logging.WARNING)
        logger = factory.create_logger()
        assert logger.level == logging.WARNING
        # Every installed handler must honor the configured level —
        # previously the console handler was hardcoded to WARNING.
        for handler in logger.handlers:
            assert handler.level == logging.WARNING

    def test_debug_level_records_debug_messages(self, tmp_path: Path) -> None:
        """DEBUG level should let debug/info/warning/error through to file."""
        log_file = tmp_path / "debug.log"
        factory = LoggerFactory(log_path=log_file, source="DBG", level=logging.DEBUG)
        logger = factory.create_logger()
        logger.debug("d-msg")
        logger.info("i-msg")
        logger.warning("w-msg")
        logger.error("e-msg")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        for needle in ("d-msg", "i-msg", "w-msg", "e-msg", " - DEBUG - ", " - ERROR - "):
            assert needle in content, f"missing {needle!r} in log"

    def test_error_level_filters_out_below(self, tmp_path: Path) -> None:
        """ERROR level must drop DEBUG/INFO/WARNING, keep ERROR/CRITICAL."""
        log_file = tmp_path / "err_only.log"
        factory = LoggerFactory(log_path=log_file, source="ERR", level=logging.ERROR)
        logger = factory.create_logger()
        logger.debug("drop-debug")
        logger.info("drop-info")
        logger.warning("drop-warn")
        logger.error("keep-error")
        logger.critical("keep-crit")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "drop-debug" not in content
        assert "drop-info" not in content
        assert "drop-warn" not in content
        assert "keep-error" in content
        assert "keep-crit" in content

    def test_string_level_resolved(self, tmp_path: Path) -> None:
        """configure_logger() must accept string level names like 'DEBUG'."""
        log_file = tmp_path / "str_lvl.log"
        logger = configure_logger(log_path=log_file, source="STR", level="DEBUG")
        assert logger.level == logging.DEBUG
        for handler in logger.handlers:
            assert handler.level == logging.DEBUG

    def test_handlers_have_matching_level(self, tmp_path: Path) -> None:
        """Logger level and all handlers must agree (no silent filters)."""
        log_file = tmp_path / "match.log"
        factory = LoggerFactory(log_path=log_file, level=logging.WARNING)
        logger = factory.create_logger()
        for handler in logger.handlers:
            assert handler.level == logger.level


class TestLoggerFactoryUpdateSource:
    """LoggerFactory.update_source() — updates source on all handlers."""

    def test_updates_source_on_all_handlers(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, source="OLD")
        factory.create_logger()
        factory.update_source("NEW-SOURCE")
        logger = logging.getLogger("profiles")
        for handler in logger.handlers:
            for filt in handler.filters:
                if isinstance(filt, SourceFilter):
                    assert filt.source == "NEW-SOURCE"
                    return
        pytest.fail("No SourceFilter found")

    def test_writes_with_new_source(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        factory = LoggerFactory(log_path=log_file, source="OLD")
        logger = factory.create_logger()
        factory.update_source("UPDATED")
        logger.info("after update")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "UPDATED: after update" in content
        assert "OLD" not in content


# ── configure_logger ────────────────────────────────────────────────────────


class TestConfigureLogger:
    """configure_logger() module-level convenience function."""

    def test_returns_configured_logger(self, tmp_path: Path) -> None:
        log_file = tmp_path / "cfg_test.log"
        logger = configure_logger(log_path=log_file, source="CFG", level=logging.DEBUG)
        assert logger.name == "profiles"
        # Should have at least one handler
        assert len(logger.handlers) > 0

    def test_overrides_global_logger(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        configure_logger(log_path=log_file, source="SRC1")
        # The global _DEFAULT_LOGGER should now point to logger1
        log_file2 = tmp_path / "test2.log"
        logger2 = configure_logger(log_path=log_file2, source="SRC2")
        import profiles.core.telemetry.diagnostics as logger_module

        assert logger_module._DEFAULT_LOGGER is logger2

    def test_writes_correct_format(self, tmp_path: Path) -> None:
        log_file = tmp_path / "fmt_test.log"
        logger = configure_logger(log_path=log_file, source="FMT-SRC")
        logger.info("format check")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "FMT-SRC: format check" in content

    def test_default_arguments(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Change cwd to tmp_path so profiles.log is writeable
        monkeypatch.chdir(tmp_path)
        logger = configure_logger()
        assert logger.level == logging.INFO

    def test_info_logged(self, tmp_path: Path) -> None:
        log_file = tmp_path / "info.log"
        logger = configure_logger(log_path=log_file, source="INFO-TEST")
        logger.info("info message")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "info message" in content

    def test_warning_logged(self, tmp_path: Path) -> None:
        log_file = tmp_path / "warn.log"
        logger = configure_logger(log_path=log_file, source="WARN-TEST")
        logger.warning("warning message")
        for handler in logger.handlers:
            handler.flush()
        content = log_file.read_text(encoding="utf-8")
        assert "WARN" in content


# ── get_logger ──────────────────────────────────────────────────────────────


class TestGetLogger:
    """get_logger() — singleton accessor."""

    def test_creates_logger_if_none_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # autouse fixture already cleared _DEFAULT_LOGGER
        logger = get_logger()
        assert logger is not None
        assert logger.name == "profiles"

    def test_returns_existing_logger(self, tmp_path: Path) -> None:
        log_file = tmp_path / "existing.log"
        logger1 = configure_logger(log_path=log_file, source="EXIST")
        logger2 = get_logger()
        assert logger2 is logger1  # same instance
