# Issue #148 PR 6 — useDragDropConfig

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract App.tsx's window-level config drag/drop slice (App.tsx:334–400 @ fef5eef, plus the Escape hard-reset at 897–899) into `hooks/useDragDropConfig.ts` — behavior-preserving down to the []-dep effect's first-render captures and the render-scope `dropHandlerRef` latest-ref pattern.

**Architecture:** The hook receives `{ onConfigLoaded, showToast }` and owns: `dropOverlayVisible` state, `dragStateRef`, `applyDragState`, `dropHandlerRef` + its RENDER-SCOPE reassignment (not an effect — today App.tsx:353–355), `handleDroppedConfig`, and the window drag listeners effect (verbatim, `[]` deps, `const d = deps` subscription capture). It returns `{ dropOverlayVisible, resetDrop }` — `resetDrop()` is the Escape↔drag seam: App's `onEscape` calls it instead of `applyDragState(resetDragState())`. `utils/configDrop.ts` (pure tracker: `nextDragState`, `resetDragState`, `pickConfigFile`, `isAcceptedConfigName`) is untouched.

**Tech Stack:** React 19 custom hook, TypeScript, vitest + @testing-library/react + jsdom drag events, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` → "PR 6 — `useDragDropConfig`". All App.tsx line refs are against `refactor/148-pr5-use-theme` @ fef5eef (App.tsx = 1317 lines).

## Global Constraints

- Behavior-preserving, **including quirks** (the "quirks survive" framing applies to the drag-drop tracker):
  - The listeners effect keeps its exact `[]` dep list with subscription-time `const d = deps` capture. **Preserved quirk:** `onDrop`'s "Not a ProFiles configuration file." toast (App.tsx:385) reads the FIRST-render `d.showToast` (identity churns per render — useToast is a plain closure — but its internals only touch stable setState, so the capture works). Do not convert to a latest-ref.
  - `dropHandlerRef.current` is reassigned at RENDER SCOPE (App.tsx:353–355, deliberately not inside an effect) — every drop uses the CURRENT `handleConfigLoaded` (fresh closure over latest state). Preserve this exact structure; it is the codebase's latest-ref idiom for an async consumer.
  - `handleDroppedConfig`'s order is verbatim: `file.text()` → `loadConfigContent(file.name, content)` → `await deps.onConfigLoaded(cfg)` → success toast `` `Session config applied: ${file.name}` `` → catch: `err.message || "Failed to apply dropped configuration"` error toast. Note the catch swallows the error (no rethrow, no state change) — preserve.
  - Depth-counting tracker behavior is pinned by `utils/configDrop.test.ts` already; the hook tests pin the WIRING (overlay visibility, listeners, drop routing), not the reducer math.
  - `resetDrop()` = `applyDragState(resetDragState())` — hides the overlay AND zeroes the depth (a subsequent dragenter re-shows from depth 1). The WKWebView comment ("Cancelled drags may never fire dragleave — make Escape a hard reset for the drop overlay") moves to the hook's `resetDrop`; the App call site keeps a one-line pointer.
- Hook interface (normative — Task 2 imports these exact names):
  ```ts
  import type { AppConfigData } from "../api/types";
  export function useDragDropConfig(deps: {
    onConfigLoaded: (cfg: AppConfigData) => Promise<void>;
    showToast: (msg: string, kind?: "info" | "error") => void;
  }): {
    dropOverlayVisible: boolean;
    resetDrop: () => void;
  };
  ```
- No new npm dependencies; `dist/` churn uncommitted; conventional commits `(web)`/`(test)`.
- Branch: `refactor/148-pr6-drag-drop` off `refactor/148-pr5-use-theme` @ fef5eef (**stacked** on unmerged #178 → #179 → #182 → #184; PR opens with base `main`).
- Tests: `cd src/profiles/web && npx vitest run [file]`; type check `npm run build`. Gate = ALL GREEN (baseline 354; expected end ≈ 363 — use actuals in reports).
- Carry-forwards (fold-when-touched): none apply — this PR touches only App.tsx + the new hook files; App.tsx carries no open deferred minors (the `App.tsx:991 section-header wording` PR3 minor was cosmetic and the section header moved; do not hunt for it). The two remaining `handleScanRef` comment sites are NOT touched.

## Review Focus

1. **Depth-counting wiring** — nested enter/leave pairs must keep the overlay up until the last leave. Pinned by hook tests "overlay tracks nested enter/leave pairs and hides only at depth zero".
2. **Latest `onConfigLoaded` at drop time** — a drop after a rerender must use the NEW callback (render-scope `dropHandlerRef` reassignment). Pinned by hook test "drop uses the LATEST onConfigLoaded (rerender between mount and drop)".
3. **First-render showToast capture** — the not-a-config toast comes from the subscription-render deps. Pinned indirectly: the []-dep list is verbatim (code inspection) + the hook test asserting the toast text fires (any identity would pass it; the mechanism is pinned by the verbatim-move review).
4. **Reset completeness** — resetDrop must zero depth, not just hide the overlay. Pinned by hook test "resetDrop hides the overlay and resets the depth tracker".
5. **Accepted-file routing** — `.profiles`/`.profiles.yaml`/`.yaml`/`.yml` accepted; other files → error toast, no onConfigLoaded; no files → silent. Pinned by three hook tests (routing table).

---

### Task 1: `hooks/useDragDropConfig.ts` — hook tests + implementation (TDD)

**Files:**
- Create: `src/profiles/web/src/hooks/useDragDropConfig.ts`, `src/profiles/web/src/hooks/useDragDropConfig.test.tsx`

**Interfaces:**
- Consumes: `nextDragState`, `resetDragState`, `pickConfigFile`, `DragTrackerState` from `../utils/configDrop` (untouched); `loadConfigContent` from `../api/client`; `AppConfigData` from `../api/types`.
- Produces (normative — Task 2 imports): `useDragDropConfig` per the Global Constraints block.

- [ ] **Step 1: Write the failing hook tests** — renderHook; `vi.mock("../api/client", ...)` mocking `loadConfigContent` (resolve a minimal `AppConfigData` fixture); deps via a `depsFn` factory with `onConfigLoaded`/`showToast` as vi.fn()s so `rerender` can swap them; drive drag events with `fireEvent.dragEnter(window, { dataTransfer: { types: ["Files"] } })` / `dragLeave` / `drop` (drop events carry `{ dataTransfer: { types: ["Files"], files: [file] } }`; `new File(["content"], "machine.profiles")`). Test list (exact names):
  1. `dragenter with files shows the overlay` — enter → `dropOverlayVisible === true`.
  2. `dragenter without files does not show the overlay` — enter with `types: ["text/plain"]` → still false.
  3. `overlay tracks nested enter/leave pairs and hides only at depth zero` — enter, enter, leave → still visible; leave → hidden.
  4. `drop with an accepted file hides the overlay and applies the config` — enter; drop `machine.profiles` → overlay hidden; `loadConfigContent` called with ("machine.profiles", "content"); `onConfigLoaded` called with the resolved fixture; `showToast` called with "Session config applied: machine.profiles".
  5. `drop with a non-config file toasts the error and does not apply` — drop `notes.txt` → `showToast` with ("Not a ProFiles configuration file.", "error"); `onConfigLoaded` NOT called; overlay hidden.
  6. `drop with no files is silent` — drop with `files: []` → no toast, no apply, overlay hidden.
  7. `loadConfigContent failure toasts the server message` — mock rejects `Error("Bad YAML")` → `showToast` with ("Bad YAML", "error"); overlay already hidden by the drop reset.
  8. `loadConfigContent failure without a message toasts the fallback` — mock rejects a plain string rejection (or Error("")) → toast "Failed to apply dropped configuration".
  9. `drop uses the LATEST onConfigLoaded (rerender between mount and drop)` — mount with onConfigLoaded v1; enter; rerender with v2; drop → v2 called, v1 not.
  10. `resetDrop hides the overlay and resets the depth tracker` — enter; `act(() => result.current.resetDrop())` → hidden; enter; leave → hidden. (Discriminates: if resetDrop only hid the overlay without zeroing depth, the post-reset enter would make depth 2 and the single leave would leave it visible.)
  11. `unmount removes the window listeners` — unmount; fire enter/drop on window → no overlay state update (assert via spy-free observable: no throw and a second renderHook's fresh instance stays false — simplest: assert `showToast` not called after a drop post-unmount).
- [ ] **Step 2: Run — expected FAIL** (module missing).
- [ ] **Step 3: Implement `useDragDropConfig`** — move App.tsx:334–400 verbatim into the hook with `deps` indirection: state `dropOverlayVisible`; `dragStateRef`; `applyDragState` (verbatim); `handleDroppedConfig` reading `deps.onConfigLoaded`/`deps.showToast` (render-scope); `dropHandlerRef.current = (file) => { void handleDroppedConfig(file); }` at RENDER SCOPE (verbatim structure — NOT an effect); the listeners effect with `[]` deps + `const d = deps` subscription capture, `d.showToast` in onDrop, `dropHandlerRef.current(picked)` routing; `resetDrop` with the WKWebView comment. File-header doc comment: mechanism (subscription capture for the listeners' sync reads; render-scope dropHandlerRef reassignment for the async config apply — the codebase's latest-ref idiom), preserved quirks (first-render showToast capture in onDrop; catch swallows), "do not fix" (PR 3 precedent), and the Escape seam note (App's onEscape calls resetDrop).
- [ ] **Step 4: Run — expected PASS** (11/11). Full suite green (354 + 11 = 365); `npm run build` clean.
- [ ] **Step 5: Commit** — `refactor(web): add useDragDropConfig hook (window drag/drop + Escape reset) (#148)`

### Task 2: Rewire App.tsx onto the hook

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (delete ~70 lines, add ~10)

- [ ] **Step 1: Add the hook call** at the old slice's site (~line 334, AFTER `handleConfigLoaded` is declared — check: handleConfigLoaded is at 297, so the 334 site is fine):

```tsx
// Dropped configuration files: window-level drag/drop, session-only trial.
const { dropOverlayVisible, resetDrop } = useDragDropConfig({
  onConfigLoaded: handleConfigLoaded,
  showToast,
});
```

- [ ] **Step 2: Rewire the Escape seam** — `onEscape` (~892–899): replace `applyDragState(resetDragState());` + the WKWebView comment with `resetDrop(); // hard reset lives in useDragDropConfig (WKWebView dragleave gap)`. Keep the other four setters verbatim.
- [ ] **Step 3: Delete the moved code** — 334–355 (state, applyDragState, dropHandlerRef, handleDroppedConfig, render-scope reassignment) and 367–400 (the listeners effect). Clean up now-unused imports ONLY if tsc flags them (`nextDragState`, `resetDragState`, `DragTrackerState`, `pickConfigFile`, `isAcceptedConfigName` if unused — `isAcceptedConfigName` may have other App uses; check) and `DropConfigOverlay` wiring stays (`visible={dropOverlayVisible}`).
- [ ] **Step 4: Verify** — full suite green (365); `npm run build` clean; grep App.tsx: zero hits for `dragStateRef`, `applyDragState`, `dropHandlerRef`, `handleDroppedConfig`, `addEventListener("drag` ; `resetDrop` exactly 2 uses (destructure + onEscape); `nextDragState|pickConfigFile|DragTrackerState` zero hits unless still legitimately used (they shouldn't be — configDrop imports move entirely to the hook).
- [ ] **Step 5: Commit** — `refactor(web): route App.tsx drag/drop through useDragDropConfig (#148)`

### Task 3: Whole-PR verification, push, open PR

- [ ] **Step 1: Final gates** — full suite green; `npm run build` clean; `git status` clean except dist/tsbuildinfo churn; 3 commits total (plan + Task 1 + Task 2), messages exact.
- [ ] **Step 2: Push + open PR (stacked on #178 → #179 → #182 → #184)** — `git push -u origin refactor/148-pr6-drag-drop`; `gh pr create --base main --title "refactor(web): extract useDragDropConfig (App.tsx decomposition, PR 6/7)"` with a body following PR #184's pattern: What (hook + Escape seam via resetDrop + quirks preserved: depth-counting tracker, render-scope dropHandlerRef, first-render toast capture), Safety net (11 hook tests), Test plan (vitest green, tsc clean, manual: drag a .profiles over the window → overlay + session trial; drag a .txt → error toast; Escape mid-drag → overlay gone).
- [ ] **Step 3: Confirm CI** — `gh pr checks` (3 workflows pending → pass).
