"""Step-based workflow engine for file launch hooks."""

from __future__ import annotations

import datetime
import logging
import subprocess
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Literal

from profiles.core.config.models import WorkflowStep
from profiles.core.environment.interactions import confirm_dialog_3way
from profiles.core.environment.message_dialog import show_notify_dialog
from profiles.core.telemetry import events


class WorkflowOutcome(Enum):
    """Result of workflow execution."""

    CONTINUE = "continue"  # Proceed to standard OS launch
    SKIP_LAUNCH = "skip_launch"  # Workflow completed, skip OS launch
    ABORT = "abort"  # Workflow aborted by user or error


AskCallback = Callable[[str], Literal["yes", "skip", "no"]]
NotifyCallback = Callable[[str, bool], None]

FailMode = Literal["warn", "abort", "skip"]


def _emit_workflow_step(
    logger: logging.Logger | None,
    *,
    index: int,
    total: int,
    action: str,
    result: str,
) -> None:
    """Emit a WORKFLOW_STEP event when *logger* is available (no-op otherwise)."""
    if logger is not None:
        events.workflow_step(logger, index=index, total=total, action=action, result=result)


def _ask_step_input(
    ask_content: str,
    *,
    user_choice: Literal["yes", "skip", "no"] | None,
    ask_callback: AskCallback | None,
    headless: bool,
) -> Literal["yes", "skip", "no"]:
    """Resolve the user's choice for an ``ask`` guard.

    Priority: explicit *user_choice* (test helper) → *ask_callback* →
    the 3-way dialog (or its headless prompt).
    """
    if user_choice is not None:
        return user_choice
    if ask_callback is not None:
        return ask_callback(ask_content)
    return confirm_dialog_3way(ask_content, headless=headless)


# pylint: disable-next=too-many-arguments
# Public facade mirroring the workflow config surface; kwargs are additive.
def run_workflow(
    steps: list[WorkflowStep],
    file_path: Path | None,
    *,
    headless: bool = False,
    ask_callback: AskCallback | None = None,
    notify_callback: NotifyCallback | None = None,
    user_choice: Literal["yes", "skip", "no"] | None = None,
    timeout: int | None = None,
    failmode: FailMode = "warn",
    username: str | None = None,
    hostname: str | None = None,
    failure_context: list[str] | None = None,
    logger: logging.Logger | None = None,
) -> WorkflowOutcome:
    """Execute a list of workflow steps sequentially.

    Args:
        steps: List of WorkflowStep models to execute.
        file_path: File path being operated on (for variable substitution).
        headless: If True, run without GUI dialogues.
        ask_callback: Custom callback for 'ask' guards (useful for tests/mocking).
        notify_callback: Custom callback for 'notify' steps.
        user_choice: Optional override for 'ask' prompt choice (testing helper).
        timeout: Maximum seconds to wait for each blocking step. None = no limit.
            Overridden by a step's own ``timeout`` field when set.
        failmode: Global failure behavior: `"warn"` (log, continue),
            `"abort"` (stop workflow), `"skip"` (stop workflow, skip OS launch).
        username: Operator username, substituted as `{username}`.
        hostname: Machine hostname, substituted as `{hostname}`.
        failure_context: Optional mutable list appended with a human-readable
            failure description when the workflow aborts due to a step error.
        logger: Optional logger for workflow execution traces.

    Returns:
        WorkflowOutcome indicating whether to proceed to OS launch, skip, or abort.
    """
    if not steps:
        return WorkflowOutcome.CONTINUE

    skip_next = False

    for i, step in enumerate(steps):
        # If previous step was skipped via "skip", skip this step
        if skip_next:
            if logger is not None:
                logger.debug("Skipping step %d (action: %s)", i + 1, step.action)
            skip_next = False
            continue

        _emit_workflow_step(
            logger, index=i + 1, total=len(steps), action=step.action, result="start"
        )

        # Handle 'ask' confirmation guard if present
        if step.ask:
            ask_content = _substitute_variables(
                step.ask,
                file_path,
                action_content=step.content,
                username=username,
                hostname=hostname,
            )
            choice = _ask_step_input(
                ask_content,
                user_choice=user_choice,
                ask_callback=ask_callback,
                headless=headless,
            )

            if choice == "no":
                _emit_workflow_step(
                    logger, index=i + 1, total=len(steps), action=step.action, result="aborted"
                )
                return WorkflowOutcome.ABORT
            if choice == "skip":
                _emit_workflow_step(
                    logger,
                    index=i + 1,
                    total=len(steps),
                    action=step.action,
                    result="skipped-user",
                )
                # If skipping the last step, return SKIP_LAUNCH
                if i == len(steps) - 1:
                    return WorkflowOutcome.SKIP_LAUNCH
                skip_next = True
                continue

        # Evaluate conditional guard
        if not step.evaluate_condition():
            _emit_workflow_step(
                logger,
                index=i + 1,
                total=len(steps),
                action=step.action,
                result="skipped-condition",
            )
            continue

        # Resolve effective timeout: per-step overrides global
        effective_timeout = step.timeout if step.timeout is not None else timeout

        # Execute the action for this step
        outcome = _execute_step(
            step,
            file_path,
            headless=headless,
            notify_callback=notify_callback,
            timeout=effective_timeout,
            failmode=failmode,
            username=username,
            hostname=hostname,
            failure_context=failure_context,
            logger=logger,
        )
        if outcome is not None:
            return outcome

    return WorkflowOutcome.CONTINUE


def _resolve_failure(
    on_failure: Literal["stop", "warn", "continue"],
    failmode: FailMode,
    *,
    step_content: str | None = None,
    failure_context: list[str] | None = None,
    logger: logging.Logger | None = None,
) -> WorkflowOutcome | None:
    """Resolve a step failure: per-step ``on_failure`` then global ``failmode``.

    Returns a terminal WorkflowOutcome or None to continue.

    Resolution order:
        1. ``on_failure == "stop"`` → ABORT (independent of failmode).
        2. ``on_failure == "warn"`` → log warning, continue.
        3. ``on_failure == "continue"`` → silent, continue.
        4. Otherwise fall back to global ``failmode`` (``"warn"``/``"abort"``/``"skip"``).
    """
    if on_failure == "stop":
        if logger is not None:
            events.workflow_aborted(logger, reason=f"on_failure=stop: {step_content}")
        if failure_context is not None and step_content is not None:
            failure_context.append(f"Step failed (on_failure=stop): {step_content}")
        return WorkflowOutcome.ABORT
    if on_failure == "warn":
        if logger is not None:
            events.workflow_step_failed(
                logger, failmode="on_failure=warn", action=step_content or ""
            )
        return None
    if on_failure == "continue":
        return None
    # Unknown on_failure → fall back to global failmode
    if failmode == "abort":
        if logger is not None:
            events.workflow_aborted(logger, reason=f"failmode=abort: {step_content}")
        if failure_context is not None and step_content is not None:
            failure_context.append(f"Step failed (failmode=abort): {step_content}")
        return WorkflowOutcome.ABORT
    if failmode == "skip":
        if logger is not None:
            events.workflow_step_failed(logger, failmode="failmode=skip", action=step_content or "")
        return WorkflowOutcome.SKIP_LAUNCH
    # failmode == "warn" (default)
    if logger is not None:
        events.workflow_step_failed(logger, failmode="failmode=warn", action=step_content or "")
    return None


# Internal context fan-out: failmode/username/hostname/logger all step-scoped.
# pylint: disable=too-many-arguments
def _execute_step(
    step: WorkflowStep,
    file_path: Path | None,
    *,
    headless: bool = False,
    notify_callback: NotifyCallback | None = None,
    timeout: int | None = None,
    failmode: FailMode = "warn",
    username: str | None = None,
    hostname: str | None = None,
    failure_context: list[str] | None = None,
    logger: logging.Logger | None = None,
) -> WorkflowOutcome | None:
    """Execute a single step. Returns terminal WorkflowOutcome or None to continue."""
    content = _substitute_variables(step.content, file_path, username=username, hostname=hostname)

    if step.action == "notify":
        if notify_callback is not None:
            notify_callback(content, step.wait)
        else:
            show_notify_dialog(content, blocking=step.wait, headless=headless)
            if logger is not None:
                logger.debug("Displayed notify dialog (headless=%s): %s", headless, content)
        return None

    if step.action == "replace":
        _emit_workflow_step(logger, index=0, total=1, action="replace", result=content)
        # Launch replace command instead of OS default file launch
        success = _run_command(content, wait=step.wait, timeout=timeout, logger=logger)
        if logger is not None:
            logger.debug("Replace command success: %s", success)
        return WorkflowOutcome.SKIP_LAUNCH

    if step.action in ("run", "check"):
        _emit_workflow_step(logger, index=0, total=1, action=step.action, result=content)
        # "run" honors the step's wait flag; "check" always blocks.
        success = _run_command(
            content,
            wait=step.wait if step.action == "run" else True,
            timeout=timeout,
            logger=logger,
        )
        if not success:
            return _resolve_failure(
                step.on_failure,
                failmode,
                step_content=content,
                failure_context=failure_context,
                logger=logger,
            )
        return None

    if step.action == "run_after":
        _emit_workflow_step(logger, index=0, total=1, action="run_after", result=content)
        _run_command(content, wait=False, timeout=None, logger=logger)

    return None


def _substitute_variables(
    template: str,
    file_path: Path | None,
    *,
    action_content: str | None = None,
    username: str | None = None,
    hostname: str | None = None,
) -> str:
    """Substitute variables in step content string (supporting both {{token}} and {token})."""
    res = template
    tokens = {
        "content": action_content,
        "username": username,
        "hostname": hostname,
        "date": datetime.date.today().isoformat(),
        "path": str(file_path) if file_path else None,
        "filename": file_path.name if file_path else None,
        "dir": str(file_path.parent) if file_path else None,
        "stem": file_path.stem if file_path else None,
        "ext": file_path.suffix if file_path else None,
    }

    for key, val in tokens.items():
        if val is not None:
            res = res.replace("{{" + key + "}}", val)
            res = res.replace("{" + key + "}", val)

    return res


def _run_command(
    command: str, wait: bool, *, timeout: int | None = None, logger: logging.Logger | None = None
) -> bool:
    """Run shell command."""
    try:
        if wait:
            res = subprocess.run(command, shell=True, check=False, timeout=timeout)
            if logger is not None:
                events.command_exit(logger, code=res.returncode, command=command)
            return res.returncode == 0
        else:
            # Fire-and-forget spawn: Popen must outlive this call.
            # pylint: disable-next=consider-using-with
            subprocess.Popen(command, shell=True)
            if logger is not None:
                logger.debug("Command spawned in background")
            return True
    except subprocess.TimeoutExpired:
        if logger is not None:
            events.command_timeout(
                logger, timeout_s=timeout if timeout is not None else 0, command=command
            )
        return False
    except Exception as e:
        if logger is not None:
            events.command_failed(logger, error=str(e), command=command)
        return False


__all__ = ["WorkflowOutcome", "run_workflow", "FailMode"]
