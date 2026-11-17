# Decompose App.tsx into Focused Hooks + Components — Design

- **Date:** 2026-11-16
- **Status:** Approved (partner approved 2026-11-16; builder-check calls incorporated)
- **Related:** [issue #148](https://github.com/falbany/ProFiles/issues/148) (parent),
  [issue #129](https://github.com/falbany/ProFiles/issues/129) (closed by PR 5),
  2026-10-24-drop-config-design.md (drag/drop behavior being extracted)

## Intent

`src/profiles/web/src/App.tsx` is a 1925-line monolith (issue audit said 1803;
it has grown) mixing scan orchestration, theme, barcode mode, drag-drop,
global shortcuts, LAN toggle, telemetry and toast handling. AGENTS.md's
presentation-layer rule ("delegate business logic to `profiles.core`/utils,
UI only") is unenforceable at this size, and the tangle has already caused
real bugs: stale closures in the scan flow, shortcut-guard gaps, and a dozen
duplicated scan try/catch blocks. This refactor decomposes App.tsx into
**independently testable hooks + one component**, moving pure decision logic
into `utils/` — **behavior-preserving**, except the planned #129 fix.

## Decisions from the conversation

- **Sliced delivery** (partner): a series of small PRs following the issue's
  sequencing — scan controller first, then shortcuts/theme/barcode, then
  components. No big-bang PR.
- **App-level characterization test** (partner): PR 1 adds a scan-flow
  characterization test written **against the current code** and kept green
  through the rewiring, because App-level coverage is otherwise one file
  (`App.configEditor.test.tsx`).
- **New `src/profiles/web/src/hooks/` directory** for all `use*` hooks
  (assistant proposal, unobjected). The existing hook `utils/useModalA11y.ts`
  violates AGENTS.md's "utils = stateless, framework-agnostic" rule and moves
  to `hooks/` in PR 2.
- AGENTS.md's web tree and `tests/AGENTS.md` are updated in the same commit
  that creates `hooks/` (repo "Keep in sync" rule).

## Verified current state (2026-11-16, App.tsx @ main a200d33)

Line map for the extraction (all verified against current code; the issue's
line numbers are stale by ~+120):

| Concern | Current location |
|---|---|
| Scan state + generation/abort refs | 74–89 (`files`, `totalCount`, `hasScanned`, `loadingMore`, `scanning`, `sort`, `scanGenerationRef`, `scanAbortRef`, `pendingAutoRescanRef`) |
| `beginScan` / `isCurrentScan` / `finishScan` | 183–204 |
| Selection anchor `selectedPathRef` | 211 |
| `loadScanResults` / `runScan` / `handleLoadMore` | 267–323 |
| Toast state + `showToast` / `dismissToast` | 98, 155–176 |
| External event poll (`lastEventIdRef`, `externalConfigApplyRef`) | 458–489 |
| Drag-drop tracker + window listeners + `handleDroppedConfig` | 431–524 |
| Merge extension/filter blocks | 544–551 (`handleDirectoryPicked`), 659–666 (`handleDirectoryChange`) |
| Init flow (`initializeFromConfig`, `runInitialLoad`) | 567–635 |
| Scan try/catch/finally blocks | 10 sites — see scanWith call-site table |
| Barcode mode (state, buffer, effect, `applyBarcodeValues`, camera handler) | 132–133, 1076–1245 |
| Auto-rescan periodic timer | 152–153, 1250–1271 |
| Deferred auto-rescan scheduling | 713–755 (filter/recursive/extension handlers) |
| Global shortcuts keydown effect | 1291–1498 |
| Theme (state, persistence effect, toggles) | 66, 343, 393, 570–580, 1397–1400, 1500–1508, 1615 |
| LAN confirm dialog (inline, `waitForLanState` flow) | 1843–1907 |
| `handleCopyUri` (path→URI) | 925–933 |

**Baseline:** web suite 267 tests / 18 files green (`npx vitest run` in
`src/profiles/web`). Every PR keeps it green. `dist/` is tracked but recent
main history does not commit its churn — leave `dist/` changes uncommitted
(run `npm run build` for verification only).

## Goals

- App.tsx shrinks to composition + presentation wiring (target ≲ 600 lines).
- Each extracted hook is unit-testable in isolation and ships its own tests.
- The ten duplicated scan try/catch/finally blocks collapse into one
  `scanWith(params, opts)` inside `useScanController`.
- Business logic leaves the UI: path→URI helper, barcode `shouldScan`
  decision, directory-preference merge helper.
- Fix #129 as part of `useTheme`: restore persisted theme on mount, stop
  session-trial themes leaking into `localStorage`.
- Zero behavior change in everything else (toasts, scan semantics, shortcut
  behavior, message texts preserved verbatim).

## Non-goals

- No `theme: auto` via `matchMedia` (#129 mentions it — follow-up issue).
- No extraction of the inline verify-hash dialog (1764–1823; candidate
  follow-up).
- No change to the API client surface, server, or CLI.
- No new features, no visual changes.
- `confirmDeleteFile`'s raw `fetch("/api/actions/delete")` stays (inconsistent
  with the api client; noted as follow-up cleanup, not this refactor).

## Anti-goals

- No god-context / global store: hooks keep their state; App stays the
  composer. A state-management rewrite is out of scope.
- No abstraction for abstraction's sake: a two-line inline pattern
  (`cfg.extensions[0] ?? ""`) is not "deduplicated" into the helper.

## Approaches considered

1. **One branch, one PR doing the whole decomposition** — smallest review
   count, but a ~1900-line diff touching every flow at once; exactly the
   risk the issue warns about. **Rejected** (partner chose slices).
2. **Sliced PRs per the issue's sequencing** — each slice keeps the suite
   green and is independently reviewable/revertable. **Picked.**
3. **Store/context rewrite (reducer + provider)** — would enforce layering
   hardest, but it is a rewrite of state flow, not a refactor; bigger blast
   radius than the problem justifies. **Rejected.**

## The PR series

Branch prefix `refactor/148-*`. PRs 1–6 titled "Part of #148"; PR 7
"Closes #148"; PR 5 also "Fixes #129". All in `src/profiles/web/src/`.
Test command: `npx vitest run` in `src/profiles/web`; type check via
`npm run build` (runs `tsc -b`).

### PR 1 — `useScanController` + merge helper + characterization test

**Test first:** new `App.scanFlow.test.tsx` mirroring the conventions of
`App.configEditor.test.tsx` (mocked api client, jsdom, `__APP_VERSION__`
global, Range polyfills). Written and green **before** extraction, kept green
after. Target scenarios (builder may refine, must cover at least):

1. Initial load: system info + config resolve → `executeScan` called with
   config-derived params → first page rendered.
2. 200-with-warning → warning surfaced as error toast (#130).
3. Scan rejection → error toast with the site's message prefix.
4. Deferred auto-rescan: typing schedules it; an explicit scan within the
   800 ms window wins (exactly one `executeScan`).
5. Directory change: `selectDirectory` config merges preferences (each
   site's own fallback: keep-current at the picked site, `""` at the
   changed site) and scans with merged values.
6. Load-more appends page 2 with path-based dedup.
7. Sort change reloads page 1 with sort params and resets selection.
8. Scan requested with no active directory → no `executeScan` call, no
   toast (pins the centralized empty-directory guard).

**New hook `hooks/useScanController.ts`** owns: scan state (74–89 incl.
`sort` — it is results-fetch ordering and moves with the controller),
generation/abort/pending-rescan refs, `beginScan`/`isCurrentScan`/
`finishScan`, `loadScanResults`, `runScan`, `handleLoadMore`, and:

```ts
type ScanParams = Parameters<typeof executeScan>[0];
type ScanOutcome =
  | { ok: true; firstPage: { items: ScannedFileItem[]; count: number } }
  | { ok: false };

// Self-contained: begins a generation, scans, finishes.
scanWith(params: ScanParams, opts?: { errorPrefix?: string }): Promise<ScanOutcome>;
// Generation-carrying core: caller already began the generation.
scanWithGeneration(generation: number, params: ScanParams,
                   opts?: { errorPrefix?: string }): Promise<ScanOutcome>;
```

`scanWith(params, opts)` = `beginScan()` then `scanWithGeneration`.
`scanWithGeneration` protocol (exact): **guard — empty `params.directory`
returns `{ok:false}` with no side effects** (no generation, no fetch; this
centralizes the `!activeDirectory` early-returns of `handleScan` 683–698 and
`handleClearFilter` 757–773, which are then removed as redundant); then
`executeScan` (200-with-warning → error toast, #130); first-page
`loadScanResults`; on success invoke the injected `onFreshResults()`
callback; catch → error toast `` `${errorPrefix ?? "Scan failed"}:
${err.message}` `` when generation is current; `finally` → `finishScan`.

**Early-claim sites** (builder call): the sites that today call
`beginScan()` *before* awaiting something — `handleDirectoryPicked` (before
`selectDirectory`, mid-await bail at 543), `handleDirectoryChange` (before
`selectDirectory`, bail at 657), `handleConfigLoaded` (388, before its state
applies), `handleReloadConfig` (330, before the fetches), `runInitialLoad`
(609) — keep that ordering via `beginScan()` + `scanWithGeneration`, so
race semantics, mid-await `isCurrentScan` bails, and spinner timing are
preserved exactly. The five sites that scan immediately (`handleScan`,
`handleClearFilter`, `handleDisableRecursive`, `handleFilterFolder`,
`handleFilterExtension`) use self-contained `scanWith`. This two-layer
split (builder call) is what makes "behavior-preserving" and
"deduplicate all ten blocks" simultaneously true.

The hook is injected with `{ showToast, getScanParams, onFreshResults }`;
`getScanParams()` returns the latest `{directory, extension, filter_text,
recursive}` so deferred rescans never read stale closures (the `handleScanRef`
pattern, 700–704, dies with this).

**Call-site migration (toast text preserved verbatim):**

| Site | Uses | errorPrefix |
|---|---|---|
| `handleScan`, `handleClearFilter`, `handleDisableRecursive`, `handleFilterFolder`, `handleFilterExtension` | `scanWith` | `"Scan failed"` |
| `handleDirectoryPicked` | `beginScan` + `scanWithGeneration` | `"Scan failed"` |
| `handleDirectoryChange` | `beginScan` + `scanWithGeneration` | `"Directory change failed"` (returns `outcome.ok`) |
| `handleConfigLoaded` | `beginScan` + `scanWithGeneration` | `"Scan failed after config load"` |
| `handleReloadConfig` | `beginScan` + `scanWithGeneration` | `"Failed to reload configuration"` (scan errors are toasted by the core; the outer catch keeps covering fetch errors; the outer `finally` keeps `finishScan` — beginScan at entry sets the spinner even if a fetch throws) |

`initializeFromConfig` (567–606) deliberately **keeps** the generation-carrying
`runScan` primitive: the init protocol intentionally sets no spinner ("the
init panel owns the feedback", 609–613), and `runInitialLoad` owns the
generation bump. The hook therefore exposes the `beginScan`/`runScan`/
`finishScan` primitives as well as `scanWith`/`scanWithGeneration`; PR 1
documents this exception in place.

**Deferred auto-rescan** (`pendingAutoRescanRef`, 800 ms) moves into the
hook: `scheduleDeferredRescan()` (used by the filter/recursive/extension
handlers), cancelled by `beginScan` (collision rule, 184–186) and on
unmount (teardown effect 638–647 moves into the hook).

`applySort(next)` on the hook: `setSort(next)` → reset selection via
`onFreshResults` → generation-carrying `loadScanResults(generation, next)`
with catch `"Sort failed"` / `finishScan` — the inline JSX block 1581–1596
moves out of render.

**Pure helper `utils/scanDefaults.ts`:**
`mergeDirectoryPreference(current: string, candidates: string[] | undefined,
fallback: string): string` = keep current when included, else
`candidates[0]`, else `fallback`. Replaces blocks 544–551 **and** 659–666 —
which today differ in their empty-list fallback (builder call): the picked
site falls back to the current value (`?? activeExtension` / `?? filterText`),
the changed site falls back to `""` (`?? ""`); both preserved via the
`fallback` argument, not unified. (The issue counted three blocks; the
third, in the config-load paths, is unconditional first-value semantics —
`cfg.extensions[0] ?? ""` — deliberately left inline, see anti-goals.)

**Repo hygiene in this PR:** create `hooks/`; update AGENTS.md web tree +
`tests/AGENTS.md`.

### PR 2 — small hooks: `useToast`, `useExternalEvents`, `useAutoRescanTimer`

- `useToast()`: state 98 + timer ref + `showToast`/`dismissToast` (155–176).
  Returns `{ toastMessage, showToast, dismissToast }`; 84 call sites keep
  working unchanged through the returned `showToast`.
- `useExternalEvents({ onConfigApplied, showToast })`: poll effect +
  `lastEventIdRef` + `externalConfigApplyRef` (458–489).
- `useAutoRescanTimer({ scan })`: `autoRescanInterval` state + interval
  effect + `handleTimerSet` (152–153, 1250–1271); periodic ticks call the
  injected `scan()` (= `scanWith(getScanParams())`).
- Move `utils/useModalA11y.ts` (+ its test) to `hooks/`.

### PR 3 — `useGlobalShortcuts`

The 200-line keydown effect (1291–1498) becomes
`useGlobalShortcuts(deps)` where `deps` groups: `anyModalOpen` (still
computed in App from modal state), selection data (`visibleFiles`,
`moveSelection(compute)` — see below), and the action callbacks the
effect already calls (`onExecute`, `onScan`, `onReloadConfig`, `onGoHome`,
`onProperties`, `onEscape` (also resets the drop overlay), modal open/toggle
setters, `onToggleTheme`, barcode toggles). Focus helpers
(`querySelector` on comboboxes / file list) live inside the hook.
Behavior identical: modal-inert guard, editable-target guard, control-target
guard, key-for-key.

Two preservation rules (builder calls, from the review):

- **`moveSelection(compute: (currentIndex: number, visibleCount: number) => number)`**
  applies its result inside a functional `setSelectedIndex` updater and
  writes `selectedPathRef` there, exactly as the current arrow/Home/End/
  PageUp/PageDown handlers (1452–1490) do — an absolute-index callback read
  from a closure would lose key-repeat steps when two keydowns land before
  re-render. (The ref write inside the updater is impure under StrictMode
  double-invoke; the current code does the same — preserved as-is.)
- **Staleness profile preserved:** action callbacks reach the keydown
  handler through subscription-time capture — the effect assigns
  `const d = deps` on each (re)subscription and `handleKeyDown` reads
  `d.*`, with the original 8-item dependency list verbatim — so
  re-subscription cadence and closure-capture windows match the
  pre-refactor code (latest-refs apply only to fire-time reads: timer
  ticks, the barcode 50 ms timeouts), and today's quirks (e.g. the stale
  `reloading` guard allowing a second Ctrl+R to re-enter mid-reload)
  survive unchanged rather than being silently fixed mid-refactor.
  (erratum folded from the PR 3 plan, 2026-11-17)

### PR 4 — `useBarcodeMode` + barcode decision + camera reuse

- `useBarcodeMode`: state + buffer ref (132–133), capture-phase keydown
  effect (1187–1245), `handleBarcodeToggle` (1139–1151),
  `applyBarcodeValues` (1153–1183). Injected: `showToast`, `scanWith`,
  `getScanParams`, state appliers (`onApplyValues(values)` in App for
  filter/ext/recursive/dir), `onSingleMatch(file)`.
- **The 50 ms commit deferral survives** (builder call): both scan paths
  (`applyBarcodeValues` 1172–1182 and the plain-filter path 1216–1222) keep
  `setTimeout(..., 50)` and read `getScanParams()` *inside* the timeout —
  the same guarantee `handleScanRef` gave the current code (scan reads the
  just-committed values; issue #34). A synchronous `scanWith(getScanParams())`
  right after `onApplyValues` would read pre-apply state and silently
  regress #34.
- `handleCameraDetected` (1076–1137) — the inline duplicate of
  execute+load — is rewritten onto `scanWith`; the single-match prompt
  (`count === 1 && items.length === 1`) is decided by the camera handler from
  `scanWith`'s returned `firstPage` (this behavior exists **only** in the
  camera path — preserve it there, error prefix `"Scan error"`).
- Pure decision (1165–1170) → `barcodeShouldScan(values)` in
  `utils/barcodeScanner.ts`, unit-tested.

### PR 5 — `useTheme` (+ fixes #129)

`hooks/useTheme.ts`:

- Initial state reads `localStorage.getItem("profiles-theme")` (try/catch,
  value validated ∈ {"dark","light"}, else "dark") — the missing read side
  of #129.
- `applyTheme(next, { persist })` replaces raw `setTheme` everywhere; the
  `data-theme` attribute effect stays; the **always-persist** effect
  (1500–1508) is deleted — persistence happens only when `persist` is true.
- Provenance per current documented intent: config-load/reload themes
  (`resolveSessionTheme`, 343 & 393) → `persist: false` (kills the
  session-trial leak); `initializeFromConfig` (570–580) → `persist: true`
  (config is source of truth at startup); user toggles (Ctrl+Shift+T,
  StatusBar) → `persist: true`.
- #129's `auto`-via-`matchMedia` idea: non-goal (follow-up issue).

Tests: localStorage restore, trial-load does not persist, config-init
persists, toggles persist, `data-theme` attribute follows.

### PR 6 — `useDragDropConfig`

`useDragDropConfig({ onConfigLoaded, showToast })`: tracker ref + overlay
visibility (431–437), window listeners (491–524), `handleDroppedConfig`
(439–451), plus the Escape hard-reset hook-up consumed by the shortcuts hook
(via the exported `applyDragState(resetDragState())` equivalent — builder
picks the seam, e.g. the hook returns `resetDrop()`). Existing
`utils/configDrop.ts` (pure tracker) is untouched.

### PR 7 — `LanConfirmDialog` + `pathToFileUri` + closes #148

- **`components/LanConfirmDialog.tsx`** (1843–1907): props
  `{ pending: boolean | null, systemInfo, onConfirmed(sys), onCancel }`.
  The component owns the observe-and-verify flow — `setLanEnabled`,
  `waitForLanState`, failure refetch — importing the api client directly
  (precedent: `ConfigEditorModal`), and toasts its own outcomes with the
  current message texts (1876–1904).
- **`utils/fileUri.ts`: `pathToFileUri(path: string): string`** replacing
  `new URL("file:///").href + path.replace(/\\/g, "/")` (925–933), which is
  wrong for UNC paths. Required behavior:
  - `C:\a\b.txt` → `file:///C:/a/b.txt`
  - `C:/a/b.txt` → `file:///C:/a/b.txt`
  - `\\server\share\a.txt` → `file://server/share/a.txt`
  - `/home/u/a.txt` → `file:///home/u/a.txt`
  - spaces / non-ASCII percent-encoded, `#`/`?` escaped.
  Unit-tested; `handleCopyUri` becomes a thin caller.

**End state:** App.tsx ≈ composition + presentation wiring; every extracted
unit has tests; suite green.

## Testing strategy

- Characterization test (PR 1) is the App-level safety net for the whole
  series and is never weakened by later PRs; scenarios may be extended, not
  deleted.
- Each hook ships focused unit tests (renderHook or component-level as
  appropriate); pure helpers get table tests in `utils/*.test.ts`.
- Existing `App.configEditor.test.tsx` stays green untouched (except import
  paths if it uses moved pieces — it doesn't today).
- Every PR: full `npx vitest run` green + `npm run build` (tsc) clean;
  `ruff`/pylint untouched (no Python changes).

## Constraints

- React 19, vitest + testing-library, no new dependencies.
- AGENTS.md layering: hooks live in `web/src/hooks/`, pure logic in
  `web/src/utils/`; App stays presentation-only.
- "Keep in sync" rule: AGENTS.md tree + `tests/AGENTS.md` updated in the
  commit introducing `hooks/`.
- Toast texts, shortcut behavior, and message prefixes are part of
  behavior — preserved verbatim (table above is the spec).

## Left to the builder

- Exact TS signatures beyond the sketches above (semantics are fixed).
- The Escape↔drag-reset seam in PR 6.
- Characterization-test scenario trimming beyond the eight mandatory ones.
- Fixture reuse patterns for hook tests (follow `tests/AGENTS.md` and
  existing component-test conventions).

## Calls made during the builder check (partner: skim while reviewing)

The reviewer subagent found six preservation gaps; all resolved as builder
calls (marked inline above): ① `mergeDirectoryPreference` gained a `fallback`
argument — the two merge blocks genuinely differ today (`""` vs keep-current)
and both are preserved; ② two-layer `scanWith`/`scanWithGeneration` split so
early-claim sites keep their exact race/spinner semantics; ③ empty-directory
guard centralized in the scan core, per-site early-returns removed as
redundant; ④ barcode 50 ms commit deferral kept verbatim; ⑤
`moveSelection` is functional-updater style (key-repeat steps preserved);
⑥ shortcut staleness profile preserved via latest-ref (existing quirks like
double-Ctrl+R re-entry survive the refactor untouched).
