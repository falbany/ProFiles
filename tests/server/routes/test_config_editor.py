"""Tests for POST /api/config/validate — validate editor content in memory."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.config.template import STARTER_CONFIG_TEMPLATE
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def config_state(tmp_path: Path) -> ServerState:
    config = AppConfig(
        title="Editor Session",
        search_dir=str(tmp_path),
        extensions=(".txt",),
    )
    config.config_path = tmp_path / ".profiles"
    return ServerState(config=config, active_directory=tmp_path)


@pytest.mark.anyio
async def test_validate_returns_valid_true_for_starter_template(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Verify a freshly rendered starter template validates with no issues."""
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/validate",
            json={
                "content": STARTER_CONFIG_TEMPLATE.format(cwd=str(tmp_path)),
                "filename": ".profiles",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "issues": []}


@pytest.mark.anyio
async def test_validate_returns_issues_for_bad_yaml(config_state: ServerState) -> None:
    """Verify invalid YAML yields a valid=False payload with an error issue."""
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/validate",
            json={"content": "defaults: [unclosed", "filename": ".profiles"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["issues"][0]["severity"] == "error"
    assert payload["issues"][0]["message"]


@pytest.mark.anyio
async def test_validate_does_not_change_state(config_state: ServerState) -> None:
    """Verify validation is read-only: the live configuration is untouched."""
    original = config_state.config
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/validate",
            json={"content": "defaults: [unclosed", "filename": ".profiles"},
        )

    assert response.status_code == 200
    assert config_state.config is original
