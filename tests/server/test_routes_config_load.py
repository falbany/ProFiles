"""Tests for config load/create endpoints."""

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
        title="Test Bench",
        search_dir=str(tmp_path),
        extensions=(".mttl",),
    )
    config.config_path = tmp_path / ".profiles"
    return ServerState(config=config, active_directory=tmp_path)


@pytest.mark.anyio
async def test_get_config_reports_path_and_existence(
    config_state: ServerState, tmp_path: Path
) -> None:
    config_path = tmp_path / ".profiles"
    config_path.write_text("version: 1\n", encoding="utf-8")
    config_state.config.config_path = config_path
    config_state.config_path = config_path

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_path"] == str(config_path)
    assert payload["config_exists"] is True
    assert payload["active_directory"] == str(tmp_path)


@pytest.mark.anyio
async def test_load_valid_file_replaces_state(config_state: ServerState, tmp_path: Path) -> None:
    config_path = tmp_path / "loaded.profiles"
    config_path.write_text(
        "version: 1\ndefaults:\n  search_dir: '/tmp/scan'\n",
        encoding="utf-8",
    )

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_path"] == str(config_path)
    assert payload["config_exists"] is True
    assert payload["active_directory"] == str(config_path.parent)


@pytest.mark.anyio
async def test_load_missing_file_is_400(config_state: ServerState, tmp_path: Path) -> None:
    missing = tmp_path / "missing.profiles"
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(missing)})

    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_load_non_config_suffix_is_400(config_state: ServerState, tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_text("nope", encoding="utf-8")
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(bad)})

    assert response.status_code == 400
    assert "config" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_load_g5_machine_config_wins(config_state: ServerState, tmp_path: Path) -> None:
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

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    assert response.json()["active_directory"] == str(scan_dir)


@pytest.mark.anyio
async def test_load_g5_falls_back_to_file_folder(config_state: ServerState, tmp_path: Path) -> None:
    config_dir = tmp_path / "fallback-dir"
    config_dir.mkdir()
    config_path = config_dir / ".profiles"
    config_path.write_text("version: 1\n", encoding="utf-8")

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    assert response.json()["active_directory"] == str(config_dir)


@pytest.mark.anyio
async def test_create_writes_starter(config_state: ServerState, tmp_path: Path) -> None:
    target_dir = tmp_path / "new-config-dir"
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/create", json={"directory": str(target_dir)})

    assert response.status_code == 200
    created = target_dir / ".profiles"
    assert created.exists()
    assert created.is_file()
    assert response.json()["config_path"] == str(created)


@pytest.mark.anyio
async def test_create_refuses_overwrite(config_state: ServerState, tmp_path: Path) -> None:
    target_dir = tmp_path / "occupied-dir"
    target_dir.mkdir()
    target = target_dir / ".profiles"
    target.write_text("existing", encoding="utf-8")

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/create", json={"directory": str(target_dir)})

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()
