"""Tests for file action endpoints used by the web context menu."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.actions import ActionResult, ActionStatus
from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def test_state() -> ServerState:
    return ServerState(config=AppConfig(title="Test Bench"))


@pytest.mark.anyio
async def test_reveal_selects_file_and_returns_action_result(
    test_state: ServerState, tmp_path: Path
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample")
    expected = ActionResult(status=ActionStatus.SUCCESS, message="Revealed", path=target)
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.reveal_in_file_manager", return_value=expected
    ) as reveal:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/actions/reveal", json={"file_path": str(target)})

    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Revealed", "path": str(target)}
    reveal.assert_called_once_with(target.resolve())


@pytest.mark.anyio
async def test_reveal_returns_failure_instead_of_false_success(
    test_state: ServerState, tmp_path: Path
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample")
    expected = ActionResult(status=ActionStatus.FAILED, message="Explorer failed", path=target)
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.reveal_in_file_manager", return_value=expected
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/actions/reveal", json={"file_path": str(target)})

    assert response.status_code == 500
    assert response.json()["detail"] == "Explorer failed"


@pytest.mark.anyio
async def test_file_metadata_endpoint_returns_properties(
    test_state: ServerState, tmp_path: Path
) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample")
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/actions/metadata", json={"file_path": str(target)})

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "sample.txt"
    assert data["path"] == str(target)
    assert data["size_bytes"] == 6
    assert "modified" in data
    assert "created" in data


@pytest.mark.anyio
async def test_delete_endpoint_removes_file(test_state: ServerState, tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("sample")
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/actions/delete", json={"file_path": str(target)})

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert not target.exists()
