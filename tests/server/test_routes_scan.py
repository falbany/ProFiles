"""Test scanner and actions endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
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
