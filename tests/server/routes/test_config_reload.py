"""Tests for POST /api/config/reload — re-read the attached config from disk."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def config_state(tmp_path: Path) -> ServerState:
    config = AppConfig(
        title="Stale In-Memory",
        search_dir=str(tmp_path),
        extensions=(".old",),
    )
    config.config_path = tmp_path / ".profiles"
    return ServerState(config=config, active_directory=tmp_path)


@pytest.mark.anyio
async def test_reload_rereads_file_from_disk(config_state: ServerState, tmp_path: Path) -> None:
    config_path = tmp_path / ".profiles"
    config_path.write_text(
        "version: 1\ndefaults:\n  title: Fresh From Disk\n  extensions: ['.newext']\n",
        encoding="utf-8",
    )
    config_state.config.config_path = config_path
    config_state.config_path = config_path

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/reload")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reloaded"] is True
    assert payload["title"] == "Fresh From Disk"
    assert ".newext" in payload["extensions"]
    assert ".old" not in payload["extensions"]
    assert config_state.config.title == "Fresh From Disk"


@pytest.mark.anyio
async def test_reload_reruns_directory_resolution(
    config_state: ServerState, tmp_path: Path
) -> None:
    config_dir = tmp_path / "config-dir"
    config_dir.mkdir()
    scan_dir = tmp_path / "machine-scan"
    scan_dir.mkdir()
    config_path = config_dir / ".profiles"
    config_path.write_text(
        "version: 1\n"
        "configs:\n"
        "  machine:\n"
        "    match:\n"
        "      hostname: ['*']\n"
        "    scan: ['" + str(scan_dir) + "']\n",
        encoding="utf-8",
    )
    config_state.config.config_path = config_path
    config_state.config_path = config_path

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/reload")

    assert response.status_code == 200
    assert response.json()["active_directory"] == str(scan_dir)


@pytest.mark.anyio
async def test_reload_missing_file_degrades_gracefully(
    config_state: ServerState, tmp_path: Path
) -> None:
    missing = tmp_path / "gone.profiles"
    config_state.config.config_path = missing
    config_state.config_path = missing
    original = config_state.config

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/reload")

    assert response.status_code == 200
    payload = response.json()
    assert payload["reloaded"] is False
    assert payload["config_exists"] is False
    # The in-memory config is kept — no silent wipe to defaults.
    assert config_state.config is original


@pytest.mark.anyio
async def test_reload_invalid_file_returns_400_and_keeps_config(
    config_state: ServerState, tmp_path: Path
) -> None:
    config_path = tmp_path / ".profiles"
    config_path.write_text("defaults: [unclosed", encoding="utf-8")
    config_state.config.config_path = config_path
    config_state.config_path = config_path
    original = config_state.config

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/reload")

    assert response.status_code == 400
    assert "detail" in response.json()
    assert config_state.config is original


@pytest.mark.anyio
async def test_reload_reports_theme_change(config_state: ServerState, tmp_path: Path) -> None:
    config_path = tmp_path / ".profiles"
    config_path.write_text(
        "version: 1\ndefaults:\n  theme: 'light'\n",
        encoding="utf-8",
    )
    config_state.config.config_path = config_path
    config_state.config_path = config_path

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/reload")

    assert response.status_code == 200
    assert response.json()["theme"] == "light"
