"""Test system and health endpoints for the local FastAPI server."""

from __future__ import annotations

import logging
import time

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.routes.system import _rebind_worker
from profiles.server.state import ServerState


def _wait_for(condition, timeout_s: float = 5.0) -> bool:
    """Poll ``condition`` until truthy or ``timeout_s`` elapsed."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


@pytest.fixture
def test_state() -> ServerState:
    config = AppConfig(title="Test Bench")
    return ServerState(config=config)


class _StubServer:
    """BindableServer stand-in recording rebind calls."""

    host = "127.0.0.1"

    @property
    def is_running(self) -> bool:
        return True

    def rebind(self, host: str) -> None:
        raise AssertionError("stub must be renamed before a test rebinds")


@pytest.mark.anyio
async def test_health_check(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.anyio
async def test_system_info(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system")
        assert response.status_code == 200
        data = response.json()
        assert "hostname" in data
        assert "ip" in data
        assert "username" in data
        assert "os_release" in data
        assert "lan_enabled" in data


@pytest.mark.anyio
async def test_system_info_reports_unknown_bind_state(
    test_state: ServerState,
) -> None:
    """No registered server (bare app factory) leaves the state unknown."""
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system")
        assert response.status_code == 200
        assert response.json()["lan_enabled"] is None


@pytest.mark.anyio
async def test_bind_without_server_returns_503(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/system/bind", json={"lan": True})
        assert response.status_code == 503


@pytest.mark.anyio
async def test_bind_runs_rebind_on_registered_server(
    test_state: ServerState,
) -> None:
    """lan=True schedules the rebind and answers before it completes."""
    calls: list[str] = []

    class _RecordingServer(_StubServer):
        @property
        def is_running(self) -> bool:  # noqa: F811
            return True

        def rebind(self, host: str) -> None:  # noqa: F811
            calls.append(host)
            self.host = host

    stub = _RecordingServer()
    app = create_app(test_state)
    app.state.background_server = stub
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/system/bind", json={"lan": True})
        assert response.status_code == 200
        # The rebind is asynchronous: the response ships first.
        assert response.json() == {
            "host": "0.0.0.0",
            "lan_enabled": True,
            "status": "rebinding",
        }
        assert _wait_for(lambda: calls == ["0.0.0.0"]), calls


@pytest.mark.anyio
async def test_bind_worker_logs_bind_changed_on_success(
    test_state: ServerState, caplog: pytest.LogCaptureFixture
) -> None:
    """The rebind worker leaves a BIND_CHANGED line on success."""

    class _OkServer(_StubServer):
        def rebind(self, host: str) -> None:  # noqa: F811
            self.host = host

    stub = _OkServer()
    with caplog.at_level(logging.INFO, logger="profiles"):
        _rebind_worker(stub, "127.0.0.1")

    assert 'BIND_CHANGED host="127.0.0.1" lan=false' in caplog.text


def test_bind_worker_logs_failure_and_no_bind_changed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed rebind logs BIND_CHANGE_FAILED; the server keeps serving."""
    from profiles.desktop.lifecycle import ServerStartError

    class _FailingServer(_StubServer):
        def rebind(self, host: str) -> None:  # noqa: F811
            raise ServerStartError("bind denied")

    stub = _FailingServer()
    with caplog.at_level(logging.INFO, logger="profiles"):
        _rebind_worker(stub, "0.0.0.0")

    assert 'BIND_CHANGE_FAILED host="0.0.0.0" error="bind denied"' in caplog.text
    assert "BIND_CHANGED" not in caplog.text
    assert stub.host == "127.0.0.1"


@pytest.mark.anyio
async def test_bind_failure_reverts_and_state_stays_unchanged(
    test_state: ServerState,
) -> None:
    """A failed rebind is answered optimistically; the state reverts.

    The route cannot know the rebind outcome synchronously (the old server
    cannot shut down while serving this request), so it answers
    ``rebinding`` and the revert — done by the lifecycle — is observable
    through ``GET /api/system``.
    """
    from profiles.desktop.lifecycle import ServerStartError

    class _FailingServer(_StubServer):
        def rebind(self, host: str) -> None:  # noqa: F811
            raise ServerStartError("bind denied")

    stub = _FailingServer()
    app = create_app(test_state)
    app.state.background_server = stub
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/system/bind", json={"lan": True})
        assert response.status_code == 200
        assert response.json()["status"] == "rebinding"
        status = await client.get("/api/system")
        assert status.json()["lan_enabled"] is False
