"""Structured telemetry events for profiles.log.

Each helper emits one event line in the grammar::

    HOSTNAME: EVENT_NAME key="value" key=value ...

Reference: docs/superpowers/specs/2026-08-29-log-format-and-telemetry-design.md
"""

from __future__ import annotations

import logging

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
    """Emit APP_STARTED."""
    logger.info('APP_STARTED version="%s" headless=%s', version, _bool(headless))


def app_closed(logger: logging.Logger, *, uptime_s: float) -> None:
    """Emit APP_CLOSED."""
    logger.info("APP_CLOSED uptime_s=%.0f", uptime_s)


def app_restarting(logger: logging.Logger) -> None:
    """Emit APP_RESTARTING."""
    logger.info("APP_RESTARTING")


def app_launched(logger: logging.Logger, *, command: str) -> None:
    """Emit APP_LAUNCHED."""
    logger.info('APP_LAUNCHED command="%s"', command)


def app_gui_failed(logger: logging.Logger, *, error: str) -> None:
    """Emit APP_GUI_FAILED."""
    logger.error('APP_GUI_FAILED error="%s"', error)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def config_loaded(logger: logging.Logger, *, path: str, mode: str, release: str) -> None:
    """Emit CONFIG_LOADED."""
    logger.info('CONFIG_LOADED path=%s mode="%s" release="%s"', _quote(path), mode, release)


def config_reloaded(logger: logging.Logger, *, path: str) -> None:
    """Emit CONFIG_RELOADED."""
    logger.info("CONFIG_RELOADED path=%s", _quote(path))


def config_created(logger: logging.Logger, *, path: str) -> None:
    """Emit CONFIG_CREATED."""
    logger.info("CONFIG_CREATED path=%s", _quote(path))


def config_reload_failed(logger: logging.Logger, *, error: str) -> None:
    """Emit CONFIG_RELOAD_FAILED."""
    logger.error('CONFIG_RELOAD_FAILED error="%s"', error)


def config_invalid(logger: logging.Logger, *, error: str) -> None:
    """Emit CONFIG_INVALID."""
    logger.error('CONFIG_INVALID error="%s"', error)


def config_create_failed(logger: logging.Logger, *, error: str) -> None:
    """Emit CONFIG_CREATE_FAILED."""
    logger.error('CONFIG_CREATE_FAILED error="%s"', error)


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
    """Emit SCAN_FAILED."""
    logger.warning('SCAN_FAILED dir=%s error="%s"', _quote(directory), error)


# ---------------------------------------------------------------------------
# UI / Theme / Language
# ---------------------------------------------------------------------------


def theme_switched(logger: logging.Logger, *, value: str, warnings: int = 0) -> None:
    """Emit THEME_SWITCHED."""
    logger.info('THEME_SWITCHED value="%s" warnings=%d', value, warnings)


def lang_switched(logger: logging.Logger, *, value: str) -> None:
    """Emit LANG_SWITCHED."""
    logger.info('LANG_SWITCHED value="%s"', value)


def wcag_contrast_faint(logger: logging.Logger, *, pair: str, ratio: str, fg: str, bg: str) -> None:
    """Emit WCAG_CONTRAST_FAINT."""
    logger.warning('WCAG_CONTRAST_FAINT pair="%s" ratio=%s fg=%s bg=%s', pair, ratio, fg, bg)


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


def file_open_config(logger: logging.Logger, *, path: str) -> None:
    """Emit FILE_OPEN_CONFIG."""
    logger.info("FILE_OPEN_CONFIG path=%s", _quote(path))


def file_open_log(logger: logging.Logger, *, path: str) -> None:
    """Emit FILE_OPEN_LOG."""
    logger.info("FILE_OPEN_LOG path=%s", _quote(path))


def file_not_found(logger: logging.Logger, *, path: str) -> None:
    """Emit FILE_NOT_FOUND."""
    logger.warning("FILE_NOT_FOUND path=%s", _quote(path))


def file_not_a_file(logger: logging.Logger, *, path: str) -> None:
    """Emit FILE_NOT_A_FILE."""
    logger.warning("FILE_NOT_A_FILE path=%s", _quote(path))


def file_launch_failed(logger: logging.Logger, *, path: str, error: str) -> None:
    """Emit FILE_LAUNCH_FAILED."""
    logger.error('FILE_LAUNCH_FAILED path=%s error="%s"', _quote(path), error)


def file_deleted(logger: logging.Logger, *, path: str) -> None:
    """Emit FILE_DELETED."""
    logger.info("FILE_DELETED path=%s", _quote(path))


def file_delete_failed(logger: logging.Logger, *, path: str, error: str) -> None:
    """Emit FILE_DELETE_FAILED."""
    logger.error('FILE_DELETE_FAILED path=%s error="%s"', _quote(path), error)


def file_launched(
    logger: logging.Logger,
    *,
    path: str,
    version: str = "",
    user: str = "",
    args: str = "",
) -> None:
    """Emit FILE_LAUNCHED (merges the old USER=… audit line)."""
    parts = [f"path={_quote(path)}"]
    if version:
        parts.append(f'version="{version}"')
    if user:
        parts.append(f'user="{user}"')
    if args:
        parts.append(f'args="{args}"')
    logger.info("FILE_LAUNCHED %s", " ".join(parts))


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


def workflow_step(
    logger: logging.Logger, *, index: int, total: int, action: str, result: str
) -> None:
    """Emit WORKFLOW_STEP."""
    logger.info(
        'WORKFLOW_STEP index=%d total=%d action="%s" result="%s"',
        index,
        total,
        action,
        result,
    )


def workflow_step_failed(logger: logging.Logger, *, failmode: str, action: str) -> None:
    """Emit WORKFLOW_STEP_FAILED."""
    logger.warning('WORKFLOW_STEP_FAILED failmode="%s" action="%s"', failmode, action)


def workflow_aborted(logger: logging.Logger, *, reason: str) -> None:
    """Emit WORKFLOW_ABORTED."""
    logger.error('WORKFLOW_ABORTED reason="%s"', reason)


def processing_failed(logger: logging.Logger, *, path: str, error: str) -> None:
    """Emit PROCESSING_FAILED."""
    logger.error('PROCESSING_FAILED path=%s error="%s"', _quote(path), error)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def command_timeout(logger: logging.Logger, *, timeout_s: int, command: str) -> None:
    """Emit COMMAND_TIMEOUT."""
    logger.warning('COMMAND_TIMEOUT timeout_s=%d command="%s"', timeout_s, command)


def command_exit(logger: logging.Logger, *, code: int, command: str) -> None:
    """Emit COMMAND_EXIT."""
    logger.debug('COMMAND_EXIT code=%d command="%s"', code, command)


def command_failed(logger: logging.Logger, *, error: str, command: str) -> None:
    """Emit COMMAND_FAILED."""
    logger.error('COMMAND_FAILED error="%s" command="%s"', error, command)


# ---------------------------------------------------------------------------
# Context menu — right-click actions
# ---------------------------------------------------------------------------


def file_revealed(logger: logging.Logger, *, path: str, status: str, error: str = "") -> None:
    """Emit FILE_REVEALED. status is "ok" or "failed"."""
    if error:
        logger.debug(
            'FILE_REVEALED path=%s status="%s" error="%s"',
            _quote(path),
            status,
            error,
        )
    else:
        logger.debug('FILE_REVEALED path=%s status="%s"', _quote(path), status)


def external_opened(
    logger: logging.Logger, *, kind: str, path: str, status: str, reason: str = "", error: str = ""
) -> None:
    """Emit EXTERNAL_OPENED. kind is "folder" or "terminal"."""
    parts = [f'kind="{kind}"', f"path={_quote(path)}", f'status="{status}"']
    if reason:
        parts.append(f'reason="{reason}"')
    if error:
        parts.append(f'error="{error}"')
    logger.debug("EXTERNAL_OPENED %s", " ".join(parts))


def filter_changed(logger: logging.Logger, *, kind: str, value: str) -> None:
    """Emit FILTER_CHANGED. kind is "folder" or "extension"."""
    logger.info('FILTER_CHANGED kind="%s" value=%s', kind, _quote(value))


def filter_rejected(logger: logging.Logger, *, kind: str, reason: str, value: str) -> None:
    """Emit FILTER_REJECTED. reason describes why the filter was not applied."""
    logger.debug(
        'FILTER_REJECTED kind="%s" reason="%s" value=%s',
        kind,
        reason,
        _quote(value),
    )


def hash_computed(
    logger: logging.Logger,
    *,
    algorithm: str,
    path: str,
    status: str,
    duration_ms: float = 0.0,
    reason: str = "",
    error: str = "",
) -> None:
    """Emit HASH_COMPUTED. status is "ok", "failed", or "rejected"."""
    if status == "ok":
        logger.info(
            'HASH_COMPUTED algorithm="%s" path=%s status="ok" duration_ms=%.3f',
            algorithm,
            _quote(path),
            duration_ms,
        )
    elif status == "failed":
        logger.debug(
            'HASH_COMPUTED algorithm="%s" path=%s status="failed" error="%s"',
            algorithm,
            _quote(path),
            error,
        )
    else:  # rejected
        logger.debug(
            'HASH_COMPUTED algorithm="%s" path=%s status="rejected" reason="%s"',
            algorithm,
            _quote(path),
            reason,
        )


def hash_verified(
    logger: logging.Logger,
    *,
    algorithm: str,
    path: str,
    match: bool | None = None,
    status: str = "",
    reason: str = "",
    error: str = "",
) -> None:
    """Emit HASH_VERIFIED. match is True/False for verification outcomes;
    pass status="rejected" or status="failed" with reason/error for pre-checks."""
    if match is True:
        logger.info(
            'HASH_VERIFIED algorithm="%s" path=%s match=true',
            algorithm,
            _quote(path),
        )
    elif match is False:
        logger.warning(
            'HASH_VERIFIED algorithm="%s" path=%s match=false',
            algorithm,
            _quote(path),
        )
    elif status == "failed":
        logger.debug(
            'HASH_VERIFIED algorithm="%s" path=%s status="failed" error="%s"',
            algorithm,
            _quote(path),
            error,
        )
    else:  # rejected
        logger.debug(
            'HASH_VERIFIED algorithm="%s" path=%s status="rejected" reason="%s"',
            algorithm,
            _quote(path),
            reason,
        )
