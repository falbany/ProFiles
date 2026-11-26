# Watch Mode (#223) + Selection Preservation (#218) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rescan the list when the watched directory changes (dependency-free polling watcher, local + SMB/NFS) instead of re-walking it on a timer, and preserve the row selection across every refresh.

**Architecture:** A core `DirectoryWatcher` polls **directory mtimes only** (probe; no per-file snapshot) on a daemon thread, debounces bursts (~500 ms) and adapts its interval to measured walk duration. The FastAPI server owns one shared watcher, exposes `POST /api/scan/watch`, and announces changes as a monotone `watch_seq` counter on the existing 1 s SSE status tick. The web client reconciles its toggle from the SSE payload and triggers the existing `scanWith` generation protocol; selection follows the previously selected `path`, restoring it across page boundaries via a new `find_path` lookup on `/results`.

**Tech Stack:** Python 3.11 stdlib only (threading, os.walk) for the watcher; FastAPI route additions; React 19 + TypeScript hooks; vitest for web tests.

**Spec:** `docs/superpowers/specs/2026-11-26-watch-mode-design.md` — read it before starting; this plan argues from it. Also read `AGENTS.md` and `tests/AGENTS.md`.

## Global Constraints

- **No new dependencies** — Python runtime deps and npm deps both stay frozen (spec non-goal).
- Watcher constants (spec-decided, tunable only as a whole): `debounce_s=0.5`, `base_interval_s=1.0`, `max_interval_s=5.0`; next interval = `max(base_interval_s, 3 × measured_walk_duration)` clamped to `max_interval_s`.
- SSE status payload gains exactly: `watching: bool`, `watch_interval_s: float | None`, `watch_seq: int`, `watch_error: str | None`.
- `POST /api/scan/watch` request: `{"enabled": bool, "recursive": bool}`; response: `{"watching": bool, "interval_s": float | None}`.
- `find_path` response: `{"count": int, "offset": int}`; `offset: -1` = path gone.
- Exact copy: dead-root `watch_error` = `"Watch stopped: directory does not exist"`; toasts: enable `"Watching for changes."`, disable `"Watch disabled."`, error toast shows the raw `watch_error` text.
- Probe-only is intentional: in-place file edits must NOT trigger a rescan (spec non-goal; pinned by a test).
- `watch_error` fires at most one toast per distinct message (no toast spam).
- Python style: `from __future__ import annotations`, full type hints (no `Any`), docstrings on public functions; ruff + pylint 10/10 expected; pytest cov gate 85 %.
- Web: colocated vitest files (`X.test.ts` beside `X.ts`), `npx tsc --noEmit` clean.
- SSE stream tests must go through a real bound uvicorn port — never through `ASGITransport` (it buffers the stream; see existing pattern at `tests/server/routes/test_scan.py:458`).
- Branch: `feat/223-watch-mode`. Commits: conventional, referencing `(#223)` or `(#218)`.

## Review Focus

Failure modes the spec implies that a person will hit; each is pinned by the named test:

1. **Share unmounts while watching** — the UI must un-toggle with exactly one toast, never keep a dead "Watching" badge. → `test_missing_root_errors_and_stops` (Task 2), `test_scan_to_missing_directory_stops_watch_with_error` (Task 5), reconcile-toast test (Task 8).
2. **A station writes a 200-file burst** — exactly one rescan per burst, not 200. → `test_burst_coalesces_to_one_call` (Task 2).
3. **Changes inside excluded subtrees or below the scan depth** — no rescan, and the walk never descends there. → `test_snapshot_excluded_dirs_pruned` (Task 1), `test_depth_zero_ignores_subdir_changes` (Task 2).
4. **In-place edit of an existing file** — no rescan; this is the documented probe-only limitation, and the test exists so nobody "fixes" it by accident. → `test_in_place_edit_not_detected` (Task 2).
5. **A refresh that shrinks or reorders the list** — the selection must never silently land on a different file; a vanished selection becomes an inert "nothing selected". → `followSelection` tests (Task 9).

---

### Task 1: Core — directory-mtime snapshot

**Files:**
- Create: `src/profiles/core/processing/watcher.py`
- Test: `tests/core/processing/test_watcher.py`

**Interfaces:**
- Produces: `DEFAULT_DEBOUNCE_S: float = 0.5`, `DEFAULT_BASE_INTERVAL_S: float = 1.0`, `DEFAULT_MAX_INTERVAL_S: float = 5.0`; `snapshot_dir_mtimes(root: Path, exclude_dirs: Sequence[str] | None = None, *, max_depth: int | None = None) -> dict[str, float]`. `max_depth` = levels of subdirectories to descend **below root** (`0` = root only; `None` = unlimited).

- [ ] **Step 1: Create the feature branch and commit the spec**

```bash
git checkout -b feat/223-watch-mode
git add docs/superpowers/specs/2026-11-26-watch-mode-design.md docs/superpowers/plans/2026-11-26-watch-mode.md
git commit -m "docs: watch mode + selection preservation design (#223)"
```

- [ ] **Step 2: Write the failing tests** in `tests/core/processing/test_watcher.py` (new `__init__.py` already exists in that dir; style per `tests/AGENTS.md` — `from __future__ import annotations`, class-grouped):

  - `test_snapshot_includes_root_and_subdirectories` — tree `root/` + `root/sub/` → snapshot keys are `str(root)` and `str(root/"sub")`, values positive floats.
  - `test_snapshot_excluded_dirs_pruned` — `exclude_dirs=("node_modules",)` with `root/node_modules/x/` and `root/keep/` → `node_modules` absent, `keep` present.
  - `test_snapshot_case_insensitive_exclusion` — pattern `"Node_Modules"` still prunes `node_modules` (`_is_excluded` lowercases; import it from `profiles.utils.file_utils`).
  - `test_snapshot_max_depth_zero_root_only` — `max_depth=0` → exactly one key (root).
  - `test_snapshot_max_depth_limits_descent` — `max_depth=1` → root + first-level dirs, `root/a/b/` absent.
  - `test_snapshot_missing_root_raises` — nonexistent root raises `OSError`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/core/processing/test_watcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'profiles.core.processing.watcher'`

- [ ] **Step 4: Implement `snapshot_dir_mtimes`**

`os.walk(root, topdown=True)`; prune with `dirs[:] = [d for d in dirs if not _is_excluded(d, exclude_dirs or ())]`; enforce `max_depth` by comparing the relative part count and clearing `dirs` (stop descending, still stat); `entry.stat().st_mtime` per directory; `root.stat()` first so a missing root raises. Reuse `_is_excluded` from `profiles.utils.file_utils` (direct from-import — same semantics as the scan walk: case-insensitive fnmatch, bare `"*"` excludes everything).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/core/processing/test_watcher.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/profiles/core/processing/watcher.py tests/core/processing/test_watcher.py
git commit -m "feat(core): directory-mtime snapshot for the watch-mode probe (#223)"
```

### Task 2: Core — `DirectoryWatcher` thread

**Files:**
- Modify: `src/profiles/core/processing/watcher.py`
- Test: `tests/core/processing/test_watcher.py` (same file, new test classes)

**Interfaces:**
- Consumes: `snapshot_dir_mtimes`, the three constants (Task 1).
- Produces:

```python
class DirectoryWatcher:
    def __init__(
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
    ) -> None: ...
    def start(self) -> None: ...  # idempotent; spawns daemon thread
    def stop(self) -> None: ...  # idempotent; sets stop event + join(5)
    def retarget(
        self, directory: Path
    ) -> None: ...  # swap root, drop snapshot (re-baseline, no fire)
    @property
    def directory(self) -> Path: ...
    @property
    def interval_s(self) -> float: ...  # current adaptive interval (clamped)
    @property
    def is_running(self) -> bool: ...
```

- [ ] **Step 1: Write the failing tests** (new classes `TestDirectoryWatcherBasics`, `TestDirectoryWatcherDetection`; all tests construct the watcher with fast constants `base_interval_s=0.05, debounce_s=0.1, max_interval_s=0.3`; helpers: a `CallbackRecorder` with `threading.Event` + call list, `assert_fired(rec, timeout=5.0)` → `rec.event.wait(timeout)`, `assert_not_fired(rec, timeout=0.5)`):

  - `test_baseline_does_not_fire` — start on an empty tmp dir → `assert_not_fired` (0.5 s window).
  - `test_file_create_fires_once` — create one file after start → `assert_fired`, then after 0.5 s quiet assert call count == 1.
  - `test_burst_coalesces_to_one_call` — create 10 files in a loop → `assert_fired` → after 0.5 s quiet, count == 1.
  - `test_delete_and_rename_fire` — delete a file → fires; create a second watcher instance, rename a file → fires.
  - `test_excluded_change_does_not_fire` — `exclude_dirs=("scratch",)`; write into `root/scratch/f.txt` → `assert_not_fired` (1.0 s window — the excluded tree must never even be walked).
  - `test_depth_zero_ignores_subdir_changes` — `max_depth=0`; write into `root/sub/f.txt` → `assert_not_fired` (1.0 s).
  - `test_in_place_edit_not_detected` — create `a.txt`, let it fire once, reset the recorder, rewrite `a.txt` content in place → `assert_not_fired` (1.0 s). Comment on the test: *probe-only by design (spec non-goal)*.
  - `test_stop_is_idempotent_and_joins` — `stop(); stop()` → `is_running` False.
  - `test_retarget_rebaselines_without_firing` — start on dir A, `retarget(dirB)` → `assert_not_fired`; then create a file in dirB → `assert_fired`; `watcher.directory == dirB`.
  - `test_missing_root_errors_and_stops` — construct on `tmp_path/"nope"`, start → `on_error` called once with a non-empty message, `is_running` False.
  - `test_interval_s_within_clamps` — after start, `base_interval_s <= interval_s <= max_interval_s`.
  - `test_start_is_idempotent` — `start(); start()` → exactly one worker (assert via `is_running` and no crash).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/processing/test_watcher.py -v`
Expected: new tests FAIL with `AttributeError` (no `DirectoryWatcher`); Task 1 tests still PASS.

- [ ] **Step 3: Implement `DirectoryWatcher`**

Thread loop (`threading.Thread(daemon=True)`): first walk is the baseline (store, never fires). Each cycle: sleep toward the deadline in ≤0.1 s slices watching the `threading.Event` (responsive stop); walk; measure with `time.monotonic()`; `interval_s = min(max_interval_s, max(base_interval_s, 3 * walk_duration))`. Diff = dict inequality vs previous snapshot. On diff: record `last_change = now`, keep polling (snapshot NOT stored yet); fire `on_change()` once when a walk comes back unchanged AND `now - last_change >= debounce_s`, then store the snapshot. Errors: a walk raising `OSError` is retried once; the second consecutive failure calls `on_error(message)` and ends the thread (a missing root at baseline errors immediately). `retarget` swaps `directory` and clears the snapshot under a lock. Guard all callbacks — nothing else; callbacks stay cheap and non-blocking by contract (server side only bumps a counter).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/processing/test_watcher.py -v`
Expected: PASS (if a timing test flakes locally, widen windows, never narrow assertions)

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/processing/watcher.py tests/core/processing/test_watcher.py
git commit -m "feat(core): DirectoryWatcher — debounced, adaptive directory-mtime probe (#223)"
```

### Task 3: Server — watch state, `POST /api/scan/watch`, status payload

**Files:**
- Modify: `src/profiles/server/state.py` (the `ServerState` dataclass, fields after `scan_progress_count` at `state.py:59`)
- Modify: `src/profiles/core/processing/scanner.py` (public boundary helper near `_resolve_scan_config` at `scanner.py:121`)
- Modify: `src/profiles/server/routes/scan.py` (route after `execute_scan`; payload in `scan_status_payload` at `scan.py:266`)
- Test: `tests/server/routes/test_scan_watch.py` (new), `tests/core/processing/test_scanner_boundary.py` (new)

**Interfaces:**
- Consumes: `DirectoryWatcher` (Task 2), `snapshot_dir_mtimes` not needed here.
- Produces:
  - `ServerState` fields: `watcher: DirectoryWatcher | None = None`, `watch_seq: int = 0`, `watch_error: str | None = None`, `watch_recursive: bool = True`, `_watch_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)`.
  - `scanner.effective_search_boundary(directory: str, config: AppConfig | None, *, recursive: bool) -> tuple[int, tuple[str, ...]]` — `(max_depth, exclude_dirs)`; `recursive=False` → `(0, excludes)`; else `(depth, excludes)` where both come from the existing `_resolve_scan_config` merge (`active.max_search_depth` else `config.max_search_depth` else `DEFAULT_MAX_SEARCH_DEPTH`).
  - Route `POST /api/scan/watch` → `{"watching": bool, "interval_s": float | None}`.
  - `scan_status_payload(state)` gains the four Global-Constraint fields.
  - Module-level helpers in `routes/scan.py`: `_start_watcher(state: ServerState, *, recursive: bool) -> None` (stop any existing watcher; resolve boundary via `effective_search_boundary(str(state.active_directory), state.config, recursive=recursive)`; build `DirectoryWatcher(state.active_directory, exclude_dirs, max_depth=depth, on_change=..., on_error=...)` where the two callbacks are closures capturing *state* — `on_change` = `with state._watch_lock: state.watch_seq += 1` (cheap, non-blocking — the watcher-thread contract), `on_error` = stop and record the message; `start()`; store on state; clear `watch_error`) and `_stop_watcher(state: ServerState, *, error: str | None = None) -> None` (stop + `state.watcher = None`; set or clear `watch_error`).

- [ ] **Step 1: Write the failing tests**

  `tests/core/processing/test_scanner_boundary.py`:
  - `test_boundary_recursive_uses_config_depth_and_excludes` — `AppConfig(search_dir=..., max_search_depth=4, search_exclude_dirs=("node_modules",))` → `(4, ("node_modules",))`.
  - `test_boundary_non_recursive_is_depth_zero` — same config, `recursive=False` → `(0, ("node_modules",))`.

  `tests/server/routes/test_scan_watch.py` (local fixture mirroring `test_scan.py:35` — `ServerState(config=AppConfig(...), active_directory=test_dir)` over a tmp dir with one file):
  - `test_watch_enable_requires_directory` — `ServerState` with `active_directory=None` → POST `{"enabled": true, "recursive": true}` → 400, detail `"Active directory is not set"`.
  - `test_watch_enable_start_roundtrip` — enable → 200 `{"watching": True}`, `interval_s` is a float ≥ 1.0; `state.watcher` is not None and `is_running`; then disable → `{"watching": False}`, `state.watcher is None`, thread joined.
  - `test_watch_disable_idempotent` — disable with no watcher → 200 `{"watching": False}`.
  - `test_watch_enable_replaces_existing_watcher` — enable twice → still exactly one running watcher (old one stopped: `not old.is_running`).
  - `test_status_payload_watch_fields` — call `scan_status_payload(state)` directly: default keys `watching=False, watch_interval_s=None, watch_seq=0, watch_error=None`; after `state.watch_seq = 3` and storing a real **stopped** `DirectoryWatcher` (`directory=tmp dir`, no-op callbacks, never started) → `watching=True`, seq 3. (No SSE stream test here — the stream shape is unchanged; `watch_seq` reaching clients is covered end-to-end by the Task 8 hook tests.)
  - `test_watch_error_cleared_on_enable` — `state.watch_error = "x"` → enable → `watch_error is None`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/core/processing/test_scanner_boundary.py tests/server/routes/test_scan_watch.py -v`
Expected: FAIL (`effective_search_boundary` / route / payload fields missing)

- [ ] **Step 3: Implement** — `effective_search_boundary` in `scanner.py` (thin wrapper over `_resolve_scan_config`; `recursive=False` forces depth 0); the `ServerState` fields; the route, helpers, and payload fields in `routes/scan.py` (import `DirectoryWatcher` from core and `effective_search_boundary` from scanner — server→core imports are the established direction; the route returns `{"watching": state.watcher is not None, "interval_s": state.watcher.interval_s if state.watcher else None}`)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/processing/test_scanner_boundary.py tests/server/routes/test_scan_watch.py -v && pylint src/profiles/server/routes/scan.py src/profiles/core/processing/scanner.py`
Expected: PASS, pylint ≥ 9

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/state.py src/profiles/server/routes/scan.py src/profiles/core/processing/scanner.py tests/server/routes/test_scan_watch.py tests/core/processing/test_scanner_boundary.py
git commit -m "feat(server): POST /api/scan/watch + watch fields on the SSE status payload (#223)"
```

### Task 4: Server — re-target and dead-root policy in `execute_scan`

**Files:**
- Modify: `src/profiles/server/routes/scan.py` (`execute_scan`, lines 53–54 where `active_directory` is assigned)
- Test: `tests/server/routes/test_scan_watch.py` (same file)

**Interfaces:**
- Consumes: `_start_watcher` / `_stop_watcher` (Task 3).
- Produces: scan behavior — every scan that sets `active_directory` from the payload also records `state.watch_recursive = payload.recursive` and re-targets a running watcher; a scan onto a missing directory stops the watcher with `watch_error = "Watch stopped: directory does not exist"`.

- [ ] **Step 1: Write the failing tests** (append to `tests/server/routes/test_scan_watch.py`)

  - `test_scan_to_new_directory_retargets_watcher` — enable watch on `dirA` → POST `/api/scan` `{"directory": str(dirB), "recursive": true, "extension": "", "filter_text": ""}` (dirB exists with a file) → response 200; `state.watcher` is not None, `is_running`, `state.watcher.directory == dirB`, `watch_error is None`, `watch_recursive is True`.
  - `test_scan_to_missing_directory_stops_watch_with_error` — enable watch on `dirA` → POST scan `{"directory": str(tmp_path/"nope"), ...}` → response carries `warning`; `state.watcher is None`, `state.watch_error == "Watch stopped: directory does not exist"`; status payload `watching=False`.
  - `test_scan_records_recursive_intent` — POST scan with `recursive: false` while watching → `state.watch_recursive is False` (the next enable mirrors the non-recursive boundary).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/server/routes/test_scan_watch.py -v`
Expected: the three new tests FAIL (watcher unchanged / error unset)

- [ ] **Step 3: Implement** in `execute_scan` right after the `if payload.directory:` assignment block: set `state.watch_recursive = payload.recursive`, then `if state.watcher is not None:` → `if not state.active_directory.exists(): _stop_watcher(state, error="Watch stopped: directory does not exist")` else `_start_watcher(state, recursive=payload.recursive)` (a full restart IS the re-target: re-baselines the snapshot and re-resolves the per-directory boundary — the spec's owner call on builder question Q2/Q3).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/server/routes/test_scan_watch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/routes/scan.py tests/server/routes/test_scan_watch.py
git commit -m "feat(server): watch re-targets on directory change, stops on dead root (#223)"
```

### Task 5: Server — `find_path` on `/api/scan/results`

**Files:**
- Modify: `src/profiles/server/routes/scan.py` (`get_scan_results` signature at `scan.py:202`, early return after the sorted list at `scan.py:227`)
- Test: `tests/server/routes/test_scan_find_path.py` (new; reuse the `_row`/fixture pattern from `tests/server/routes/test_scan.py:21-47`)

**Interfaces:**
- Produces: `GET /api/scan/results?find_path=<abs path>&sort_by=<col>&sort_dir=<asc|desc>` → `{"count": int, "offset": int}` (`offset: -1` = not found). `find_path` short-circuits before item serialization.

- [ ] **Step 1: Write the failing tests**

  - `test_find_path_returns_offset_in_scan_order` — seed cache with rows `a.mttl`, `b.mttl`, `c.mttl` → `find_path` of `b`'s path → `{"offset": 1, "count": 3}`, response has no `items` key.
  - `test_find_path_respects_sort` — `sort_by` on a column where sorting reverses the rows → offset reflects the *sorted* position.
  - `test_find_path_missing_returns_minus_one` — unknown path → `{"offset": -1}`.
  - `test_find_path_attribute_sort_uses_typed_order` — rows with `FileAttrs` sorted by an attribute-backed column → offset follows the typed order (mirrors `_sorted_results`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/server/routes/test_scan_find_path.py -v`
Expected: FAIL (parameter ignored, `items` always present)

- [ ] **Step 3: Implement** — add `find_path: str | None = Query(default=None)`; after `cached, sort_applied = _sorted_results(...)`, when `find_path` is not None return `{"count": total, "offset": next((i for i, row in enumerate(cached) if str(getattr(row, "path", "")) == find_path), -1)}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/server/routes/test_scan_find_path.py tests/server/routes/test_scan.py -v`
Expected: PASS (existing `/results` tests unchanged)

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/routes/scan.py tests/server/routes/test_scan_find_path.py
git commit -m "feat(server): find_path offset lookup on scan results (#218)"
```

### Task 6: Web — shared SSE status feed

**Files:**
- Create: `src/profiles/web/src/hooks/useScanStatusFeed.ts`
- Create: `src/profiles/web/src/hooks/useScanStatusFeed.test.ts`
- Modify: `src/profiles/web/src/hooks/useScanProgress.ts` (refactor onto the feed; external API unchanged)

**Interfaces:**
- Produces:

```ts
export interface ScanStatusTick {
  inProgress: boolean;
  progress: number | null;
  directory: string;
  watching: boolean;
  watchIntervalS: number | null;
  watchSeq: number | null;
  watchError: string | null;
}
export const INITIAL_TICK: ScanStatusTick;      // watching:false, nulls elsewhere
export function useScanStatusFeed(): ScanStatusTick;
```

  `useScanProgress(active: boolean): ScanProgress` — same contract as today (progress hidden while `!active`), but the EventSource is the feed's and stays open for the app lifetime.

- [ ] **Step 1: Write the failing test** `useScanStatusFeed.test.ts` — a minimal `MockEventSource` class (static registry of instances; `addEventListener(event, handler)`; `emit(event, dataJson)`; `close()` tracked). Stub `global.EventSource`. Use `@testing-library/react` `renderHook` + `act`:
  - `test_parses_full_status_payload` — emit the snake_case JSON `{"in_progress":true,"progress":7,"directory":"/d","watching":true,"watch_interval_s":1.5,"watch_seq":4,"watch_error":null}` → hook state matches camelCase fields.
  - `test_partial_payload_defaults` — emit only `{"progress":3}` → `watching:false`, `watchSeq:null`, `inProgress:false`.
  - `test_malformed_payload_keeps_last_good_state` — emit valid then invalid JSON → state keeps the valid values.
  - `test_missing_eventsource_is_inert` — delete `global.EventSource` → `INITIAL_TICK`, no crash.
  - `test_single_connection_shared` — assert `MockEventSource.instances.length === 1` after `useScanProgress(true)` and `useScanStatusFeed()` are both mounted (two renderHooks) — the #152 hook must NOT open a second source.
  - `test_use_scan_progress_gates_on_active` — with the feed live and `active=false`, `progress` is `null`; with `active=true` it flows through.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/profiles/web && npx vitest run src/hooks/useScanStatusFeed.test.ts`
Expected: FAIL (module missing)

- [ ] **Step 3: Implement** — `useScanStatusFeed` is a **module-level singleton store**, not per-hook-instance state: module holds `sharedSource: EventSource | null`, `sharedTick: ScanStatusTick`, and a subscriber `Set`; the connection opens on the first subscriber and closes when the last unsubscribes (app-lifetime in practice). The hook itself is `useSyncExternalStore(subscribe, () => sharedTick)` — that is what makes the single-connection test pass with both consumers mounted. `status` listener parses the JSON payload into `ScanStatusTick` (snake→camel; keep-last-good on parse error; error listener blanks `progress` only). `useScanProgress` delegates to the feed and gates displayed values on `active`; update its docstring: the connection is now app-lifetime via the shared store, visibility gating unchanged (#152 behavior preserved).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/profiles/web && npx vitest run src/hooks/useScanStatusFeed.test.ts && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/hooks/useScanStatusFeed.ts src/profiles/web/src/hooks/useScanStatusFeed.test.ts src/profiles/web/src/hooks/useScanProgress.ts
git commit -m "feat(web): app-lifetime SSE status feed shared by progress and watch (#223)"
```

### Task 7: Web — `useWatchMode`, client API, SearchBar toggle, App wiring

**Files:**
- Create: `src/profiles/web/src/hooks/useWatchMode.ts`
- Create: `src/profiles/web/src/hooks/useWatchMode.test.ts`
- Modify: `src/profiles/web/src/api/client.ts` (add `setWatchMode` near `executeScan`, `client.ts:340`)
- Modify: `src/profiles/web/src/api/types.ts` (add `ScanWatchResponse`)
- Modify: `src/profiles/web/src/components/SearchBar.tsx` (new toggle button between the Timer button at `SearchBar.tsx:187-199` and the Barcode button)
- Modify: `src/profiles/web/src/components/SearchBar.test.tsx`
- Modify: `src/profiles/web/src/App.tsx` (hook wiring at the timer block `App.tsx:511`; SearchBar props at `App.tsx:995`)

**Interfaces:**
- Consumes: `useScanStatusFeed` (Task 6), `POST /api/scan/watch` (Task 3).
- Produces:

```ts
// client.ts
export async function setWatchMode(params: { enabled: boolean; recursive?: boolean }):
  Promise<{ watching: boolean; interval_s: number | null }>;
// types.ts
export interface ScanWatchResponse { watching: boolean; interval_s: number | null }
// useWatchMode.ts
export interface WatchModeDeps {
  scan: () => void;                                  // App's handleScan wrapper (latest-ref pattern)
  showToast: (msg: string, kind?: "info" | "error") => void;
  isScanning: () => boolean;                         // fresh per-render closure, read via depsRef
}
export interface WatchMode {
  watching: boolean;
  watchIntervalS: number | null;
  handleWatchSet: (enable: boolean) => Promise<void>;
}
export function useWatchMode(deps: WatchModeDeps): WatchMode;
// SearchBar.tsx props (added)
watchActive: boolean;
watchDisabled: boolean;   // scanning || no active directory
watchLabel: string | null; // e.g. "2s" — tooltip cadence, null when unknown
onWatchToggle: () => void;
```

  Semantics pinned by the spec: toggle state **derives from the feed** (`tick.watching`); a `watch_seq` bump while watching triggers `scan()` unless `isScanning()` (then a pending flag drains exactly one trailing scan on the first tick where `tick.inProgress` is false — server-side progress is the settle signal, so App's `handleScan` needs no wiring); a server-reported `watching:false` the client didn't cause un-toggles silently when `watch_error` is empty, with **one** error toast per distinct message otherwise; enabling/disabling toasts once (`"Watching for changes."` / `"Watch disabled."`).

- [ ] **Step 1: Write the failing tests** — `useWatchMode.test.ts` (reuse the `MockEventSource` pattern; drive ticks with `act(() => instances[0].emit("status", json))`):
  - `test_first_tick_records_baseline_no_scan` — emit `watch_seq: 1, watching: false` → `scan` not called.
  - `test_seq_bump_triggers_single_scan` — enable (`handleWatchSet(true)` with a mocked fetch → `{watching: true, interval_s: 1.5}`), emit `watch_seq: 2, watching: true` → `scan` called once; a second tick with the same seq → no further call.
  - `test_bump_during_scan_defers_one_trailing_scan` — emit `watch_seq: 3` while `isScanning()` returns true → no immediate scan; emit `{in_progress: false, watch_seq: 3, watching: true}` → exactly one scan.
  - `test_server_untoggle_silent_without_error` — after enabling, emit `{watching: false, watch_error: null}` → `watching` false, no toast.
  - `test_server_untoggle_toasts_once_on_error` — emit `{watching: false, watch_error: "Watch stopped: directory does not exist"}` twice → `showToast` called once with that message, kind `"error"`.
  - `test_enable_disable_toast_once` — `handleWatchSet(true)` → toast `"Watching for changes."`; `handleWatchSet(false)` → toast `"Watch disabled."`.
  - `test_enable_failure_toasts_error` — mocked fetch rejects → error toast prefixed `"Watch failed: "`, `watching` stays false.

  `SearchBar.test.tsx` additions:
  - `test_watch_toggle_renders_and_calls_on_watch_toggle` — click → handler called.
  - `test_watch_toggle_disabled_while_scanning` — `scanning=true, watchDisabled=true` → button disabled.
  - `test_watch_toggle_active_style_and_cadence_label` — `watchActive=true, watchLabel="2s"` → active class present, tooltip text contains `every 2s`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/profiles/web && npx vitest run src/hooks/useWatchMode.test.ts src/components/SearchBar.test.tsx`
Expected: FAIL (module/props missing)

- [ ] **Step 3: Implement**

  `client.ts` + `types.ts`: as the interface block (POST JSON, `apiError(res, "Failed to toggle watch mode")`).
  `useWatchMode`: local `watching` state seeded from ticks; refs `lastSeqRef` (first tick records, never fires), `pendingRef`, `lastErrorRef` (toast dedupe), `intentRef` (client-caused transitions vs server-driven). `handleWatchSet` calls `setWatchMode`, applies the response, toasts once.
  `SearchBar.tsx`: new icon button styled exactly like the Timer button (`Eye` from `lucide-react`, `animate-pulse` while active), `disabled={watchDisabled}`, `aria-label` toggling `"Enable watch mode"` / `"Disable watch mode"`, `Tooltip` text: active → `` `Watching · every ${watchLabel ?? "?"}` `` , idle → `"Watch for changes — rescan when the directory changes"`.
  `App.tsx`: after the `useAutoRescanTimer` block — `const watch = useWatchMode({ scan: () => { void handleScan(); }, showToast, isScanning: () => scan.scanning })`; mutual exclusion (spec: two modes of one control): `handleWatchToggle` = if watching → `handleWatchSet(false)`; else if `autoRescanInterval > 0` → `handleTimerSet(0)` then `handleWatchSet(true)`. Wrap the timer setters: `const handleTimerSetExclusive = (s: number) => { if (s > 0 && watch.watching) void watch.handleWatchSet(false); handleTimerSet(s); }` and pass it to both `TimerModal`'s `onSetInterval` (`App.tsx:1159`) and any timer UI path. SearchBar props: `watchActive={watch.watching}` `watchDisabled={scan.scanning || !activeDirectory}` `watchLabel={watch.watchIntervalS ? `${Math.round(watch.watchIntervalS)}s` : null}` `onWatchToggle={handleWatchToggle}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/profiles/web && npx vitest run src/hooks/useWatchMode.test.ts src/components/SearchBar.test.tsx && npx tsc --noEmit`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/hooks/useWatchMode.ts src/profiles/web/src/hooks/useWatchMode.test.ts src/profiles/web/src/api/client.ts src/profiles/web/src/api/types.ts src/profiles/web/src/components/SearchBar.tsx src/profiles/web/src/components/SearchBar.test.tsx src/profiles/web/src/App.tsx
git commit -m "feat(web): watch toggle — SSE-driven rescan, mutually exclusive with the timer (#223)"
```

### Task 8: Web — #218 selection preservation

**Files:**
- Create: `src/profiles/web/src/utils/selection.ts`
- Create: `src/profiles/web/src/utils/selection.test.ts`
- Modify: `src/profiles/web/src/api/client.ts` (add `findScanResultsPath`)
- Modify: `src/profiles/web/src/hooks/useScanController.ts` (expose `currentGeneration(): number` on `ScanController`)
- Modify: `src/profiles/web/src/App.tsx` (`onFreshResults` at `App.tsx:170-173`; reconcile effect at `App.tsx:243-256`; new restore helper; `handleExecute` guard comment at `App.tsx:597`)
- Modify: `src/profiles/web/src/components/FileListTable.tsx` (`aria-activedescendant` guard at `FileListTable.tsx:468`)

**Interfaces:**
- Consumes: `find_path` endpoint (Task 5), `fetchScanResults` (existing).
- Produces:

```ts
// utils/selection.ts
import type { ScannedFileItem } from "../api/types";
/** Index of *previousPath* in *files*, or -1 when absent/null. Pure. */
export function followSelection(previousPath: string | null, files: ScannedFileItem[]): number;
// client.ts
export async function findScanResultsPath(params: { path: string; sort_by?: string; sort_dir?: SortDirection }):
  Promise<{ count: number; offset: number }>;
```

- [ ] **Step 1: Write the failing tests** — `selection.test.ts`:
  - `test_follow_selection_finds_moved_row` — path present at index 5 → returns 5 (selection follows, index moved).
  - `test_follow_selection_absent_returns_minus_one` — path gone → -1.
  - `test_follow_selection_null_returns_minus_one` — null previous path → -1 (caller keeps its own clamp for the untracked case).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd src/profiles/web && npx vitest run src/utils/selection.test.ts`
Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

  `selection.ts` — the pure function.
  `client.ts` — `findScanResultsPath`: GET `/api/scan/results?find_path=...` (+ optional sort params), returns `{count, offset}`.
  `App.tsx`:
  - `onFreshResults` body becomes empty with a docstring: *selection follows the previous path on every fresh result set (#218) — the reconcile effect owns it; nothing to reset here.* The `selectedPathRef.current = null; setSelectedIndex(0)` lines are REMOVED (this was the #218 bug).
  - Reconcile effect (`App.tsx:243-256`) becomes: `const queryPath = selectedPathRef.current`; `if (!queryPath)` → keep today's clamp (`Math.min(prev, Math.max(0, visibleFiles.length - 1))`) for the never-selected case; else `const followed = followSelection(queryPath, visibleFiles)` → `>= 0` selects; `< 0` → `void restoreSelection(queryPath)`.
  - `restoreSelection(path: string)` (defined after `handleSelectIndex`): skipped when all rows are loaded (`scan.files.length >= scan.totalCount` — genuinely gone); one in-flight guard ref keyed by path; `const { offset } = await findScanResultsPath({ path, sort_by: scan.sort?.column, sort_dir: scan.sort?.direction })`; `offset < 0` OR the row is loaded but filtered out of `visibleFiles` → clear: `selectedPathRef.current = null; setSelectedIndex(-1)`; `offset >= scan.files.length` → fetch the missing window in ONE request `fetchScanResults({ offset: scan.files.length, limit: Math.min(offset + 1 - scan.files.length, 50_000), sort_by, sort_dir })`, append with the existing dedupe-by-path guard, then re-run `followSelection` on the updated `visibleFiles` (via a state-driven re-entry: store nothing — simply set the appended files then let the reconcile effect fire again on the new `visibleFiles`); every state write guarded by `scan.isCurrentScan(gen)` with `gen = scan.scanGenerationRef` captured at entry (expose it — the controller interface already returns `isCurrentScan`; capture the generation via `scan.claimGeneration` is wrong here, so read the current number: add `currentGeneration(): number` to `ScanController` returning `scanGenerationRef.current`, one-line addition in `useScanController.ts`).
  - `handleExecute` (`App.tsx:597`): no code change needed (`visibleFiles[-1]` is undefined and the existing guard holds) — add a comment pinning that `-1` means "nothing selected".
  - `FileListTable.tsx:468`: `aria-activedescendant={renderedCount > 0 && selectedIndex >= 0 ? \`file-row-${selectedIndex}\` : undefined}` (a `-1` id must never be announced). Row highlight and the scroll effect (`FileListTable.tsx:332` already guards `selectedIndex < 0`) need no change.
  - Keyboard navigation from `-1` needs no change: every `moveSelection` compute in `useAppCommands.ts` floors with `Math.max(0, ...)` (verified: `useAppCommands.ts:401,410,419,441,451`), so the first arrow key selects row 0.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd src/profiles/web && npx vitest run src/utils/selection.test.ts && npx tsc --noEmit && npx vitest run`
Expected: PASS, full web suite green

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/utils/selection.ts src/profiles/web/src/utils/selection.test.ts src/profiles/web/src/api/client.ts src/profiles/web/src/App.tsx src/profiles/web/src/hooks/useScanController.ts src/profiles/web/src/components/FileListTable.tsx
git commit -m "fix(web): selection survives refreshes by path, clears instead of re-selecting (#218)"
```

### Task 9: Docs, trees, dist, full gates

**Files:**
- Modify: `README.md`, `README.fr.md` (feature list + one paragraph in the scan/auto-rescan area)
- Modify: `docs/network-server-guide.en.md`, `docs/network-server-guide.fr.md` (watch section)
- Modify: `AGENTS.md` (tree: add `│   ├── watcher.py` under `core/processing` with a one-line description, keep the dated sync note)
- Modify: `tests/AGENTS.md` (tree: `test_watcher.py`, `test_scanner_boundary.py`, `test_scan_watch.py`, `test_scan_find_path.py`; update `tests/README.md` likewise)
- Modify: `src/profiles/web/dist/**` (rebuilt)

- [ ] **Step 1: Write the docs** — READMEs: one bullet "Watch mode — the list rescans itself when the directory changes (no fixed timer)" + a short paragraph (toggle beside the timer, mutually exclusive, server shares one watcher with all LAN clients). Network guides: a "Watch mode" section: one watcher per server shared by LAN clients; cadence adapts to share speed (~1–2 s locally, a few seconds on busy shares); in-place edits are not detected (probe watches directory mtimes — stations writing via temp-then-rename are caught); the timer and watch are two modes of one control; a vanished share stops the watch with a toast.
- [ ] **Step 2: Update both AGENTS.md trees** to match the new files exactly (project rule: same commit as the code).
- [ ] **Step 3: Rebuild dist**

Run: `cd src/profiles/web && npm ci && npm run build`
Expected: build succeeds; `dist/` updated.

- [ ] **Step 4: Run the full gate**

Run: `ruff format --check . && ruff check . && pylint src/profiles && pytest && cd src/profiles/web && npx tsc --noEmit && npx vitest run`
Expected: all green; coverage ≥ 85 %; pre-existing macOS `pyobjc` pyright noise is tolerated per CI precedent (pyright runs only in CI on the touched files).
- [ ] **Step 5: Live verification** (repo convention for SSE features, cf. #152): `uv run profiles --server-only` serves the built dist at `http://127.0.0.1:8088`; in a browser enable Watch, create/delete/rename a file in the watched tree, confirm one rescan (~1–2 s), selection preserved across it, and the dead-root toast after `rm -rf` of a subdir watch target is NOT tested destructively — instead re-point the server at a removable path if convenient; otherwise skip (server tests cover the policy).
- [ ] **Step 6: Commit**

```bash
git add README.md README.fr.md docs/network-server-guide.en.md docs/network-server-guide.fr.md AGENTS.md tests/AGENTS.md tests/README.md src/profiles/web/dist
git commit -m "docs: watch mode guide + trees sync; build(web): rebuild dist (#223)"
```

---

## Final verification checklist (maps to the spec's scope)

- [ ] `pytest` green, coverage ≥ 85 % (gate)
- [ ] `pylint src/profiles` ≥ 8 (repo runs 10/10)
- [ ] `ruff format --check . && ruff check .` clean
- [ ] Web: `npx tsc --noEmit` + full vitest run green
- [ ] Review Focus items 1–5 each pinned by its named test
- [ ] No new Python or npm dependency (`pyproject.toml`, `package.json` untouched)
- [ ] Branch `feat/223-watch-mode` ready for PR — Closes #223, Closes #218 (the maintainer opens the PR, per repo convention)
