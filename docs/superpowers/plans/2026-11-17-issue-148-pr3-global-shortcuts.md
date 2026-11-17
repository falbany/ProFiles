# Issue #148 PR 3 — useGlobalShortcuts (the 200-line keydown effect)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract App.tsx's global keyboard-navigation/shortcuts effect (~206 lines, App.tsx:993–1218 @ main-post-PR-2) into `hooks/useGlobalShortcuts.ts` — behavior-preserving down to the staleness profile — and add the App-level characterization test for the config-handoff poll seam deferred from PR 2's final review.

**Architecture:** The hook receives a deps bag; the effect **captures the bag at subscription time** and re-subscribes on the ORIGINAL effect's exact 8-item dep list, so every closure-capture window is identical to today. Escape/onContextMenu/actions become injected callbacks; React setters pass through raw (stable identities, functional updates preserved); selection goes through `moveSelection(compute)` in functional-updater style (App writes `selectedPathRef` inside the updater, as today). `anyModalOpen` stays computed in App. `TABLE_PAGE_JUMP = 20` moves into the hook file.

**Tech Stack:** React 19 custom hook, TypeScript, vitest + @testing-library/react + jsdom key events, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` → "PR 3 — `useGlobalShortcuts`" + the two preservation rules from "Calls made during the builder check" (⑤ moveSelection functional-updater; ⑥ staleness profile preserved). All App.tsx line refs are against `refactor/148-pr2-small-hooks` @ 332e951 (App.tsx = 1630 lines).

## Global Constraints

- Behavior-preserving, **including quirks**: the stale `reloading` guard window (second Ctrl+R during an in-flight reload can re-enter until the first dep-changing setState lands) must survive unchanged. This rules out per-render latest-ref injection for action callbacks — see the Ruling below.
- Mechanism ruling (spec-text erratum, binding for this plan): the spec's "action callbacks reach the keydown handler through a latest-ref" is amended to **subscription-time capture**: the effect assigns `const d = deps` on each (re)subscription and `handleKeyDown` reads `d.*`. Combined with keeping the original dep list verbatim (`[anyModalOpen, visibleFiles, selectedIndex, activeDirectory, activeExtension, filterText, recursive, barcodeMode]`), this reproduces re-subscription cadence AND closure-capture windows exactly. The spec's intent ("today's quirks survive unchanged") is the authority.
- Key-for-key shortcut behavior identical: Escape-before-modal-guard ordering; the interactive-target guard (`closest("button, a, [role='menuitem'], [role='option'], [role='columnheader'], [role='separator']")`); input/select Enter→scan; every `e.preventDefault()` placement; Ctrl-with/without-Shift disambiguation (L vs Shift+L, B vs Shift+B, T vs Shift+T).
- No new npm dependencies; `dist/` churn uncommitted; conventional commits `(web)`.
- Branch: `refactor/148-pr3-global-shortcuts` off `refactor/148-pr2-small-hooks` @ 332e951 (**stacked** on unmerged PR #178; PR opens with base `main` — the diff shrinks to this PR's commits once #178 merges).
- Tests: `cd src/profiles/web && npx vitest run [file]`; type check `npm run build`. Gate = ALL GREEN (baseline 310/24).

## Review Focus

1. **Staleness profile** — a callback identity change with UNCHANGED state deps must NOT be seen by the running handler; a state-dep change must re-subscribe and be seen. Pinned by hook test "captures callbacks at subscription time (staleness profile preserved)" (both directions).
2. **Modal-inert guard with Escape carve-out** — Escape closes surfaces even while `anyModalOpen` is true; every other shortcut is inert. Pinned by hook tests "escape closes surfaces even when a modal is open" and "shortcuts are inert while a modal is open".
3. **Key disambiguation** — Ctrl+L (focus list) vs Ctrl+Shift+L (log viewer); Ctrl+B (barcode) vs Ctrl+Shift+B (camera); Ctrl+T (timer) vs Ctrl+Shift+T (theme). Pinned by three disambiguation assertions inside the shortcut tests.
4. **Selection computes** — each navigation key's clamp/identity semantics (Home keeps `prev===0?prev:0`; End keeps `prev===next?prev:next`; arrows clamp; Page±20). Pinned by "navigation moves selection via functional computes" asserting each compute's output table.
5. **Target guards** — Enter in an input selects scan-Enter path (no execute); keys on a `button` target are ignored; body-keyed Enter executes. Pinned by "target guards route keys correctly".

---

### Task 1: Characterization extension — config_applied poll drives a full config refresh

**Files:**
- Modify: `src/profiles/web/src/App.scanFlow.test.tsx`

**Interfaces:**
- Consumes: existing scaffold (mocked client, fixtures). The poll (`fetchNotifications`) currently returns `{ events: [] }` — this test gives it a real event.
- Produces: the App-level pin for the poll→`onConfigApplied`→`handleConfigLoaded`→scan seam (PR 2 final review recommendation), kept green through Task 3's rewire.

- [ ] **Step 1: Add the test** (fake timers like S4: `vi.useFakeTimers({ shouldAdvanceTime: true })` + `userEvent.setup({ advanceTimers })`):

`config_applied notification re-applies config and rescans` — init settles with the default config; then `fetchNotificationsSpy` → `{ events: [{ id: 1, message: "Config applied by second launch.", config_applied: true }] }`; `fetchConfigSpy` (second return) → `makeAppConfig({ filters: ["handoff"], extensions: [".yaml"], active_directory: "C:/handoff" })`. Advance 4000 ms. Assert: `fetchNotificationsSpy` called with `0`; `fetchConfigSpy` called twice (init + apply); the LAST `executeScan` call === `{ directory: "C:/handoff", extension: ".yaml", filter_text: "handoff", recursive: false }`; the toast (`role="status"`) shows `"Config applied by second launch."`.

- [ ] **Step 2: Run — expected GREEN against current code** (8/8 in the file; fix the test if red — never App.tsx).
- [ ] **Step 3: Commit** — `test(web): characterize config-handoff poll refresh path (#148)`

### Task 2: `hooks/useGlobalShortcuts.ts` — hook tests + implementation

**Files:**
- Create: `src/profiles/web/src/hooks/useGlobalShortcuts.ts`, `src/profiles/web/src/hooks/useGlobalShortcuts.test.tsx`

**Interfaces (normative — Task 3 imports these exact names):**

```ts
import type { Dispatch, SetStateAction } from "react";
import type { ContextMenuPosition } from "../components/ContextMenu";
import type { ScannedFileItem } from "../api/types";

export interface GlobalShortcutsDeps {
  // Re-subscription cadence — the ORIGINAL effect's exact dep list.
  anyModalOpen: boolean;
  visibleFiles: ScannedFileItem[];
  selectedIndex: number;
  activeDirectory: string;
  activeExtension: string;
  filterText: string;
  recursive: boolean;
  barcodeMode: boolean;
  // Handlers captured at subscription time (same staleness windows as today).
  onEscape: () => void;
  onContextMenu: (pos: ContextMenuPosition) => void;
  onExecute: () => void;
  onScan: () => void;
  onReloadConfig: () => void;
  onGoHome: () => void;
  onProperties: (file: ScannedFileItem) => void;
  onToggleTheme: () => void;
  // React setters, passed raw (stable identities; functional updates preserved).
  setShowLogViewer: Dispatch<SetStateAction<boolean>>;
  setShowShortcuts: Dispatch<SetStateAction<boolean>>;
  setShowTimerModal: Dispatch<SetStateAction<boolean>>;
  setShowConfigEditor: Dispatch<SetStateAction<boolean>>;
  setBarcodeMode: Dispatch<SetStateAction<boolean>>;
  setShowCameraScanner: Dispatch<SetStateAction<boolean>>;
  // Selection — functional-updater style; App writes selectedPathRef inside the updater.
  moveSelection: (compute: (currentIndex: number, visibleCount: number) => number) => void;
}
export function useGlobalShortcuts(deps: GlobalShortcutsDeps): void;
```

- [ ] **Step 1: Write the failing hook tests** — fixture DOM in the test file (`data-testid='file-list'` element + `#directory-combobox`/`#extension-combobox`/`#filter-combobox` inputs + a row `[data-row-index="N"]`), key events via `fireEvent.keyDown(window, { key, ctrlKey, shiftKey })`. Test list:
  1. `escape closes surfaces even when a modal is open` (anyModalOpen true → `onEscape` called; plain key → nothing)
  2. `shortcuts are inert while a modal is open` (Ctrl+R/F5/Enter/arrows → no callback fired)
  3. `ctrl+L focuses the file list` (+ Shift+L variant does NOT focus but toggles log viewer)
  4. `target guards route keys correctly` (Enter in input → `onScan`; Enter on a `button` target → nothing; Enter on body → `onExecute`)
  5. `context menu opens at the selected row` (ContextMenu key & Shift+F10 → `onContextMenu` with `visibleFiles[selectedIndex]` and x/y = rect+24/center or 24 fallbacks; no file → no call)
  6. `action shortcuts fire their callbacks` (F5→onScan, Ctrl+R→onReloadConfig, Ctrl+H→onGoHome, P→onProperties(file), Ctrl+Shift+T→onToggleTheme, Ctrl+B→setBarcodeMode updater, Ctrl+Shift+B→setShowCameraScanner updater, Ctrl+T→setShowTimerModal(true), Ctrl+,→setShowConfigEditor(true), ?/Ctrl+/→setShowShortcuts updater)
  7. `focus shortcuts target the comboboxes` (Ctrl+D/E/F → document.activeElement is each input)
  8. `navigation moves selection via functional computes` — capture `moveSelection`'s compute arg per key and assert the output table: ArrowDown (0,10)→1, ArrowDown (9,10)→9; ArrowUp (0,10)→0, ArrowUp (5,10)→4; Home (5,10)→0 AND (0,10)→0; End (3,10)→9 AND (9,10)→9; PageUp (25,100)→5; PageDown (0,100)→20, PageDown (95,100)→99
  9. `captures callbacks at subscription time (staleness profile preserved)` — render deps with `onReloadConfig` v1; `rerender` with v2 (all state deps UNCHANGED) → Ctrl+R invokes **v1**; then `rerender` with v3 AND a changed state dep (`filterText`) → Ctrl+R invokes **v3**. (Pins Ruling: subscription-time capture; this is the double-Ctrl+R quirk's survival proof.)
  10. `unmount removes the listener` (keydown after unmount → nothing)
- [ ] **Step 2: Run — expected FAIL** (module missing). Implement by moving App.tsx:1011–1218 verbatim into the effect: `const d = deps;` captured per subscription (the Ruling), body reads `d.anyModalOpen`/`d.visibleFiles`/`d.selectedIndex`/`d.on*`/`d.set*`; Escape branch → `d.onEscape()`; context-menu branch keeps the row-query + rect math verbatim → `d.onContextMenu({ x, y, file })`; navigation branches → `d.moveSelection((prev, count) => ...)` with the per-key computes (Home `(prev) => (prev === 0 ? prev : 0)`; End `(prev, count) => { const next = Math.max(0, count - 1); return prev === next ? prev : next; }`; arrows/Page keys clamp verbatim); `TABLE_PAGE_JUMP = 20` + its comment move into the hook file; effect dep list verbatim: `[deps.anyModalOpen, deps.visibleFiles, deps.selectedIndex, deps.activeDirectory, deps.activeExtension, deps.filterText, deps.recursive, deps.barcodeMode]`; carry the issue-#55 comments.
- [ ] **Step 3: Run hook tests — expected PASS** (10/10). Then full suite (311 = 310 + 1 characterization from Task 1) green; `npm run build` clean.
- [ ] **Step 4: Commit** — `refactor(web): add useGlobalShortcuts hook (keydown nav + shortcuts) (#148)`

### Task 3: Rewire App.tsx onto the hook

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (delete ~206 lines, add ~40)

**Interfaces:**
- Consumes: `useGlobalShortcuts`/`GlobalShortcutsDeps` from Task 2.
- Produces: same App component; `anyModalOpen` computation STAYS in App (997–1010 verbatim, with its comment).

- [ ] **Step 1: Add the wiring after `handleProperties`/`applyDragState` and all referenced handlers exist (place near the old effect site, ~line 993):**

```tsx
// Plain function (builder call): the file uses no useCallback precedent, and
// the hook captures deps at subscription time, so moveSelection's per-render
// identity is harmless — do NOT memoize.
const moveSelection = (compute: (currentIndex: number, visibleCount: number) => number) => {
  setSelectedIndex((prev) => {
    const next = compute(prev, visibleFiles.length);
    selectedPathRef.current = visibleFiles[next]?.path ?? null;
    return next;
  });
};
const onEscape = () => {
  setContextMenuPos(null);
  setShowShortcuts(false);
  setShowLogViewer(false);
  setShowTimerModal(false);
  // Cancelled drags may never fire dragleave (WKWebView) — make
  // Escape a hard reset for the drop overlay.
  applyDragState(resetDragState());
};
useGlobalShortcuts({
  anyModalOpen, visibleFiles, selectedIndex,
  activeDirectory, activeExtension, filterText, recursive, barcodeMode,
  onEscape,
  onContextMenu: setContextMenuPos,
  onExecute: handleExecute,
  onScan: handleScan,
  onReloadConfig: handleReloadConfig,
  onGoHome: handleGoToHomeDirectory,
  onProperties: handleProperties,
  onToggleTheme: () => setTheme((prev) => (prev === "dark" ? "light" : "dark")),
  setShowLogViewer, setShowShortcuts, setShowTimerModal,
  setShowConfigEditor, setBarcodeMode, setShowCameraScanner,
  moveSelection,
});
```

The old effect (1011–1218), `TABLE_PAGE_JUMP` (61) and its comment are deleted. No new React imports needed (plain-function `moveSelection`, builder call above).
- [ ] **Step 2: Verify** — full suite green (311); `npm run build` clean; grep App.tsx: zero references to `TABLE_PAGE_JUMP` and no leftover keydown-nav code (the barcode capture-phase listener at ~989 stays — different concern, PR 4's).
- [ ] **Step 3: Commit** — `refactor(web): route App.tsx keyboard handling through useGlobalShortcuts (#148)`

### Task 4: Whole-PR verification, push, open PR

- [ ] **Step 1: Final gates** — full suite green; `npm run build` clean; `git status` clean except dist/tsbuildinfo churn; 4 commits total, messages exact.
- [ ] **Step 2: Push + open PR (stacked on #178)** — `git push -u origin refactor/148-pr3-global-shortcuts`; `gh pr create --base main --title "refactor(web): extract useGlobalShortcuts (App.tsx decomposition, PR 3/7)" --body "$(cat <<'EOF'
Part of #148 (PR 3/7 of the series in docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md). **Stacked on #178** — shows its commits until that PR merges.

## What
- New `hooks/useGlobalShortcuts.ts`: the ~200-line global keydown effect moves out of App.tsx, key-for-key identical (Escape-before-modal-guard, interactive-target guard, Ctrl disambiguation, focus helpers inside the hook).
- Staleness profile preserved exactly: the effect captures its deps bag at subscription time and re-subscribes on the original 8-item dep list — known quirks (e.g. second Ctrl+R during an in-flight reload re-entering) survive unchanged.
- Selection moves through `moveSelection(compute)` in functional-updater style; `selectedPathRef` still written inside the updater.
- Adds the App-level characterization test for the config-handoff poll seam (config_applied → re-apply → rescan), deferred from PR 2's final review.

## Safety net
- 10-scenario hook test suite (guard ordering, disambiguation, navigation compute table, staleness profile, unmount).
- Characterization suite extended to 8 tests; green throughout.

## Test plan
- [ ] `cd src/profiles/web && npx vitest run` green
- [ ] `npm run build` (tsc) clean
- [ ] Manual: arrows/Home/End/PageUp/PageDown navigation, Enter execute, F5/Ctrl+R/Ctrl+H, ?/Ctrl+/ shortcuts modal, Ctrl+B barcode, Ctrl+Shift+B camera, Escape closing modals while open
EOF
)"`
- [ ] **Step 3: Confirm CI started** — `gh pr checks` (3 workflows pending → pass; CI runs on the stacked branch).
