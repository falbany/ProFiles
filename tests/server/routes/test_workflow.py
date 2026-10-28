"""Tests for interactive workflow runner endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig, WorkflowStep
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def workflow_state(tmp_path: Path) -> ServerState:
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    target_file = test_dir / "tool.mttl"
    target_file.write_text("content")

    config = AppConfig(
        title="Test Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="notify", message="Notice: Launching {{filename}}"),
                WorkflowStep(action="run", command="echo prepare", ask="Execute prepare?"),
            )
        },
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_workflow_start_returns_steps_and_session(workflow_state: ServerState) -> None:
    app = create_app(workflow_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(workflow_state.active_directory), "filename": "tool.mttl"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["filename"] == "tool.mttl"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["action"] == "notify"
        assert data["steps"][1]["action"] == "run"
        assert data["steps"][1]["ask"] == "Execute prepare?"


@pytest.mark.anyio
async def test_workflow_advances_through_prompts(workflow_state: ServerState) -> None:
    app = create_app(workflow_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Start
        start_resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(workflow_state.active_directory), "filename": "tool.mttl"},
        )
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session_id"]

        # Step 1: notify prompt
        status_resp = await client.get(f"/api/workflow/{session_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "waiting_notify"
        assert "Notice: Launching" in status_data["notify_message"]

        # Acknowledge notify
        ack_resp = await client.post(
            f"/api/workflow/{session_id}/respond",
            json={"action": "ack"},
        )
        assert ack_resp.status_code == 200

        # Step 2: ask prompt
        status_resp2 = await client.get(f"/api/workflow/{session_id}")
        assert status_resp2.status_code == 200
        status_data2 = status_resp2.json()
        assert status_data2["status"] == "waiting_ask"
        assert status_data2["ask_prompt"] == "Execute prepare?"

        # Respond yes to ask
        with (
            patch("profiles.core.environment.workflow._execute_step", return_value=0),
            patch("profiles.core.actions.launch_file", return_value=True),
        ):
            resp_step = await client.post(
                f"/api/workflow/{session_id}/respond",
                json={"action": "yes"},
            )
            assert resp_step.status_code == 200
            final_data = resp_step.json()
            assert final_data["status"] == "completed"


@pytest.mark.anyio
async def test_workflow_run_after_is_non_blocking(workflow_state: ServerState) -> None:
    # Update state with a run_after step
    workflow_state.config.launch_hooks = {
        "*.mttl": (
            WorkflowStep(action="run_after", command="echo async"),
            WorkflowStep(action="notify", message="After async notice"),
        )
    }
    app = create_app(workflow_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Start: should execute run_after immediately and stop at notify
        resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(workflow_state.active_directory), "filename": "tool.mttl"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Session should be waiting_notify, not idle or pending
        assert data["status"] == "waiting_notify"
        # First step (run_after) should be completed
        assert data["steps"][0]["action"] == "run_after"
        assert data["steps"][0]["status"] == "completed"
        # Second step (notify) should be running (current focus)
        assert data["steps"][1]["status"] == "running"


@pytest.fixture
def notice_state(tmp_path: Path) -> ServerState:
    """State whose workflow exercises the message-only notice path."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Notice Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(
                    action="run", command="echo prepare", message="**Preparing** {{stem}}..."
                ),
                WorkflowStep(action="run", command="echo launch"),
            )
        },
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_step_records_expose_command_and_message(workflow_state: ServerState) -> None:
    app = create_app(workflow_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(workflow_state.active_directory), "filename": "tool.mttl"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["steps"][0]["command"] == ""
        assert data["steps"][0]["message"] == "Notice: Launching tool.mttl"
        assert data["steps"][1]["command"] == "echo prepare"


@pytest.mark.anyio
async def test_command_step_message_pauses_as_notice(notice_state: ServerState) -> None:
    """A message-only run step pauses the session until acknowledged."""
    app = create_app(notice_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(notice_state.active_directory), "filename": "tool.mttl"},
        )
        data = resp.json()
        assert data["status"] == "waiting_notice"
        assert data["notice_message"] == "**Preparing** tool..."
        assert data["steps"][0]["status"] == "running"

        with patch("profiles.core.actions.launch_file", return_value=True):
            ack = await client.post(
                f"/api/workflow/{data['session_id']}/respond",
                json={"action": "ack"},
            )
        final = ack.json()
        assert final["status"] == "completed"
        assert final["notice_message"] is None
        assert final["steps"][0]["status"] == "completed"
        assert final["steps"][1]["status"] == "completed"


@pytest.mark.anyio
async def test_composed_ask_carries_ask_message(tmp_path: Path) -> None:
    """An ask guard with a message returns both parts for composed display."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Composed Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(
                    action="run",
                    command="echo hi",
                    message="# Advanced mode",
                    ask="Execute: {command}?",
                ),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(test_dir), "filename": "tool.mttl"},
        )
        data = resp.json()
        assert data["status"] == "waiting_ask"
        assert data["ask_message"] == "# Advanced mode"
        # {command} token resolves in the ask prompt
        assert data["ask_prompt"] == "Execute: echo hi?"

        with (
            patch("profiles.core.environment.workflow._execute_step", return_value=0),
            patch("profiles.core.actions.launch_file", return_value=True),
        ):
            yes = await client.post(
                f"/api/workflow/{data['session_id']}/respond",
                json={"action": "yes"},
            )
        assert yes.json()["status"] == "completed"
