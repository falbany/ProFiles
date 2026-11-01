"""Step-based workflow engine for file launch hooks."""

from __future__ import annotations

import datetime
import locale
import logging
import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from profiles.core.config.conditions import evaluate_hook_condition
from profiles.core.config.models import WorkflowStep
from profiles.core.environment.interactions import confirm_dialog_3way
from profiles.core.environment.message_dialog import show_notify_dialog
from profiles.core.telemetry import events


class WorkflowOutcome(Enum):
    """Result of workflow execution."""

    CONTINUE = "continue"  # Proceed to standard OS launch
    SKIP_LAUNCH = "skip_launch"  # Workflow completed, skip OS launch
    ABORT = "abort"  # Workflow aborted by user or error


AskCallback = Callable[[str, str | None], Literal["yes", "skip", "no"]]
NotifyCallback = Callable[[str, bool], None]

FailMode = Literal["warn", "abort", "skip"]


# Bound for the *combined* stdout+stderr text kept per blocking command step.
# Diagnostics live at the end of output, so the tail is kept, not the head.
_OUTPUT_CAPTURE_LIMIT = 4096
_OUTPUT_TRUNCATION_MARKER = "…"


@dataclass(frozen=True)
class CommandResult:
    """Typed result of an internal command run.

    Attributes:
        code: Shell return code (0 = success). Detached spawns report 0;
            timeouts and spawn errors report -1.
        output: Combined stdout + stderr, decoded with the locale-preferred
            encoding (``errors="replace"``) and tail-bounded to
            ``_OUTPUT_CAPTURE_LIMIT`` characters. Empty for detached spawns.
    """

    code: int
    output: str = ""

    @property
    def success(self) -> bool:
        """Whether the command exited with code 0."""
        return self.code == 0


@dataclass
class _WorkflowState:
    """Mutable state threaded across the steps of one workflow run."""

    last_output: str = ""


def _emit_workflow_step(
    logger: logging.Logger | None,
    *,
    index: int,
    total: int,
    action: str,
    result: str,
    phase: str = "pre",
) -> None:
    """Emit a WORKFLOW_STEP event when *logger* is available (no-op otherwise)."""
    if logger is not None:
        events.workflow_step(
            logger, index=index, total=total, action=action, result=result, phase=phase
        )


def _ask_step_input(
    ask_content: str,
    *,
    pre_message: str | None,
    user_choice: Literal["yes", "skip", "no"] | None,
    ask_callback: AskCallback | None,
    headless: bool,
) -> Literal["yes", "skip", "no"]:
    """Resolve the user's choice for an ``ask`` guard.

    Priority: explicit *user_choice* (test helper) → *ask_callback* →
    the 3-way dialog (or its headless prompt). *pre_message* is the
    step's rendered ``message`` shown above the question when present.
    """
    if user_choice is not None:
        return user_choice
    if ask_callback is not None:
        return ask_callback(ask_content, pre_message)
    return confirm_dialog_3way(ask_content, headless=headless, pre_message=pre_message)


def _resolve_ask_choice(
    step: WorkflowStep,
    file_path: Path | None,
    *,
    username: str | None,
    hostname: str | None,
    last_output: str = "",
    user_choice: Literal["yes", "skip", "no"] | None,
    ask_callback: AskCallback | None,
    headless: bool,
) -> Literal["yes", "skip", "no"] | None:
    """Resolve a step's ``ask`` guard choice; None when the step has no guard.

    Priority mirrors :func:`_ask_step_input`: explicit *user_choice* →
    *ask_callback* → 3-way dialog (or headless prompt). The step's
    message/question are token-substituted first (including ``{{output}}``).
    """
    if not step.ask:
        return None
    command_sub, message_sub = _resolve_step_texts(
        step, file_path, username=username, hostname=hostname, last_output=last_output
    )
    return _ask_step_input(
        _substitute_variables(
            step.ask,
            file_path,
            command=command_sub,
            message=message_sub,
            username=username,
            hostname=hostname,
            output=last_output,
        ),
        pre_message=message_sub if step.message else None,
        user_choice=user_choice,
        ask_callback=ask_callback,
        headless=headless,
    )


def filter_steps_by_phase(
    steps: list[WorkflowStep], phase: Literal["pre", "post"]
) -> list[WorkflowStep]:
    """Return the steps of *steps* whose ``phase`` equals *phase*.

    Steps configured before the ``phase`` key existed default to ``pre``,
    so legacy configurations land entirely in the pre bucket.
    """
    return [step for step in steps if step.phase == phase]


def evaluate_step_condition(
    step: WorkflowStep,
    file_path: Path | None,
    *,
    username: str | None = None,
    hostname: str | None = None,
    output: str = "",
) -> bool:
    """Evaluate a step's ``if`` condition with tokens substituted first.

    The condition string goes through the same :func:`_substitute_variables`
    pipeline as ``message``/``ask`` (verbatim values, no shell quoting), so
    ``file:{{dir}}\\.marker`` or ``env:SITE={{hostname}}`` resolve to literal
    text before the grammar in
    :func:`profiles.core.config.conditions.evaluate_hook_condition` runs.
    """
    if not step.if_:
        return True
    condition = _substitute_variables(
        step.if_,
        file_path,
        username=username,
        hostname=hostname,
        output=output,
    )
    return evaluate_hook_condition(condition)


# Public facade mirroring the workflow config surface; kwargs are additive.
# pylint: disable-next=too-many-arguments
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
    phase: Literal["pre", "post"] = "pre",
) -> WorkflowOutcome:
    """Execute a list of workflow steps sequentially.

    Args:
        steps: List of WorkflowStep models to execute.
        file_path: File path being operated on (for variable substitution).
        headless: If True, run without GUI dialogues.
        ask_callback: Custom callback for 'ask' guards (useful for tests/mocking).
            Called with ``(ask_text, pre_message)`` where *pre_message* is the
            step's rendered ``message`` (None when unset).
        notify_callback: Custom callback for 'notify' steps and non-blocking
            notices from command steps.
        user_choice: Optional override for 'ask' prompt choice (testing helper).
        timeout: Maximum seconds to wait for each blocking step. None = no limit.
            Overridden by a step's own ``timeout`` field when set.
        failmode: Global failure behavior: `"warn"` (log, continue),
            `"abort"` (stop workflow), `"skip"` (stop workflow, skip OS launch).
        username: Operator username, substituted as `{username}`.
        hostname: Machine hostname, substituted as `{hostname}`.
        failure_context: Optional mutable list appended with a human-readable
            failure description when the workflow aborts due to a step error.
            Descriptions include the exit code, and the captured command
            output when the failing step sets ``output: show``/``fail_only``.
        logger: Optional logger for workflow execution traces.
        phase: Execution phase of this pass (`"pre"` before the OS launch,
            `"post"` after a successful launch) — telemetry wording only;
            pass the steps already filtered by :func:`filter_steps_by_phase`.

    Returns:
        WorkflowOutcome indicating whether to proceed to OS launch, skip, or abort.
    """
    if not steps:
        return WorkflowOutcome.CONTINUE

    state = _WorkflowState()

    for i, step in enumerate(steps):
        _emit_workflow_step(
            logger,
            index=i + 1,
            total=len(steps),
            action=step.action,
            result="start",
            phase=phase,
        )

        # Handle 'ask' confirmation guard if present
        choice = _resolve_ask_choice(
            step,
            file_path,
            username=username,
            hostname=hostname,
            last_output=state.last_output,
            user_choice=user_choice,
            ask_callback=ask_callback,
            headless=headless,
        )
        if choice is not None:
            if choice == "no":
                _emit_workflow_step(
                    logger,
                    index=i + 1,
                    total=len(steps),
                    action=step.action,
                    result="aborted",
                    phase=phase,
                )
                return WorkflowOutcome.ABORT
            if choice == "skip":
                _emit_workflow_step(
                    logger,
                    index=i + 1,
                    total=len(steps),
                    action=step.action,
                    result="skipped-user",
                    phase=phase,
                )
                # If skipping the last step, end without OS launch
                if i == len(steps) - 1:
                    return WorkflowOutcome.SKIP_LAUNCH
                continue

        # Evaluate conditional guard (tokens substituted before evaluation)
        if not evaluate_step_condition(
            step,
            file_path,
            username=username,
            hostname=hostname,
            output=state.last_output,
        ):
            _emit_workflow_step(
                logger,
                index=i + 1,
                total=len(steps),
                action=step.action,
                result="skipped-condition",
                phase=phase,
            )
            continue

        # Resolve effective timeout: per-step overrides global
        effective_timeout = step.timeout if step.timeout is not None else timeout

        # Execute the action for this step. When an ``ask`` guard already
        # displayed the step's message in the composed dialog, do not show
        # it again as a notice.
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
            show_notice=not bool(step.ask and step.message),
            # Resolved through the dialog or an ask_callback: the message
            # was displayed. An explicit *user_choice* bypasses display
            # entirely, so the notify step still shows its message.
            ask_displayed=choice is not None and user_choice is None,
            state=state,
        )
        if outcome is not None:
            return outcome

    return WorkflowOutcome.CONTINUE


def _failure_description(
    step_command: str,
    *,
    rc: int | None = None,
    captured_output: str | None = None,
) -> str:
    """Build the human-readable failure text for a failing command step.

    The exit code is always included when known; the trailing ``Last
    output:`` block is appended only when the caller passes captured
    output (``output: show`` / ``fail_only`` steps).
    """
    if rc is not None:
        text = f"Step failed (rc={rc}): {step_command}"
    else:
        text = f"Step failed: {step_command}"
    if captured_output:
        indented = "\n  ".join(captured_output.splitlines())
        text = f"{text}\nLast output:\n  {indented}"
    return text


# pylint: disable-next=too-many-arguments
def _resolve_failure(
    on_failure: Literal["stop", "warn", "continue"],
    failmode: FailMode,
    *,
    step_command: str | None = None,
    failure_context: list[str] | None = None,
    logger: logging.Logger | None = None,
    rc: int | None = None,
    captured_output: str | None = None,
) -> WorkflowOutcome | None:
    """Resolve a step failure: per-step ``on_failure`` then global ``failmode``.

    Returns a terminal WorkflowOutcome or None to continue.

    Resolution order:
        1. ``on_failure == "stop"`` → ABORT (independent of failmode).
        2. ``on_failure == "warn"`` → log warning, continue.
        3. ``on_failure == "continue"`` → silent, continue.
        4. Otherwise fall back to global ``failmode`` (``"warn"``/``"abort"``/``"skip"``).

    When *rc* is known the failure descriptions include the exit code, and
    *captured_output* (when given) is appended as a ``Last output:`` block.
    """
    if on_failure == "stop":
        if logger is not None:
            events.workflow_aborted(logger, reason=f"on_failure=stop: {step_command}")
        if failure_context is not None and step_command is not None:
            failure_context.append(
                _failure_description(step_command, rc=rc, captured_output=captured_output)
            )
        return WorkflowOutcome.ABORT
    if on_failure == "warn":
        if logger is not None:
            events.workflow_step_failed(
                logger, failmode="on_failure=warn", action=step_command or ""
            )
        return None
    if on_failure == "continue":
        return None
    # Unknown on_failure → fall back to global failmode
    if failmode == "abort":
        if logger is not None:
            events.workflow_aborted(logger, reason=f"failmode=abort: {step_command}")
        if failure_context is not None and step_command is not None:
            failure_context.append(
                _failure_description(step_command, rc=rc, captured_output=captured_output)
            )
        return WorkflowOutcome.ABORT
    if failmode == "skip":
        if logger is not None:
            events.workflow_step_failed(logger, failmode="failmode=skip", action=step_command or "")
        return WorkflowOutcome.SKIP_LAUNCH
    # failmode == "warn" (default)
    if logger is not None:
        events.workflow_step_failed(logger, failmode="failmode=warn", action=step_command or "")
    return None


def _show_step_notice(
    message: str,
    *,
    notify_callback: NotifyCallback | None,
    headless: bool,
) -> None:
    """Show a command step's ``message`` as a non-blocking notice."""
    if notify_callback is not None:
        notify_callback(message, False)
    else:
        show_notify_dialog(message, blocking=False, headless=headless)


def _show_captured_output(
    captured_output: str,
    *,
    notify_callback: NotifyCallback | None,
    headless: bool,
) -> None:
    """Show a blocking command's captured output as a non-blocking notice."""
    if captured_output:
        _show_step_notice(captured_output, notify_callback=notify_callback, headless=headless)


def _warn_ignored_output(step: WorkflowStep, reason: str, logger: logging.Logger | None) -> None:
    """Debug-log that ``output:`` is ignored on a non-blocking step."""
    if step.output != "hide" and logger is not None:
        logger.debug("'output' is ignored on a non-blocking step: %s", reason)


# Internal context fan-out: failmode/username/hostname/logger all step-scoped.
# pylint: disable=too-many-arguments
def _run_action_command(
    step: WorkflowStep,
    command: str,
    *,
    blocking: bool,
    timeout: int | None,
    failmode: FailMode,
    failure_context: list[str] | None,
    notify_callback: NotifyCallback | None,
    headless: bool,
    logger: logging.Logger | None,
    state: _WorkflowState | None,
) -> WorkflowOutcome | None:
    """Execute a ``run`` / ``check`` step command and resolve its aftermath.

    Applies the capture rules: the combined output is always tracked in
    *state*; ``output: show`` displays it on success, ``show``/``fail_only``
    display a rc + output failure notice on failure. Failure resolution
    delegates to :func:`_resolve_failure`.
    """
    if not blocking:
        _warn_ignored_output(step, f"{step.action} (wait is false)", logger)
    result = _run_command(
        command,
        wait=blocking,
        timeout=timeout,
        logger=logger,
    )
    if state is not None:
        state.last_output = result.output
    if result.success:
        if step.output == "show":
            _show_captured_output(result.output, notify_callback=notify_callback, headless=headless)
        return None
    # Failure: show captured output when the step asks for it (show /
    # fail_only), regardless of how the failure resolves.
    show_captured = step.output in ("show", "fail_only")
    if show_captured:
        _show_step_notice(
            _failure_description(command, rc=result.code, captured_output=result.output),
            notify_callback=notify_callback,
            headless=headless,
        )
    return _resolve_failure(
        step.on_failure,
        failmode,
        step_command=command,
        failure_context=failure_context,
        logger=logger,
        rc=result.code,
        captured_output=result.output if show_captured else None,
    )


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
    show_notice: bool = True,
    ask_displayed: bool = False,
    state: _WorkflowState | None = None,
) -> WorkflowOutcome | None:
    """Execute a single step. Returns terminal WorkflowOutcome or None to continue.

    Args:
        step: The step to execute.
        file_path: File path for token substitution.
        headless: If True, run without GUI dialogues.
        notify_callback: Custom callback for notify steps and notices.
        timeout: Maximum seconds to wait for the command (None = no limit).
        failmode: Global failure behavior when ``on_failure`` is unknown.
        username: Operator username, substituted as ``{username}``.
        hostname: Machine hostname, substituted as ``{hostname}``.
        failure_context: Optional list appended with failure descriptions.
        logger: Optional logger for workflow execution traces.
        show_notice: Whether to surface the step's ``message`` as a
            non-blocking notice before executing the command. Callers that
            already displayed it (e.g. in the composed ask dialog or via a
            web session) pass False to avoid showing it twice.
        ask_displayed: Whether the step's ``ask`` guard was just resolved
            through a channel that displayed the step's message (the 3-way
            dialog or an *ask_callback*). On ``notify`` steps the composed
            ask dialog **is** the notification display, so the dialog is
            not shown a second time (no second blocking gate).
        state: Optional workflow state receiving the captured output of
            blocking command steps (fed back as the ``{{output}}`` token).
    """
    last_output = state.last_output if state is not None else ""
    command, message = _resolve_step_texts(
        step, file_path, username=username, hostname=hostname, last_output=last_output
    )

    if step.action == "notify":
        if step.command and logger is not None:
            logger.debug(
                "'command' is ignored on a 'notify' step: %s",
                step.command,
            )
        if ask_displayed:
            # The composed ask dialog already displayed this notification
            # (message rendered above the question); answering Yes completed
            # the interaction — do not gate the user a second time.
            if logger is not None:
                logger.debug("Notify already displayed by its ask dialog: %s", message)
            return None
        if notify_callback is not None:
            notify_callback(message, step.wait)
        else:
            show_notify_dialog(message, blocking=step.wait, headless=headless)
            if logger is not None:
                logger.debug("Displayed notify dialog (headless=%s): %s", headless, message)
        return None

    if show_notice and message:
        _show_step_notice(message, notify_callback=notify_callback, headless=headless)

    if step.action == "replace":
        _emit_workflow_step(logger, index=0, total=1, action="replace", result=command)
        # Launch replace command instead of OS default file launch
        result = _run_command(command, wait=step.wait, timeout=timeout, logger=logger)
        if state is not None:
            state.last_output = result.output
        if logger is not None:
            logger.debug("Replace command success: %s", result.success)
        if step.output == "show":
            _show_captured_output(result.output, notify_callback=notify_callback, headless=headless)
        return WorkflowOutcome.SKIP_LAUNCH

    if step.action in ("run", "check"):
        _emit_workflow_step(logger, index=0, total=1, action=step.action, result=command)
        # "run" honors the step's wait flag; "check" always blocks.
        blocking = step.wait if step.action == "run" else True
        return _run_action_command(
            step,
            command,
            blocking=blocking,
            timeout=timeout,
            failmode=failmode,
            failure_context=failure_context,
            notify_callback=notify_callback,
            headless=headless,
            logger=logger,
            state=state,
        )

    if step.action == "run_after":
        _emit_workflow_step(logger, index=0, total=1, action="run_after", result=command)
        _warn_ignored_output(step, "run_after (detached spawn)", logger)
        _run_command(command, wait=False, timeout=None, logger=logger)

    return None


def _resolve_step_texts(
    step: WorkflowStep,
    file_path: Path | None,
    *,
    username: str | None = None,
    hostname: str | None = None,
    last_output: str = "",
) -> tuple[str, str]:
    """Resolve a step's ``command`` and ``message`` with token substitution.

    Standard tokens (``{{path}}``, ``{{username}}``, ``{{output}}``, ...)
    are substituted first — shell-quoted in the command (see
    :func:`_substitute_variables`), verbatim in the message; the
    ``{{command}}`` / ``{{message}}`` step tokens are then cross-resolved
    in a single pass (mutual references are not recursive).
    """
    command = _substitute_variables(
        step.command,
        file_path,
        username=username,
        hostname=hostname,
        output=last_output,
        shell_quote=True,
    )
    message = _substitute_variables(
        step.message, file_path, username=username, hostname=hostname, output=last_output
    )
    if command and message:
        command = _replace_step_token(command, "message", message)
        message = _replace_step_token(message, "command", command)
    return command, message


def _replace_step_token(text: str, key: str, value: str) -> str:
    """Replace both brace forms (``{{key}}`` and ``{key}``) of a single token."""
    text = text.replace("{{" + key + "}}", value)
    return text.replace("{" + key + "}", value)


def _quote_for_shell(value: str) -> str:
    """Quote *value* as a single argument for the platform shell.

    POSIX uses ``shlex.quote``; Windows uses ``subprocess.list2cmdline``
    (the double-quote form ``cmd.exe`` understands). Values without shell
    metacharacters come back unchanged, so simple templates are unaffected.
    """
    if os.name == "nt":
        return subprocess.list2cmdline([value])
    return shlex.quote(value)


def _substitute_variables(
    template: str,
    file_path: Path | None,
    *,
    command: str | None = None,
    message: str | None = None,
    username: str | None = None,
    hostname: str | None = None,
    output: str = "",
    shell_quote: bool = False,
) -> str:
    """Substitute variables in step text (supporting both {{token}} and {token}).

    ``command`` / ``message`` carry the current step's already-substituted
    command / message, referenced as ``{{command}}`` / ``{{message}}`` from
    any step text (e.g. an ``ask`` prompt). ``output`` carries the captured
    output of the most recent completed blocking command step, referenced
    as ``{{output}}`` (empty string before any has run).

    With ``shell_quote=True`` (command templates only — never display text),
    every substituted value is quoted as a single shell argument. Templates
    that already wrap a token in quotes have those quotes consumed, so
    ``'{{path}}'`` and ``"{{path}}"`` stay correct while a hostile value
    arriving from a filename or from ``{{output}}`` cannot break out
    (worst case the command fails, it never executes injected shell).
    """
    res = template
    tokens: dict[str, str | None] = {
        "command": command,
        "message": message,
        "username": username,
        "hostname": hostname,
        "date": datetime.date.today().isoformat(),
        "path": str(file_path) if file_path else None,
        "filename": file_path.name if file_path else None,
        "dir": str(file_path.parent) if file_path else None,
        "stem": file_path.stem if file_path else None,
        "ext": file_path.suffix if file_path else None,
        "output": output,
    }

    for key, val in tokens.items():
        if val is None:
            continue
        # An empty value stays verbatim (substitutes to nothing, as before)
        # instead of becoming an explicit empty shell argument.
        value = _quote_for_shell(val) if shell_quote and val else val
        # Quoted-template forms first: the template's own quotes are
        # consumed so a platform-quoted value is never double-quoted.
        for q in ("'", '"'):
            res = res.replace(q + "{{" + key + "}}" + q, value)
            res = res.replace(q + "{" + key + "}" + q, value)
        res = res.replace("{{" + key + "}}", value)
        res = res.replace("{" + key + "}", value)

    return res


def _decode_command_stream(stream: bytes | None) -> str:
    """Decode a captured byte stream using the locale-preferred encoding."""
    if not stream:
        return ""
    return stream.decode(locale.getpreferredencoding(False), errors="replace")


def _bound_captured_output(stdout: bytes | None, stderr: bytes | None) -> str:
    """Combine stdout+stderr into the tail-bounded captured-output text."""
    text = _decode_command_stream(stdout) + _decode_command_stream(stderr)
    if len(text) > _OUTPUT_CAPTURE_LIMIT:
        return _OUTPUT_TRUNCATION_MARKER + text[-_OUTPUT_CAPTURE_LIMIT:]
    return text


def _run_command(
    command: str, wait: bool, *, timeout: int | None = None, logger: logging.Logger | None = None
) -> CommandResult:
    """Run a shell command, capturing combined output for blocking runs.

    Blocking runs (``wait=True``) return the exit code plus the combined
    stdout+stderr, tail-bounded (``~4 KB``). Detached spawns (``wait=False``)
    report code 0 with empty output — nothing to capture.
    """
    try:
        if wait:
            res = subprocess.run(
                command, shell=True, check=False, timeout=timeout, capture_output=True
            )
            result = CommandResult(
                code=res.returncode,
                output=_bound_captured_output(res.stdout, res.stderr),
            )
            if logger is not None:
                events.command_exit(logger, code=res.returncode, command=command)
                # Always routed through the dedicated logger so the output
                # keeps the log grammar and reaches the web log viewer,
                # regardless of the step's ``output:`` display mode.
                events.command_output(
                    logger, code=result.code, command=command, output=result.output
                )
            return result
        # Fire-and-forget spawn: Popen must outlive this call.
        # pylint: disable-next=consider-using-with
        subprocess.Popen(command, shell=True)
        if logger is not None:
            logger.debug("Command spawned in background")
        return CommandResult(code=0, output="")
    except subprocess.TimeoutExpired:
        if logger is not None:
            events.command_timeout(
                logger, timeout_s=timeout if timeout is not None else 0, command=command
            )
        return CommandResult(code=-1, output="")
    except Exception as e:
        if logger is not None:
            events.command_failed(logger, error=str(e), command=command)
        return CommandResult(code=-1, output="")


__all__ = [
    "CommandResult",
    "FailMode",
    "WorkflowOutcome",
    "evaluate_step_condition",
    "filter_steps_by_phase",
    "run_workflow",
]
