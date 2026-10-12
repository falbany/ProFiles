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
