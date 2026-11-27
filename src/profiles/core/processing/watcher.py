"""Directory-mtime snapshot and polling watcher for watch mode (#223).

Foundation module for the dependency-free polling watcher: a cheap walk
that stats *directories only* — create/delete/rename all mutate a parent
directory's mtime, which is the dominant change pattern on the target
workload (probe-only by design; in-place content edits are not detected).

:func:`snapshot_dir_mtimes` is the pure walk; :class:`DirectoryWatcher`
polls it from a daemon thread with burst debouncing and an adaptive
interval. Pure, UI-free, server-free core logic.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path

from profiles.utils.file_utils import _is_excluded

# Watcher cadence defaults (spec-decided values; consumed by the polling
# DirectoryWatcher that lives in this same module).
DEFAULT_DEBOUNCE_S: float = 0.5
DEFAULT_BASE_INTERVAL_S: float = 1.0
DEFAULT_MAX_INTERVAL_S: float = 5.0

# Longest single sleep of the poller: upper bound on stop() responsiveness.
_SLEEP_SLICE_S: float = 0.1


def snapshot_dir_mtimes(
    root: Path,
    exclude_dirs: Sequence[str] | None = None,
    *,
    max_depth: int | None = None,
) -> dict[str, float]:
    """Snapshot the mtime of *root* and every non-excluded subdirectory.

    The walk is top-down and prunes excluded subtrees *before* descending,
    so an excluded tree is never even walked. Exclusion semantics match the
    scan walk's ``exclude_dirs``: case-insensitive fnmatch on directory
    basenames (see :func:`profiles.utils.file_utils._is_excluded`).

    Args:
        root: Directory to snapshot. Must exist — a missing root raises.
        exclude_dirs: Glob patterns (``*``, ``?``, ``[seq]``) matched
            case-insensitively against directory basenames to prune from
            the walk. ``None`` or empty excludes nothing.
        max_depth: Levels of subdirectories to descend **below root**
            (``0`` = root only; ``None`` = unlimited). Directories beyond
            the budget are absent from the snapshot.

    Returns:
        ``{directory_path: mtime}`` keyed by ``str()`` of the path, with
        the root itself always included.

    Raises:
        OSError: *root* does not exist or cannot be statted.
    """
    patterns = tuple(exclude_dirs or ())
    root_stat = root.stat()  # A missing root raises before any walk.
    snapshot: dict[str, float] = {str(root): root_stat.st_mtime}
    root_parts = len(root.parts)
    for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
        # Directories listed by this yield sit one level below *dirpath*.
        depth = len(Path(dirpath).parts) - root_parts
        if max_depth is not None and depth >= max_depth:
            # Depth budget exhausted: one level too deep to stat, so clear
            # (which also stops the descent).
            dirnames.clear()
        else:
            dirnames[:] = [d for d in dirnames if not _is_excluded(d, patterns)]
        for name in dirnames:
            sub = Path(dirpath) / name
            snapshot[str(sub)] = sub.stat().st_mtime
    return snapshot


class DirectoryWatcher:
    """Debounced, adaptive poller of directory mtimes on a daemon thread.

    Each cycle walks :func:`snapshot_dir_mtimes` and compares it with the
    previous walk. On a diff the debounce window starts (the snapshot is
    kept in flight, not committed); :attr:`on_change` fires exactly once
    per burst, when a walk comes back unchanged after ``debounce_s`` of
    quiet, and the quiet snapshot is committed. The first walk after
    :meth:`start` (or :meth:`retarget`) is the baseline and never fires.
    The inter-walk interval adapts to the measured walk duration, clamped
    to ``[base_interval_s, max_interval_s]``.

    Callbacks run on the watcher thread and must stay cheap and
    non-blocking by contract (the server side only bumps a counter under
    its own lock); they are guarded so a raising callback can never kill
    the poller, and dispatched outside the watcher's lock so they may call
    back into the watcher (e.g. ``stop()``).

    Args:
        directory: Root to watch. May be missing at start: the baseline
            walk then fails twice in a row, ``on_error`` fires once and
            the poller stops.
        exclude_dirs: Glob patterns pruned from the walk (never sampled,
            never fired upon) — same semantics as the scan walk.
        max_depth: Levels of subdirectories to sample below the root
            (``0`` = root only; ``None`` = unlimited).
        debounce_s: Quiet time required before a burst announces once.
        base_interval_s: Minimum inter-walk interval.
        max_interval_s: Maximum inter-walk interval.
        on_change: Invoked without arguments once per debounced burst.
        on_error: Invoked with a message string when two consecutive walk
            attempts fail; the poller stops afterwards.
    """

    def __init__(  # pylint: disable=too-many-arguments  # plan-fixed signature (#223)
        self,
        directory: Path,
        exclude_dirs: Sequence[str] | None = None,
        *,
        max_depth: int | None = None,
        debounce_s: float = DEFAULT_DEBOUNCE_S,
        base_interval_s: float = DEFAULT_BASE_INTERVAL_S,
        max_interval_s: float = DEFAULT_MAX_INTERVAL_S,
        on_change: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._exclude_dirs: tuple[str, ...] = tuple(exclude_dirs or ())
        self._max_depth = max_depth
        self._debounce_s = debounce_s
        self._base_interval_s = base_interval_s
        self._max_interval_s = max_interval_s
        self._on_change = on_change
        self._on_error = on_error
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # State shared with retarget()/the properties — guarded by _lock:
        self._directory = directory
        self._snapshot: dict[str, float] | None = None  # None: next walk baselines.
        self._last_change: float | None = None  # Last seen diff (monotonic).
        self._interval_s = base_interval_s  # Current adaptive interval.
        self._running = False

    def start(self) -> None:
        """Start the poller thread (idempotent while already running)."""
        with self._lock:
            if self._running:
                return
            self._running = True
        self._stop_event.clear()
        thread = threading.Thread(target=self._run, name="profiles-dirwatcher", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop the poller and join it (idempotent; safe from callbacks)."""
        self._stop_event.set()
        thread = self._thread
        # A callback may stop() from the watcher thread itself: joining the
        # current thread is impossible — the loop is already unwinding via
        # the stop event.
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(5.0)

    def retarget(self, directory: Path) -> None:
        """Watch *directory* instead, re-baselining without firing.

        Drops the snapshot under the lock: the next walk is a fresh
        baseline, so the swap itself never announces a change.
        """
        with self._lock:
            self._directory = directory
            self._snapshot = None
            self._last_change = None

    @property
    def directory(self) -> Path:
        """The directory currently watched."""
        with self._lock:
            return self._directory

    @property
    def interval_s(self) -> float:
        """Current adaptive inter-walk interval (clamped), in seconds."""
        with self._lock:
            return self._interval_s

    @property
    def is_running(self) -> bool:
        """Whether the poller thread is alive and polling."""
        with self._lock:
            return self._running

    def _run(self) -> None:
        try:
            self._poll()
        finally:
            with self._lock:
                self._running = False

    def _poll(self) -> None:
        interval = self._base_interval_s
        while not self._stop_event.is_set():
            interval = self._walk_cycle()  # First pass: the baseline walk.
            if self._sleep_slices(interval):
                break  # Stop requested (or the poller failed terminally).

    def _sleep_slices(self, duration_s: float) -> bool:
        """Sleep toward the deadline in slices, watching the stop event.

        Args:
            duration_s: Total sleep budget in seconds.

        Returns:
            True when a stop was requested (the caller must unwind).
        """
        deadline = time.monotonic() + duration_s
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            self._stop_event.wait(min(remaining, _SLEEP_SLICE_S))
        return True

    def _walk_cycle(self) -> float:
        """One walk + debounce integration; returns the next sleep interval."""
        with self._lock:
            directory = self._directory
        started = time.monotonic()
        try:
            current = self._walk(directory)
        except OSError:
            try:
                current = self._walk(directory)  # One retry on a transient error.
            except OSError as error:
                self._fail(f"DirectoryWatcher stopped: cannot walk {directory} ({error})")
                return self._interval_s
        self._update_interval(time.monotonic() - started)
        self._integrate(directory, current, time.monotonic())
        return self._interval_s

    def _walk(self, directory: Path) -> dict[str, float]:
        return snapshot_dir_mtimes(directory, self._exclude_dirs, max_depth=self._max_depth)

    def _update_interval(self, walk_duration_s: float) -> None:
        """Adapt the interval to the measured walk duration (clamped)."""
        # Slow trees are polled less aggressively: schedule 3x the last walk
        # duration, clamped to the configured [base, max] window.
        interval = min(self._max_interval_s, max(self._base_interval_s, 3.0 * walk_duration_s))
        with self._lock:
            self._interval_s = interval

    def _integrate(self, walked: Path, current: dict[str, float], now: float) -> None:
        """Debounce state machine; fires ``on_change`` outside the lock."""
        with self._lock:
            if walked != self._directory:
                return  # Stale walk across a retarget: discard it.
            previous = self._snapshot
            if previous is None:
                self._snapshot = current  # Baseline: store, never fire.
                return
            if current != previous:
                # Change in flight: keep the latest walk as the diff
                # reference and (re)start the debounce window; the commit
                # is deferred until a walk repeats unchanged.
                self._snapshot = current
                self._last_change = now
                return
            if self._last_change is None or now - self._last_change < self._debounce_s:
                return  # No pending change, or still inside the debounce window.
            self._last_change = None  # Consume the burst: fire exactly once.
        # The quiet snapshot is already committed (== the diff reference);
        # announce outside the lock so callbacks may call back in.
        self._safe_callback(self._on_change)

    def _fail(self, message: str) -> None:
        """Terminal walk failure: stop the poller, then report the error."""
        self._stop_event.set()
        with self._lock:
            self._running = False  # is_running False *before* on_error fires.
        self._safe_callback(self._on_error, message)

    def _safe_callback(self, callback: Callable[..., None], *args: object) -> None:
        """Invoke a callback, containing failures so the poller survives.

        Callbacks are cheap and non-blocking by contract; a raising one
        must never kill the watcher thread.
        """
        with suppress(Exception):
            callback(*args)
