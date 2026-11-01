"""Test config and filesystem routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def test_state(tmp_path: Path) -> ServerState:
    test_dir = tmp_path / "programs"
    test_dir.mkdir()
    (test_dir / "prog.mttl").write_text("dummy")
    config = AppConfig(
        title="Test Bench",
        search_dir=str(test_dir),
        extensions=(".mttl",),
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_get_config(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Bench"
        assert len(data["directories"]) == 1
        assert str(test_state.active_directory) == data["active_directory"]


@pytest.mark.anyio
async def test_get_config_uses_presets_for_selected_scan_directory(test_state: ServerState) -> None:
    test_state.config.configurations = [
        MachineConfiguration(
            name="production",
            scan=(str(test_state.active_directory),),
            extensions=("mttl OR mttx", "mttl"),
            filters=("", "tmp", "prod"),
        )
    ]
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config")

    assert response.status_code == 200
    data = response.json()
    assert data["extensions"] == ["mttl OR mttx", "mttl", ".mttl"]
    assert data["filters"] == ["", "tmp", "prod", "PROD", "DEV"]


@pytest.mark.anyio
async def test_select_directory(test_state: ServerState, tmp_path: Path) -> None:
    new_dir = tmp_path / "new_programs"
    new_dir.mkdir()
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/select-directory",
            json={"directory": str(new_dir)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_directory"] == str(new_dir)
        assert test_state.active_directory == new_dir


@pytest.mark.anyio
async def test_select_directory_returns_its_configuration_presets(
    test_state: ServerState, tmp_path: Path
) -> None:
    new_dir = tmp_path / "new_programs"
    new_dir.mkdir()
    test_state.config.configurations = [
        MachineConfiguration(
            name="new-programs",
            scan=(str(new_dir),),
            extensions=("exe",),
            filters=("installer",),
        )
    ]
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/select-directory",
            json={"directory": str(new_dir)},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["extensions"][0] == "exe"
    assert data["filters"][0] == "installer"


@pytest.mark.anyio
async def test_select_directory_keeps_symlink_form_of_user_path(
    test_state: ServerState, tmp_path: Path
) -> None:
    """The picked directory is stored as sent, not canonicalized.

    resolve() rewrites Windows mapped network drives (M:/...) to their UNC
    target; the active directory must keep the user's drive-letter form.
    A symlink stands in for that transformation on every platform.
    """
    real_dir = tmp_path / "real_programs"
    real_dir.mkdir()
    link = tmp_path / "link_programs"
    link.symlink_to(real_dir, target_is_directory=True)
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/select-directory",
            json={"directory": str(link)},
        )

    assert response.status_code == 200
    assert response.json()["active_directory"] == str(link)
    assert test_state.active_directory == link


@pytest.mark.anyio
async def test_fs_browse(test_state: ServerState, tmp_path: Path) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/fs/browse?path={tmp_path}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert any(item["name"] == "programs" and item["is_dir"] for item in data["items"])
