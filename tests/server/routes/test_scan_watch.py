"""Tests for the watch-mode route, helpers and status payload (#223, Task 3).

Covers ``POST /api/scan/watch`` (enable/disable lifecycle on the active
directory) and the four watch fields ``scan_status_payload`` adds to the
SSE ``status`` event. The stream shape itself is unchanged — ``watch_seq``
reaching clients is covered end-to-end by the Task 8 hook tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.processing.watcher import DirectoryWatcher
from profiles.server.app import create_app
from profiles.server.routes.scan import scan_status_payload
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
    state = ServerState(config=config, active_directory=test_dir)
    # Safety net: never leak a poller thread out of a test.
    yield state
    if state.watcher is not None:
        state.watcher.stop()


@pytest.mark.anyio
async def test_watch_enable_requires_directory(tmp_path: Path) -> None:
    """Enabling watch with no active directory is a 400, not a crash."""
    config = AppConfig(title="Test Bench", search_dir=str(tmp_path))
    state = ServerState(config=config, active_directory=None)
    app = create_app(state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})

    assert response.status_code == 400
    assert response.json()["detail"] == "Active directory is not set"
    assert state.watcher is None


@pytest.mark.anyio
async def test_watch_enable_start_roundtrip(test_state: ServerState) -> None:
    """Enable starts a running watcher reporting its interval; disable stops it."""
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        enable = await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        assert enable.status_code == 200
        assert enable.json()["watching"] is True
        assert isinstance(enable.json()["interval_s"], float)
        assert enable.json()["interval_s"] >= 1.0

        watcher = test_state.watcher
        assert watcher is not None
        assert watcher.is_running

        disable = await client.post("/api/scan/watch", json={"enabled": False})
        assert disable.status_code == 200
        assert disable.json()["watching"] is False
        assert disable.json()["interval_s"] is None
        assert test_state.watcher is None
        # stop() joins the poller thread before returning.
        assert not watcher.is_running


@pytest.mark.anyio
async def test_watch_disable_idempotent(test_state: ServerState) -> None:
    """Disabling with no watcher running is a harmless 200."""
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/scan/watch", json={"enabled": False})

    assert response.status_code == 200
    assert response.json()["watching"] is False
    assert response.json()["interval_s"] is None


@pytest.mark.anyio
async def test_watch_enable_replaces_existing_watcher(test_state: ServerState) -> None:
    """A second enable stops the first watcher: exactly one poller stays running."""
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        first = test_state.watcher
        assert first is not None

        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        second = test_state.watcher

    assert second is not None
    assert second is not first
    assert not first.is_running
    assert second.is_running


def test_status_payload_watch_fields(test_state: ServerState) -> None:
    """The status payload carries the four watch fields."""
    default = scan_status_payload(test_state)
    assert default["watching"] is False
    assert default["watch_interval_s"] is None
    assert default["watch_seq"] == 0
    assert default["watch_error"] is None

    test_state.watch_seq = 3
    directory = test_state.active_directory
    assert directory is not None
    # A REAL stopped watcher (no mocks): built, never started.
    stopped = DirectoryWatcher(
        directory,
        on_change=lambda: None,
        on_error=lambda message: None,
    )
    test_state.watcher = stopped

    payload = scan_status_payload(test_state)
    assert payload["watching"] is True
    assert payload["watch_seq"] == 3
    assert payload["watch_interval_s"] == stopped.interval_s
    assert payload["watch_error"] is None


@pytest.mark.anyio
async def test_watch_error_cleared_on_enable(test_state: ServerState) -> None:
    """A stale watch_error from a previous run is cleared by a fresh enable."""
    test_state.watch_error = "x"
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        assert response.status_code == 200

    assert test_state.watch_error is None
