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
                WorkflowStep(action="notify", content="Notice: Launching {{filename}}"),
                WorkflowStep(action="run", content="echo prepare", ask="Execute prepare?"),
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
            WorkflowStep(action="run_after", content="echo async"),
            WorkflowStep(action="notify", content="After async notice"),
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
