"""Interactive workflow runner routes for stepping through file launch hooks."""

from __future__ import annotations

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


@dataclass
class StepRecord:
    index: int
    action: str
    content: str
    ask: str | None
    wait: bool
    status: Literal["pending", "running", "completed", "skipped", "failed"] = "pending"
    message: str = ""


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
        "completed",
        "aborted",
        "failed",
    ] = "idle"
    ask_prompt: str | None = None
    ask_answered: bool = False
    notify_message: str | None = None
    skip_next: bool = False
    final_message: str = ""
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
        "content": r.content,
        "ask": r.ask,
        "wait": r.wait,
        "status": r.status,
        "message": r.message,
    }


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
            rec.message = "Skipped by previous step"
            session.skip_next = False
            session.current_index += 1
            continue

        # If step has an ask prompt and we haven't asked yet:
        if step.ask and not session.ask_answered:
            prompt_text = _substitute_variables(
                step.ask,
                session.file_path,
                action_content=step.content,
                username=username,
                hostname=hostname,
            )
            session.status = "waiting_ask"
            session.ask_prompt = prompt_text
            rec.status = "running"
            return

        # If step is notify and we haven't acknowledged yet:
        if step.action == "notify" and session.notify_message is None:
            msg_text = _substitute_variables(
                step.content,
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
        session.ask_answered = False
        session.notify_message = None

        if not step.evaluate_condition(session.file_path):
            rec.status = "skipped"
            rec.message = "Condition not met"
            session.current_index += 1
            continue

        if step.action == "notify":
            rec.status = "completed"
            session.current_index += 1
            continue

        # Execute action (run, check, replace, run_after)
        ret = workflow._execute_step(
            step,
            session.file_path,
            headless=True,
            username=username,
            hostname=hostname,
        )

        if step.action == "replace":
            rec.status = "completed" if ret == 0 else "failed"
            session.status = "completed"
            session.final_message = f"Launched replacement: {step.content}"
            return

        if ret != 0:
            rec.status = "failed"
            on_fail = step.on_failure or "warn"
            if on_fail in ("stop", "abort"):
                session.status = "failed"
                session.final_message = f"Step {i + 1} failed with code {ret}"
                return
            rec.message = f"Warning: command returned code {ret}"
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
    step_records = [
        StepRecord(
            index=idx + 1,
            action=s.action,
            content=s.content,
            ask=s.ask,
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
        "notify_message": session.notify_message,
        "final_message": session.final_message,
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
        "notify_message": session.notify_message,
        "final_message": session.final_message,
        "steps": [_format_step_record(r) for r in session.step_records],
    }


@router.post("/{session_id}/respond")
async def respond_workflow(session_id: str, payload: RespondWorkflowRequest) -> dict:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "waiting_notify":
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
            session.step_records[session.current_index].message = "Aborted by user"
            session.final_message = "Workflow aborted by user."
            return {
                "session_id": session_id,
                "status": session.status,
                "final_message": session.final_message,
                "steps": [_format_step_record(r) for r in session.step_records],
            }
        elif payload.action == "skip":
            session.step_records[session.current_index].status = "skipped"
            session.step_records[session.current_index].message = "Skipped by user"
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
        "notify_message": session.notify_message,
        "final_message": session.final_message,
        "steps": [_format_step_record(r) for r in session.step_records],
    }
