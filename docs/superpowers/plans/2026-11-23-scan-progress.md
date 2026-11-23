# Live Scan Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** While a scan this window initiated runs, `ScanStatusStrip` shows a live, SSE-fed file count — `Scanning <dir> — 1,234 files — 42s` — including during the startup scan.

**Architecture:** `scan_and_process_dynamic` gains an optional `on_progress` callback invoked at the `_scan_and_filter` consumption point (filter-passing candidates); `execute_scan` feeds it into a generation-guarded `ServerState.scan_progress_count` that the existing `/api/scan/events` SSE payload now carries; a new `useScanProgress` hook consumes the stream and the strip renders the count only when the server reports `in_progress`.

**Tech Stack:** Python 3 stdlib typing (core), FastAPI + sse-starlette (server), React + TypeScript + vitest + @testing-library/react (web).

**Spec:** `docs/superpowers/specs/2026-11-23-scan-progress-design.md` — the plan argues from the spec; executors read both.

## Global Constraints

- No new pip or npm dependencies.
- Core stays UI-free; `on_progress` is documented "must not raise"; no defensive wrapping around it.
- SSE event name stays `"status"`, tick stays 1s; payload is exactly `{in_progress, count, progress, directory}`.
- `scan_progress_count` resets at the **top** of `execute_scan`, before the `exists()` early return; the callback write is generation-guarded (`scan_generation == state.scan_generation`).
- Strip visibility = `scanning || initialScanActive` (client-owned state only — never SSE `in_progress`).
- Count segment renders only when SSE `in_progress` is true AND `progress != null`; otherwise `ScanStatusStrip` output is byte-identical to today's.
- Quality gates: `ruff format` + `ruff check` clean, `pylint src/profiles` ≥ 8.0, `pytest --cov=src/profiles --cov-fail-under=85`, web vitest suite green; type hints + docstrings on all new public functions.

## Review Focus

Failure modes the spec implies but no single task test fully exercises — each is pinned by the test named on its line:

1. SSE stream drops mid-scan → strip silently degrades to elapsed-only and silently resumes counts after reconnect (no toast, no spinner change). → Task 3, error/resume hook tests.
2. Malformed or non-JSON SSE data → event ignored, nothing crashes. → Task 3, malformed-JSON test.
3. A `progress` value arrives while `in_progress` is false (post-scan tick, sort reload) → no count segment, ever. → Task 4 strip test + Task 3 `in_progress` gating test.
4. A new scan starts while old numbers could still be on screen (missing-directory POST, auto-rescan chain) → counter reads 0 at the new scan's start. → Task 2 reset test.
5. Environment without `EventSource` (jsdom test env, exotic browsers) → hook is inert, app renders normally. → Task 3 no-stub test + Task 5 App test runs against the same guard.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/profiles/core/processing/scanner.py` | Modify | `on_progress` param on `_run_scan_pipeline` + `scan_and_process_dynamic`; counting loop |
| `src/profiles/server/state.py` | Modify | `scan_progress_count: int = 0` field |
| `src/profiles/server/routes/scan.py` | Modify | reset + generation-guarded callback + SSE payload field |
| `src/profiles/web/src/hooks/useScanProgress.ts` | Create | EventSource lifecycle + `ScanProgress` state |
| `src/profiles/web/src/components/ScanStatusStrip.tsx` | Modify | optional count segment |
| `src/profiles/web/src/components/ActionBar.tsx` | Modify | props + `scanning \|\| initialScanActive` gate |
| `src/profiles/web/src/App.tsx` | Modify | `initialScanActive` state + hook instantiation + wiring |
| `tests/core/processing/test_scanner.py` | Modify | callback tests |
| `tests/server/routes/test_scan.py` | Modify | SSE payload + reset + guard tests |
| `src/profiles/web/src/hooks/useScanProgress.test.tsx` | Create | hook tests |
| `src/profiles/web/src/components/ScanStatusStrip.test.tsx` | Create | strip tests |
| `src/profiles/web/src/components/ActionBar.test.tsx` | Create | gate tests |
| `src/profiles/web/src/App.scanFlow.test.tsx` | Modify | initial-load strip test |

---

### Task 1: Core — `on_progress` callback on the scan pipeline

**Files:**
- Modify: `src/profiles/core/processing/scanner.py` (`_run_scan_pipeline` at line 359, `scan_and_process_dynamic` at line 538)
- Test: `tests/core/processing/test_scanner.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `scan_and_process_dynamic(..., on_progress: Callable[[int], None] | None = None) -> list[ScannedFileDynamic]` — keyword-only, after the existing `*`; called at the `_scan_and_filter` consumption point with the running count of yielded candidates (final call value == `len(results)`). Task 2 passes this kwarg.

- [ ] **Step 1: Write the failing tests** in `tests/core/processing/test_scanner.py`:

```python
def test_scan_and_process_dynamic_reports_progress(tmp_path: Path) -> None:
    """on_progress receives monotonically rising counts of filter-passing
    candidates; the final value equals the returned result count."""
    scan_dir = tmp_path / "prog"
    scan_dir.mkdir()
    for i in range(3):
        (scan_dir / f"f{i}.mttl").write_text("x")
    (scan_dir / "skip.txt").write_text("x")

    seen: list[int] = []
    results = scan_and_process_dynamic(str(scan_dir), extension=".mttl", on_progress=seen.append)

    assert seen == sorted(seen)
    assert len(seen) >= 1
    assert seen[-1] == len(results) == 3  # only .mttl candidates counted


def test_scan_and_process_dynamic_without_progress_callback(tmp_path: Path) -> None:
    """Default (None) is a no-op: same results, no callback."""
    scan_dir = tmp_path / "prog"
    scan_dir.mkdir()
    (scan_dir / "a.mttl").write_text("x")
    assert scan_and_process_dynamic(str(scan_dir), extension=".mttl")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/processing/test_scanner.py::test_scan_and_process_dynamic_reports_progress -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'on_progress'`

- [ ] **Step 3: Implement** in `scanner.py`:

- Add `on_progress: Callable[[int], None] | None = None` to `_run_scan_pipeline`'s keyword params and to `scan_and_process_dynamic`'s keyword params (docstring: "Called with the running count of filter-passing candidates during collection. Must not raise."); `scan_and_process_dynamic` forwards it to `_run_scan_pipeline`.
- Replace the `list(_scan_and_filter(...))` consumption (`scanner.py:412-423`) with an explicit counting loop:

```python
files_to_process: list[T] = []
for count, candidate in enumerate(
    _scan_and_filter(
        directories,
        extension=extension,
        filter_text=filter_text,
        recursive=recursive,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        config=config,
        recursive_override=recursive_override,
    ),
    start=1,
):
    files_to_process.append(candidate)
    if on_progress is not None:
        on_progress(count)
```

- [ ] **Step 4: Run both new tests + the file's existing suite**

Run: `uv run pytest tests/core/processing/test_scanner.py -v`
Expected: PASS (all, including pre-existing tests)

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/processing/scanner.py tests/core/processing/test_scanner.py
git commit -m "feat(core): optional on_progress callback on scan_and_process_dynamic (#152)"
```

---

### Task 2: Server — progress in `ServerState` and the SSE payload

**Files:**
- Modify: `src/profiles/server/state.py` (field block near line 58)
- Modify: `src/profiles/server/routes/scan.py` (`execute_scan` lines 30-74, `scan_events` lines 175-194)
- Test: `tests/server/routes/test_scan.py`

**Interfaces:**
- Consumes: `scan_and_process_dynamic(..., on_progress=...)` from Task 1.
- Produces: `ServerState.scan_progress_count: int` (default 0); SSE `status` payload `{in_progress, count, progress, directory}`. Task 3's hook parses `progress` and `in_progress` from this payload.

- [ ] **Step 1: Write the failing tests** in `tests/server/routes/test_scan.py` (module imports gain `json`):

```python
async def _first_event_data(client: AsyncClient) -> dict:
    """Read one `status` event from the SSE stream, then close it."""
    async with client.stream("GET", "/api/scan/events") as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                return json.loads(line.removeprefix("data:").strip())
    raise AssertionError("no SSE data event received")


@pytest.mark.anyio
async def test_scan_events_stream_includes_progress(test_state: ServerState) -> None:
    """The status payload carries progress alongside the existing fields."""
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = await _first_event_data(client)
    assert set(payload) >= {"in_progress", "count", "progress", "directory"}
    assert payload["progress"] == 0


@pytest.mark.anyio
async def test_scan_progress_reset_survives_missing_directory(
    test_state: ServerState, tmp_path: Path
) -> None:
    """A scan of a nonexistent directory still resets the counter (the
    early return sits after the reset)."""
    test_state.scan_progress_count = 99
    app = create_app(test_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/scan",
            json={"directory": str(tmp_path / "nope"), "extension": ".mttl", "recursive": True},
        )
        assert resp.json()["warning"] == "Directory does not exist"
        payload = await _first_event_data(client)
    assert payload["progress"] == 0


@pytest.mark.anyio
async def test_scan_progress_generation_guard(test_state: ServerState) -> None:
    """Callbacks from a scan superseded mid-flight write nothing."""
    captured: dict = {}

    def fake_scan(*args: object, **kwargs: object) -> list:
        captured["on_progress"] = kwargs.get("on_progress")
        test_state.scan_generation += 1  # a newer scan supersedes this one
        return []

    app = create_app(test_state)
    with patch("profiles.core.processing.scanner.scan_and_process_dynamic", fake_scan):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/scan", json={"extension": ".mttl", "recursive": True})
            if captured["on_progress"] is not None:
                captured["on_progress"](500)
            payload = await _first_event_data(client)
    assert captured["on_progress"] is not None
    assert payload["progress"] == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/server/routes/test_scan.py -v`
Expected: FAIL — `scan_progress_count` attribute missing / `progress` key missing

- [ ] **Step 3: Implement**

- `state.py`: add `scan_progress_count: int = 0` next to `cached_results` (with a one-line comment: candidates found so far by the running scan).
- `routes/scan.py` in `execute_scan`:
  - Immediately after `state.scan_generation += 1` (line 34), add `state.scan_progress_count = 0`.
  - Define above the `to_thread` call:

```python
def _push_progress(count: int) -> None:
    if scan_generation == state.scan_generation:
        state.scan_progress_count = count
```

  - Pass `on_progress=_push_progress` into `scan_and_process_dynamic`.
- In `scan_events`'s `event_generator` payload dict (line 187-190), add `"progress": state.scan_progress_count`.

- [ ] **Step 4: Run the file's suite**

Run: `uv run pytest tests/server/routes/test_scan.py -v`
Expected: PASS (all, including pre-existing tests)

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/state.py src/profiles/server/routes/scan.py tests/server/routes/test_scan.py
git commit -m "feat(server): stream scan progress via /api/scan/events SSE (#152)"
```

---

### Task 3: Web — `useScanProgress` hook

**Files:**
- Create: `src/profiles/web/src/hooks/useScanProgress.ts`
- Test: `src/profiles/web/src/hooks/useScanProgress.test.tsx`

**Interfaces:**
- Consumes: SSE payload shape from Task 2 (`data.progress`, `data.in_progress`; event name `"status"`).
- Produces:

```ts
export interface ScanProgress {
  /** Latest candidates count from the stream; null = degraded/no data yet. */
  progress: number | null;
  /** Whether the server reports a scan running (gates the count segment). */
  inProgress: boolean;
}
export function useScanProgress(active: boolean): ScanProgress
```

Task 4 consumes both fields; Task 5 consumes the hook itself.

- [ ] **Step 1: Write the failing tests** in `useScanProgress.test.tsx`. Use a file-local fake (share the class shape with Task 5's App test):

```tsx
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  closed = false;
  handlers = new Map<string, (ev: unknown) => void>();
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, cb: (ev: unknown) => void) {
    this.handlers.set(name, cb);
  }
  close() {
    this.closed = true;
  }
  emitStatus(data: unknown) {
    this.handlers.get("status")?.({ data: JSON.stringify(data) });
  }
  emitError() {
    this.handlers.get("error")?.({});
  }
}

const emitLastStatus = (data: unknown) =>
  FakeEventSource.instances.at(-1)?.emitStatus(data);
```

Tests (all stub `window.EventSource = FakeEventSource as unknown as typeof EventSource` in `beforeEach`, restore after — except the no-stub test):
1. opens one EventSource on `/api/scan/events` when `active` becomes true; closes it when `active` flips false and on unmount.
2. `emitStatus({in_progress: true, count: 9, progress: 1234, directory: "/x"})` → result `{progress: 1234, inProgress: true}`.
3. `emitError()` → `progress` becomes `null` (inProgress unchanged); a later `emitStatus` restores values (silent resume).
4. malformed data (`{data: "not json"}`) → state unchanged, no throw.
5. without any stub (no `EventSource`) → `{progress: null, inProgress: false}`, no crash.
6. render → unmount → render again: first instance `closed === true`, exactly two instances (no leak; StrictMode-style remount safe).

- [ ] **Step 2: Run to verify failure**

Run: `cd src/profiles/web && npx vitest run useScanProgress`
Expected: FAIL — module `./useScanProgress` not found

- [ ] **Step 3: Implement** `useScanProgress.ts`:

- When `active` is true and `typeof EventSource !== "undefined"` and no live source: open one, `addEventListener("status", ...)`; handler JSON-parses `event.data` in try/catch (parse failure → ignore) and sets `{progress: data.progress ?? null, inProgress: Boolean(data.in_progress)}`; `onerror` sets progress to `null` only (browser auto-reconnects; the source object stays).
- When `active` is false or on unmount: close and drop the source, reset to `{progress: null, inProgress: false}`.
- No `EventSource` global → stay at the initial state. Docstring mirrors the spec's degraded-mode rule: silent fallback, no toasts, no retry logic.

- [ ] **Step 4: Run to verify pass**

Run: `cd src/profiles/web && npx vitest run useScanProgress`
Expected: PASS (all 6)

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/hooks/useScanProgress.ts src/profiles/web/src/hooks/useScanProgress.test.tsx
git commit -m "feat(web): useScanProgress hook consuming the scan SSE stream (#152)"
```

---

### Task 4: Web — count segment in `ScanStatusStrip` + ActionBar gate

**Files:**
- Modify: `src/profiles/web/src/components/ScanStatusStrip.tsx`
- Modify: `src/profiles/web/src/components/ActionBar.tsx` (props at lines 7-27, strip render at line 79)
- Test: `src/profiles/web/src/components/ScanStatusStrip.test.tsx` (create)
- Test: `src/profiles/web/src/components/ActionBar.test.tsx` (create)

**Interfaces:**
- Consumes: `ScanProgress` from Task 3 (`progress`, `inProgress` field names).
- Produces: `ScanStatusStripProps` gains `progress: number | null` and `inProgress: boolean`; `ActionBarProps` gains `initialScanActive?: boolean` (default `false`) and `scanProgress?: ScanProgress` (default `{progress: null, inProgress: false}`). Task 5 passes both.

- [ ] **Step 1: Write the failing tests**

`ScanStatusStrip.test.tsx`:
1. `inProgress: true, progress: 1234` → renders a `[data-testid="scan-progress-count"]` element whose text is `` `${(1234).toLocaleString()} files` `` (locale-agnostic assertion).
2. `inProgress: true, progress: null` → no count element; output otherwise unchanged (still renders `Scanning` + directory).
3. `inProgress: false, progress: 1234` (sort-reload case) → no count element.

`ActionBar.test.tsx`:
1. `scanning: true` → strip rendered.
2. `scanning: false, initialScanActive: true` → strip rendered (startup case).
3. `scanning: false, initialScanActive: false` → no strip.
4. `scanning: true, scanProgress: {progress: 5, inProgress: true}` → count element visible inside the bar.

- [ ] **Step 2: Run to verify failure**

Run: `cd src/profiles/web && npx vitest run ScanStatusStrip ActionBar`
Expected: FAIL — props don't exist / strip unconditionally rendered

- [ ] **Step 3: Implement**

- `ScanStatusStrip.tsx`: accept the two new props (with the spec's semantics in the docstring); between the directory span and the `" — "` elapsed segment render:

```tsx
{inProgress && progress != null && (
  <>
    {" — "}
    <span data-testid="scan-progress-count" className="font-mono tabular-nums text-ink-secondary">
      {progress.toLocaleString()} files
    </span>
  </>
)}
```

- `ActionBar.tsx`: add the two props (typed with the imported `ScanProgress`); the strip render gate becomes:

```tsx
{(scanning || initialScanActive) && (
  <ScanStatusStrip
    directory={scanningDirectory}
    progress={scanProgress?.progress ?? null}
    inProgress={scanProgress?.inProgress ?? false}
  />
)}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd src/profiles/web && npx vitest run ScanStatusStrip ActionBar`
Expected: PASS (all 7)

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/components/ScanStatusStrip.tsx src/profiles/web/src/components/ActionBar.tsx src/profiles/web/src/components/ScanStatusStrip.test.tsx src/profiles/web/src/components/ActionBar.test.tsx
git commit -m "feat(web): live file count in ScanStatusStrip; strip gate covers initial load (#152)"
```

---

### Task 5: Web — App wiring (`initialScanActive` + hook)

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (`initializeFromConfig` around lines 418-429; ActionBar JSX around lines 950-970; hook instantiation near the other `use*` calls)
- Test: `src/profiles/web/src/App.scanFlow.test.tsx`

**Interfaces:**
- Consumes: `useScanProgress` (Task 3), ActionBar props (Task 4).
- Produces: nothing new — this completes the feature.

- [ ] **Step 1: Write the failing test** in `App.scanFlow.test.tsx`, following the file's existing api-mock pattern: defer the mocked `executeScan` with a never-yet-resolved promise, render `<App />`, assert `[data-testid="scan-status-strip"]` is present during the initial load; resolve the deferred, await settlement, assert it is gone. Stub `window.EventSource` with the Task 3 `FakeEventSource` (import or redeclare) so the hook is live during the test.

- [ ] **Step 2: Run to verify failure**

Run: `cd src/profiles/web && npx vitest run App.scanFlow`
Expected: FAIL — no strip during initial load (`scanning` stays false while `runScan` runs)

- [ ] **Step 3: Implement** in `App.tsx`:

- `const [initialScanActive, setInitialScanActive] = useState(false);` next to the other init state (`initError`, ~line 70).
- In `initializeFromConfig`, wrap the existing `if (initialDir)` scan block: `setInitialScanActive(true)` before the `try`, `finally { setInitialScanActive(false); }` after the existing `catch` (covers success, failure, and retry — the retry path re-enters the same code).
- Near the controller hookup: `const scanProgress = useScanProgress(scan.scanning || initialScanActive);`
- ActionBar JSX gains `initialScanActive={initialScanActive}` and `scanProgress={scanProgress}`.

- [ ] **Step 4: Run to verify pass + no regressions in App suites**

Run: `cd src/profiles/web && npx vitest run App.scanFlow App.commandPalette App.configEditor`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/App.tsx src/profiles/web/src/App.scanFlow.test.tsx
git commit -m "feat(web): wire scan progress into App, strip visible during initial load (#152)"
```

---

### Task 6: Quality gates + dist rebuild

**Files:**
- Modify: `src/profiles/web/dist/` (build output)

- [ ] **Step 1: Backend gates**

Run: `uv run ruff format . && uv run ruff check --fix . && uv run pylint src/profiles --fail-under=8.0 && uv run pytest --cov=src/profiles --cov-fail-under=85 -q`
Expected: all clean; commit any formatting fallout it makes.

- [ ] **Step 2: Web suite + build**

Run: `cd src/profiles/web && npm test && npm run build`
Expected: suite green; `dist/` rebuilt (this is what the server serves).

- [ ] **Step 3: Commit dist**

```bash
git add src/profiles/web/dist
git commit -m "build(web): rebuild dist with live scan progress (#152)"
```
