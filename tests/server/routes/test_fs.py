"""Tests for filesystem browsing behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def fs_state(tmp_path: Path) -> ServerState:
    return ServerState(
        config=AppConfig(title="Test", search_dir=str(tmp_path)),
        active_directory=tmp_path,
    )


@pytest.mark.anyio
async def test_default_hides_hidden(fs_state: ServerState, tmp_path: Path) -> None:
    visible = tmp_path / "visible.txt"
    visible.write_text("ok", encoding="utf-8")
    (tmp_path / ".hidden.txt").write_text("hidden", encoding="utf-8")
    (tmp_path / ".git").mkdir()

    app = create_app(fs_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/fs/browse?path={tmp_path}")

    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert "visible.txt" in names
    assert ".hidden.txt" not in names
    assert ".git" not in names


@pytest.mark.anyio
async def test_include_hidden_reveals_only_configs(fs_state: ServerState, tmp_path: Path) -> None:
    (tmp_path / ".profiles").write_text("version: 1\n", encoding="utf-8")
    (tmp_path / ".hidden.profiles.yaml").write_text("version: 1\n", encoding="utf-8")
    (tmp_path / ".profiles.yml").write_text("version: 1\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".notes").write_text("n", encoding="utf-8")

    app = create_app(fs_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/fs/browse?path={tmp_path}&include_hidden=true")

    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert ".profiles" in names
    assert ".hidden.profiles.yaml" in names
    assert ".profiles.yml" in names
    assert ".git" not in names
    assert ".venv" not in names
    assert ".notes" not in names


@pytest.mark.anyio
async def test_hidden_config_flagged_as_config(fs_state: ServerState, tmp_path: Path) -> None:
    hidden = tmp_path / ".profiles"
    hidden.write_text("version: 1\n", encoding="utf-8")

    app = create_app(fs_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/fs/browse?path={tmp_path}&include_hidden=true")

    assert response.status_code == 200
    items = response.json()["items"]
    config_entry = next(item for item in items if item["name"] == ".profiles")
    assert config_entry["is_config"] is True
    assert config_entry["extension"] == ".profiles"


@pytest.mark.anyio
async def test_browse_keeps_symlink_form_of_requested_path(
    fs_state: ServerState, tmp_path: Path
) -> None:
    """The browsed directory is echoed back in the form the client sent.

    resolve() would canonicalize Windows mapped network drives (M:/...) to
    their UNC target, making the picker display paths the user never
    configured. A symlink stands in for that transformation on every
    platform.
    """
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "visible.txt").write_text("ok", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(real_dir, target_is_directory=True)

    app = create_app(fs_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/fs/browse?path={link}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_path"] == str(link)
    assert [item["path"] for item in payload["items"]] == [str(link / "visible.txt")]
