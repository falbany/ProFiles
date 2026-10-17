"""Test scanner and actions endpoints."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.core.processing.scanner import ScannedFileDynamic
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
async def test_scan_results_contain_hook_metadata(test_state: ServerState) -> None:
    from profiles.core.config.models import WorkflowStep

    test_state.config.launch_hooks = {"*.mttl": (WorkflowStep(action="run", content="echo hook"),)}
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/scan",
            json={"extension": ".mttl", "filter_text": "", "recursive": True},
        )
        get_resp = await client.get("/api/scan/results")
        assert get_resp.status_code == 200
        items = get_resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["has_hook"] is True
        assert items[0]["hook_pattern"] == "*.mttl"


@pytest.mark.anyio
async def test_late_scan_does_not_replace_newer_scan_results(
    test_state: ServerState,
    tmp_path: Path,
) -> None:
    first_directory = test_state.active_directory
    assert first_directory is not None
    second_directory = tmp_path / "other-programs"
    second_directory.mkdir()
    first_started = threading.Event()
    release_first = threading.Event()

    def delayed_scan(*, directories: str, **_: object) -> list[ScannedFileDynamic]:
        directory = Path(directories)
        if directory == first_directory:
            first_started.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("First scan was not released")
            filename = "first.mttl"
        else:
            filename = "second.mttl"
        return [
            ScannedFileDynamic(
                path=directory / filename,
                column_values={},
                rel_path=filename,
            )
        ]

    app = create_app(test_state)
    with patch(
        "profiles.server.routes.scan.scanner.scan_and_process_dynamic",
        side_effect=delayed_scan,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_task = asyncio.create_task(
                client.post(
                    "/api/scan",
                    json={"directory": str(first_directory), "recursive": True},
                )
            )
            try:
                assert await asyncio.to_thread(first_started.wait, timeout=5)
                second_response = await client.post(
                    "/api/scan",
                    json={"directory": str(second_directory), "recursive": True},
                )
                assert second_response.status_code == 200
            finally:
                release_first.set()

            first_response = await first_task
            results_response = await client.get("/api/scan/results")

    assert first_response.status_code == 200
    assert results_response.json()["items"][0]["filename"] == "second.mttl"


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
async def test_results_sorted_naturally_by_column(test_state: ServerState, tmp_path: Path) -> None:
    """Sorting reorders the whole result set, with digits compared numerically."""
    scan_state = ServerState(config=test_state.config, active_directory=test_state.active_directory)
    scan_state.cached_results = [
        ScannedFileDynamic(
            path=tmp_path / f"item_{n}_prod.mttl", column_values={"Type": "prod"}, rel_path=""
        )
        for n in (10, 2, 1)
    ]

    app = create_app(scan_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ascending = await client.get("/api/scan/results", params={"sort_by": "Type"})
        # "prod" is identical on every row, so the tie-break falls back to the
        # file name and 1 < 2 < 10 (natural, not lexicographic).
        assert [r["filename"] for r in ascending.json()["items"]] == [
            "item_1_prod.mttl",
            "item_2_prod.mttl",
            "item_10_prod.mttl",
        ]
        assert ascending.json()["sort_by"] == "Type"
        assert ascending.json()["sort_dir"] == "asc"

        descending = await client.get(
            "/api/scan/results", params={"sort_by": "Type", "sort_dir": "desc"}
        )
        assert [r["filename"] for r in descending.json()["items"]] == [
            "item_10_prod.mttl",
            "item_2_prod.mttl",
            "item_1_prod.mttl",
        ]
        assert descending.json()["sort_dir"] == "desc"


@pytest.mark.anyio
async def test_results_sort_applies_before_paging(test_state: ServerState, tmp_path: Path) -> None:
    """A page taken from a sorted list keeps the same order as the full list."""
    scan_state = ServerState(config=test_state.config, active_directory=test_state.active_directory)
    scan_state.cached_results = [
        ScannedFileDynamic(
            path=tmp_path / f"file_{i}.mttl", column_values={"Type": f"t{i}"}, rel_path=""
        )
        for i in range(5)
    ]

    app = create_app(scan_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        full = await client.get("/api/scan/results", params={"sort_by": "Type", "sort_dir": "desc"})
        page = await client.get(
            "/api/scan/results",
            params={"sort_by": "Type", "sort_dir": "desc", "offset": 1, "limit": 2},
        )

    full_names = [r["filename"] for r in full.json()["items"]]
    assert full_names == ["file_4.mttl", "file_3.mttl", "file_2.mttl", "file_1.mttl", "file_0.mttl"]
    assert [r["filename"] for r in page.json()["items"]] == full_names[1:3]
    assert page.json()["has_more"] is True


@pytest.mark.anyio
async def test_results_unknown_sort_column_keeps_scan_order(test_state: ServerState) -> None:
    """An unknown column is ignored rather than emptying or reordering the list."""
    scan_state = ServerState(config=test_state.config, active_directory=test_state.active_directory)
    scan_state.cached_results = [
        ScannedFileDynamic(
            path=test_state.active_directory / "b.mttl", column_values={}, rel_path=""
        ),
        ScannedFileDynamic(
            path=test_state.active_directory / "a.mttl", column_values={}, rel_path=""
        ),
    ]

    app = create_app(scan_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/scan/results", params={"sort_by": "Nope"})

    filenames = [r["filename"] for r in response.json()["items"]]
    assert filenames == ["b.mttl", "a.mttl"]
    assert "sort_by" not in response.json()


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
