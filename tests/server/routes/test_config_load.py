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


VALID_DROP = "defaults:\n  title: Dropped\n"


class TestLoadContentEndpoint:
    """POST /api/config/load-content — session-only trial from dropped files."""

    @pytest.mark.anyio
    async def test_valid_content_swaps_config_and_rederives_directory(
        self, config_state: ServerState, tmp_path: Path
    ) -> None:
        # Baseline a real resolved path (mirrors the GET test): the shared
        # _config_response helper normalizes config_path, so "unchanged"
        # is only meaningful from a set value.
        config_state.config_path = tmp_path / ".profiles"
        path_before = config_state.config_path
        stale_dir = tmp_path / "stale-dir"
        stale_dir.mkdir()
        config_state.active_directory = stale_dir
        fresh_dir = tmp_path / "fresh-dir"
        fresh_dir.mkdir()
        content = (
            "version: 1\n"
            "configs:\n"
            "  machine:\n"
            "    match:\n"
            "      hostname: ['*']\n"
            "    scan: ['" + str(fresh_dir) + "']\n"
        )
        app = create_app(config_state)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/config/load-content",
                json={"filename": "my.profiles", "content": content},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["session_trial"] is True
        # Session-only: the attached config path stays untouched so restart
        # resolution is unaffected…
        assert config_state.config_path == path_before
        # …but the active directory IS re-derived from the dropped config,
        # exactly like a launch with it (issue #5). Keeping the stale
        # directory would merge the new config against the wrong directory.
        assert config_state.active_directory == fresh_dir
        assert body["active_directory"] == str(fresh_dir)

    @pytest.mark.anyio
    async def test_drop_merges_extensions_for_new_directory(
        self, config_state: ServerState, tmp_path: Path
    ) -> None:
        """Extensions/filters are merged for the NEW directory, not the old."""
        stale_dir = tmp_path / "stale-dir"
        stale_dir.mkdir()
        config_state.active_directory = stale_dir
        fresh_dir = tmp_path / "fresh-dir"
        fresh_dir.mkdir()
        content = (
            "version: 1\n"
            "defaults:\n"
            "  extensions: ['.global']\n"
            "configs:\n"
            "  machine:\n"
            "    match:\n"
            "      hostname: ['*']\n"
            "    scan: ['" + str(fresh_dir) + "']\n"
            "    extensions: ['.new']\n"
        )
        app = create_app(config_state)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/config/load-content",
                json={"filename": "my.profiles", "content": content},
            )

        assert response.status_code == 200
        body = response.json()
        # The per-directory override of the freshly derived directory wins —
        # against the stale directory the merge would have matched no
        # machine config and returned only the global default.
        assert body["extensions"][0] == ".new"
        assert ".global" in body["extensions"]

    @pytest.mark.anyio
    async def test_invalid_content_returns_400_and_keeps_config(
        self, config_state: ServerState
    ) -> None:
        original = config_state.config
        app = create_app(config_state)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/config/load-content",
                json={"filename": "broken.profiles", "content": "defaults: [unclosed"},
            )

        assert response.status_code == 400
        assert "broken.profiles" in response.json()["detail"]
        assert config_state.config is original

    @pytest.mark.anyio
    async def test_wrong_filename_rejected(self, config_state: ServerState) -> None:
        app = create_app(config_state)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/config/load-content",
                json={"filename": "notes.txt", "content": VALID_DROP},
            )

        assert response.status_code == 400

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "filename",
        ["my.profiles", ".profiles", "prod.profiles.yaml", "data.yml", "config.yaml"],
    )
    async def test_accepted_suffixes(self, config_state: ServerState, filename: str) -> None:
        app = create_app(config_state)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/config/load-content",
                json={"filename": filename, "content": VALID_DROP},
            )

        assert response.status_code == 200, f"{filename} should be accepted"
        assert response.json()["session_trial"] is True

    @pytest.mark.anyio
    async def test_no_disk_writes(
        self, config_state: ServerState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        before = sorted(str(p) for p in tmp_path.rglob("*"))
        app = create_app(config_state)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/config/load-content",
                json={"filename": "my.profiles", "content": VALID_DROP},
            )

        assert response.status_code == 200
        assert sorted(str(p) for p in tmp_path.rglob("*")) == before


@pytest.mark.anyio
async def test_load_yml_suffix_is_accepted(config_state: ServerState, tmp_path: Path) -> None:
    config_path = tmp_path / ".profiles.yml"
    config_path.write_text(
        "version: 1\ndefaults:\n  search_dir: '/tmp/scan'\n",
        encoding="utf-8",
    )

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_exists"] is True


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
async def test_load_resolves_search_dir_like_launch(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Issue #5 defect B: loading must resolve the directory like a launch.

    A config whose ``search_dir`` exists must activate that directory — not
    the folder that happens to contain the ``.profiles`` file.
    """
    config_dir = tmp_path / "config-home"
    config_dir.mkdir()
    search_dir = tmp_path / "project-a"
    search_dir.mkdir()
    config_path = config_dir / "my.profiles"
    config_path.write_text(
        "version: 1\ndefaults:\n  search_dir: '" + str(search_dir) + "'\n",
        encoding="utf-8",
    )

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    assert response.json()["active_directory"] == str(search_dir)


@pytest.mark.anyio
async def test_load_prefers_scan_dirs_over_config_file_folder(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Issue #5 defect B: existing scan dirs beat the config file's folder."""
    config_dir = tmp_path / "config-home"
    config_dir.mkdir()
    scan_dir = tmp_path / "machine-scan"
    scan_dir.mkdir()
    config_path = config_dir / "my.profiles"
    config_path.write_text(
        "version: 1\n"
        "configs:\n"
        "  machine:\n"
        "    match:\n"
        "      hostname: ['no-such-host']\n"
        "    scan: ['" + str(scan_dir) + "']\n",
        encoding="utf-8",
    )

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    # Even without a hostname match, the (fallback) machine config's scan
    # dir is preferred over the folder containing the .profiles file.
    assert response.json()["active_directory"] == str(scan_dir)


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
