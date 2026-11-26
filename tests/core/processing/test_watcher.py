"""Tests for profiles.core.processing.watcher — snapshot_dir_mtimes + DirectoryWatcher."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from profiles.core.processing import watcher as watcher_module
from profiles.core.processing.watcher import snapshot_dir_mtimes

# Fast cadence for the DirectoryWatcher tests (brief #223): an order of
# magnitude below the production defaults so the suite stays fast.
_FAST_BASE_INTERVAL_S: float = 0.05
_FAST_DEBOUNCE_S: float = 0.1
_FAST_MAX_INTERVAL_S: float = 0.3

# Poll-cycle settle time: after start()/retarget(), the asynchronous baseline
# walk lands within a couple of poll cycles (a walk is ~1 ms); mutating the
# tree earlier than that would bake the mutation into the baseline.
_SETTLE_S: float = 0.15


class CallbackRecorder:
    """Thread-safe recorder for watcher callbacks: Event + argument list.

    Watcher callbacks run on the watcher thread, so the fired signal is a
    ``threading.Event`` and the recorded arguments sit behind a lock.
    """

    def __init__(self) -> None:
        self.event = threading.Event()
        self._messages: list[str | None] = []
        self._lock = threading.Lock()

    def __call__(self, message: str | None = None) -> None:
        """Record one invocation (fits both ``on_change`` and ``on_error``)."""
        with self._lock:
            self._messages.append(message)
        self.event.set()

    def reset(self) -> None:
        """Forget every recorded call (multi-phase scenarios)."""
        with self._lock:
            self._messages.clear()
        self.event.clear()

    @property
    def call_count(self) -> int:
        """Number of recorded invocations."""
        with self._lock:
            return len(self._messages)

    @property
    def last_message(self) -> str | None:
        """Most recently recorded argument, if any."""
        with self._lock:
            return self._messages[-1] if self._messages else None


def make_fast_watcher(
    directory: Path,
    on_change: Callable[[], None],
    on_error: Callable[[str], None],
    *,
    exclude_dirs: Sequence[str] | None = None,
    max_depth: int | None = None,
) -> watcher_module.DirectoryWatcher:
    """Build a watcher with the fast test cadence (module constants above)."""
    return watcher_module.DirectoryWatcher(
        directory,
        exclude_dirs,
        max_depth=max_depth,
        debounce_s=_FAST_DEBOUNCE_S,
        base_interval_s=_FAST_BASE_INTERVAL_S,
        max_interval_s=_FAST_MAX_INTERVAL_S,
        on_change=on_change,
        on_error=on_error,
    )


def assert_fired(recorder: CallbackRecorder, timeout: float = 5.0) -> None:
    """Block until the recorder fires; fail the test after *timeout* seconds."""
    assert recorder.event.wait(timeout), "watcher callback did not fire in time"


def assert_not_fired(recorder: CallbackRecorder, timeout: float = 0.5) -> None:
    """Assert the recorder stays quiet for *timeout* seconds."""
    assert not recorder.event.wait(timeout), "watcher fired but nothing changed"


class TestSnapshotDirMtimes:
    """Tests for core.watcher.snapshot_dir_mtimes."""

    def test_snapshot_includes_root_and_subdirectories(self, tmp_path: Path) -> None:
        """The snapshot keys cover the root and every first-level subdirectory."""
        sub = tmp_path / "sub"
        sub.mkdir()

        snapshot = snapshot_dir_mtimes(tmp_path)

        assert set(snapshot) == {str(tmp_path), str(sub)}
        assert all(mtime > 0 for mtime in snapshot.values())

    def test_snapshot_excluded_dirs_pruned(self, tmp_path: Path) -> None:
        """An excluded directory (and its whole subtree) never enters the snapshot."""
        excluded_child = tmp_path / "node_modules" / "x"
        excluded_child.mkdir(parents=True)
        keep = tmp_path / "keep"
        keep.mkdir()

        snapshot = snapshot_dir_mtimes(tmp_path, exclude_dirs=("node_modules",))

        assert str(tmp_path / "node_modules") not in snapshot
        assert str(excluded_child) not in snapshot
        assert str(keep) in snapshot

    def test_snapshot_case_insensitive_exclusion(self, tmp_path: Path) -> None:
        """Pattern matching is case-insensitive, like the scan walk's excludes."""
        excluded = tmp_path / "node_modules"
        excluded.mkdir()
        (excluded / "f.txt").write_text("x")

        snapshot = snapshot_dir_mtimes(tmp_path, exclude_dirs=("Node_Modules",))

        assert str(excluded) not in snapshot

    def test_snapshot_max_depth_zero_root_only(self, tmp_path: Path) -> None:
        """max_depth=0 descends nowhere: the snapshot holds the root alone."""
        (tmp_path / "sub").mkdir()

        snapshot = snapshot_dir_mtimes(tmp_path, max_depth=0)

        assert set(snapshot) == {str(tmp_path)}

    def test_snapshot_max_depth_limits_descent(self, tmp_path: Path) -> None:
        """max_depth=1 keeps root + first-level dirs; deeper dirs are absent."""
        first = tmp_path / "a"
        second = first / "b"
        second.mkdir(parents=True)

        snapshot = snapshot_dir_mtimes(tmp_path, max_depth=1)

        assert set(snapshot) == {str(tmp_path), str(first)}
        assert str(second) not in snapshot

    def test_snapshot_missing_root_raises(self, tmp_path: Path) -> None:
        """A nonexistent root raises OSError (never a silent empty snapshot)."""
        with pytest.raises(OSError):
            snapshot_dir_mtimes(tmp_path / "nope")


class TestDirectoryWatcherBasics:
    """Lifecycle tests for core.watcher.DirectoryWatcher."""

    def test_baseline_does_not_fire(self, tmp_path: Path) -> None:
        """The first walk is a baseline: an untouched tree never fires."""
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        try:
            watcher.start()
            assert_not_fired(recorder)
        finally:
            watcher.stop()

    def test_start_is_idempotent(self, tmp_path: Path) -> None:
        """start() twice spawns one worker: no crash, the poller keeps running."""
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        try:
            watcher.start()
            watcher.start()  # Second call must be a no-op, not a crash.
            assert watcher.is_running
        finally:
            watcher.stop()
        assert not watcher.is_running

    def test_stop_is_idempotent_and_joins(self, tmp_path: Path) -> None:
        """stop() twice is safe: the worker joins and is_running goes False."""
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        watcher.start()
        watcher.stop()
        watcher.stop()  # Idempotent: no crash on an already-stopped watcher.
        assert not watcher.is_running

    def test_interval_s_within_clamps(self, tmp_path: Path) -> None:
        """The adaptive interval always sits inside [base_interval_s, max_interval_s]."""
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        try:
            watcher.start()
            assert _FAST_BASE_INTERVAL_S <= watcher.interval_s <= _FAST_MAX_INTERVAL_S
        finally:
            watcher.stop()

    def test_missing_root_errors_and_stops(self, tmp_path: Path) -> None:
        """A missing root reports one non-empty error and stops the worker."""
        change_recorder = CallbackRecorder()
        error_recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path / "nope", change_recorder, error_recorder)
        try:
            watcher.start()
            assert_fired(error_recorder)
            assert error_recorder.call_count == 1
            assert error_recorder.last_message  # Non-empty message.
            assert not watcher.is_running
            assert change_recorder.call_count == 0
        finally:
            watcher.stop()

    def test_retarget_rebaselines_without_firing(self, tmp_path: Path) -> None:
        """retarget() swaps the root and re-baselines: no fire, then watching."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(dir_a, recorder, recorder)
        try:
            watcher.start()
            watcher.retarget(dir_b)
            time.sleep(_SETTLE_S)  # Let dir_b's baseline walk land.
            assert_not_fired(recorder)
            (dir_b / "new.txt").write_text("x")
            assert_fired(recorder)
            assert watcher.directory == dir_b
        finally:
            watcher.stop()

    def test_retarget_discards_inflight_walk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A walk already in flight across retarget() is discarded, not baselined.

        Supplementary deterministic race coverage: a stale walk of the old root
        must never be stored as a baseline of the new one (which would fire on
        the new root's first diff with a stale reference).
        """
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(dir_a, recorder, recorder)
        walk_started = threading.Event()
        retarget_done = threading.Event()
        real_walk = snapshot_dir_mtimes

        def blocking_walk(
            root: Path,
            exclude_dirs: Sequence[str] | None = None,
            *,
            max_depth: int | None = None,
        ) -> dict[str, float]:
            result = real_walk(root, exclude_dirs, max_depth=max_depth)
            if root == dir_a:
                walk_started.set()
                retarget_done.wait(timeout=5.0)  # Hold the walk open.
            return result

        monkeypatch.setattr(watcher_module, "snapshot_dir_mtimes", blocking_walk)
        try:
            watcher.start()
            assert walk_started.wait(timeout=5.0)
            watcher.retarget(dir_b)
            retarget_done.set()  # Release the stale dir_a walk.
            assert_not_fired(recorder)
            (dir_b / "new.txt").write_text("x")
            assert_fired(recorder)
        finally:
            watcher.stop()


class TestDirectoryWatcherDetection:
    """Change-detection tests for core.watcher.DirectoryWatcher."""

    def test_file_create_fires_once(self, tmp_path: Path) -> None:
        """Creating one file fires exactly once, then stays quiet."""
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        try:
            watcher.start()
            time.sleep(_SETTLE_S)  # Baseline first, so the create is a real diff.
            (tmp_path / "new.txt").write_text("x")
            assert_fired(recorder)
            time.sleep(0.5)  # Quiet period well past the debounce window.
            assert recorder.call_count == 1
        finally:
            watcher.stop()

    def test_burst_coalesces_to_one_call(self, tmp_path: Path) -> None:
        """A 10-file burst is debounced into exactly one on_change call."""
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        try:
            watcher.start()
            time.sleep(_SETTLE_S)
            for index in range(10):
                (tmp_path / f"f{index}.txt").write_text("x")
            assert_fired(recorder)
            time.sleep(0.5)
            assert recorder.call_count == 1
        finally:
            watcher.stop()

    def test_delete_and_rename_fire(self, tmp_path: Path) -> None:
        """A deletion fires one watcher; a rename fires a second instance."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "gone.txt").write_text("x")
        (dir_b / "before.txt").write_text("x")
        delete_recorder = CallbackRecorder()
        rename_recorder = CallbackRecorder()
        watcher_a = make_fast_watcher(dir_a, delete_recorder, delete_recorder)
        watcher_b = make_fast_watcher(dir_b, rename_recorder, rename_recorder)
        try:
            watcher_a.start()
            watcher_b.start()
            time.sleep(_SETTLE_S)  # Both baselines must land first.
            (dir_a / "gone.txt").unlink()
            (dir_b / "before.txt").rename(dir_b / "after.txt")
            assert_fired(delete_recorder)
            assert_fired(rename_recorder)
        finally:
            watcher_a.stop()
            watcher_b.stop()

    def test_excluded_change_does_not_fire(self, tmp_path: Path) -> None:
        """A change inside an excluded subtree never fires (never even walked)."""
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder, exclude_dirs=("scratch",))
        try:
            watcher.start()
            time.sleep(_SETTLE_S)
            (scratch / "f.txt").write_text("x")
            assert_not_fired(recorder, timeout=1.0)
        finally:
            watcher.stop()

    def test_depth_zero_ignores_subdir_changes(self, tmp_path: Path) -> None:
        """max_depth=0 samples the root only: subdirectory changes never fire."""
        sub = tmp_path / "sub"
        sub.mkdir()
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder, max_depth=0)
        try:
            watcher.start()
            time.sleep(_SETTLE_S)
            (sub / "f.txt").write_text("x")
            assert_not_fired(recorder, timeout=1.0)
        finally:
            watcher.stop()

    def test_in_place_edit_not_detected(self, tmp_path: Path) -> None:
        """In-place content edits are invisible to the probe.

        Probe-only by design (spec non-goal): the watcher samples directory
        mtimes only, and rewriting a file's content does not touch the parent
        directory's mtime. This test exists so nobody "fixes" it by accident.
        """
        recorder = CallbackRecorder()
        watcher = make_fast_watcher(tmp_path, recorder, recorder)
        target = tmp_path / "a.txt"
        try:
            watcher.start()
            time.sleep(_SETTLE_S)
            target.write_text("first")  # Creation: a real change, must fire…
            assert_fired(recorder)
            recorder.reset()  # …then go quiet for the in-place edit.
            target.write_text("second")  # Content only: no directory mtime change.
            assert_not_fired(recorder, timeout=1.0)
        finally:
            watcher.stop()
