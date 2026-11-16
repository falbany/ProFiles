# Issue #148 PR 1 — useScanController + scan-defaults helper + characterization test

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract all scan orchestration out of `App.tsx` into `hooks/useScanController.ts` (one `scanWith` replacing ten duplicated try/catch/finally blocks), add the `mergeDirectoryPreference` util, and pin the current scan-flow behavior with an App-level characterization test — with zero behavior change.

**Architecture:** Two-layer scan core per the spec: `scanWith(params)` = guard + `beginScan()` + `scanWithGeneration(gen, params)`; early-claim sites (directory picked/changed, config load, reload, init) keep `beginScan()`-before-await via `scanWithGeneration`. Sort state and the deferred-rescan timer move into the hook; selection stays in App and is reset via an `onFreshResults` callback.

**Tech Stack:** React 19 custom hook, TypeScript, vitest + @testing-library/react (jsdom), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` (PR 1 section "The PR series → PR 1"; the call-site table and `scanWith` protocol there are normative). All `App.tsx` line references below are against main @ f908667 (file = 1925 lines).

## Global Constraints

- Behavior-preserving refactor. Error-toast prefixes verbatim: `"Scan failed"`, `"Directory change failed"`, `"Scan failed after config load"`, `"Failed to reload configuration"`, `"Sort failed"`, `"Couldn't load more results — scroll to try again."`; scan-error text = `` `${prefix}: ${(err as Error)?.message ?? String(err)}` `` (covers both current spellings `err.message` and `err?.message ?? err`).
- 200-with-warning scan responses surface `res.warning` as an **error** toast (issue #130).
- Empty-directory guard: no `directory` in scan params → no generation, no fetch, no toast.
- No new npm dependencies; React 19 / vitest / testing-library as installed.
- `dist/` churn stays **uncommitted** (`npm run build` is verification only).
- Conventional commits, scope `(web)`. Branch: `refactor/148-pr1-scan-controller` off `main`.
- Test command (from repo root): `cd src/profiles/web && npx vitest run [file]`; type check: `cd src/profiles/web && npm run build` (runs `tsc -b && vite build`).

## Review Focus

Failure modes the spec implies that a person using the app would notice, most likely first — each pinned by a named test below:

1. Two scans racing (second starts while first in-flight) → first's fetches aborted; first paints no results and no toast. — Task 4, `superseded generation stays silent`.
2. Explicit scan within the 800 ms deferred-rescan window → exactly one scan; the deferred one is cancelled. — Task 2, scenario 4; Task 4, `deferred rescan cancelled by explicit scan`.
3. Directory config with empty `filters`/`extensions` → the *changed* site falls back to `""` (NOT keep-current); the *picked* site keeps current. — Task 2 scenario 5b; Task 3 unit tests.
4. Scan with no active directory → zero network calls, zero toasts, spinner untouched. — Task 2 scenario 8; Task 4, `scanWith empty-directory guard`.
5. Non-`Error` rejection (e.g. a thrown string) → toast says `Scan failed: boom`, never `Scan failed: undefined`. — Task 4, `scanWith error prefix` includes a string-rejection case.

---

### Task 1: Characterization scaffold + init/warning/failure scenarios

**Files:**
- Create: `src/profiles/web/src/App.scanFlow.test.tsx`
- Branch: `git checkout -b refactor/148-pr1-scan-controller` (first step)

**Interfaces:**
- Consumes: `App` default export, api client functions (`./api/client`), types from `./api/types`.
- Produces: the App-level safety net every later task must keep green. These tests pin **current** behavior — they must pass **before** any refactor. A red result means the test misread current behavior: fix the test, never `App.tsx` in Tasks 1–2.

- [ ] **Step 1: Create the branch**

```bash
git checkout main && git pull && git checkout -b refactor/148-pr1-scan-controller
```

- [ ] **Step 2: Write the scaffold + scenarios 1–3**

Copy the scaffold preamble from `src/profiles/web/src/App.configEditor.test.tsx` (it is the established pattern): `// @vitest-environment jsdom`, `vi.mock("./api/client", importOriginal)` re-exporting everything and overriding: `fetchSystemInfo`, `fetchConfig`, `fetchScanResults`, `fetchNotifications`, `executeScan`, `selectDirectory`; the `__APP_VERSION__ ??= "0.0.0-test"` global; the `Range` `getClientRects`/`getBoundingClientRect` polyfills; the `ResizeObserverStub` class. Copy its `makeSystemInfo()` fixture verbatim and its `makeAppConfig(overrides)` fixture (defaults: `directories: ["C:/data"]`, `extensions: [".mttl"]`, `filters: []`, `active_directory: "C:/data"`, `recursive_search: false`, `config_exists: true`, `session_trial: false`).

Mock return defaults in `beforeEach`: `fetchSystemInfo` → `makeSystemInfo()`, `fetchConfig` → `makeAppConfig()`, `fetchNotifications` → `{ events: [] }`, `executeScan` → `{}`, `fetchScanResults` → `{ items: [], count: 0 }`, `selectDirectory` → `makeAppConfig()`.

File-scanned fixture helper:

```ts
function makeFile(name: string, path?: string): ScannedFileItem {
  return { filename: name, rel_path: name, path: path ?? `C:/data/${name}` } as ScannedFileItem;
}
```

Tests (describe `"App scan flow (characterization)"`):

1. **`initial load scans with config-derived params and renders results`** — `fetchConfig` → `makeAppConfig({ filters: ["all"] })`, `fetchScanResults` → `{ items: [makeFile("a.txt"), makeFile("b.txt")], count: 2 }`. Render `<App />`; `await screen.findByText("a.txt")`. Assert `executeScanSpy` called once with exactly `{ directory: "C:/data", extension: ".mttl", filter_text: "all", recursive: false }`.
2. **`scan 200-with-warning surfaces the warning as an error toast`** — after init render settles, set `executeScanSpy` → `{ warning: "Directory does not exist" }`, click `screen.getByRole("button", { name: "Scan" })`. Assert `await screen.findByRole("status")` contains `"Directory does not exist"` (toast renders in `ActionBar` with `role="status"`).
3. **`scan failure shows the site's error prefix`** — after init, `executeScanSpy.mockRejectedValueOnce(new Error("boom"))`, click Scan. Assert the status role contains `"Scan failed: boom"`.

- [ ] **Step 3: Run — expected GREEN against current code**

Run: `cd src/profiles/web && npx vitest run src/App.scanFlow.test.tsx`
Expected: PASS (3 tests). If red: the test misunderstood current behavior — fix the test, not `App.tsx`.

- [ ] **Step 4: Commit**

```bash
git add src/profiles/web/src/App.scanFlow.test.tsx
git commit -m "test(web): characterize App scan flow before scan-controller extraction (#148)"
```

### Task 2: Characterization — deferred rescan, directory merge, sort, empty-directory guard

**Files:**
- Modify: `src/profiles/web/src/App.scanFlow.test.tsx`

**Interfaces:**
- Consumes: same scaffold. Selectors: filter input `getByLabelText("File filter")` (`#filter-combobox`), directory input `getByLabelText("Directory")` (`#directory-combobox`), column header `getByRole("columnheader", { name: "Name" })`, scan button `getByRole("button", { name: "Scan" })`, toast `getByRole("status")`.

- [ ] **Step 1: Add scenarios 4, 5, 7, 8**

4. **`typing schedules a deferred rescan; an explicit scan inside the window wins`** — `vi.useFakeTimers()` + `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`. Render with init mocks (`executeScanSpy` cleared after init). `await userEvent.type(screen.getByLabelText("File filter"), "ab")`; `act(() => vi.advanceTimersByTime(800))`; assert `executeScanSpy` called once more with `filter_text: "ab"`. Fresh render (clear mocks): type `"a"`, press `Enter` in the same input, `advanceTimersByTime(800)` — assert no further `executeScan` call (explicit scan cancelled the deferred one). `vi.useRealTimers()` in `afterEach`.
5. **`directory change merges preferences with the changed-site empty fallback`** — init with `filters: ["all"]`. `selectDirectorySpy` → `makeAppConfig({ active_directory: "C:/other", extensions: [".py", ".mttl"], filters: ["prod"] })`; type `"C:/other{Enter}"` into the Directory input. Assert last `executeScan` call = `{ directory: "C:/other", extension: ".mttl", filter_text: "prod", recursive: false }` (current ext kept — in list; current filter replaced — not in list). Then `selectDirectorySpy` → `makeAppConfig({ active_directory: "C:/empty", extensions: [], filters: [] })`; type `"C:/empty{Enter}"`. Assert last call = `{ directory: "C:/empty", extension: "", filter_text: "", recursive: false }` — the changed site falls back to `""`, not keep-current.
7. **`sort change reloads page 1 with sort params`** — init with `makeAppConfig({ column_names: ["filename"], column_headers: ["Name"] })`, `fetchScanResults` → one page of 2 files. Clear mocks; click the `Name` columnheader. Assert `fetchScanResultsSpy` called with object containing `{ offset: 0, sort_by: "filename", sort_dir: "asc" }` (and `executeScanSpy` NOT called — sort reloads, not rescans).
8. **`no active directory: scan is a silent no-op`** — `fetchConfig` → `makeAppConfig({ active_directory: "", directories: [] })`. After render: assert `executeScanSpy` never called; click Scan; assert still never called and no error toast appeared.

(Spec scenario 6, load-more dedup, is scroll/virtualizer-driven — pinned at hook level in Task 4, not via jsdom geometry.)

- [ ] **Step 2: Run — expected GREEN**

Run: `cd src/profiles/web && npx vitest run src/App.scanFlow.test.tsx`
Expected: PASS (7 tests total). Fix the test if red; never `App.tsx`.

- [ ] **Step 3: Commit**

```bash
git add src/profiles/web/src/App.scanFlow.test.tsx
git commit -m "test(web): characterize deferred rescan, directory merge, sort, empty-dir guard (#148)"
```

### Task 3: `utils/scanDefaults.ts` — mergeDirectoryPreference

**Files:**
- Create: `src/profiles/web/src/utils/scanDefaults.ts`
- Test: `src/profiles/web/src/utils/scanDefaults.test.ts`
- Modify: `src/profiles/web/src/App.tsx:544-551` (`handleDirectoryPicked`), `App.tsx:659-666` (`handleDirectoryChange`)

**Interfaces:**
- Produces: `mergeDirectoryPreference(current: string, candidates: string[] | undefined, fallback: string): string` — returns `current` when `candidates?.includes(current)`, else `candidates?.[0]`, else `fallback`. Later tasks rely on this exact name/arity.

- [ ] **Step 1: Write the failing unit test (table form)**

Cases: `(".txt", [".txt", ".py"], ".keep") → ".txt"`; `(".py", [".txt"], ".keep") → ".txt"` (keep misses → first); `(".py", undefined, ".keep") → ".keep"`; `(".py", [], ".keep") → ".keep"` (picked-site fallback = current); `(".py", [], "") → ""` (changed-site fallback = empty); `(".py", [], "all") → "all"`; `("", ["a"], "") → "a"`.

- [ ] **Step 2: Run — expected FAIL** (`mergeDirectoryPreference` not defined)

Run: `cd src/profiles/web && npx vitest run src/utils/scanDefaults.test.ts`

- [ ] **Step 3: Implement in `utils/scanDefaults.ts`** — docstring states the two call sites' distinct fallbacks (picked keeps current, changed resets to `""`).

- [ ] **Step 4: Run — expected PASS**

- [ ] **Step 5: Adopt at both call sites**

In `handleDirectoryPicked`: `nextExtension = mergeDirectoryPreference(activeExtension, directoryConfig?.extensions, activeExtension)`; `nextFilter = mergeDirectoryPreference(filterText, directoryConfig?.filters, filterText)`. In `handleDirectoryChange`: same shape with `directoryConfig.extensions` / `directoryConfig.filters` and fallback `""`.

- [ ] **Step 6: Full suite GREEN (characterization proves behavior preserved) + commit**

Run: `cd src/profiles/web && npx vitest run`
Expected: 275 tests pass (267 + 7 characterization + 7 helper ≈; exact count may differ by ±2 — all green is the requirement).

```bash
git add src/profiles/web/src/utils/scanDefaults.ts src/profiles/web/src/utils/scanDefaults.test.ts src/profiles/web/src/App.tsx
git commit -m "refactor(web): dedupe directory preference merge into scanDefaults helper (#148)"
```

### Task 4: `hooks/useScanController.ts` — hook tests + implementation

**Files:**
- Create: `src/profiles/web/src/hooks/useScanController.ts` (creates the `hooks/` directory)
- Test: `src/profiles/web/src/hooks/useScanController.test.tsx`
- Modify: `AGENTS.md:90` (tree line), `tests/AGENTS.md` (verify only — its tree mirrors the Python `tests/` dir, co-located vitest tests are not listed, so no change expected)

**Interfaces:**
- Consumes: `executeScan`, `fetchScanResults` from `../api/client`; `ScanSort`, `ScannedFileItem` from `../api/types`; `SCAN_PAGE_SIZE` from `../components/FileListTable`; `mergeDirectoryPreference` NOT used here (App-level).
- Produces (later tasks, esp. Task 5, rely on these exact names):

```ts
export type ScanParams = Parameters<typeof executeScan>[0];
export type ScanOutcome =
  | { ok: true; firstPage: { items: ScannedFileItem[]; count: number } }
  | { ok: false };

export interface ScanControllerDeps {
  showToast: (msg: string, kind?: "info" | "error") => void;
  getScanParams: () => ScanParams;   // latest-state scan params; read via latest-ref
  onFreshResults: () => void;        // called after each successful fresh first page
}

export interface ScanController {
  files: ScannedFileItem[]; totalCount: number; hasScanned: boolean;
  loadingMore: boolean; scanning: boolean; sort: ScanSort | null;
  beginScan(): number;                      // cancels pending deferred rescan, aborts prior gen, bumps, setScanning(true), setLoadingMore(false)
  claimGeneration(): number;                // abort + new AbortController + bump ONLY (no UI state) — runInitialLoad's protocol
  isCurrentScan(generation: number): boolean;
  finishScan(generation: number): void;
  runScan(generation: number, params: ScanParams): Promise<boolean>;  // execute + warning toast + loadScanResults(gen) + onFreshResults; init flow only
  scanWith(params: ScanParams, opts?: { errorPrefix?: string }): Promise<ScanOutcome>;
  scanWithGeneration(gen: number, params: ScanParams, opts?: { errorPrefix?: string }): Promise<ScanOutcome>;
  applySort(next: ScanSort | null): void;   // setSort → onFreshResults → beginScan → loadScanResults(gen, next); catch "Sort failed"
  handleLoadMore(): Promise<void>;          // moved verbatim from App.tsx:301-323
  scheduleDeferredRescan(): void;           // clears pending, 800ms → scanWith(getScanParams())
}
export function useScanController(deps: ScanControllerDeps): ScanController;
```

Semantics fixed by the spec: `scanWith` guards empty `params.directory` **before** `beginScan` (returns `{ ok: false }`, no side effects), then `beginScan()` + `scanWithGeneration`. `scanWithGeneration`: guard → `executeScan(params, signal)` (200-with-warning → `showToast(warning, "error")` when current) → `loadScanResults(gen)` (sets files/totalCount/hasScanned, returns res) → `onFreshResults()` → `{ ok: true, firstPage }`; catch → current ? `showToast(`${prefix ?? "Scan failed"}: ${(err as Error)?.message ?? String(err)}`, "error")` : silent → `{ ok: false }`; `finally` → `finishScan(gen)`. Deps are read through a latest-ref so stale closures can't capture old state. `AUTO_RESCAN_DEBOUNCE_MS = 800` and the pending-rescan ref move here from App; a cleanup effect on unmount cancels the pending timer and aborts in-flight fetches (App.tsx:637-647 moves here).

- [ ] **Step 1: Write the failing hook tests** (`renderHook` + `vi.mock("../api/client")`, deps stubbed: `showToast: vi.fn()`, `getScanParams` returning a mutable object, `onFreshResults: vi.fn()`). One full example, then the rest by name + key assertions:

```tsx
it("scanWith empty-directory guard", async () => {
  const { result } = renderHook(() => useScanController(deps));
  const outcome = await act(() => result.current.scanWith({ ...params, directory: "" }));
  expect(outcome).toEqual({ ok: false });
  expect(executeScanSpy).not.toHaveBeenCalled();
  expect(result.current.scanning).toBe(false);
});
```

1. `scanWith happy path` — execute resolves, fetch → `{ items: [f1], count: 1 }`: outcome `{ ok: true, firstPage: { items: [f1], count: 1 } }`; `result.current.files` = `[f1]`; `hasScanned` true; `scanning` false; `onFreshResults` called once.
2. `scanWith surfaces 200-with-warning as error toast` — execute → `{ warning: "dir gone" }`: `showToast("dir gone", "error")`; scan still completes (`ok: true`).
3. `scanWith error prefix` — execute rejects `new Error("boom")`: toast `"Scan failed: boom"`; with `opts.errorPrefix = "Directory change failed"`: that prefix; execute rejects `"boom"` (a string): toast `"Scan failed: boom"` (not `undefined`); `ok: false`.
4. `superseded generation stays silent` — `const g1 = beginScan(); beginScan();` then `scanWithGeneration(g1, params)`: execute IS called (with g1's signal), but `files` stay `[]`, `onFreshResults` not called, `showToast` not called, and `scanning` remains `true` (newer generation owns it).
5. `applySort reloads with sort params` — `applySort({ column: "filename", direction: "asc" })`: fetch called with `{ offset: 0, sort_by: "filename", sort_dir: "asc" }`; `sort` state updated; `onFreshResults` called; rejection → toast `"Sort failed: boom"` and `scanning` false.
6. `handleLoadMore appends with path dedup` — seed via `scanWith` first page `{ items: [f1, f2], count: 3 }`; next fetch → `[f1dup, f3]` (`f1dup` same path as f1): files = `[f1, f2, f3]`, `totalCount` 3, `loadingMore` false; fetch called with `{ offset: 2, limit: SCAN_PAGE_SIZE }`. Guard: after completion another `handleLoadMore` (`files.length >= totalCount`) issues no fetch. Rejection → toast `"Couldn't load more results — scroll to try again."`, `loadingMore` false.
7. `scheduleDeferredRescan uses latest params; explicit scan cancels it` — fake timers: schedule with `getScanParams` mutated to `filter_text: "v2"` after scheduling → advance 800 → execute called with `filter_text: "v2"` (latest-ref, not stale). Fresh hook: schedule then `scanWith(params)` immediately → advance 800 → exactly one execute call total.
8. `unmount cleanup` — schedule a deferred rescan + `beginScan()` (capture the signal from the execute mock call args), unmount, advance 800 → no execute call; captured `signal.aborted === true`.
9. `claimGeneration` — bump without spinner: `scanning` stays `false` after `claimGeneration()`, prior generation's fetch is aborted (same signal assertion as 8).

- [ ] **Step 2: Run — expected FAIL** (module missing)

Run: `cd src/profiles/web && npx vitest run src/hooks/useScanController.test.tsx`

- [ ] **Step 3: Implement `useScanController`** — move the logic verbatim from `App.tsx` (state 74–89 incl. `sort`; `beginScan` 183–198 decomposed as pending-cancel + `claimGeneration` + spinner flags; `isCurrentScan`/`finishScan` 200–204; `loadScanResults` 267–280; `runScan` 282–298 with the 294–297 selection reset replaced by `onFreshResults()`; `handleLoadMore` 301–323; teardown 637–647; `pendingAutoRescanRef` scheduling 713–755 pattern). `sort` state lives in the hook.

- [ ] **Step 4: Run hook tests — expected PASS**

- [ ] **Step 5: Update AGENTS.md tree + commit**

AGENTS.md line 90 → `│   ├── src/                  #   App.tsx, components/, api/, utils/, hooks/`. `tests/AGENTS.md`: verify no web/src co-located section exists (expected: no change).

```bash
git add src/profiles/web/src/hooks/ AGENTS.md
git commit -m "refactor(web): add useScanController hook (scan state, generations, scanWith) (#148)"
```

### Task 5: Rewire App.tsx onto the controller

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (delete ≈140 lines, add ≈15)

**Interfaces:**
- Consumes: everything on `ScanController` from Task 4, plus `mergeDirectoryPreference` from Task 3.
- Produces: App still exports the same default component; `handleScan`/`handleScanRef` remain (timer effect at 1250–1262 and barcode consumers at 1179/1222 still use them — they die in PR 2/PR 4, not here).

- [ ] **Step 1: Wire the hook**

After the toast hook-up point in `App`:

```tsx
const scan = useScanController({
  showToast,
  getScanParams: () => ({ directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive }),
  onFreshResults: () => { selectedPathRef.current = null; setSelectedIndex(0); },
});
```

- [ ] **Step 2: Delete the moved code**

App state 74–89 (scan block incl. `sort`, `scanGenerationRef`, `scanAbortRef`, `pendingAutoRescanRef`), `beginScan`/`isCurrentScan`/`finishScan` (183–204), `loadScanResults`/`runScan`/`handleLoadMore` (267–323), `AUTO_RESCAN_DEBOUNCE_MS` (line 58 only — `PREFILTER_DEBOUNCE_MS` at 56 stays), teardown effect (637–647), sort state (82), and the deferred-scheduling bodies inside `handleFilterTextChange`/`handleRecursiveToggle`/`handleExtensionChange` (713–755 → `scan.scheduleDeferredRescan()`). Keep `selectedPathRef` + `selectedIndex` in App.

- [ ] **Step 3: Migrate the call sites (spec table is normative)**

- `handleScan` → `await scan.scanWith({ directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive }, { errorPrefix: "Scan failed" })` (its `!activeDirectory` early return is now redundant — the hook guards).
- `handleClearFilter` → `setFilterText("")` + `scan.scanWith({ directory: activeDirectory, extension: activeExtension, filter_text: "", recursive }, { errorPrefix: "Scan failed" })`.
- `handleDisableRecursive` → `setRecursive(false)` + `scan.scanWith({ directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive: false }, ...)`.
- `handleFilterFolder(folder)` / `handleFilterExtension(ext)` → setState + `void scan.scanWith({...}, { errorPrefix: "Scan failed" })` (fire-and-forget, as today).
- `handleDirectoryPicked` (530–565): keep `const gen = scan.beginScan()` **before** `await selectDirectory`, keep the mid-await `if (!scan.isCurrentScan(gen)) return;`, then `await scan.scanWithGeneration(gen, {...}, { errorPrefix: "Scan failed" })`.
- `handleDirectoryChange` (652–680): same early-claim shape, prefix `"Directory change failed"`, `return (await scan.scanWithGeneration(...)).ok`.
- `handleConfigLoaded` (387–428): `const gen = scan.beginScan()` at top; `if (targetDirectory) await scan.scanWithGeneration(gen, {...}, { errorPrefix: "Scan failed after config load" }) else scan.finishScan(gen)`.
- `handleReloadConfig` (325–385): keep `beginScan` at top and the outer catch/finally verbatim (fetch errors still toast `"Failed to reload configuration: …"`; outer `finishScan` stays — `beginScan` set the spinner); scan line becomes `await scan.scanWithGeneration(scanGeneration, {...}, { errorPrefix: "Failed to reload configuration" })`.
- `runInitialLoad`/`initializeFromConfig` (567–635): replace the raw ref manipulation (614–616) with `const scanGeneration = scan.claimGeneration()`; `initializeFromConfig` keeps `scan.runScan(scanGeneration, {...})` and its own catch (`"Initial scan failed: …"`, note: current prefix keeps `isCurrentScan` gating).
- Sort JSX (1581–1596) → `onSortChange={scan.applySort}`; `FileListTable`/`ActionBar`/`StatusBar` props re-target to `scan.*` (`files`, `totalCount`, `scanning`, `loadingMore`, `hasScanned`, `sort`); `handleExport`/`visibleFiles`/`prefilterNote` read `scan.files` / `scan.totalCount`.
- `handleScanRef` (700–704) stays, now wrapping the migrated `handleScan`.

- [ ] **Step 4: Verify everything**

Run: `cd src/profiles/web && npx vitest run` — expected: all green (characterization + configEditor + hook tests + rest).
Run: `cd src/profiles/web && npm run build` — expected: `tsc -b` clean, build succeeds. Do not commit `dist/`.

- [ ] **Step 5: Commit**

```bash
git add src/profiles/web/src/App.tsx
git commit -m "refactor(web): route App.tsx scan flows through useScanController (#148)"
```

### Task 6: Whole-PR verification, push, open PR

- [ ] **Step 1: Final gates** — `cd src/profiles/web && npx vitest run` (all green) && `npm run build` (clean); `git status` shows only `dist/` churn if any (leave uncommitted); `git log --oneline main..` shows the 5 task commits, no unrelated files (verify with `git show --stat`).

- [ ] **Step 2: Push + open PR**

```bash
git push -u origin refactor/148-pr1-scan-controller
gh pr create --base main --title "refactor(web): extract useScanController + scanDefaults (App.tsx decomposition, PR 1/7)" --body "$(cat <<'EOF'
Part of #148 (PR 1/7 of the series in docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md).

## What
- New `hooks/useScanController.ts`: all scan orchestration (state, generations/abort, `scanWith`/`scanWithGeneration`, sort reload, deferred auto-rescan, load-more) replacing ten duplicated try/catch/finally blocks in App.tsx.
- New pure helper `utils/scanDefaults.ts`: `mergeDirectoryPreference(current, candidates, fallback)` — preserves each call site's distinct empty-list fallback.
- App.tsx rewired onto the controller; behavior-preserving (toast texts, race semantics, spinner timing unchanged).

## Safety net
- New `App.scanFlow.test.tsx` (8-scenario App-level characterization, written against pre-refactor code and kept green).
- New `useScanController.test.tsx` + `scanDefaults.test.ts`.

## Test plan
- [ ] \`cd src/profiles/web && npx vitest run\` green
- [ ] \`npm run build\` (tsc) clean
- [ ] Manual: scan, filter typing (deferred rescan), directory switch, sort, empty-directory startup
EOF
)"
```

- [ ] **Step 3: Confirm CI started** — `gh pr checks` (web + quality workflows triggered).
