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


# ---------------------------------------------------------------------------
# Per-user config path policy (issue #191)
# ---------------------------------------------------------------------------


class TestActiveConfigPathPolicy:
    """ServerState.active_config_path fallback rules from issue #191."""

    def test_never_returns_an_existing_directory(self, test_state, tmp_path: Path) -> None:
        """A directory (the ~/.profiles log-dir collision) is never the config."""
        collision = tmp_path / ".profiles"
        collision.mkdir()  # a DIRECTORY named like a config
        test_state.config_path = collision
        assert test_state.active_config_path() != collision
        assert not test_state.active_config_path().is_dir()

    def test_falls_back_to_default_config_path_when_unanchored(
        self, test_state, tmp_path: Path, isolated_user_home, monkeypatch
    ) -> None:
        """No recorded path → default_config_path (CWD-aware, issue #191).

        An informative empty CWD proposes in place; a System32-style CWD
        proposes the per-user ``~/.profiles/.profiles``.
        """
        test_state.config_path = None
        test_state.config.config_path = None

        empty_cwd = tmp_path / "empty-cwd"
        empty_cwd.mkdir()
        monkeypatch.chdir(empty_cwd)
        assert test_state.active_config_path() == empty_cwd / ".profiles"

        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()
        monkeypatch.chdir(system32)
        assert test_state.active_config_path() == (isolated_user_home / ".profiles" / ".profiles")

    def test_recorded_file_path_is_returned_as_is(self, test_state, tmp_path: Path) -> None:
        anchored = tmp_path / "sub" / ".profiles"
        anchored.parent.mkdir()
        anchored.write_text("version: 1\n", encoding="utf-8")
        test_state.config_path = anchored
        assert test_state.active_config_path() == anchored


@pytest.mark.anyio
async def test_get_config_prefills_home_for_uninformative_cwd(
    tmp_path: Path, isolated_user_home, monkeypatch
) -> None:
    """Empty-config first paint never scans System32 (issue #191).

    Given: a defaults-only config with NO candidate directories at all
    When: GET /api/config runs with a %SystemRoot%\\System32-style CWD
    Then: the active-directory fallback is the (isolated) home folder
    """
    config = AppConfig(title="Fresh Install", search_dir="", extensions=(".mttl",))
    config.config_path = tmp_path / "nowhere" / ".profiles"
    state = ServerState(config=config, active_directory=None)

    monkeypatch.setenv("SystemRoot", str(tmp_path))
    system32 = tmp_path / "System32"
    system32.mkdir()
    monkeypatch.chdir(system32)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["active_directory"] == str(isolated_user_home)
