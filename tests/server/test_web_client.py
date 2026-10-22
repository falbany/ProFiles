"""Tests for the FastAPI application factory — client connection telemetry."""

from __future__ import annotations

import logging

import httpx
import pytest

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
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
