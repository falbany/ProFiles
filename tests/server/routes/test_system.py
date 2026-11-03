"""Test system and health endpoints for the local FastAPI server."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


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
    """lan=True rebinds to 0.0.0.0 and reflects the new state."""
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
        assert response.json() == {"host": "0.0.0.0", "lan_enabled": True}
        assert calls == ["0.0.0.0"]


@pytest.mark.anyio
async def test_bind_failure_returns_500_and_state_is_unchanged(
    test_state: ServerState,
) -> None:
    """A failed rebind reports the error; the bind state stays on the server."""
    from profiles.desktop.lifecycle import ServerStartError

    class _FailingServer(_StubServer):
        def rebind(self, host: str) -> None:  # noqa: F811
            raise ServerStartError("bind denied")

    stub = _FailingServer()
    app = create_app(test_state)
    app.state.background_server = stub
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/system/bind", json={"lan": True})
        assert response.status_code == 500
        assert "bind denied" in response.json()["detail"]
        status = await client.get("/api/system")
        assert status.json()["lan_enabled"] is False
