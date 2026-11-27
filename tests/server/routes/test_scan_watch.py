"""Tests for the watch-mode route, helpers and status payload (#223, Tasks 3-4).

Covers ``POST /api/scan/watch`` (enable/disable lifecycle on the active
directory), the scan re-target / dead-root policy in ``execute_scan``
(Task 4), and the four watch fields ``scan_status_payload`` adds to the
SSE ``status`` event. The stream shape itself is unchanged — ``watch_seq``
reaching clients is covered end-to-end by the Task 8 hook tests.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.processing import watcher as watcher_module
from profiles.core.processing.watcher import DirectoryWatcher
from profiles.server.app import create_app
from profiles.server.routes import scan as scan_routes
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
        enable = await client.post("/api/scan/watch", json={"enabled": True, "recursive": False})
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
        # The enable path records the recursion intent too (Task 4 ruling):
        # posting recursive=False distinguishes the write from the field
        # default (True) — a later scan/enable mirrors the boundary here.
        assert test_state.watch_recursive is False


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


# --- Task 4: scan re-target and dead-root policy in execute_scan ---------


@pytest.mark.anyio
async def test_scan_to_new_directory_retargets_watcher(
    test_state: ServerState, tmp_path: Path
) -> None:
    """A scan onto a new directory re-targets the running watcher onto it."""
    dir_b = tmp_path / "releases"
    dir_b.mkdir()
    (dir_b / "tool_2.0_PROD.mttl").write_text("launchable")
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        first = test_state.watcher
        assert first is not None

        response = await client.post(
            "/api/scan",
            json={
                "directory": str(dir_b),
                "recursive": True,
                "extension": "",
                "filter_text": "",
            },
        )
        assert response.status_code == 200

    watcher = test_state.watcher
    assert watcher is not None
    # A full restart IS the re-target: the old poller is gone, exactly one
    # poller stays running and it now watches dir_b.
    assert watcher is not first
    assert not first.is_running
    assert watcher.is_running
    assert watcher.directory == dir_b
    assert test_state.watch_error is None
    assert test_state.watch_recursive is True


@pytest.mark.anyio
async def test_scan_to_missing_directory_stops_watch_with_error(
    test_state: ServerState, tmp_path: Path
) -> None:
    """A scan onto a dead root stops the watch with an explicit error."""
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        assert test_state.watcher is not None

        response = await client.post(
            "/api/scan",
            json={
                "directory": str(tmp_path / "nope"),
                "recursive": True,
                "extension": "",
                "filter_text": "",
            },
        )

    assert response.status_code == 200
    assert "warning" in response.json()
    assert test_state.watcher is None
    assert test_state.watch_error == "Watch stopped: directory does not exist"
    payload = scan_status_payload(test_state)
    assert payload["watching"] is False
    assert payload["watch_error"] == "Watch stopped: directory does not exist"


@pytest.mark.anyio
async def test_scan_records_recursive_intent(test_state: ServerState) -> None:
    """A non-recursive scan records its intent for the next enable."""
    directory = test_state.active_directory
    assert directory is not None
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        assert test_state.watch_recursive is True

        response = await client.post(
            "/api/scan",
            json={
                "directory": str(directory),
                "recursive": False,
                "extension": "",
                "filter_text": "",
            },
        )
        assert response.status_code == 200

    assert test_state.watch_recursive is False
    assert test_state.watcher is not None


@pytest.mark.anyio
async def test_scan_same_directory_and_intent_skips_restart(test_state: ServerState) -> None:
    """A rescan of the same directory with the same intent keeps the poller.

    Final-review refinement (#223): restarting the watcher on every
    rescan was needless churn (and every stop is a thread join) — the
    same-directory/same-intent scan must leave the running watcher
    untouched, by identity.
    """
    directory = test_state.active_directory
    assert directory is not None
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        first = test_state.watcher
        assert first is not None

        response = await client.post(
            "/api/scan",
            json={
                "directory": str(directory),
                "recursive": True,
                "extension": "",
                "filter_text": "",
            },
        )
        assert response.status_code == 200

    assert test_state.watcher is first
    assert first.is_running
    assert test_state.watch_recursive is True


@pytest.mark.anyio
async def test_scan_same_directory_changed_intent_restarts(test_state: ServerState) -> None:
    """A same-directory scan with a flipped recursion intent still re-targets.

    The intent change alters the effective boundary (depth/excludes), so
    the watcher must restart even though the root is unchanged.
    """
    directory = test_state.active_directory
    assert directory is not None
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        first = test_state.watcher
        assert first is not None

        response = await client.post(
            "/api/scan",
            json={
                "directory": str(directory),
                "recursive": False,
                "extension": "",
                "filter_text": "",
            },
        )
        assert response.status_code == 200

    assert test_state.watcher is not first
    assert not first.is_running
    assert test_state.watcher is not None
    assert test_state.watcher.is_running
    assert test_state.watch_recursive is False


def test_stale_error_cannot_clear_replacement(test_state: ServerState) -> None:
    """A stale watcher's error exit must not clear its replacement.

    The identity-checked teardown (:func:`_watcher_error_exit`) only
    clears the watch state when the failing watcher is still the active
    one — an outgoing poller finishing a failing walk after a
    replacement started must leave the replacement (and its error state)
    alone.
    """
    directory = test_state.active_directory
    assert directory is not None
    stale = DirectoryWatcher(directory, on_change=lambda: None, on_error=lambda _m: None)
    fresh = DirectoryWatcher(directory, on_change=lambda: None, on_error=lambda _m: None)
    test_state.watcher = fresh

    scan_routes._watcher_error_exit(test_state, stale, "stale boom")
    assert test_state.watcher is fresh
    assert test_state.watch_error is None

    scan_routes._watcher_error_exit(test_state, fresh, "fresh boom")
    assert test_state.watcher is None
    assert test_state.watch_error == "fresh boom"


def test_seq_lock_free_during_stop_join(
    test_state: ServerState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stop's thread join must never hold the cheap state lock.

    Regression pin for the final-review fix (#223): while
    ``_stop_watcher`` joins a poller stuck mid-walk, work needing
    ``_watch_lock`` (what a watcher's seq-bump callback does) must
    complete — holding the cheap lock across the join deadlocked it
    until the join timeout, freezing the caller for up to 5 seconds.
    """
    release = threading.Event()
    walk_entered = threading.Event()
    real_snapshot = watcher_module.snapshot_dir_mtimes

    def slow_snapshot(
        root: Path,
        exclude_dirs: Sequence[str] | None = None,
        *,
        max_depth: int | None = None,
    ) -> dict[str, float]:
        walk_entered.set()
        release.wait(timeout=5.0)
        return real_snapshot(root, exclude_dirs, max_depth=max_depth)

    monkeypatch.setattr(watcher_module, "snapshot_dir_mtimes", slow_snapshot)
    scan_routes._start_watcher(test_state, recursive=True)
    assert walk_entered.wait(timeout=5.0)

    stop_done = threading.Event()

    def _stop() -> None:
        scan_routes._stop_watcher(test_state)
        stop_done.set()

    stopper = threading.Thread(target=_stop, daemon=True)
    try:
        stopper.start()
        acquired = threading.Event()

        def _poke() -> None:
            with test_state._watch_lock:  # pylint: disable=protected-access
                acquired.set()

        poker = threading.Thread(target=_poke, daemon=True)
        poker.start()
        assert acquired.wait(timeout=2.0), "state lock held across the stop join"
    finally:
        release.set()
        stopper.join(timeout=10.0)
    assert stop_done.wait(timeout=10.0)


# --- #240 Task 2: the scan's derived depth/recursion feeds the watch -------


@pytest.fixture
def depth_state(tmp_path: Path) -> ServerState:
    """State rooted at the 4-level depth tree (same shape as the core tests).

    Creates ``root/{f1.mttl, l1/{f2.mttl, l2/{f3.mttl, l3/{f4.mttl}}}}``;
    ``config.max_search_depth`` stays at the default (10) so a depth pick
    is the only boundary in play.
    """
    l2 = tmp_path / "l1" / "l2"
    l3 = l2 / "l3"
    l3.mkdir(parents=True)
    (tmp_path / "f1.mttl").write_text("1")
    (tmp_path / "l1" / "f2.mttl").write_text("2")
    (l2 / "f3.mttl").write_text("3")
    (l3 / "f4.mttl").write_text("4")
    config = AppConfig(
        title="Test Bench",
        search_dir=str(tmp_path),
        extensions=(".mttl",),
    )
    state = ServerState(config=config, active_directory=tmp_path)
    # Safety net: never leak a poller thread out of a test.
    yield state
    if state.watcher is not None:
        state.watcher.stop()


@pytest.mark.anyio
async def test_scan_records_watch_depth_and_recursion(depth_state: ServerState) -> None:
    """A depth pick records the DERIVED recursion and the picked depth.

    max_depth=1 implies non-recursive (1 > 1 is False): the watch fields
    must reflect that derivation, not the raw payload (which carries no
    ``recursive`` at all here).
    """
    root = depth_state.active_directory
    assert root is not None
    app = create_app(depth_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/scan", json={"directory": str(root), "max_depth": 1})
        assert response.status_code == 200

    assert depth_state.watch_recursive is False
    assert depth_state.watch_max_depth == 1


@pytest.mark.anyio
async def test_legacy_scan_leaves_watch_depth_none(depth_state: ServerState) -> None:
    """A legacy checkbox scan records the intent but no depth pick."""
    root = depth_state.active_directory
    assert root is not None
    app = create_app(depth_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/scan", json={"directory": str(root), "recursive": False})
        assert response.status_code == 200

    assert depth_state.watch_recursive is False
    assert depth_state.watch_max_depth is None


@pytest.mark.anyio
async def test_depth_change_retargets_watcher(depth_state: ServerState) -> None:
    """A changed depth pick re-targets the watcher; the probe follows the pick.

    Same root, same directory, only the picked depth moves (1 → 3): the
    watcher must restart onto the boundary the scan walks — a root-only
    probe for the depth-1 pick (non-recursive → forced depth 0) and a
    depth-3 probe for the depth-3 pick.
    """
    root = depth_state.active_directory
    assert root is not None
    app = create_app(depth_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        first = depth_state.watcher
        assert first is not None

        # Depth pick 1: derived non-recursive — root-only probe.
        pick_one = await client.post("/api/scan", json={"directory": str(root), "max_depth": 1})
        assert pick_one.status_code == 200
        mid = depth_state.watcher

        # Depth pick 3: intent changed (3 != 1) — re-target, probe depth 3.
        pick_three = await client.post("/api/scan", json={"directory": str(root), "max_depth": 3})
        assert pick_three.status_code == 200

    assert depth_state.watch_max_depth == 3
    assert depth_state.watch_recursive is True
    watcher = depth_state.watcher
    assert watcher is not None
    assert watcher is not first
    assert watcher is not mid
    assert not first.is_running
    assert not mid.is_running
    assert watcher.is_running
    # The probe samples the depth the scan walks (protected attribute —
    # no public reader exists; same disable pattern as the state lock).
    assert watcher._max_depth == 3  # pylint: disable=protected-access
    assert mid._max_depth == 0  # pylint: disable=protected-access


@pytest.mark.anyio
async def test_watch_probe_honors_sentinel(depth_state: ServerState) -> None:
    """The ∞ sentinel re-targets the probe unclamped onto the walk boundary.

    The "unlimited" dropdown pick sends the int32 sentinel (2147483647);
    the API accepts it (``ge=1``, no upper bound) and the probe must carry
    it verbatim — clamping it to the config default (10) would let the
    watch miss changes below level 10 that a sentinel scan still walks.
    """
    root = depth_state.active_directory
    assert root is not None
    app = create_app(depth_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        enable = await client.post("/api/scan/watch", json={"enabled": True, "recursive": True})
        assert enable.status_code == 200
        assert depth_state.watcher is not None

        response = await client.post(
            "/api/scan", json={"directory": str(root), "max_depth": 2147483647}
        )
        assert response.status_code == 200

    assert depth_state.watch_max_depth == 2147483647
    assert depth_state.watch_recursive is True
    watcher = depth_state.watcher
    assert watcher is not None
    assert watcher.is_running
    # The probe samples the depth the scan walks (protected attribute —
    # no public reader exists; same disable pattern as the state lock).
    assert watcher._max_depth == 2147483647  # pylint: disable=protected-access
