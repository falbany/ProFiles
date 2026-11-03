"""Tests for the config editor endpoints: validate + content."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
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


@pytest.mark.anyio
async def test_content_returns_active_config_text(tmp_path: Path) -> None:
    """Verify GET /content returns the on-disk text of the active config file."""
    config_path = tmp_path / ".profiles"
    file_text = 'version: 1\ndefaults:\n  title: "On Disk"\n'
    config_path.write_text(file_text, encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == file_text
    assert payload["filename"] == ".profiles"
    assert payload["config_path"] == str(config_path)
    assert payload["session_trial"] is False


@pytest.mark.anyio
async def test_content_flags_session_trial(tmp_path: Path) -> None:
    """Verify a config with no recorded disk path is reported as a session trial."""
    config = AppConfig(
        title="Trial Session",
        search_dir=str(tmp_path),
        extensions=(".txt",),
    )
    # A config applied from dropped content carries no recorded disk path:
    # neither the state nor the AppConfig tracks the file it came from.
    config.config_path = None
    state = ServerState(config=config, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_trial"] is True
    assert payload["config_path"] is None


@pytest.mark.anyio
async def test_content_for_missing_file_returns_text_or_error(
    config_state: ServerState,
) -> None:
    """Pinned behavior: a recorded-but-deleted config file answers 404."""
    missing_path = config_state.active_config_path()
    assert not missing_path.exists()

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/content")

    assert response.status_code == 404
    assert str(missing_path) in response.json()["detail"]
