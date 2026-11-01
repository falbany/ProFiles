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


@pytest.fixture
def capture_state(tmp_path: Path) -> ServerState:
    """State whose workflow runs a real output-producing command."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Capture Bench",
        search_dir=str(test_dir),
        launch_hooks={"*.mttl": (WorkflowStep(action="run", command="echo captured-output"),)},
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_run_step_exposes_captured_output(capture_state: ServerState) -> None:
    """A blocking run step reports its captured output per step and session-wide."""
    app = create_app(capture_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("profiles.core.actions.launch_file", return_value=True):
            resp = await client.post(
                "/api/workflow/start",
                json={
                    "directory": str(capture_state.active_directory),
                    "filename": "tool.mttl",
                },
            )
        data = resp.json()
        assert data["status"] == "completed"
        assert "captured-output" in data["steps"][0]["output"]
        assert "captured-output" in data["last_output"]


@pytest.mark.anyio
async def test_failed_stop_step_reports_rc_and_output(tmp_path: Path) -> None:
    """A failing ``stop`` step with output: show surfaces rc + output in final_message."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Failure Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(
                    action="check",
                    command="echo boom & exit 3",
                    output="show",
                    on_failure="stop",
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
        assert data["status"] == "failed"
        assert data["steps"][0]["status"] == "failed"
        assert "rc=3" in data["final_message"]
        assert "Last output:" in data["final_message"]


@pytest.mark.anyio
async def test_skip_on_ask_lets_next_step_ask(tmp_path: Path) -> None:
    """Skip ignores only the answered step; the next step still asks its own guard."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Skip Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="run", command="echo prepare", ask="Prepare the file?"),
                WorkflowStep(action="run", command="echo validate", ask="Validate before launch?"),
                WorkflowStep(action="run", command="echo log"),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("profiles.core.environment.workflow._execute_step", return_value=0),
            patch("profiles.core.actions.launch_file", return_value=True),
        ):
            resp = await client.post(
                "/api/workflow/start",
                json={"directory": str(test_dir), "filename": "tool.mttl"},
            )
            data = resp.json()
            assert data["status"] == "waiting_ask"
            assert data["ask_prompt"] == "Prepare the file?"

            skip = await client.post(
                f"/api/workflow/{data['session_id']}/respond",
                json={"action": "skip"},
            )
            skipped = skip.json()
            # Only step 1 is skipped; step 2 pauses on its own ask guard.
            assert skipped["steps"][0]["status"] == "skipped"
            assert skipped["steps"][0]["note"] == "Skipped by user"
            assert skipped["steps"][1]["status"] == "running"
            assert skipped["steps"][1]["note"] != "Skipped by previous step"
            assert skipped["status"] == "waiting_ask"
            assert skipped["ask_prompt"] == "Validate before launch?"

            # Step 2 executes on Yes; the workflow then completes via step 3.
            yes = await client.post(
                f"/api/workflow/{skipped['session_id']}/respond",
                json={"action": "yes"},
            )
            final = yes.json()
            assert final["steps"][1]["status"] == "completed"
            assert final["steps"][2]["status"] == "completed"
            assert final["status"] == "completed"


@pytest.mark.anyio
async def test_output_token_resolves_in_ask_prompt(tmp_path: Path) -> None:
    """An ask prompt sees the {{output}} captured by the previous command step."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Output Ask Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="run", command="echo probe-output-123"),
                WorkflowStep(
                    action="run", command="echo prepare", ask="Probe said {{output}} — run?"
                ),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("profiles.core.actions.launch_file", return_value=True):
            resp = await client.post(
                "/api/workflow/start",
                json={"directory": str(test_dir), "filename": "tool.mttl"},
            )
        data = resp.json()
        assert data["status"] == "waiting_ask"
        assert "probe-output-123" in data["ask_prompt"]


@pytest.mark.anyio
async def test_output_token_resolves_in_notice_message(tmp_path: Path) -> None:
    """A non-blocking notice message sees the {{output}} of the previous step."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Output Notice Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="run", command="echo probe-output-456"),
                WorkflowStep(action="run", command="echo prepare", message="Result: {{output}}"),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("profiles.core.actions.launch_file", return_value=True):
            resp = await client.post(
                "/api/workflow/start",
                json={"directory": str(test_dir), "filename": "tool.mttl"},
            )
        data = resp.json()
        assert data["status"] == "waiting_notice"
        assert "probe-output-456" in data["notice_message"]


@pytest.mark.anyio
async def test_replace_final_message_is_token_substituted(tmp_path: Path) -> None:
    """A replace step's final_message shows the resolved command, not the raw template."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Replace Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="run", command="echo probe-output-789"),
                WorkflowStep(action="replace", command="echo 'Opening {{filename}}'"),
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
        assert data["status"] == "completed"
        assert data["final_message"] == "Launched replacement: echo 'Opening tool.mttl'"


@pytest.mark.anyio
async def test_notify_with_ask_single_gate(tmp_path: Path) -> None:
    """notify + ask: Yes completes the step — no second waiting_notify gate (#22)."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Notify Ask Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="notify", message="# Ready", ask="Proceed?", wait=True),
                WorkflowStep(action="run", command="echo post", ask="Run post-launch?"),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with (
            patch("profiles.core.environment.workflow._execute_step", return_value=0),
            patch("profiles.core.actions.launch_file", return_value=True),
        ):
            resp = await client.post(
                "/api/workflow/start",
                json={"directory": str(test_dir), "filename": "tool.mttl"},
            )
            data = resp.json()
            assert data["status"] == "waiting_ask"
            assert data["ask_prompt"] == "Proceed?"
            assert data["ask_message"] == "# Ready"

            yes = await client.post(
                f"/api/workflow/{data['session_id']}/respond",
                json={"action": "yes"},
            )
            final = yes.json()
            # The notify step completed; the session advanced to step 2's
            # own ask instead of pausing again on a notification.
            assert final["steps"][0]["status"] == "completed"
            assert final["status"] == "waiting_ask"
            assert final["ask_prompt"] == "Run post-launch?"
            assert final["notify_message"] is None

            yes2 = await client.post(
                f"/api/workflow/{final['session_id']}/respond",
                json={"action": "yes"},
            )
            assert yes2.json()["status"] == "completed"


@pytest.mark.anyio
async def test_abort_aborts_interactive_session(workflow_state: ServerState) -> None:
    """Closing mid-workflow aborts the session server-side (#24)."""
    app = create_app(workflow_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/workflow/start",
            json={"directory": str(workflow_state.active_directory), "filename": "tool.mttl"},
        )
        session_id = resp.json()["session_id"]
        assert resp.json()["status"] == "waiting_notify"

        abort = await client.post(f"/api/workflow/{session_id}/abort")
        assert abort.status_code == 200
        data = abort.json()
        assert data["status"] == "aborted"
        assert data["final_message"] == "Aborted by user (modal closed)."
        assert data["steps"][0]["status"] == "failed"
        assert data["steps"][0]["note"] == "Aborted by user (modal closed)"

        # Idempotent: a second abort returns the same terminal state.
        again = await client.post(f"/api/workflow/{session_id}/abort")
        assert again.status_code == 200
        assert again.json()["status"] == "aborted"

        status = await client.get(f"/api/workflow/{session_id}")
        assert status.json()["status"] == "aborted"


@pytest.mark.anyio
async def test_abort_unknown_session_returns_404() -> None:
    app = create_app(ServerState(config=None, active_directory=None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/workflow/does-not-exist/abort")
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_abort_terminal_session_is_a_noop(capture_state: ServerState) -> None:
    """Aborting an already-finished session leaves its outcome untouched."""
    app = create_app(capture_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("profiles.core.actions.launch_file", return_value=True):
            resp = await client.post(
                "/api/workflow/start",
                json={
                    "directory": str(capture_state.active_directory),
                    "filename": "tool.mttl",
                },
            )
        data = resp.json()
        assert data["status"] == "completed"
        original_final = data["final_message"]

        abort = await client.post(f"/api/workflow/{data['session_id']}/abort")
        assert abort.status_code == 200
        assert abort.json()["status"] == "completed"
        assert abort.json()["final_message"] == original_final


def test_purge_stale_sessions_keeps_waiting_and_fresh_terminal() -> None:
    """TTL purge drops only terminal sessions past the age limit."""
    import time as time_mod

    from profiles.server.routes import workflow as wf_routes

    def make_session(session_id: str, status: str, created_at: float) -> wf_routes.WorkflowSession:
        return wf_routes.WorkflowSession(
            session_id=session_id,
            directory=Path("/tmp"),
            filename="tool.mttl",
            file_path=Path("/tmp/tool.mttl"),
            pattern="*.mttl",
            steps=[],
            step_records=[],
            status=status,
            created_at=created_at,
        )

    now = time_mod.time()
    stale = make_session("stale", "completed", now - wf_routes._SESSION_TTL_SECONDS - 10)
    fresh = make_session("fresh", "completed", now)
    waiting = make_session("waiting", "waiting_ask", now - wf_routes._SESSION_TTL_SECONDS - 10)
    wf_routes._sessions.update({"stale": stale, "fresh": fresh, "waiting": waiting})
    try:
        wf_routes._purge_stale_sessions()
        assert "stale" not in wf_routes._sessions
        assert "fresh" in wf_routes._sessions
        assert "waiting" in wf_routes._sessions
    finally:
        for key in ("fresh", "waiting"):
            wf_routes._sessions.pop(key, None)


# ---------------------------------------------------------------------------
# Post-launch phase (#9) and condition substitution (#8) in web sessions
# ---------------------------------------------------------------------------


@pytest.fixture
def post_phase_state(tmp_path: Path) -> ServerState:
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Post Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="run", command="echo prepare"),
                WorkflowStep(action="notify", message="Launched {{filename}}", phase="post"),
            )
        },
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_post_step_waits_after_launch(post_phase_state: ServerState) -> None:
    """A post-phase notify pauses only after the OS launch succeeded (#9)."""
    app = create_app(post_phase_state)
    with patch("profiles.core.actions.launch_file", return_value=True) as mock_launch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/workflow/start",
                json={
                    "directory": str(post_phase_state.active_directory),
                    "filename": "tool.mttl",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            # The pre step ran, the launch happened, and the post notify
            # is now waiting for acknowledgement.
            assert data["steps"][0]["status"] == "completed"
            assert data["steps"][1]["phase"] == "post"
            assert data["status"] == "waiting_notify"
            assert "Launched tool.mttl" in data["notify_message"]
            mock_launch.assert_called_once()


@pytest.mark.anyio
async def test_post_session_completes_after_ack(post_phase_state: ServerState) -> None:
    app = create_app(post_phase_state)
    with patch("profiles.core.actions.launch_file", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/api/workflow/start",
                json={
                    "directory": str(post_phase_state.active_directory),
                    "filename": "tool.mttl",
                },
            )
            session_id = start.json()["session_id"]
            ack = await client.post(f"/api/workflow/{session_id}/respond", json={"action": "ack"})
            data = ack.json()
            assert data["status"] == "completed"
            assert data["final_message"] == "Launched tool.mttl"


@pytest.mark.anyio
async def test_post_ask_no_completes_session_instead_of_abort(tmp_path: Path) -> None:
    """'No' on a post step ends the post workflow; the launch stands (#9)."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Post Ask Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                WorkflowStep(action="run", command="echo audit", ask="Run audit?", phase="post"),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    with patch("profiles.core.actions.launch_file", return_value=True) as mock_launch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/api/workflow/start",
                json={"directory": str(test_dir), "filename": "tool.mttl"},
            )
            data = start.json()
            assert data["status"] == "waiting_ask"
            respond = await client.post(
                f"/api/workflow/{data['session_id']}/respond", json={"action": "no"}
            )
            result = respond.json()
            assert result["status"] == "completed"
            assert result["final_message"] == "Launched tool.mttl"
            mock_launch.assert_called_once()


@pytest.mark.anyio
async def test_condition_tokens_substituted_in_session(tmp_path: Path) -> None:
    """``if:`` conditions see file tokens in web sessions too (#8)."""
    test_dir = tmp_path / "apps"
    test_dir.mkdir()
    (test_dir / "tool.mttl").write_text("content")

    config = AppConfig(
        title="Cond Bench",
        search_dir=str(test_dir),
        launch_hooks={
            "*.mttl": (
                # Marker exists next to the file → negated condition skips it
                WorkflowStep(action="run", command="echo gated", if_="!file:{{dir}}/tool.mttl"),
                WorkflowStep(action="run", command="echo ungated", if_="file:{{dir}}"),
            )
        },
    )
    state = ServerState(config=config, active_directory=test_dir)
    app = create_app(state)
    with patch("profiles.core.actions.launch_file", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start = await client.post(
                "/api/workflow/start",
                json={"directory": str(test_dir), "filename": "tool.mttl"},
            )
            data = start.json()
            assert data["status"] == "completed"
            assert data["steps"][0]["status"] == "skipped"
            assert data["steps"][0]["note"] == "Condition not met"
            assert data["steps"][1]["status"] == "completed"
