"""Test scanner and actions endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.server.app import create_app
from profiles.server.state import ServerState


@pytest.fixture
def test_state(tmp_path: Path) -> ServerState:
    test_dir = tmp_path / "programs"
    test_dir.mkdir()
    (test_dir / "app_1.0_PROD.mttl").write_text("launchable")
    config = AppConfig(
        title="Test Bench",
        search_dir=str(test_dir),
        extensions=(".mttl",),
    )
    return ServerState(config=config, active_directory=test_dir)


@pytest.mark.anyio
async def test_scan_and_get_results(test_state: ServerState) -> None:
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger scan
        post_resp = await client.post(
            "/api/scan",
            json={"extension": ".mttl", "filter_text": "", "recursive": True},
        )
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        assert post_data["count"] >= 1

        # Fetch cached results
        get_resp = await client.get("/api/scan/results")
        assert get_resp.status_code == 200
        results = get_resp.json()
        assert len(results["items"]) >= 1
        assert results["items"][0]["filename"] == "app_1.0_PROD.mttl"


@pytest.mark.anyio
async def test_scan_uses_config_exclusions_and_columns(test_state: ServerState) -> None:
    test_state.config.search_exclude_dirs = ("build",)
    test_state.config.search_exclude_files = ("*.tmp",)
    test_state.config.column_names = ("File", "Version")
    test_state.config.column_headers = ("File", "Version")
    test_state.config.columns = {"File": object(), "Version": object()}

    app = create_app(test_state)
    with patch(
        "profiles.server.routes.scan.scanner.scan_and_process_dynamic", return_value=[]
    ) as scan_mock:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/scan",
                json={
                    "directory": str(test_state.active_directory),
                    "extension": ".mttl",
                    "filter_text": "",
                    "recursive": True,
                },
            )

    assert resp.status_code == 200
    kwargs = scan_mock.call_args.kwargs
    assert kwargs["exclude_dirs"] == ("build",)
    assert kwargs["exclude_files"] == ("*.tmp",)
    assert kwargs["column_names"] == ("File", "Version")
    assert kwargs["columns"] == test_state.config.columns


@pytest.mark.anyio
async def test_scan_applies_exclusions_from_config_matching_scan_path(
    test_state: ServerState,
) -> None:
    excluded_by_config = test_state.active_directory / "release_tmp.mttl"
    excluded_by_config.write_text("exclude", encoding="utf-8")
    excluded_by_config2 = test_state.active_directory / "release.bak"
    excluded_by_config2.write_text("exclude", encoding="utf-8")
    excluded_dir = test_state.active_directory / "tmp"
    excluded_dir.mkdir()
    (excluded_dir / "nested.mttl").write_text("exclude", encoding="utf-8")
    test_state.config.search_exclude_dirs = ("tmp",)
    test_state.config.search_exclude_files = ("*.bak",)
    test_state.config.configurations = [
        MachineConfiguration(
            name="programs",
            scan=(str(test_state.active_directory),),
            search_exclude_files=("*tmp*", "*.bak"),
        )
    ]
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        scan_response = await client.post(
            "/api/scan",
            json={"recursive": True},
        )
        results_response = await client.get("/api/scan/results")

    assert scan_response.status_code == 200
    assert results_response.status_code == 200
    filenames = [item["filename"] for item in results_response.json()["items"]]
    assert "release_tmp.mttl" not in filenames
    assert "release.bak" not in filenames
    assert "nested.mttl" not in filenames
    assert "app_1.0_PROD.mttl" in filenames


@pytest.mark.anyio
async def test_actions_hash(test_state: ServerState, tmp_path: Path) -> None:
    target_file = tmp_path / "programs" / "app_1.0_PROD.mttl"
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/actions/hash",
            json={"file_path": str(target_file), "algorithm": "md5"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "hash" in data
        assert len(data["hash"]) == 32  # MD5 hex length


@pytest.mark.anyio
@pytest.mark.parametrize(("launch_result", "expected_status"), [(True, 200), (False, 400)])
async def test_launch_with_args_handles_boolean_result(
    test_state: ServerState,
    tmp_path: Path,
    launch_result: bool,
    expected_status: int,
) -> None:
    target_file = tmp_path / "programs" / "app_1.0_PROD.mttl"
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.launch_file_with_args",
        return_value=launch_result,
    ) as launch_mock:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/actions/launch-with-args",
                json={"file_path": str(target_file), "args": "--preview"},
            )

    assert response.status_code == expected_status
    launch_mock.assert_called_once_with(target_file.resolve(), "--preview")
