"""Interactive workflow runner routes for stepping through file launch hooks."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from profiles.core import actions
from profiles.core.config.models import WorkflowStep
from profiles.core.environment import matcher, workflow
from profiles.core.environment.workflow import _substitute_variables
from profiles.utils.network import get_hostname, get_username

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

# Dedicated application logger: workflow execution traces and captured
# command output land in profiles.log and the web log viewer.
_LOGGER = logging.getLogger("profiles")


@dataclass
class StepRecord:
    index: int
    action: str
    command: str
    message: str = ""
    ask: str | None = None
    wait: bool = True
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "pending"
    note: str = ""
    output: str = ""


@dataclass
class WorkflowSession:
    session_id: str
    directory: Path
    filename: str
    file_path: Path
    pattern: str
    steps: list[WorkflowStep]
    step_records: list[StepRecord]
    current_index: int = 0
    status: Literal[
        "idle",
        "running",
        "waiting_ask",
        "waiting_notify",
        "waiting_notice",
        "completed",
        "aborted",
        "failed",
    ] = "idle"
    ask_prompt: str | None = None
    ask_message: str | None = None
    ask_answered: bool = False
    notify_message: str | None = None
    notice_message: str | None = None
    notice_acknowledged: bool = False
    skip_next: bool = False
    final_message: str = ""
    last_output: str = ""
    release: str = ""
    args: str = ""


# In-memory session store
_sessions: dict[str, WorkflowSession] = {}


class StartWorkflowRequest(BaseModel):
    directory: str
    filename: str
    release: str = ""
    args: str = ""


class RespondWorkflowRequest(BaseModel):
    action: Literal["yes", "skip", "no", "ack"]


def _format_step_record(r: StepRecord) -> dict:
    return {
        "index": r.index,
        "action": r.action,
        "command": r.command,
        "message": r.message,
        "ask": r.ask,
        "wait": r.wait,
        "status": r.status,
        "note": r.note,
        "output": r.output,
    }


# The engine facade is internal to core; sessions reuse it deliberately.
# pylint: disable=protected-access
def _execute_step_with_capture(
    step: WorkflowStep,
    session: WorkflowSession,
    *,
    username: str,
    hostname: str,
) -> tuple[workflow.WorkflowOutcome | None, str, list[str]]:
    """Execute *step* with logging and capture enabled.

    The dedicated application logger keeps execution traces and captured
    output in profiles.log (web log viewer).

    Returns:
        ``(outcome, captured_output, failure_context)`` where
        *captured_output* is the blocking command's combined streams and
        *failure_context* carries the rc/output failure description of a
        terminal failure (empty otherwise).
    """
    state = workflow._WorkflowState()
    failure_context: list[str] = []
    ret = workflow._execute_step(
        step,
        session.file_path,
        headless=True,
        username=username,
        hostname=hostname,
        show_notice=False,
        logger=_LOGGER,
        state=state,
        failure_context=failure_context,
    )
    return ret, state.last_output, failure_context


# pylint: enable=protected-access


def _advance_session(session: WorkflowSession) -> None:
    """Run steps synchronously until reaching an interactive prompt or end."""
    username = get_username()
    hostname = get_hostname()

    while session.current_index < len(session.steps):
        i = session.current_index
        step = session.steps[i]
        rec = session.step_records[i]

        if session.skip_next:
            rec.status = "skipped"
            rec.note = "Skipped by previous step"
            session.skip_next = False
            session.current_index += 1
            continue

        # If step has an ask prompt and we haven't asked yet:
        # the dialog composes the step's Markdown message (if any) above
        # the ask question, mirroring the native engine behavior.
        if step.ask and not session.ask_answered:
            command_sub, message_sub = workflow._resolve_step_texts(
                step,
                session.file_path,
                username=username,
                hostname=hostname,
            )
            ask_content = _substitute_variables(
                step.ask,
                session.file_path,
                command=command_sub,
                message=message_sub,
                username=username,
                hostname=hostname,
            )
            session.status = "waiting_ask"
            session.ask_prompt = ask_content
            session.ask_message = message_sub if step.message else None
            rec.status = "running"
            return

        # Non-blocking notice for a command step's message (no ask guard):
        # pause until the web UI acknowledges, then execute the command.
        # Placed after the condition check so skipped steps stay silent.
        if (
            step.action != "notify"
            and step.message
            and not step.ask
            and not session.notice_acknowledged
        ):
            _, message_sub = workflow._resolve_step_texts(
                step,
                session.file_path,
                username=username,
                hostname=hostname,
            )
            session.status = "waiting_notice"
            session.notice_message = message_sub
            rec.status = "running"
            return

        # If step is notify and we haven't acknowledged yet:
        if step.action == "notify" and session.notify_message is None:
            _, msg_text = workflow._resolve_step_texts(
                step,
                session.file_path,
                username=username,
                hostname=hostname,
            )
            session.status = "waiting_notify"
            session.notify_message = msg_text
            rec.status = "running"
            return

        # Execute normal or acknowledged step
        rec.status = "running"
        session.ask_prompt = None
        session.ask_message = None
        session.ask_answered = False
        session.notify_message = None
        session.notice_acknowledged = False

        if not step.evaluate_condition():
            rec.status = "skipped"
            rec.note = "Condition not met"
            session.current_index += 1
            continue

        if step.action == "notify":
            rec.status = "completed"
            session.current_index += 1
            continue

        # Execute action (run, check, replace, run_after)
        ret, captured_output, failure_context = _execute_step_with_capture(
            step, session, username=username, hostname=hostname
        )

        if step.action in ("run", "check", "replace"):
            rec.output = captured_output
            session.last_output = captured_output

        if step.action == "replace":
            # replace returns WorkflowOutcome.SKIP_LAUNCH (not int), or None
            rec.status = "completed"
            session.status = "completed"
            session.final_message = f"Launched replacement: {step.command}"
            return

        if step.action == "run_after":
            # run_after runs asynchronously in background and must not block
            rec.status = "completed"
            session.current_index += 1
            continue

        if ret is not None and ret != 0:
            rec.status = "failed"
            on_fail = step.on_failure or "warn"
            if on_fail in ("stop", "abort"):
                session.status = "failed"
                # failure_context carries the rc + captured-output
                # description for steps configured to reveal them.
                session.final_message = (
                    failure_context[-1] if failure_context else f"Step {i + 1} failed"
                )
                return
            rec.note = "Warning: step returned error outcome"
        else:
            rec.status = "completed"

        session.current_index += 1

    # All steps completed — proceed to OS launch
    session.status = "completed"
    file_path = session.file_path
    if session.args:
        launched = actions.launch_file_with_args(file_path, session.args)
    else:
        launched = actions.launch_file(file_path)

    session.final_message = f"Launched {file_path.name}" if launched else "Failed to open file"


@router.post("/start")
async def start_workflow(payload: StartWorkflowRequest, request: Request) -> dict:
    state = getattr(request.app.state, "server_state", None)
    config = getattr(state, "config", None) if state else None
    if not config or not config.launch_hooks:
        raise HTTPException(status_code=400, detail="No launch workflows configured")

    target_dir = Path(payload.directory).expanduser().resolve()
    target_file = target_dir / payload.filename
    if not target_file.exists():
        raise HTTPException(status_code=404, detail="File does not exist")

    patterns = list(config.launch_hooks.keys())
    matched_pattern = matcher.select_most_specific_pattern(patterns, payload.filename)
    if not matched_pattern or matched_pattern not in config.launch_hooks:
        raise HTTPException(status_code=400, detail="No matching workflow found for file")

    steps = list(config.launch_hooks[matched_pattern])
    username = get_username()
    hostname = get_hostname()
    step_records = [
        StepRecord(
            index=idx + 1,
            action=s.action,
            command=_substitute_variables(
                s.command,
                target_file,
                username=username,
                hostname=hostname,
            ),
            message=_substitute_variables(
                s.message,
                target_file,
                username=username,
                hostname=hostname,
            ),
            ask=_substitute_variables(
                s.ask,
                target_file,
                username=username,
                hostname=hostname,
            )
            if s.ask
            else None,
            wait=s.wait,
        )
        for idx, s in enumerate(steps)
    ]

    session_id = str(uuid.uuid4())
    session = WorkflowSession(
        session_id=session_id,
        directory=target_dir,
        filename=payload.filename,
        file_path=target_file,
        pattern=matched_pattern,
        steps=steps,
        step_records=step_records,
        release=payload.release,
        args=payload.args,
    )
    _sessions[session_id] = session

    # Advance until first interactive prompt or finish
    _advance_session(session)

    return {
        "session_id": session_id,
        "filename": payload.filename,
        "pattern": matched_pattern,
        "status": session.status,
        "current_index": session.current_index,
        "ask_prompt": session.ask_prompt,
        "ask_message": session.ask_message,
        "notice_message": session.notice_message,
        "notify_message": session.notify_message,
        "final_message": session.final_message,
        "last_output": session.last_output,
        "steps": [_format_step_record(r) for r in session.step_records],
    }


@router.get("/{session_id}")
async def get_workflow_session(session_id: str) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "filename": session.filename,
        "pattern": session.pattern,
        "status": session.status,
        "current_index": session.current_index,
        "ask_prompt": session.ask_prompt,
        "ask_message": session.ask_message,
        "notice_message": session.notice_message,
        "notify_message": session.notify_message,
        "final_message": session.final_message,
        "last_output": session.last_output,
        "steps": [_format_step_record(r) for r in session.step_records],
    }


@router.post("/{session_id}/respond")
async def respond_workflow(session_id: str, payload: RespondWorkflowRequest) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "waiting_notice":
        if payload.action != "ack":
            raise HTTPException(status_code=400, detail="Expected ack for notice")
        session.notice_message = None
        session.notice_acknowledged = True
        _advance_session(session)

    elif session.status == "waiting_notify":
        if payload.action != "ack":
            raise HTTPException(status_code=400, detail="Expected ack for notification")
        session.notify_message = None
        session.step_records[session.current_index].status = "completed"
        session.current_index += 1
        _advance_session(session)

    elif session.status == "waiting_ask":
        if payload.action == "no":
            session.status = "aborted"
            session.step_records[session.current_index].status = "failed"
            session.step_records[session.current_index].note = "Aborted by user"
            session.final_message = "Workflow aborted by user."
            return {
                "session_id": session_id,
                "status": session.status,
                "final_message": session.final_message,
                "steps": [_format_step_record(r) for r in session.step_records],
            }
        elif payload.action == "skip":
            session.step_records[session.current_index].status = "skipped"
            session.step_records[session.current_index].note = "Skipped by user"
            session.ask_prompt = None
            if session.current_index == len(session.steps) - 1:
                session.status = "completed"
                session.final_message = "Skipped launch on final step."
                return {
                    "session_id": session_id,
                    "status": session.status,
                    "final_message": session.final_message,
                    "steps": [_format_step_record(r) for r in session.step_records],
                }
            session.skip_next = True
            session.current_index += 1
            _advance_session(session)
        elif payload.action == "yes":
            session.ask_prompt = None
            session.ask_answered = True
            _advance_session(session)

    return {
        "session_id": session_id,
        "status": session.status,
        "current_index": session.current_index,
        "ask_prompt": session.ask_prompt,
        "ask_message": session.ask_message,
        "notice_message": session.notice_message,
        "notify_message": session.notify_message,
        "final_message": session.final_message,
        "last_output": session.last_output,
        "steps": [_format_step_record(r) for r in session.step_records],
    }
