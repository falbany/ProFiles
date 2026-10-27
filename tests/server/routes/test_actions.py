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
async def test_open_config_uses_active_config_path(test_state: ServerState, tmp_path: Path) -> None:
    """The Config button must open the ACTIVE config file, not cwd/.profiles."""
    config_path = tmp_path / ".profiles.yaml"
    config_path.write_text("version: 1\n", encoding="utf-8")
    test_state.config_path = config_path
    test_state.config.config_path = config_path
    expected = ActionResult(status=ActionStatus.SUCCESS, message="opened", path=config_path)
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.open_config_file", return_value=expected
    ) as open_mock:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/actions/open-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert open_mock.call_args.args[0] == config_path


@pytest.mark.anyio
async def test_open_config_falls_back_to_core_search_when_path_unknown(
    test_state: ServerState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no recorded config path, the core search drives resolution."""
    test_state.config_path = None
    test_state.config.config_path = None
    config_path = tmp_path / ".profiles"
    config_path.write_text("version: 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    expected = ActionResult(status=ActionStatus.SUCCESS, message="opened", path=config_path)
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.open_config_file", return_value=expected
    ) as open_mock:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/actions/open-config")

    assert response.status_code == 200
    assert open_mock.call_args.args[0] == config_path


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
async def test_launch_forwards_config_and_logger(test_state: ServerState, tmp_path: Path) -> None:
    target = tmp_path / "app.mttl"
    target.write_text("dummy")
    test_state.config.search_dir = str(tmp_path)
    expected = ActionResult(status=ActionStatus.SUCCESS, message="Launched", path=target)
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.launch_selected_file", return_value=expected
    ) as launch_mock:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/actions/launch",
                json={"directory": str(tmp_path), "filename": "app.mttl", "release": "1.0"},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "Launched", "path": str(target)}
    launch_mock.assert_called_once()
    kwargs = launch_mock.call_args.kwargs
    assert kwargs.get("config") is test_state.config
    assert "logger" in kwargs


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


@pytest.mark.anyio
async def test_export_csv_saves_content_and_reports_path(
    test_state: ServerState, tmp_path: Path
) -> None:
    """The export endpoint delegates to core and reports the written path."""
    expected = ActionResult(
        status=ActionStatus.SUCCESS,
        message=f"CSV exported to {tmp_path / 'out.csv'}",
        path=tmp_path / "out.csv",
    )
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.save_csv_export", return_value=expected
    ) as save_mock:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/actions/export-csv",
                json={"content": "name,version\n", "filename": "profiles-export-x.csv"},
            )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": f"CSV exported to {tmp_path / 'out.csv'}",
        "path": str(tmp_path / "out.csv"),
    }
    assert save_mock.call_args.args == ("name,version\n", "profiles-export-x.csv")


@pytest.mark.anyio
async def test_export_csv_reports_failure_without_raising(test_state: ServerState) -> None:
    """A core-level failure is surfaced as a failed status, not an HTTP error."""
    expected = ActionResult(
        status=ActionStatus.FAILED,
        message="Could not write CSV export:\n/x/out.csv (Permission denied)",
        path=Path("/x/out.csv"),
    )
    app = create_app(test_state)

    with patch("profiles.server.routes.actions.actions.save_csv_export", return_value=expected):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/actions/export-csv",
                json={"content": "a,b\n", "filename": "out.csv"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
