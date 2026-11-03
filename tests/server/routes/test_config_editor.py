"""Tests for the config editor endpoints: validate + content + save."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
from profiles.core.config.template import STARTER_CONFIG_TEMPLATE
from profiles.server.app import create_app
from profiles.server.routes.config import has_disk_path
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
async def test_content_flags_session_trial_after_live_drop(
    config_state: ServerState,
) -> None:
    """Pin the live flow: a dropped config must never expose a disk anchor.

    Ruling R4: ``_config_response`` re-records a resolved path into the
    state even for a drop, so trial detection must ride the explicit
    ``ServerState.session_trial`` flag — not path absence.
    """
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        drop = await client.post(
            "/api/config/load-content",
            json={"filename": "my.profiles", "content": "defaults:\n  title: Dropped\n"},
        )
        assert drop.status_code == 200
        assert drop.json()["session_trial"] is True

        assert has_disk_path(config_state) is False

        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_trial"] is True
    assert payload["config_path"] is None
    assert payload["filename"] == "Dropped"


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


@pytest.mark.anyio
async def test_save_refused_for_session_trial(config_state: ServerState, tmp_path: Path) -> None:
    """Verify save is refused (400) for a session trial and writes nothing.

    Given: A config applied from dropped content (no disk anchor)
    When: POST /save is called
    Then: 400 is returned and no file appears on disk
    """
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        drop = await client.post(
            "/api/config/load-content",
            json={"filename": "my.profiles", "content": "defaults:\n  title: Dropped\n"},
        )
        assert drop.status_code == 200
        assert has_disk_path(config_state) is False

        response = await client.post(
            "/api/config/save",
            json={"content": "defaults:\n  title: Saved\n"},
        )

    assert response.status_code == 400
    assert not (tmp_path / ".profiles").exists()


@pytest.mark.anyio
async def test_save_rejects_invalid_content_without_writing(tmp_path: Path) -> None:
    """Verify invalid content answers 400 with the issues list, file bytes unchanged.

    Given: A disk-anchored session with an on-disk config file
    When: POST /save is called with invalid YAML and no force flag
    Then: 400 with the issues list and the file bytes are untouched
    """
    config_path = tmp_path / ".profiles"
    file_text = 'defaults:\n  title: "On Disk"\n'
    config_path.write_text(file_text, encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save",
            json={"content": "defaults: [unclosed"},
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["severity"] == "error"
    assert detail[0]["message"]
    assert config_path.read_text(encoding="utf-8") == file_text


@pytest.mark.anyio
async def test_save_force_writes_invalid_content(tmp_path: Path) -> None:
    """Verify force=True writes invalid content to disk and answers SAVED.

    Given: A disk-anchored session and invalid YAML content
    When: POST /save is called with force=True
    Then: 200 SAVED and the file contains the invalid text verbatim
    """
    config_path = tmp_path / ".profiles"
    config_path.write_text('defaults:\n  title: "On Disk"\n', encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)
    invalid_text = "defaults: [unclosed"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save",
            json={"content": invalid_text, "force": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(config_path)
    assert config_path.read_text(encoding="utf-8") == invalid_text
    assert "config" in payload


@pytest.mark.anyio
async def test_save_writes_and_applies_valid_config(tmp_path: Path) -> None:
    """Verify a valid save writes the file and applies it to the live state.

    Given: A disk-anchored session and valid YAML content
    When: POST /save is called without force
    Then: 200 SAVED, the file is written, and ``state.config`` reflects
        the new content with the session-trial flag cleared
    """
    config_path = tmp_path / ".profiles"
    config_path.write_text('defaults:\n  title: "Old Title"\n', encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)
    valid_text = f"defaults:\n  title: Fresh Title\n  search_dir: '{tmp_path}'\n"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save",
            json={"content": valid_text},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(config_path)
    assert config_path.read_text(encoding="utf-8") == valid_text
    assert state.config.title == "Fresh Title"
    assert payload["config"]["title"] == "Fresh Title"
    assert state.session_trial is False
