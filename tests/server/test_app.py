"""Tests for the FastAPI application factory — client connection telemetry."""

from __future__ import annotations

import logging
import time

import httpx
import pytest

from profiles.core.config.models import AppConfig
from profiles.server.app import (
    CLIENT_IDLE_DISCONNECT_S,
    create_app,
    sweep_disconnected_clients,
)
from profiles.server.state import ServerState


@pytest.fixture
def app_state(monkeypatch: pytest.MonkeyPatch) -> ServerState:
    """Server state isolated from the repo."""
    monkeypatch.chdir(".")
    return ServerState(config=AppConfig(title="Test Bench"))


@pytest.mark.anyio
async def test_web_client_logged_on_first_request(
    app_state: ServerState, caplog: pytest.LogCaptureFixture
) -> None:
    """The first request from a client IP emits WEB_CLIENT at INFO."""
    app = create_app(app_state)

    with caplog.at_level(logging.INFO, logger="profiles"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/system")

    assert response.status_code == 200
    assert "WEB_CLIENT" in caplog.text


@pytest.mark.anyio
async def test_web_client_logged_once_per_ip(
    app_state: ServerState, caplog: pytest.LogCaptureFixture
) -> None:
    """Repeat requests from the same IP do not emit further WEB_CLIENT lines."""
    app = create_app(app_state)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="profiles"):
            await client.get("/api/system")
            first_count = sum("WEB_CLIENT" in r.message for r in caplog.records)
            await client.get("/api/system")
            second_count = sum("WEB_CLIENT" in r.message for r in caplog.records)

    assert first_count == 1
    assert second_count == 1


@pytest.mark.anyio
async def test_web_client_reconnected_after_idle_gap(
    app_state: ServerState, caplog: pytest.LogCaptureFixture
) -> None:
    """A client silent for longer than the idle threshold logs reconnected."""
    app = create_app(app_state)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        with caplog.at_level(logging.INFO, logger="profiles"):
            await client.get("/api/system")
            ip = next(iter(app.state.client_last_seen))
            app.state.client_last_seen[ip] -= CLIENT_IDLE_DISCONNECT_S + 30.0
            await client.get("/api/notifications")

    messages = [r.message for r in caplog.records if "WEB_CLIENT" in r.message]
    assert sum('event="connected"' in m for m in messages) == 1
    assert any('event="reconnected"' in m for m in messages)


def test_sweep_disconnected_clients_logs_and_drops_stale(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Entries past the idle threshold are logged and removed; fresh ones stay."""
    logger = logging.getLogger("test_sweep_clients")
    now = time.monotonic()
    last_seen = {"10.0.0.1": now - 300.0, "10.0.0.2": now - 5.0}

    with caplog.at_level(logging.INFO, logger=logger.name):
        sweep_disconnected_clients(last_seen, now, logger)

    assert "10.0.0.1" not in last_seen
    assert "10.0.0.2" in last_seen
    assert 'WEB_CLIENT event="disconnected" ip="10.0.0.1" idle_s=300' in caplog.text
    assert "10.0.0.2" not in caplog.text
