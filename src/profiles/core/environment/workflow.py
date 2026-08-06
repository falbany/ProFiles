"""Step-based workflow engine for file launch hooks."""

from __future__ import annotations

import subprocess
from enum import Enum
from pathlib import Path
from typing import Callable, Literal

from profiles.core.config.models import WorkflowStep
from profiles.core.environment.interactions import confirm_dialog_3way
from profiles.core.environment.render import render_text

class WorkflowOutcome(Enum):
    """Result of workflow execution."""
    CONTINUE = "continue"        # Proceed to standard OS launch
    SKIP_LAUNCH = "skip_launch"  # Workflow completed, skip OS launch
    ABORT = "abort"              # Workflow aborted by user or error

AskCallback = Callable[[str], Literal["yes", "skip", "no"]]
NotifyCallback = Callable[[str, bool], None]

def run_workflow(
    steps: list[WorkflowStep],
    file_path: Path | None,
    *,
    headless: bool = False,
    ask_callback: AskCallback | None = None,
    notify_callback: NotifyCallback | None = None,
    user_choice: Literal["yes", "skip", "no"] | None = None,
) -> WorkflowOutcome:
    """Execute a list of workflow steps sequentially.

    Args:
        steps: List of WorkflowStep models to execute.
        file_path: File path being operated on (for variable substitution).
        headless: If True, run without GUI dialogues.
        ask_callback: Custom callback for 'ask' guards (useful for tests/mocking).
        notify_callback: Custom callback for 'notify' steps.
        user_choice: Optional override for 'ask' prompt choice (testing helper).

    Returns:
        WorkflowOutcome indicating whether to proceed to OS launch, skip, or abort.
    """
    if not steps:
        return WorkflowOutcome.CONTINUE

    skip_next = False

    for i, step in enumerate(steps):
        # If previous step was skipped via "skip", skip this step
        if skip_next:
            skip_next = False
            continue

        # Handle 'ask' confirmation guard if present
        if step.ask:
            choice: Literal["yes", "skip", "no"]
            if user_choice is not None:
                choice = user_choice
            elif ask_callback is not None:
                choice = ask_callback(step.ask)
            else:
                choice = confirm_dialog_3way(step.ask, headless=headless)

            if choice == "no":
                return WorkflowOutcome.ABORT
            if choice == "skip":
                # If skipping the last step, return SKIP_LAUNCH
                if i == len(steps) - 1:
                    return WorkflowOutcome.SKIP_LAUNCH
                skip_next = True
                continue

        # Execute the action for this step
        outcome = _execute_step(step, file_path, headless=headless, notify_callback=notify_callback)
        if outcome is not None:
            return outcome

    return WorkflowOutcome.CONTINUE

def _execute_step(
    step: WorkflowStep,
    file_path: Path | None,
    *,
    headless: bool = False,
    notify_callback: NotifyCallback | None = None,
) -> WorkflowOutcome | None:
    """Execute a single step. Returns terminal WorkflowOutcome or None to continue."""
    content = _substitute_variables(step.content, file_path)

    if step.action == "notify":
        if notify_callback is not None:
            notify_callback(content, step.wait)
        else:
            rendered = render_text(content, headless=headless)
            if isinstance(rendered, str):
                print(rendered)

        return None

    if step.action == "replace":
        # Launch replace command instead of OS default file launch
        _run_command(content, wait=step.wait)
        return WorkflowOutcome.SKIP_LAUNCH

    if step.action == "run":
        success = _run_command(content, wait=step.wait)
        if not success and step.on_failure == "stop":
            return WorkflowOutcome.ABORT
        return None

    if step.action == "run_after":
        _run_command(content, wait=False)
        return None

    if step.action == "check":
        success = _run_command(content, wait=True)
        if not success:
            if step.on_failure == "stop":
                return WorkflowOutcome.ABORT
        return None

    return None

def _substitute_variables(template: str, file_path: Path | None) -> str:
    """Substitute variables in step content string."""
    if not file_path:
        return template

    res = template.replace("{path}", str(file_path))
    res = res.replace("{filename}", file_path.name)
    res = res.replace("{dir}", str(file_path.parent))
    res = res.replace("{stem}", file_path.stem)
    res = res.replace("{ext}", file_path.suffix)
    return res

def _run_command(command: str, wait: bool) -> bool:
    """Run shell command."""
    try:
        if wait:
            res = subprocess.run(command, shell=True, check=False)
            return res.returncode == 0
        else:
            subprocess.Popen(command, shell=True)
            return True
    except Exception:
        return False

__all__ = ["WorkflowOutcome", "run_workflow"]
