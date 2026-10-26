"""Tests for instance identity, config handoff, and notification endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState

TEST_TOKEN = "handoff-secret"


@pytest.fixture
def handoff_state(tmp_path: Path) -> ServerState:
    config = AppConfig(
        title="Instance A",
        search_dir=str(tmp_path),
        extensions=(".mttl",),
    )
    config.config_path = tmp_path / ".profiles"
    return ServerState(config=config, active_directory=tmp_path, instance_token=TEST_TOKEN)


@pytest.fixture
def forwarded_config(tmp_path: Path) -> Path:
    config_file = tmp_path / "other" / ".profiles"
    config_file.parent.mkdir()
    config_file.write_text("defaults:\n  title: Forwarded\n", encoding="utf-8")
    return config_file


def _client(state: ServerState) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=create_app(state)), base_url="http://test")


def _auth(token: str | None) -> dict[str, str]:
    return {**({"X-ProFiles-Token": token} if token else {})}


class TestIdentityEndpoint:
    """GET /api/instance/identity — the token-verified handshake."""

    @pytest.mark.anyio
    async def test_valid_token_confirms_identity(self, handoff_state: ServerState) -> None:
        async with _client(handoff_state) as client:
            response = await client.get("/api/instance/identity", headers=_auth(TEST_TOKEN))

        assert response.status_code == 200
        payload = response.json()
        assert payload["app"] == "ProFiles"
        assert payload["version"]
        assert isinstance(payload["pid"], int)

    @pytest.mark.anyio
    async def test_missing_token_is_rejected(self, handoff_state: ServerState) -> None:
        async with _client(handoff_state) as client:
            response = await client.get("/api/instance/identity")

        assert response.status_code == 403

    @pytest.mark.anyio
    async def test_wrong_token_is_rejected(self, handoff_state: ServerState) -> None:
        async with _client(handoff_state) as client:
            response = await client.get("/api/instance/identity", headers=_auth("not-the-secret"))

        assert response.status_code == 403


class TestHandoffEndpoint:
    """POST /api/instance/handoff — config forward from a second launch."""

    @pytest.mark.anyio
    async def test_applies_config_and_records_notification(
        self, handoff_state: ServerState, forwarded_config: Path
    ) -> None:
        async with _client(handoff_state) as client:
            response = await client.post(
                "/api/instance/handoff",
                json={"config_path": str(forwarded_config)},
                headers=_auth(TEST_TOKEN),
            )

        assert response.status_code == 200
        assert handoff_state.config.title == "Forwarded"
        assert handoff_state.config_path == forwarded_config.resolve()
        events = handoff_state.external_events_after(0)
        assert len(events) == 1
        assert events[0]["config_applied"] is True
        assert ".profiles" in events[0]["message"]

    @pytest.mark.anyio
    async def test_rejects_missing_token(
        self, handoff_state: ServerState, forwarded_config: Path
    ) -> None:
        async with _client(handoff_state) as client:
            response = await client.post(
                "/api/instance/handoff",
                json={"config_path": str(forwarded_config)},
            )

        assert response.status_code == 403
        assert handoff_state.config.title == "Instance A"  # untouched

    @pytest.mark.anyio
    async def test_rejects_nonexistent_config(
        self, handoff_state: ServerState, tmp_path: Path
    ) -> None:
        async with _client(handoff_state) as client:
            response = await client.post(
                "/api/instance/handoff",
                json={"config_path": str(tmp_path / "nope.profiles")},
                headers=_auth(TEST_TOKEN),
            )

        assert response.status_code == 400
        assert handoff_state.external_events_after(0) == []

    @pytest.mark.anyio
    async def test_rejects_non_config_file(
        self, handoff_state: ServerState, tmp_path: Path
    ) -> None:
        not_a_config = tmp_path / "readme.txt"
        not_a_config.write_text("hello", encoding="utf-8")
        async with _client(handoff_state) as client:
            response = await client.post(
                "/api/instance/handoff",
                json={"config_path": str(not_a_config)},
                headers=_auth(TEST_TOKEN),
            )

        assert response.status_code == 400


class TestNotificationsEndpoint:
    """GET /api/notifications — the frontend polling channel."""

    @pytest.mark.anyio
    async def test_returns_only_events_after_id(self, handoff_state: ServerState) -> None:
        handoff_state.record_external_event("config_handoff", "first", config_applied=True)
        second_id = handoff_state.record_external_event("info", "second")

        async with _client(handoff_state) as client:
            response = await client.get("/api/notifications?after=1")

        assert response.status_code == 200
        events = response.json()["events"]
        assert [event["id"] for event in events] == [second_id]
        assert events[0]["message"] == "second"

    @pytest.mark.anyio
    async def test_empty_when_no_events(self, handoff_state: ServerState) -> None:
        async with _client(handoff_state) as client:
            response = await client.get("/api/notifications?after=0")

        assert response.status_code == 200
        assert response.json()["events"] == []
