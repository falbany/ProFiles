"""Domain actions — file launch, config open, log open.

These are the pure-domain equivalents of the GUI event handlers.  Each
function returns a small ``ActionResult`` so the front-end can decide
how to surface failures (messagebox in the GUI, stderr in the CLI).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from profiles.core.config.models import AppConfig
from profiles.core.config.template import STARTER_CONFIG_TEMPLATE
from profiles.core.environment.matcher import select_most_specific_pattern
from profiles.core.environment.workflow import WorkflowOutcome, run_workflow
from profiles.core.processing.file_classifier import ensure_trailing_separator
from profiles.utils.file_utils import launch_file, launch_file_with_args, open_with_default_app


class ActionStatus(Enum):
    """Outcome of a domain action."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    FAILED = "failed"


@dataclass(frozen=True)
class ActionResult:
    """Outcome of a domain action with a human-readable message."""

    status: ActionStatus
    message: str
    path: Path | None = None


def open_config_file(
    config_path: Path,
    *,
    logger: logging.Logger | None = None,
) -> ActionResult:
    """Open the configuration file with the OS default association.

    Args:
        config_path: Path to the configuration file.
        logger: Optional logger to record the attempt.

    Returns:
        ``ActionResult`` describing the outcome.
    """
    if not config_path.exists():
        return ActionResult(
            status=ActionStatus.NOT_FOUND,
            message=f"The configuration file does not exist:\n{config_path}",
            path=config_path,
        )

    if logger is not None:
        logger.info("Opening configuration file: %s", config_path)

    if open_with_default_app(config_path):
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message="Configuration file opened.",
            path=config_path,
        )

    return ActionResult(
        status=ActionStatus.FAILED,
        message=f"Could not open configuration file:\n{config_path}",
        path=config_path,
    )


def open_log_file(
    log_path: Path,
    *,
    logger: logging.Logger | None = None,
) -> ActionResult:
    """Open the log file with the OS default association.

    If the file is missing, it is created on demand (parent directory
    included).  This mirrors the GUI behavior so the user can always
    inspect the log.

    Args:
        log_path: Path to the log file.
        logger: Optional logger to record the attempt.

    Returns:
        ``ActionResult`` describing the outcome.
    """
    if not log_path.exists():
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.touch(exist_ok=True)
        except OSError as exc:
            return ActionResult(
                status=ActionStatus.NOT_FOUND,
                message=f"The log file does not exist:\n{log_path} ({exc})",
                path=log_path,
            )

    if logger is not None:
        logger.info("Opening log file: %s", log_path)

    if open_with_default_app(log_path):
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message="Log file opened.",
            path=log_path,
        )

    return ActionResult(
        status=ActionStatus.FAILED,
        message=f"Could not open log file:\n{log_path}",
        path=log_path,
    )


# Re-export for backward compatibility — callers (and tests) that reference
# ``profiles.core.actions._launch_with_args`` still work.
_launch_with_args = launch_file_with_args


def launch_selected_file(
    directory: str,
    filename: str,
    release: str,
    username: str,
    *,
    args: str = "",
    logger: logging.Logger | None = None,
    config: AppConfig | None = None,
) -> ActionResult:
    """Launch the file at ``directory / filename`` via the OS association.

    Args:
        directory: Root directory (may be missing trailing separator).
        filename: File path relative to *directory*.
        release: ProFiles release string (logged on success).
        username: Operator name (logged on success).
        args: Optional whitespace-separated arguments forwarded to the
            OS-launcher.  Only used when non-empty; falls back to the
            plain ``launch_file`` path otherwise.
        logger: Optional logger to record the attempt.
        config: Optional loaded :class:`AppConfig`; when provided the
            per-extension hook pipeline is executed before the OS launch.
            When *config* is provided, hooks run before the OS launch and
            their outcome may short-circuit the launch (ABORT → FAILED,
            SKIP → SUCCESS with the ``instead`` hook having handled the
            file, CONTINUE → proceed to the OS launch as normal).

    Returns:
        ``ActionResult`` describing the outcome.
    """
    normalized = ensure_trailing_separator(directory)
    file_path = Path(normalized) / filename

    if not file_path.exists():
        if logger is not None:
            logger.warning("File not found: %s", file_path)
        return ActionResult(
            status=ActionStatus.NOT_FOUND,
            message=f"The selected file does not exist:\n{file_path}",
            path=file_path,
        )

    if config is not None:
        patterns = list(config.launch_hooks.keys())
        selected_pattern = select_most_specific_pattern(patterns, filename)

        if selected_pattern and selected_pattern in config.launch_hooks:
            steps = list(config.launch_hooks[selected_pattern])
            workflow_outcome = run_workflow(steps, file_path, logger=logger)

            if workflow_outcome == WorkflowOutcome.ABORT:
                if logger is not None:
                    logger.error("Launch aborted by a launch hook: %s", file_path)
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message=f"Launch aborted by a launch hook.\n\nFile: {file_path}",
                    path=file_path,
                )
            if workflow_outcome == WorkflowOutcome.SKIP_LAUNCH:
                if logger is not None:
                    logger.info(
                        "Launched %s (OS launch replaced/skipped by workflow step)",
                        file_path,
                    )
                return ActionResult(
                    status=ActionStatus.SUCCESS,
                    message=f"Launched {file_path} (OS launch handled by workflow)",
                    path=file_path,
                )

    launched = _launch_with_args(file_path, args) if args else launch_file(file_path)

    if not launched:
        if logger is not None:
            logger.error("Failed to launch file: %s", file_path)
        return ActionResult(
            status=ActionStatus.FAILED,
            message=(
                f"Failed to open the file:\n{file_path}\n\n"
                "Please check the file path and associations."
            ),
            path=file_path,
        )

    if logger is not None:
        logger.info(
            "USER=%s,PROFILE_VERSION=%s,LAUNCH=%s,ARGS=%s",
            username,
            release,
            file_path,
            args or "-",
        )
    return ActionResult(
        status=ActionStatus.SUCCESS,
        message=f"Launched {file_path}",
        path=file_path,
    )


def write_starter_config(
    path: Path,
    *,
    logger: logging.Logger | None = None,
) -> ActionResult:
    """Write the documented starter ``.profiles`` to *path*.

    The parent directory must already exist. The template embeds
    ``str(Path.cwd())`` as the default ``search_dir`` so the GUI's
    Directory field always has a usable fallback.

    Args:
        path: Target path for the new ``.profiles`` file.
        logger: Optional logger used to record the write.

    Returns:
        ``ActionResult`` describing the outcome.
    """
    target = Path(path)
    body = STARTER_CONFIG_TEMPLATE.format(cwd=str(Path.cwd()))

    try:
        target.write_text(body, encoding="utf-8")
    except OSError as exc:
        if logger is not None:
            logger.error("Failed to write starter config %s: %s", target, exc)
        return ActionResult(
            status=ActionStatus.FAILED,
            message=f"Could not write starter configuration:\n{target} ({exc})",
            path=target,
        )

    if logger is not None:
        logger.info("Wrote starter configuration: %s", target)
    return ActionResult(
        status=ActionStatus.SUCCESS,
        message=f"Starter configuration written:\n{target}",
        path=target,
    )


def clear_file(
    file_path: Path,
    *,
    logger: logging.Logger | None = None,
) -> ActionResult:
    """Delete the given file from the filesystem.

    Args:
        file_path: Path to the file to delete.
        logger: Optional logger to record the attempt.

    Returns:
        ``ActionResult`` describing the outcome.
    """
    if not file_path.exists():
        if logger is not None:
            logger.warning("File not found: %s", file_path)
        return ActionResult(
            status=ActionStatus.NOT_FOUND,
            message=f"The file does not exist:\n{file_path}",
            path=file_path,
        )

    if not file_path.is_file():
        if logger is not None:
            logger.warning("Not a file: %s", file_path)
        return ActionResult(
            status=ActionStatus.FAILED,
            message=f"Not a file:\n{file_path}",
            path=file_path,
        )

    try:
        file_path.unlink()
    except OSError as exc:
        if logger is not None:
            logger.error("Failed to delete file %s: %s", file_path, exc)
        return ActionResult(
            status=ActionStatus.FAILED,
            message=f"Failed to delete file:\n{file_path}\n\n{exc}",
            path=file_path,
        )

    if logger is not None:
        logger.info("File deleted: %s", file_path)
    return ActionResult(
        status=ActionStatus.SUCCESS,
        message=f"File deleted:\n{file_path}",
        path=file_path,
    )
