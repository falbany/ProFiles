# Issue #148 PR 4 — useBarcodeMode + barcode decision + camera pin

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract App.tsx's barcode slice — mode state + wedge-scanner capture listener (~60 lines), `handleBarcodeToggle`, `applyBarcodeValues`, `handleCameraDetected` (App.tsx:850–989 @ 70858d5) — into `hooks/useBarcodeMode.ts`, move the `shouldScan` decision to `utils/barcodeScanner.ts` as `barcodeShouldScan`, and add the two App-level characterization pins (wedge rescan, camera single-match) — behavior-preserving down to the staleness profile.

**Architecture:** The hook receives a deps bag. The capture-phase keydown effect **captures the bag at subscription time** (`const d = deps`, dep list `[deps.barcodeMode]` — PR 3's ruling pattern) for synchronous reads, and reads `depsRef.current.getScanParams()`/`.scanWith` **inside the 50 ms timeouts only** — exactly the freshness `handleScanRef.current()` gave those timeouts (issue #34). Per-render hook-body handlers (`handleBarcodeToggle`, `handleCameraDetected`, internal `applyBarcodeValues`) read `deps.*` render-scope, matching today's per-render closures. `handleCameraDetected` is already on `scan.scanWith` (done in PR 1) — this PR only relocates it and pins it.

**Tech Stack:** React 19 custom hook, TypeScript, vitest + @testing-library/react + jsdom key events, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` → "PR 4 — `useBarcodeMode` + barcode decision + camera reuse" + builder call ④ (barcode 50 ms commit deferral kept verbatim). All App.tsx line refs are against `refactor/148-pr3-global-shortcuts` @ 70858d5 (App.tsx = 1454 lines).

## Global Constraints

- Behavior-preserving, **including quirks** (the "quirks survive" framing, carried from the PR 3 ledger):
  - The 50 ms commit deferral survives VERBATIM on both scan paths (`applyBarcodeValues` App.tsx:923–925 and the plain-filter path 966): `setTimeout(..., 50)`, params read **inside** the timeout. A synchronous scan right after applying would read pre-apply state and regress #34. No timeout cleanup is added on unmount (today's code is fire-and-forget).
  - Mode stays ON when the parsed values don't warrant a scan: `scan=0`-only and unknown-key barcodes (`foo=bar` → empty `vals`) toast `"Barcode applied: …"` but leave barcodeMode true and never scan (App.tsx:910–916's `shouldScan` gate, preserved by `barcodeShouldScan`).
  - The capture listener does NOT call `stopPropagation` — today a wedge Enter on a non-editable target ALSO reaches the global-shortcuts window listener (Enter → `onExecute()`; harmless no-op on an empty list). Do not "fix" this.
  - Empty-buffer Enter returns **before** `e.preventDefault()` (App.tsx:950–953) — keep the ordering.
  - Camera handler closes the modal and toasts **before** parsing/scanning (App.tsx:851–852); single-match (`count === 1 && items.length === 1`) is decided ONLY in the camera path, error prefix `"Scan error"`; barcode rescan paths use `"Scan failed"` (today they route through `handleScan`).
- Mechanism (binding): subscription-time capture for the keydown effect's synchronous reads; latest-ref (`depsRef`) ONLY inside the 50 ms timeouts. Do NOT convert the sync reads to `depsRef` — today's effect closes over the subscription render's `showToast`/`applyBarcodeValues`, and PR 3's ruling (spec rule ⑥ erratum) applies here unchanged.
- Spec-sketch additions (builder latitude, "Left to the builder"): deps gain `onCameraClose: () => void` (today's `setShowCameraScanner(false)` at App.tsx:851) and `setFilterText` raw (plain-filter path's direct `setFilterText(result.values.filter || "")` at 962, `|| ""` quirk included). `onApplyValues(values)` covers filter/ext/recursive/dir per the spec sketch.
- No new npm dependencies; `dist/` churn uncommitted; conventional commits `(web)`.
- Branch: `refactor/148-pr4-barcode` off `refactor/148-pr3-global-shortcuts` @ 70858d5 (**stacked** on unmerged PRs #178 → #179; PR opens with base `main`).
- Tests: `cd src/profiles/web && npx vitest run [file]`; type check `npm run build`. Gate = ALL GREEN (baseline 321; expected end state ≈ 338 — counts in tasks are expectations; use actuals in reports).
- `handleGenerateBarcode` / `showBarcodeModal` / `barcodeFilePath` (barcode *generation* modal) and `singleMatchFile`/`showCameraScanner` state STAY in App (presentation wiring + modal visibility).
- AGENTS.md tree stays unchanged (`hooks/`, `utils/` already listed generically).

## Review Focus

1. **#34 stale-scan regression** — barcode values committed but the deferred scan reads pre-apply params. Pinned by hook test "50 ms timeout reads the LATEST getScanParams (issue #34)" (rerender with changed params between Enter and timer fire) and App-level wedge test (scan call must carry `filter_text: ".py"`, not the pre-barcode filter).
2. **Mode-off semantics** — mode must turn OFF on any scan-triggering barcode (2) but stay ON for `scan=0`-only and unknown-key barcodes. Pinned by hook tests "quirk: …" (two) + mode-off assertion in the key=value test.
3. **Error prefixes** — camera path `"Scan error"` vs barcode rescan `"Scan failed"`. Pinned by hook tests (camera asserts the prefix explicitly; wedge tests assert `"Scan failed"`).
4. **Single-match must not generalize** — only the camera handler decides `count === 1 && items.length === 1` → `onSingleMatch`. Pinned by hook tests (single-match fires; count≠1 / `ok:false` don't) + App-level camera test.
5. **Enter coexistence / no stopPropagation** — adding `stopPropagation` in the capture listener would silently change global-shortcuts behavior. No test can see it at hook level (the window listener isn't mounted there); verified by verbatim-move code inspection + the useGlobalShortcuts suite staying green + App-level wedge test's documented Enter note.

---

### Task 1: Characterization extension — wedge rescan + camera single-match

**Files:**
- Modify: `src/profiles/web/src/App.scanFlow.test.tsx`

**Interfaces:**
- Consumes: existing scaffold (mocked client, `makeAppConfig`/`makeFile`, `beforeEach` defaults). Real timer/fake-timer precedents: the deferred-rescan scenario (fake timers + `userEvent.setup({ advanceTimers })`) and the config-handoff scenario.
- Produces: two App-level pins kept green through Tasks 3–4's rewire. Also the FIRST component mock in this file (justified: `CameraBarcodeModal` needs `getUserMedia`/`BarcodeDetector`, unreachable in jsdom) — stub honors `isOpen`, renders a `Detect test code` button calling `onDetected("filter=cam;ext=.yaml")`, else `null`; harmless to the other 8 tests (modal closed → null).

- [ ] **Step 1: Add the file-top mock** (after the api/client mock):

```tsx
vi.mock("./components/CameraBarcodeModal", () => ({
  CameraBarcodeModal: ({ isOpen, onDetected }: { isOpen: boolean; onDetected: (code: string) => void }) =>
    isOpen ? (
      <button type="button" onClick={() => onDetected("filter=cam;ext=.yaml")}>
        Detect test code
      </button>
    ) : null,
}));
```

- [ ] **Step 2: Add test `wedge scanner input applies barcode values and rescans after 50 ms`** — fake timers (`vi.useFakeTimers({ shouldAdvanceTime: true })`, `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`, same as the deferred-rescan scenario). Render; settle init (`executeScanSpy` 1×). Click `Enable barcode mode` (SearchBar button). For each char of `"filter=.py"`: `fireEvent.keyDown(document.body, { key: ch })` (body target — non-editable, and plain letters hit no shortcut on an empty list). Then `fireEvent.keyDown(document.body, { key: "Enter" })` — NOTE in a comment: this Enter ALSO reaches the global-shortcuts listener (`onExecute`), a pre-existing no-op on the empty list; do not assert it away. `act(() => vi.advanceTimersByTime(50))`. Assert: `await screen.findByText("Barcode applied: filter=.py")` (find by text — the init `Loaded config` toast is still within its 3.5 s auto-dismiss at t=50 ms, so `role="status"` may match several toasts); `executeScanSpy` 2× with last call `{ directory: "C:/data", extension: ".mttl", filter_text: ".py", recursive: false }` (the NEW filter — the #34 pin).
- [ ] **Step 3: Add test `camera detection applies values and prompts on single match`** — real timers. Render; settle init. After init, `scanResultsSpy.mockResolvedValue({ count: 1, items: [makeFile("only.mttl")] })`. Click `Scan barcode with camera`; the stub modal appears. Click `Detect test code`. Assert: stub gone (`queryByText("Detect test code")` null); `await screen.findByText("Barcode detected!")`; `executeScanSpy` 2× with last call `{ directory: "C:/data", extension: ".yaml", filter_text: "cam", recursive: false }`; `await screen.findByRole("dialog", { name: "1 file matched: only.mttl" })`.
- [ ] **Step 4: Run — expected GREEN against current code** (10/10 in the file; fix the test if red — never App.tsx).
- [ ] **Step 5: Commit** — `test(web): characterize wedge-scan and camera single-match paths (#148)`

### Task 2: `barcodeShouldScan` in utils/barcodeScanner.ts

**Files:**
- Create: `src/profiles/web/src/utils/barcodeScanner.test.ts`
- Modify: `src/profiles/web/src/utils/barcodeScanner.ts`

**Interfaces:**
- Produces (normative — Task 3 imports this exact name):

```ts
export function barcodeShouldScan(values: Partial<BarcodeParsedInput>): boolean;
```

- [ ] **Step 1: Write the failing table tests** — `barcodeShouldScan` returns true for: `{ scan: true }` (alone), and each of `{ filter: "x" }` / `{ ext: ".py" }` / `{ recursive: false }` / `{ dir: "C:/d" }` alone (recursive FALSE still counts — presence, not truthiness); false for `{}`, `{ scan: false }`, and `{ scan: false, filter: undefined }`.
- [ ] **Step 2: Run — expected FAIL** (function not exported).
- [ ] **Step 3: Implement** — verbatim decision moved from App.tsx:910–914: `values.scan === true || values.filter !== undefined || values.ext !== undefined || values.recursive !== undefined || values.dir !== undefined`. Doc comment: "A barcode application triggers a rescan when it asked to (`scan=1`) OR changed any value — moved verbatim from App.tsx (issue #148 PR 4)."
- [ ] **Step 4: Run — expected PASS** (new file green; full suite green).
- [ ] **Step 5: Commit** — `refactor(web): extract barcodeShouldScan decision into utils (#148)`

### Task 3: `hooks/useBarcodeMode.ts` — hook tests + implementation

**Files:**
- Create: `src/profiles/web/src/hooks/useBarcodeMode.ts`, `src/profiles/web/src/hooks/useBarcodeMode.test.tsx`

**Interfaces (normative — Task 4 imports these exact names):**

```ts
import type { Dispatch, SetStateAction } from "react";
import type { ScanParams, ScanOutcome } from "./useScanController";
import type { BarcodeParsedInput } from "../utils/barcodeScanner";
import type { ScannedFileItem } from "../api/types";

export interface BarcodeModeDeps {
  showToast: (msg: string, kind?: "info" | "error") => void;
  scanWith: (params: ScanParams, opts?: { errorPrefix?: string }) => Promise<ScanOutcome>;
  getScanParams: () => ScanParams;
  onApplyValues: (values: Partial<BarcodeParsedInput>) => void;
  onSingleMatch: (file: ScannedFileItem) => void;
  onCameraClose: () => void;
  setFilterText: Dispatch<SetStateAction<string>>;
}

export function useBarcodeMode(deps: BarcodeModeDeps): {
  barcodeMode: boolean;
  setBarcodeMode: Dispatch<SetStateAction<boolean>>;
  handleBarcodeToggle: () => void;
  handleCameraDetected: (rawCode: string) => Promise<void>;
};
```

- [ ] **Step 1: Write the failing hook tests** — renderHook with a deps factory returning vi.fn()s (`scanWith` resolves `{ ok: false }` by default); fake timers; enable mode via `act(() => result.current.setBarcodeMode(true))`; wedge input via `fireEvent.keyDown(document.body, { key: ch })`. Test list:
  1. `toggle toasts and resets the buffer` — `handleBarcodeToggle()` → `Barcode mode ON — scan a barcode now.`; type `"ab"`; toggle OFF → `Barcode mode OFF.`; toggle ON; Enter → empty-buffer no-op (no parse toast, no `scanWith` — proves the buffer was reset).
  2. `key=value barcode applies values, disables mode, rescans after 50 ms` — type `"filter=x;scan=1"`, Enter → toast `Barcode applied: filter=x, scan=1`; `onApplyValues` called with `{ filter: "x", scan: true }`; `barcodeMode` now false; advance 50 ms → `scanWith` called once with `(getScanParams(), { errorPrefix: "Scan failed" })` — and NOT before the advance.
  3. `plain-filter barcode sets filter and rescans` — type `"hello"` (no `=`) → toast `Barcode filter: hello`; `setFilterText` called with `"hello"`; mode off; 50 ms → `scanWith` with `"Scan failed"`.
  4. `quirk: scan=0-only barcode does not scan and mode stays on` — type `"scan=0"` → toast `Barcode applied: scan=0`; advance 100 ms → `scanWith` NOT called; `barcodeMode` still true.
  5. `quirk: unknown-key barcode applies nothing and mode stays on` — type `"foo=bar"` → toast `Barcode applied: ` (empty summary); `onApplyValues` called with `{}`; no scan; mode still true.
  6. `escape cancels barcode mode` → mode off, toast `Barcode mode cancelled.`
  7. `editable targets are ignored (issue #58)` — keydown chars on a rendered `<input>`; then Enter on body → empty-buffer no-op (nothing accumulated, no scan, no `onApplyValues`).
  8. `modifier combos are not accumulated` — `{ key: "r", ctrlKey: true }` then Enter → no scan.
  9. `50 ms timeout reads the LATEST getScanParams (issue #34)` — enable with `getScanParams` returning `{ directory: "C:/a", extension: ".mttl", filter_text: "", recursive: false }`; `rerender` with `getScanParams` returning `{ directory: "C:/b", ... filter_text: "z" ... }` (mode dep unchanged — no re-subscription); type `"scan=1"`, Enter, advance 50 → `scanWith` called with the **C:/b** params. (Today's equivalent: `handleScanRef.current()` at fire time. Pins the classic #34 regression.)
  10. `camera detection applies, scans with Scan error prefix, prompts on single match` — `scanWith` resolves `{ ok: true, firstPage: { items: [file], count: 1 } }`; `await handleCameraDetected("dir=C:/cam;filter=q")` → `onCameraClose` called; toast `Barcode detected!`; `onApplyValues({ dir: "C:/cam", filter: "q" })`; `scanWith` called with `{ directory: "C:/cam", extension: <getScanParams>, filter_text: "q", recursive: <getScanParams> }` and `{ errorPrefix: "Scan error" }`; `onSingleMatch` called with the file.
  11. `camera multi-match and failed scans do not prompt` — `count: 2` → no `onSingleMatch`; `ok: false` → no `onSingleMatch`.
  12. `unmount removes the listener` — unmount; keydown on body → no crash, no `scanWith`.
- [ ] **Step 2: Run — expected FAIL** (module missing). Implement by moving App.tsx:850–989 verbatim into the hook:
  - `barcodeMode` state + `barcodeBufferRef` move in; the capture effect keeps its comments (wedge-scanner, issue #58) and dep list `[deps.barcodeMode]`, with `const d = deps` subscription capture; sync reads via `d.*` (`d.showToast`, `d.onApplyValues` through the internal `applyBarcodeValues`, `d.setFilterText`, `d.setBarcodeMode`); the two 50 ms timeouts read `depsRef.current.getScanParams()` + `depsRef.current.scanWith(…, { errorPrefix: "Scan failed" })` (depsRef kept latest by a per-render effect — the useAutoRescanTimer idiom).
  - Internal `applyBarcodeValues(values)`: today's body with `d.onApplyValues(values)` for the four setters, `barcodeShouldScan(values)` replacing the inline decision, and the mode-off + buffer-clear + 50 ms timeout inside the `if` (verbatim structure; the issue-#34 comment moves with it).
  - `handleBarcodeToggle` / `handleCameraDetected`: per-render hook-body handlers reading `deps.*` render-scope; camera handler keeps today's order (close → toast → parse → compute `next*` from `deps.getScanParams()` → apply via `deps.onApplyValues` → `if (nextDir)` scan → single-match check) and verbatim comments.
  - File-header doc comment: encodes the mechanism ruling (subscription capture for sync reads, latest-ref only at timeout fire), the preserved quirks (no stopPropagation, empty-buffer-Enter-before-preventDefault, no timeout cleanup, mode-stays-on gate), and "do not fix" (PR 3 precedent).
- [ ] **Step 3: Run hook tests — expected PASS** (12/12). Full suite green; `npm run build` clean.
- [ ] **Step 4: Commit** — `refactor(web): add useBarcodeMode hook (wedge listener + camera handler) (#148)`

### Task 4: Rewire App.tsx onto the hook

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (delete ~155 lines, add ~35)

**Interfaces:**
- Consumes: `useBarcodeMode`/`BarcodeModeDeps` from Task 3, `barcodeShouldScan` (indirectly, via the hook).
- Produces: same App component; `singleMatchFile`, `showCameraScanner`, barcode-generation modal state stay.

- [ ] **Step 1: Hoist `getScanParams`** — extract the inline arrow at App.tsx:155 to `const getScanParams = () => ({ directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive });` above `useScanController`, passed to both the controller and (Task 4 Step 2) the barcode hook.
- [ ] **Step 2: Add the hook call** after the `useScanController` block (~line 161; all referenced state is declared above):

```tsx
const {
  barcodeMode, setBarcodeMode, handleBarcodeToggle, handleCameraDetected,
} = useBarcodeMode({
  showToast,
  scanWith: scan.scanWith,
  getScanParams,
  onApplyValues: (values) => {
    if (values.filter !== undefined) setFilterText(values.filter);
    if (values.ext !== undefined) setActiveExtension(values.ext);
    if (values.recursive !== undefined) setRecursive(values.recursive);
    if (values.dir !== undefined) setActiveDirectory(values.dir);
  },
  onSingleMatch: setSingleMatchFile,
  onCameraClose: () => setShowCameraScanner(false),
  setFilterText,
});
```

(The applier keeps today's field order — filter, ext, recursive, dir.)
- [ ] **Step 3: Delete the moved code** — `barcodeMode`/`barcodeBufferRef` decls (116–117), `handleCameraDetected` (850–881), `handleBarcodeToggle` (883–895), `applyBarcodeValues` (897–927), the capture effect + its comments (929–989), and the `parseBarcodeInput` import (54). Rewire: SearchBar `barcodeMode`/`onBarcodeToggle`, useGlobalShortcuts `setBarcodeMode`, CameraBarcodeModal `onDetected` ← hook returns.
- [ ] **Step 4: Kill `handleScanRef`** — its only remaining consumer after Step 3 is the timer wiring (523–528). Rewire to `scan: () => { void handleScan(); }` (the timer hook's own depsRef provides latest-at-tick — identical semantics to `handleScanRef.current()`), delete the ref + its updater effect (514–518), and update the stale comment at 520–522 (it mentions handleScanRef).
- [ ] **Step 5: Verify** — full suite green; `npm run build` clean; grep App.tsx: zero hits for `barcodeBufferRef`, `parseBarcodeInput`, `applyBarcodeValues`, `handleScanRef`, `Barcode scanner input` (the capture listener was App's LAST keydown surface — confirm via `grep -n "addEventListener(\"keydown\"" src/profiles/web/src/App.tsx` → no matches).
- [ ] **Step 6: Commit** — `refactor(web): route App.tsx barcode handling through useBarcodeMode (#148)`

### Task 5: Whole-PR verification, push, open PR

- [ ] **Step 1: Final gates** — full suite green; `npm run build` clean; `git status` clean except dist/tsbuildinfo churn; 5 commits total (plan + 4), messages exact.
- [ ] **Step 2: Push + open PR (stacked on #178 → #179)** — `git push -u origin refactor/148-pr4-barcode`; `gh pr create --base main --title "refactor(web): extract useBarcodeMode (App.tsx decomposition, PR 4/7)" --body "$(cat <<'EOF'
Part of #148 (PR 4/7 of the series in docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md). **Stacked on #178 → #179** — shows their commits until those PRs merge.

## What
- New `hooks/useBarcodeMode.ts`: barcode mode state, the wedge-scanner capture-phase keydown listener, `handleBarcodeToggle`, and `handleCameraDetected` move out of App.tsx — behavior-identical, quirks included (no `stopPropagation`, empty-buffer Enter before `preventDefault`, no timeout cleanup, mode stays on for `scan=0`-only/unknown-key barcodes).
- Issue #34 seam preserved: the two 50 ms commit-deferral timeouts read `getScanParams()`/`scanWith` through a latest-ref AT FIRE TIME (the `handleScanRef` guarantee, now hook-local); synchronous handler reads use subscription-time capture (PR 3's ruling). `handleScanRef` itself is deleted — its last consumer (auto-rescan timer wiring) reads latest through the timer hook's own depsRef.
- Pure decision `barcodeShouldScan(values)` → `utils/barcodeScanner.ts` (next to `parseBarcodeInput`), unit-tested.
- Camera single-match prompt (`count === 1 && items.length === 1`, error prefix `"Scan error"`) decided only in the camera handler — now pinned by App-level characterization (the only PR 1-migrated flow without one), alongside a wedge-rescan pin.

## Safety net
- 12-scenario hook suite (toggle/buffer, both wedge paths, two quirk pins, #58 guard, staleness pin, camera single-match/no-match, unmount).
- Characterization suite extended to 10 tests; green throughout.

## Test plan
- [ ] `cd src/profiles/web && npx vitest run` green
- [ ] `npm run build` (tsc) clean
- [ ] Manual: Ctrl+B toggle + wedge scan (filter=…;scan=1), plain-text barcode, Escape cancel, camera scan single-match prompt
EOF
)"`
- [ ] **Step 3: Confirm CI started** — `gh pr checks` (3 workflows pending → pass; CI runs on the stacked branch).
