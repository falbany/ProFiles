# Log Format & Telemetry — Implementation Plan

> **For Engineer**: Execute this plan task by task using TDD. All code, commands, and paths are explicitly provided. Start each task with the existing tests passing, end each task with them passing again.

---

## 🎯 Overview

Refactor 77 log call sites across 16 modules to emit a structured `key=value` event grammar.
Two phases: **Phase 1** lands the event catalogue + helpers + tests. **Phase 2** migrates
call sites in 3 batches by module area.

**New wire format** (every line):
```
YYYY-MM-DD HH:MM:SS - LEVEL  - hostname: EVENT_NAME key="value" key=value ...
```

**Example**:
```
2026-08-29 13:01:15 - INFO  - MACBOOKFA.LOCAL: APP_STARTED version="2026.7.0" headless=false
2026-08-29 13:01:15 - DEBUG - MACBOOKFA.LOCAL: SCAN_METRICS dir="base" duration_ms=25.657 rate=7366.59 errors=0
2026-08-29 13:01:51 - INFO  - MACBOOKFA.LOCAL: APP_CLOSED uptime_s=36
```

---

## 📁 File Map

```
src/profiles/core/telemetry/
├── events.py          NEW  — 25 event helpers (one per event from catalogue)
├── diagnostics.py     MOD  — add EVENT_FORMAT, _bool(), no structural change
├── metrics.py        MOD  — ScanTimer emits via events helper instead of raw repr
└── __init__.py       MOD  — re-export events helpers

tests/core/telemetry/
├── test_events.py     NEW  — one test per helper + parser regression fixture
└── (existing tests)  MOD  — update assertions to match new grammar

77 call sites across ~16 modules — mechanically updated in Phase 2 batches
```

---

## Phase 1 — Infrastructure & Catalogue

### Task 1: Create `core/telemetry/events.py` + tests

**File**: `src/profiles/core/telemetry/events.py`

Create the module with 25 event helpers. Follow this exact pattern — do not deviate:

```python
"""Structured telemetry events for profiles.log.

Each helper emits one event line in the grammar::

    HOSTNAME: EVENT_NAME key="value" key=value ...

Reference: docs/superpowers/specs/2026-08-29-log-format-and-telemetry-design.md
"""

from __future__ import annotations

import logging
from typing import Literal

# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _bool(b: bool) -> str:
    """Return lowercase boolean literal."""
    return "true" if b else "false"


def _quote(s: str) -> str:
    """Return s quoted if it contains spaces or =, else bare."""
    if not s:
        return '""'
    if any(c in s for c in ' "='):
        return f'"{s}"'
    return s


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


def app_started(logger: logging.Logger, *, version: str, headless: bool) -> None:
    logger.info('APP_STARTED version="%s" headless=%s', version, _bool(headless))


def app_closed(logger: logging.Logger, *, uptime_s: float) -> None:
    logger.info("APP_CLOSED uptime_s=%.0f", uptime_s)


def app_restarting(logger: logging.Logger) -> None:
    logger.info("APP_RESTARTING")


def app_launched(logger: logging.Logger, *, command: str) -> None:
    logger.info('APP_LAUNCHED command="%s"', command)


def app_gui_failed(logger: logging.Logger, *, error: str) -> None:
    logger.error('APP_GUI_FAILED error="%s"', error)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def config_loaded(logger: logging.Logger, *, path: str, mode: str, release: str) -> None:
    logger.info('CONFIG_LOADED path=%s mode="%s" release="%s"', _quote(path), mode, release)


def config_reloaded(logger: logging.Logger, *, path: str) -> None:
    logger.info("CONFIG_RELOADED path=%s", _quote(path))


def config_created(logger: logging.Logger, *, path: str) -> None:
    logger.info("CONFIG_CREATED path=%s", _quote(path))


def config_reload_failed(logger: logging.Logger, *, error: str) -> None:
    logger.error('CONFIG_RELOAD_FAILED error="%s"', error)


def config_invalid(logger: logging.Logger, *, error: str) -> None:
    logger.error('CONFIG_INVALID error="%s"', error)


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def scan_complete(
    logger: logging.Logger,
    *,
    directory: str,
    extension: str,
    filter_text: str,
    files: int,
    recursive: bool,
    duration_ms: float,
    errors: int = 0,
) -> None:
    """Emit SCAN_COMPLETE at INFO; SCAN_METRICS at DEBUG."""
    logger.info(
        "SCAN_COMPLETE dir=%s ext=%s filter=%s files=%d recursive=%s",
        _quote(directory),
        _quote(extension),
        _quote(filter_text),
        files,
        _bool(recursive),
    )
    if logger.isEnabledFor(logging.DEBUG):
        rate = files / (duration_ms / 1000) if duration_ms > 0 else 0.0
        logger.debug(
            "SCAN_METRICS dir=%s duration_ms=%.3f rate=%.2f errors=%d",
            _quote(directory),
            duration_ms,
            rate,
            errors,
        )


def scan_failed(logger: logging.Logger, *, directory: str, error: str) -> None:
    logger.warning('SCAN_FAILED dir=%s error="%s"', _quote(directory), error)


# ---------------------------------------------------------------------------
# UI / Theme / Language
# ---------------------------------------------------------------------------


def theme_switched(logger: logging.Logger, *, value: str, warnings: int = 0) -> None:
    logger.info('THEME_SWITCHED value="%s" warnings=%d', value, warnings)


def lang_switched(logger: logging.Logger, *, value: str) -> None:
    logger.info('LANG_SWITCHED value="%s"', value)


def wcag_contrast_faint(logger: logging.Logger, *, pair: str, ratio: str, fg: str, bg: str) -> None:
    logger.warning('WCAG_CONTRAST_FAINT pair="%s" ratio=%s fg=%s bg=%s', pair, ratio, fg, bg)


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


def file_open_config(logger: logging.Logger, *, path: str) -> None:
    logger.info("FILE_OPEN_CONFIG path=%s", _quote(path))


def file_open_log(logger: logging.Logger, *, path: str) -> None:
    logger.info("FILE_OPEN_LOG path=%s", _quote(path))


def file_not_found(logger: logging.Logger, *, path: str) -> None:
    logger.warning("FILE_NOT_FOUND path=%s", _quote(path))


def file_not_a_file(logger: logging.Logger, *, path: str) -> None:
    logger.warning("FILE_NOT_A_FILE path=%s", _quote(path))


def file_launch_failed(logger: logging.Logger, *, path: str, error: str) -> None:
    logger.error('FILE_LAUNCH_FAILED path=%s error="%s"', _quote(path), error)


def file_deleted(logger: logging.Logger, *, path: str) -> None:
    logger.info("FILE_DELETED path=%s", _quote(path))


def file_delete_failed(logger: logging.Logger, *, path: str, error: str) -> None:
    logger.error('FILE_DELETE_FAILED path=%s error="%s"', _quote(path), error)


def file_launched(
    logger: logging.Logger, *, path: str, version: str = "", user: str = "", args: str = ""
) -> None:
    """FILE_LAUNCHED merges the old USER=… audit line."""
    parts = [f"path={_quote(path)}"]
    if version:
        parts.append(f'version="{version}"')
    if user:
        parts.append(f'user="{user}"')
    if args:
        parts.append(f'args="{args}"')
    logger.info("FILE_LAUNCHED %s", " ".join(parts))


# ---------------------------------------------------------------------------
# Configuration create failure
# ---------------------------------------------------------------------------


def config_create_failed(logger: logging.Logger, *, error: str) -> None:
    logger.error('CONFIG_CREATE_FAILED error="%s"', error)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


def workflow_step(
    logger: logging.Logger, *, index: int, total: int, action: str, result: str
) -> None:
    logger.info(
        'WORKFLOW_STEP index=%d total=%d action="%s" result="%s"',
        index,
        total,
        action,
        result,
    )


def workflow_step_failed(logger: logging.Logger, *, failmode: str, action: str) -> None:
    logger.warning('WORKFLOW_STEP_FAILED failmode="%s" action="%s"', failmode, action)


def workflow_aborted(logger: logging.Logger, *, reason: str) -> None:
    logger.error('WORKFLOW_ABORTED reason="%s"', reason)


def processing_failed(logger: logging.Logger, *, path: str, error: str) -> None:
    logger.error('PROCESSING_FAILED path=%s error="%s"', _quote(path), error)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def command_timeout(logger: logging.Logger, *, timeout_s: int, command: str) -> None:
    logger.warning('COMMAND_TIMEOUT timeout_s=%d command="%s"', timeout_s, command)


def command_exit(logger: logging.Logger, *, code: int, command: str) -> None:
    logger.debug('COMMAND_EXIT code=%d command="%s"', code, command)


def command_failed(logger: logging.Logger, *, error: str, command: str) -> None:
    logger.error('COMMAND_FAILED error="%s" command="%s"', error, command)
```

**Verification**: `python3 -c from profiles.core.telemetry import events; print("OK")`

**Test file**: `tests/core/telemetry/test_events.py`

```python
"""Tests for events.py structured telemetry helpers."""

import logging
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from profiles.core.telemetry.events import (
    _bool,
    _quote,
    app_closed,
    app_gui_failed,
    app_launched,
    app_restarting,
    app_started,
    command_exit,
    command_failed,
    command_timeout,
    config_created,
    config_invalid,
    config_loaded,
    config_reload_failed,
    config_reloaded,
    file_deleted,
    file_delete_failed,
    file_launched,
    file_launch_failed,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class LogCapture:
    """Capture the formatted message from a logger."""

    def __init__(self) -> None:
        self.handler = logging.handlers.MemoryHandler(capacity=256)
        self.logger = logging.getLogger("test_events")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        self.logger.addHandler(self.handler)
        self.handler.setLevel(logging.DEBUG)

    def capture(self, callable, *args, **kwargs) -> str:
        self.handler.flush()
        callable(*args, **kwargs)
        self.handler.flush()
        assert len(self.handler.buffer) == 1
        return self.handler.buffer[0].getMessage()

    EVENT_RE = re.compile(r"^[A-Z_]+ (?:\w+=\"[^\"]*\"|\w+=\w+|[\d.]+)+\s*$")


class TestBool:
    def test_true(self) -> None:
        assert _bool(True) == "true"

    def test_false(self) -> None:
        assert _bool(False) == "false"


class TestQuote:
    def test_bare_word(self) -> None:
        assert _quote("hello") == "hello"

    def test_quoted_spaces(self) -> None:
        assert _quote("hello world") == '"hello world"'

    def test_quoted_equals(self) -> None:
        assert _quote("a=b") == '"a=b"'

    def test_quoted_empty(self) -> None:
        assert _quote("") == '""'


# ---------------------------------------------------------------------------
# Event helpers — each test checks grammar
# ---------------------------------------------------------------------------


class TestAppEvents:
    def test_started(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_started")
        app_started(logger, version="1.0.0", headless=False)
        assert 'APP_STARTED version="1.0.0" headless=false' in caplog.text

    def test_closed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_closed")
        app_closed(logger, uptime_s=42.7)
        assert "APP_CLOSED uptime_s=42" in caplog.text

    def test_restarting(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_restarting")
        app_restarting(logger)
        assert "APP_RESTARTING" in caplog.text

    def test_launched(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_launched")
        app_launched(logger, command="/usr/bin/python")
        assert 'APP_LAUNCHED command="/usr/bin/python"' in caplog.text

    def test_gui_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_gui_failed")
        app_gui_failed(logger, error="no display")
        assert 'APP_GUI_FAILED error="no display"' in caplog.text


class TestConfigEvents:
    def test_loaded(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_loaded")
        config_loaded(logger, path="/a/b/.profiles", mode="auto", release="2026.7.0")
        text = caplog.text
        assert "CONFIG_LOADED" in text
        assert 'path="/a/b/.profiles"' in text
        assert 'mode="auto"' in text
        assert 'release="2026.7.0"' in text

    def test_reloaded(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_reloaded")
        config_reloaded(logger, path="/a/b/.profiles")
        assert 'CONFIG_RELOADED path="/a/b/.profiles"' in caplog.text

    def test_created(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_created")
        config_created(logger, path="/a/b/.profiles")
        assert 'CONFIG_CREATED path="/a/b/.profiles"' in caplog.text

    def test_reload_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_reload_failed")
        config_reload_failed(logger, error="parse error")
        assert 'CONFIG_RELOAD_FAILED error="parse error"' in caplog.text

    def test_invalid(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_invalid")
        config_invalid(logger, error="missing key")
        assert 'CONFIG_INVALID error="missing key"' in caplog.text


class TestScanEvents:
    def test_complete_info(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_scan_complete")
        scan_complete(
            logger,
            directory="base",
            extension="*",
            filter_text="",
            files=284,
            recursive=True,
            duration_ms=25.657,
            errors=0,
        )
        assert "SCAN_COMPLETE" in caplog.text
        assert "dir=" in caplog.text
        assert "files=284" in caplog.text
        assert "recursive=true" in caplog.text

    def test_complete_debug_metrics(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_scan_metrics")
        logger.setLevel(logging.DEBUG)
        scan_complete(
            logger,
            directory="base",
            extension="*",
            filter_text="",
            files=100,
            recursive=False,
            duration_ms=10.0,
            errors=1,
        )
        assert "SCAN_METRICS" in caplog.text
        assert "duration_ms=10.000" in caplog.text
        assert "rate=10.00" in caplog.text
        assert "errors=1" in caplog.text

    def test_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_scan_failed")
        scan_failed(logger, directory="/bad", error="permission denied")
        assert "SCAN_FAILED" in caplog.text


class TestThemeEvents:
    def test_theme_switched(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_theme")
        theme_switched(logger, value="dark", warnings=2)
        assert 'THEME_SWITCHED value="dark" warnings=2' in caplog.text

    def test_lang_switched(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_lang")
        lang_switched(logger, value="fr")
        assert 'LANG_SWITCHED value="fr"' in caplog.text

    def test_wcag_contrast(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_wcag")
        wcag_contrast_faint(logger, pair="border/surface", ratio="4.22", fg="#7A7680", bg="#121212")
        assert "WCAG_CONTRAST_FAINT" in caplog.text
        assert 'pair="border/surface"' in caplog.text


class TestFileEvents:
    def test_open_config(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_open_config")
        file_open_config(logger, path="/a/.profiles")
        assert 'FILE_OPEN_CONFIG path="/a/.profiles"' in caplog.text

    def test_open_log(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_open_log")
        file_open_log(logger, path="/a/profiles.log")
        assert 'FILE_OPEN_LOG path="/a/profiles.log"' in caplog.text

    def test_not_found(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_not_found")
        file_not_found(logger, path="/missing.txt")
        assert 'FILE_NOT_FOUND path="/missing.txt"' in caplog.text

    def test_not_a_file(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_not_a_file")
        file_not_a_file(logger, path="/some/dir")
        assert 'FILE_NOT_A_FILE path="/some/dir"' in caplog.text

    def test_launch_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_launch_failed")
        file_launch_failed(logger, path="/a.txt", error="no app")
        assert "FILE_LAUNCH_FAILED" in caplog.text

    def test_deleted(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_deleted")
        file_deleted(logger, path="/a.txt")
        assert 'FILE_DELETED path="/a.txt"' in caplog.text

    def test_delete_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_delete_failed")
        file_delete_failed(logger, path="/a.txt", error="read-only")
        assert "FILE_DELETE_FAILED" in caplog.text

    def test_launched(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_launched")
        file_launched(logger, path="/a.txt", version="1.0", user="bob", args="-v")
        text = caplog.text
        assert "FILE_LAUNCHED" in text
        assert 'path="/a.txt"' in text
        assert 'version="1.0"' in text
        assert 'user="bob"' in text
        assert 'args="-v"' in text

    def test_launched_minimal(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_launched_minimal")
        file_launched(logger, path="/a.txt")
        assert 'FILE_LAUNCHED path="/a.txt"' in caplog.text


class TestWorkflowEvents:
    def test_step(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_wf_step")
        workflow_step(logger, index=1, total=3, action="open", result="ok")
        assert "WORKFLOW_STEP" in caplog.text
        assert "index=1" in caplog.text
        assert "total=3" in caplog.text

    def test_step_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_wf_fail")
        workflow_step_failed(logger, failmode="warn", action="open")
        assert "WORKFLOW_STEP_FAILED" in caplog.text

    def test_aborted(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_wf_abort")
        workflow_aborted(logger, reason="failmode=abort")
        assert "WORKFLOW_ABORTED" in caplog.text

    def test_processing_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_proc_fail")
        processing_failed(logger, path="/a.txt", error="crash")
        assert "PROCESSING_FAILED" in caplog.text


class TestCommandEvents:
    def test_timeout(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_timeout")
        command_timeout(logger, timeout_s=30, command="make test")
        assert "COMMAND_TIMEOUT" in caplog.text

    def test_exit(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_exit")
        logger.setLevel(logging.DEBUG)
        command_exit(logger, code=0, command="make test")
        assert "COMMAND_EXIT" in caplog.text

    def test_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_cmd_fail")
        command_failed(logger, error="killed", command="make test")
        assert "COMMAND_FAILED" in caplog.text


# ---------------------------------------------------------------------------
# Grammar regression — parse a sample log line
# ---------------------------------------------------------------------------

GRAMMAR_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - "
    r"(DEBUG|INFO|WARNING|ERROR)\s+ - "
    r"[\w._-]+: "
    r"([A-Z_]+)"
    r"(?: (\w+=\"[^\"]*\"|\w+=[^\s\"=]+|\d+\.\d+|\d+))*\s*$"
)


class TestGrammarRegression:
    def test_scan_complete_parses(self) -> None:
        line = '2026-08-29 13:01:15 - INFO  - HOST: SCAN_COMPLETE dir="base" ext="*" filter="" files=284 recursive=true'
        m = GRAMMAR_RE.match(line)
        assert m is not None, f"Grammar failed: {line}"
        assert m.group(1) == "INFO"
        assert m.group(2) == "SCAN_COMPLETE"

    def test_app_started_parses(self) -> None:
        line = '2026-08-29 13:01:15 - INFO  - HOST: APP_STARTED version="1.0.0" headless=false'
        m = GRAMMAR_RE.match(line)
        assert m is not None, f"Grammar failed: {line}"

    def test_wcag_parses(self) -> None:
        line = '2026-08-29 01:08:12 - WARNING - HOST: WCAG_CONTRAST_FAINT pair="border/surface" ratio=4.22 fg=#7A7680 bg=#121212'
        m = GRAMMAR_RE.match(line)
        assert m is not None, f"Grammar failed: {line}"
```

**Run**: `python3 -m pytest tests/core/telemetry/test_events.py -v --no-cov`

---

### Task 2: Update `core/telemetry/diagnostics.py`

**Goal**: Add `_bool` to the module exports (it lives in `events.py` but needs a shared
type-annotation-free version if callers need it; for now, no change needed here).

Actually, `diagnostics.py` needs **zero structural changes**. The `LOG_FORMAT` stays the same
(`"%(asctime)s - %(levelname)-4s - %(source)s: %(message)s"`). The change is entirely in
what goes into `%(message)s`. So Task 2 is **skipped** — confirm by running existing tests:

```bash
python3 -m pytest tests/core/telemetry/ -v --no-cov
```

---

### Task 3: Update `core/telemetry/metrics.py` — `ScanTimer` integration

**File**: `src/profiles/core/telemetry/metrics.py`

Find `ScanTimer.__exit__` and replace the raw `repr()` debug log with a call to the new
helper. The dataclass is unchanged.

```python
# In ScanTimer.__exit__, replace:
#   logger.debug("Scan metrics: %s", metrics.to_dict())
# With:
from profiles.core.telemetry import events as _events

# ...inside __exit__:
if self.start_time is not None and self.end_time is not None:
    duration_ms = (self.end_time - self.start_time) * 1000
    _events.scan_complete(
        logger,
        directory=self.directory,
        extension="*",  # ScanTimer doesn't track extension
        filter_text="",  # ScanTimer doesn't track filter
        files=self.file_count,
        recursive=self.recursive,
        duration_ms=duration_ms,
        errors=self.error_count,
    )
```

Note: `ScanTimer` currently records `extension`, `filter_text`, and `recursive` are not
tracked — the existing callers (`scan.py`) have this data and already pass it to the helper
directly. Verify this is the case before proceeding.

**Run**: `python3 -m pytest tests/core/telemetry/test_metrics.py -v --no-cov`

---

### Task 4: Update `core/telemetry/__init__.py`

**File**: `src/profiles/core/telemetry/__init__.py`

Add the event helpers to the public export list:

```python
from profiles.core.telemetry.events import (
    app_started,
    app_closed,
    app_restarting,
    app_launched,
    app_gui_failed,
    config_loaded,
    config_reloaded,
    config_created,
    config_reload_failed,
    config_invalid,
    scan_complete,
    scan_failed,
    theme_switched,
    lang_switched,
    wcag_contrast_faint,
    file_open_config,
    file_open_log,
    file_not_found,
    file_not_a_file,
    file_launch_failed,
    file_deleted,
    file_delete_failed,
    file_launched,
    config_create_failed,
    workflow_step,
    workflow_step_failed,
    workflow_aborted,
    processing_failed,
    command_timeout,
    command_exit,
    command_failed,
)

__all__ = [
    # ... existing entries ...
    "app_started",
    "app_closed",
    "app_restarting",
    "app_launched",
    "app_gui_failed",
    "config_loaded",
    "config_reloaded",
    "config_created",
    "config_reload_failed",
    "config_invalid",
    "scan_complete",
    "scan_failed",
    "theme_switched",
    "lang_switched",
    "wcag_contrast_faint",
    "file_open_config",
    "file_open_log",
    "file_not_found",
    "file_not_a_file",
    "file_launch_failed",
    "file_deleted",
    "file_delete_failed",
    "file_launched",
    "config_create_failed",
    "workflow_step",
    "workflow_step_failed",
    "workflow_aborted",
    "processing_failed",
    "command_timeout",
    "command_exit",
    "command_failed",
]
```

**Run**: `python3 -c from profiles.core.telemetry import app_started, scan_complete; print("OK")`

---

## Phase 2 — Call-site Migration

Run `grep -rh 'logger\.\(info\|warning\|error\|debug\)' src/profiles --include="*.py" | sort -u | wc -l`
to confirm 70 unique call sites. Then migrate in 3 batches.

### Batch A — App lifecycle + config (smallest, ~20 call sites)

**Files**: `src/profiles/app.py`

| Old call                                                              | New call                                                              |
| --------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `logger.info("ProFiles started")`                                     | `events.app_started(logger, version=..., headless=...)`               |
| `logger.info("ProFiles closed")`                                      | `events.app_closed(logger, uptime_s=...)`                             |
| `logger.info("Restarting application...")`                            | `events.app_restarting(logger)`                                       |
| `logger.info("New instance launched via module: %s", cmd)`            | `events.app_launched(logger, command=cmd)`                            |
| `logger.error("Failed to create GUI: %s", exc)`                       | `events.app_gui_failed(logger, error=str(exc))`                       |
| `logger.info("Configuration loaded: %s (release=%s)", path, release)` | `events.config_loaded(logger, path=path, mode=mode, release=release)` |
| `logger.info("Configuration reloaded")`                               | `events.config_reloaded(logger, path=path)`                           |
| `logger.info("Configuration file created: %s", target)`               | `events.config_created(logger, path=target)`                          |
| `logger.error("Failed to reload configuration: %s", exc)`             | `events.config_reload_failed(logger, error=str(exc))`                 |
| `logger.error("Invalid configuration: %s", exc)`                      | `events.config_invalid(logger, error=str(exc))`                       |
| `logger.error("Failed to create config file: %s", exc)`               | `events.config_create_failed(logger, error=str(exc))`                 |

**`uptime_s` computation**: on `ProFiles closed`, compute `time.time() - self._start_time`.
Store `self._start_time = time.time()` at `app_started`.

**Run**: `python3 -m pytest tests/ -v --no-cov -k "app or config" 2>&1 | tail -20`

---

### Batch B — Scanning (~10 call sites)

**Files**: `src/profiles/core/processing/scanner.py`, `src/profiles/gui/main_window.py`

| Old call                                                                                      | New call                                                                                                                             |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `logger.debug("Scan metrics: %s", metrics.to_dict())`                                         | Already migrated in Task 3                                                                                                           |
| `logger.info("Scanned directory: %s \| Extension: %s \| Filter: %r \| Files found: %d", ...)` | `events.scan_complete(logger, directory=..., extension=..., filter_text=..., files=..., recursive=..., duration_ms=..., errors=...)` |
| `logger.warning("Error scanning directory %s: %s", directory, e)`                             | `events.scan_failed(logger, directory=directory, error=str(e))`                                                                      |

The `scan_and_process` function in `scanner.py` is the primary caller. It has `extension`,
`filter_text`, `recursive`, `duration_ms`, `file_count`, `error_count` all available.
Extract them and pass to the helper.

**Run**: `python3 -m pytest tests/core/processing/ tests/gui/ -v --no-cov 2>&1 | tail -20`

---

### Batch C — UI / theme / language / file ops / workflow (~40 call sites)

**Files**: `src/profiles/gui/main_window.py`, `src/profiles/gui/components/`, `src/profiles/core/actions.py`, `src/profiles/core/environment/workflow.py`, `src/profiles/core/environment/render.py`, others.

| Old call                                                  | New call                                                                  |
| --------------------------------------------------------- | ------------------------------------------------------------------------- |
| `logger.info("Theme switched to: %s", theme_name)`        | `events.theme_switched(logger, value=theme_name, warnings=n)`             |
| `logger.info("Language switched to: %s", new_lang)`       | `events.lang_switched(logger, value=new_lang)`                            |
| `logger.warning("WCAG contrast below AA threshold: …")`   | `events.wcag_contrast_faint(...)`                                         |
| `logger.info("Opening configuration file: %s", path)`     | `events.file_open_config(logger, path=path)`                              |
| `logger.info("Opening log file: %s", path)`               | `events.file_open_log(logger, path=path)`                                 |
| `logger.warning("File not found: %s", path)`              | `events.file_not_found(logger, path=path)`                                |
| `logger.warning("Not a file: %s", path)`                  | `events.file_not_a_file(logger, path=path)`                               |
| `logger.error("Failed to launch file: %s", path)`         | `events.file_launch_failed(logger, path=path, error=...)`                 |
| `logger.info("File deleted: %s", path)`                   | `events.file_deleted(logger, path=path)`                                  |
| `logger.error("Failed to delete file: %s", exc)`          | `events.file_delete_failed(logger, path=..., error=str(exc))`             |
| `"USER=%s,PROFILE_VERSION=%s,LAUNCH=%s,ARGS=%s" % (...)`  | `events.file_launched(logger, path=..., version=..., user=..., args=...)` |
| `logger.info("Executing step %d/%d (action: %s)", ...)`   | `events.workflow_step(...)`                                               |
| `logger.warning("Step failed (failmode=…).")`             | `events.workflow_step_failed(...)`                                        |
| `logger.error("Step failed and … Aborting.")`             | `events.workflow_aborted(...)`                                            |
| `logger.error("Error processing file %s: %s", path, exc)` | `events.processing_failed(...)`                                           |
| `logger.warning("Command timed out after %ss: %s", ...)`  | `events.command_timeout(...)`                                             |
| `logger.debug("Command exited with code %d", code)`       | `events.command_exit(...)`                                                |
| `logger.error("Command execution failed: %s", e)`         | `events.command_failed(...)`                                              |

**WCAG warning count**: `main_window.py` currently logs one warning per failing pair.
Keep the per-pair event (so the user can see which pair failed). The count field in
`THEME_SWITCHED` is the count of failing pairs detected at that switch.

**Run**: `python3 -m pytest tests/ -v --no-cov 2>&1 | tail -20`

---

## Phase 3 — Cleanup

1. Delete any legacy `logger.info("Scan metrics: %s", ...)` calls that were missed.
2. Update `docs/operations/log-format.md` with the grammar, event catalogue, and two `grep` examples.
3. Bump the `PROFILE_VERSION` log field to `2026.8.0` in `config.py`.
4. Run full test suite: `python3 -m pytest tests/ --no-cov -q`
5. Commit as `[phase3] log format: all call sites migrated, cleanup`.

---

## Test Command Reference

| Phase     | Command                                                                       |
| --------- | ----------------------------------------------------------------------------- |
| Task 1    | `python3 -m pytest tests/core/telemetry/test_events.py -v --no-cov`           |
| Tasks 1-4 | `python3 -m pytest tests/core/telemetry/ -v --no-cov`                         |
| Batch A   | `python3 -m pytest tests/test_app.py tests/core/config/ -v --no-cov`          |
| Batch B   | `python3 -m pytest tests/core/processing/ -v --no-cov`                        |
| Batch C   | `python3 -m pytest tests/ -v --no-cov 2>&1 \| tail -30`                       |
| Final     | `python3 -m pytest tests/ --no-cov -q && python3 -m ruff check src/profiles/` |

---

## Commit Strategy

| Commit  | Scope                                                               |
| ------- | ------------------------------------------------------------------- |
| Phase 1 | `core/telemetry/events.py` + `test_events.py` + metrics integration |
| Batch A | App lifecycle + config call sites                                   |
| Batch B | Scanning call sites                                                 |
| Batch C | UI / workflow / file ops call sites                                 |
| Phase 3 | Docs + cleanup + version bump                                       |

Each commit: working tests, no lint errors, one logical change.
