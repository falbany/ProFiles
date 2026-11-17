# Issue #148 PR 5 — useTheme (+ fixes #129)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract App.tsx's theme slice into `hooks/useTheme.ts` and fix issue #129 — restore the stored preference at startup and stop the session-trial theme leaking into localStorage — by replacing raw `setTheme` with provenance-controlled `applyTheme(next, { persist })`.

**Architecture:** The hook owns `theme` state (lazy initializer reads localStorage), the `data-theme` attribute effect (moved verbatim), `applyTheme(next, { persist })` for the config paths, and `toggleTheme({ persist })` for the two user toggles. `toggleTheme` reads a per-render `themeRef` (the codebase depsRef idiom) instead of a functional updater — the toggles reach the handler through `useGlobalShortcuts`'s subscription-time capture with `theme` NOT in its re-subscribe dep list, so a captured render-scope `theme` could go stale and flip the toggle the wrong way; the ref gives identical immunity to today's `setTheme((prev) => …)`. The ALWAYS-persist effect (App.tsx:921–929) is DELETED — every localStorage write goes through `applyTheme`/`toggleTheme` at call time.

**Tech Stack:** React 19 custom hook, TypeScript, vitest + @testing-library/react + jsdom, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` → "PR 5 — `useTheme` (+ fixes #129)". All App.tsx line refs are against `refactor/148-pr4-barcode` @ 69c86d0 (App.tsx = 1331 lines).

## Global Constraints

- **This PR legitimately CHANGES behavior (#129 fix) — the declared exception to "quirks survive".** Exactly two behavior changes, nothing more:
  1. **Restore at startup:** initial theme reads `localStorage["profiles-theme"]` (try/catch, validated ∈ {"dark","light"}, else "dark"). Today every mount starts "dark" until the config loads.
  2. **Trial leak killed:** config-load/reload themes (`handleConfigLoaded` App.tsx:301, `handleReloadConfig` App.tsx:251) no longer write localStorage. Today the always-persist effect writes on EVERY theme change, so a session-trial "light" config permanently overwrites the stored preference.
  Everything else is behavior-preserving: `initializeFromConfig` still persists (config is source of truth at startup, App.tsx:438–445 — its explicit `setItem` block becomes `applyTheme(…, { persist: true })`); user toggles still persist; `data-theme` attribute still follows every change; only "light" is light (resolveSessionTheme rule) everywhere including init — today's inline `cfg.theme === "auto" ? "dark" : …` ternary (440) is semantically identical to `resolveSessionTheme` and is replaced by it (DRY ruling, ledgered).
- #129's `auto`-via-`matchMedia` idea: non-goal (follow-up issue). Only "dark"/"light" are valid persisted values; a stored "auto" or garbage falls back to "dark".
- Provenance table (binding — every setTheme call site maps to exactly one of these):
  | Call site | Today | After |
  |---|---|---|
  | `handleReloadConfig` (251) | setTheme(resolveSessionTheme) → effect persists (LEAK) | `applyTheme(resolveSessionTheme(cfg.theme), { persist: false })` |
  | `handleConfigLoaded` (301) | same (LEAK) | `applyTheme(resolveSessionTheme(cfg.theme), { persist: false })` |
  | `initializeFromConfig` (438–445) | inline ternary + explicit setItem | `applyTheme(resolveSessionTheme(cfg.theme), { persist: true })` |
  | Ctrl+Shift+T via useGlobalShortcuts (915) | `setTheme((prev) => …)` → effect persists | `() => toggleTheme({ persist: true })` |
  | StatusBar toggle (1021) | same | `() => toggleTheme({ persist: true })` |
- Hook interface (normative — Task 2 imports these exact names):
  ```ts
  export type Theme = "dark" | "light";
  export function useTheme(): {
    theme: Theme;
    applyTheme: (next: Theme, opts: { persist: boolean }) => void;
    toggleTheme: (opts: { persist: boolean }) => void;
  };
  ```
  Persistence writes happen at CALL time (direct `localStorage.setItem` in try/catch), NOT inside the `setTheme` updater (no StrictMode-impure updater writes; the themeRef keeps call-time reads fresh — ruling, ledgered). `themeRef` is kept current by a per-render effect (the `useAutoRescanTimer` depsRef idiom).
- `initializeFromConfig`'s early return (`if (!scan.isCurrentScan(scanGeneration)) return;`) is untouched: a superseded init persists nothing — today the mount-time always-persist effect would have written "dark" first; after the fix the stored preference simply survives. Accepted consequence of the fix (ledgered).
- No new npm dependencies; `dist/` churn uncommitted; conventional commits `(web)`/`(test)`.
- Branch: `refactor/148-pr5-use-theme` off `refactor/148-pr4-barcode` @ 69c86d0 (**stacked** on unmerged #178 → #179 → #182; PR opens with base `main`).
- Tests: `cd src/profiles/web && npx vitest run [file]`; type check `npm run build`. Gate = ALL GREEN (baseline 343; expected end ≈ 353 — use actuals in reports).
- Characterization tests are never weakened or deleted — EXCEPT the two sanctioned folds into `App.scanFlow.test.tsx` while it is touched (see Task 2 Step 6, both are tightenings, ledgered).
- Carry-forwards (fold-when-touched): ① `App.scanFlow.test.tsx:450` stale `handleScanRef` comment → fix while that file is touched (the other two sweep sites — `useAutoRescanTimer.ts:34`, `useScanController.ts:70` — are NOT touched by this PR and stay deferred). ② `notificationsSpy.mockResolvedValue` → `mockResolvedValueOnce` in the existing config_applied test (PR 3 deferred minor) → fold while the file is touched. No other carry-forward applies (none touch theme files).

## Review Focus

1. **Restore-vs-config precedence** — stored "light" + config "dark" must end dark (config is source of truth AFTER load) but BE light between mount and config load. Pinned by App-level test "stored preference is restored at mount and overridden by the config theme after init".
2. **Trial leak actually killed** — a config_applied (trial) theme must NOT reach localStorage even though it changes the session. Pinned by App-level test "config_applied trial theme changes the session but never persists".
3. **Toggle staleness immunity** — toggles through the captured `onToggleTheme` must always flip the CURRENT theme. Pinned by hook toggle tests (themeRef) + App-level toggle pin.
4. **No orphan writers** — after the rewire, the ONLY localStorage writers are applyTheme/toggleTheme; the always-persist effect is gone. Pinned by Task 2's grep gate (`localStorage.setItem` zero hits in App.tsx).
5. **data-theme follows every path** — restore, config apply, trial, toggles. Pinned per-test (attribute asserted in each).

---

### Task 1: `hooks/useTheme.ts` — hook tests + implementation (TDD)

**Files:**
- Create: `src/profiles/web/src/hooks/useTheme.ts`, `src/profiles/web/src/hooks/useTheme.test.tsx`

**Interfaces:**
- Consumes: nothing (self-contained; jsdom localStorage).
- Produces (normative — Task 2 imports): `Theme`, `useTheme` per the Global Constraints block.

- [ ] **Step 1: Write the failing hook tests** — renderHook; real timers; seed/clear `localStorage["profiles-theme"]` per test; afterEach `localStorage.clear()` + `cleanup()`. Test list (exact names):
  1. `initial state restores a stored light preference` — seed "light" → `result.current.theme === "light"`.
  2. `initial state falls back to dark for missing, invalid, or unreadable stored values` — table: (no key → "dark"), ("garbage" → "dark"), ("auto" → "dark"), ("dark" → "dark"); plus one test where `localStorage.getItem` throws (spy `vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("deny"); })`) → "dark".
  3. `applyTheme with persist true sets the theme, updates data-theme, and writes localStorage` — `act(() => applyTheme("light", { persist: true }))` → theme "light"; `document.documentElement.dataset.theme === "light"`; `localStorage["profiles-theme"] === "light"`.
  4. `applyTheme with persist false sets the theme and data-theme but leaves storage untouched` — seed "dark"; `applyTheme("light", { persist: false })` → theme + attr "light"; `localStorage["profiles-theme"] === "dark"` (pre-existing value survives; no write, no delete).
  5. `toggleTheme with persist true flips and persists, both directions` — fresh (no key, theme starts "dark") → toggle → "light" + attr + storage "light" → toggle → "dark" + attr + storage "dark".
  6. `toggleTheme with persist false flips without persisting` — fresh → toggle → "light" + attr, storage still null.
  7. `data-theme attribute follows restore at mount` — seed "light", renderHook → `document.documentElement.dataset.theme === "light"` (the attribute effect runs on mount with the restored value).
- [ ] **Step 2: Run — expected FAIL** (module missing).
- [ ] **Step 3: Implement `useTheme`** — file-header doc comment: #129 fix scope (restore + leak kill), the provenance table (which callers persist), the themeRef staleness ruling (why toggleTheme exists alongside applyTheme — useGlobalShortcuts subscription-time capture, theme not in its dep list), "every localStorage write goes through applyTheme/toggleTheme — the App always-persist effect is gone". Body: `useState<Theme>(readStoredTheme)` with lazy `readStoredTheme()` (try/catch, validated ∈ {"dark","light"} else "dark"); `themeRef` + per-render sync effect; `applyTheme(next, { persist })` → `setTheme(next)` + conditional try/catch `setItem`; `toggleTheme({ persist })` → `applyTheme(themeRef.current === "dark" ? "light" : "dark", { persist })`; attribute effect `document.documentElement.setAttribute("data-theme", theme)` on `[theme]`. Carry the storage-unavailable comment style (`/* storage may be unavailable */`).
- [ ] **Step 4: Run — expected PASS** (7/7). Full suite green (343 + 7 = 350); `npm run build` clean.
- [ ] **Step 5: Commit** — `refactor(web): add useTheme hook with #129 restore + persist provenance (#148)`

### Task 2: Rewire App.tsx + App-level #129 pins

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (~−15 lines), `src/profiles/web/src/App.scanFlow.test.tsx` (+3 tests, 2 sanctioned folds)

**Interfaces:**
- Consumes: `useTheme`/`Theme` from Task 1.
- Produces: same App component; provenance table from Global Constraints applied verbatim.

- [ ] **Step 1: Add the two always-green pins to `App.scanFlow.test.tsx`** (extend, never weaken):
  1. `init persists the config theme to localStorage` — `fetchConfigSpy` → `makeAppConfig({ theme: "light" })`; render; settle init (`waitFor` executeScan 1×); assert `document.documentElement.dataset.theme === "light"` AND `localStorage.getItem("profiles-theme") === "light"`.
  2. `status bar toggle persists the new theme` — default config; settle init (dark); click the StatusBar toggle button (`screen.getByRole("button", { name: /light/i })` — the button shows "Light" while dark); assert attr + storage both "light".
  Expected GREEN against current code (today the always-persist effect delivers both; after the rewire applyTheme/toggleTheme do — the pins survive the rewire by construction).
- [ ] **Step 3: Add the two RED pins (the #129 fixes)**:
  3. `stored preference is restored at mount and overridden by the config theme after init` — seed `localStorage["profiles-theme"] = "light"`; default config (theme "dark"); render; assert attr === "light" IMMEDIATELY (before settling — today RED: mounts dark); then settle init; assert attr === "dark" AND storage === "dark" (config overrode both).
  4. `config_applied trial theme changes the session but never persists` — fake timers like the existing config_applied test; after init settles, poll delivers an event and `fetchConfigSpy.mockResolvedValueOnce(makeAppConfig({ theme: "light", … }))`; after the tick settles assert `document.documentElement.dataset.theme === "light"` AND `localStorage.getItem("profiles-theme") === "dark"` (the trial changed the session, storage kept the init value). RED today (storage becomes "light" via the leak).
- [ ] **Step 4: Rewire App.tsx** — per the provenance table: import `useTheme`/`Theme`; line 62 → `const { theme, applyTheme, toggleTheme } = useTheme();`; 250–251 and 298–301 → `applyTheme(resolveSessionTheme(cfg.theme), { persist: false });` (comments stay; the handleConfigLoaded comment now describes actual behavior); 438–445 → `applyTheme(resolveSessionTheme(cfg.theme), { persist: true });` with a comment noting config-is-source-of-truth persistence (#129: only the startup path persists); 915 → `onToggleTheme: () => toggleTheme({ persist: true }),`; 1021 → `onToggleTheme={() => toggleTheme({ persist: true })},`; DELETE the always-persist effect + its comment (921–929) — the attribute effect lives in the hook now.
- [ ] **Step 5: Run** — full suite GREEN (Step 1–3 pins now all pass: 350 + 4 = 354 expected); `npm run build` clean. If a Step-1/2 pin went red, the rewire broke preserved behavior — fix App, never the pin.
- [ ] **Step 6: Sanctioned folds into the touched test file** (both tightenings, never weakenings): ① the existing config_applied test's `notificationsSpy.mockResolvedValue({ events: […] })` → `mockResolvedValueOnce(...)` (PR 3 deferred minor — the test drives exactly one poll tick; behavior identical, mock tighter); ② fix the stale `handleScanRef` comment at ~line 450 (the rescan now reads latest via the barcode hook's depsRef at fire time — same guarantee, new home).
- [ ] **Step 7: Grep gates** — App.tsx: zero hits for `localStorage.setItem`, `setTheme(`, `useState<"dark"`; `data-theme` zero hits (moved to hook); `resolveSessionTheme` exactly 3 uses. Hook: attribute effect present.
- [ ] **Step 8: Commit** — `refactor(web): route App.tsx theme handling through useTheme, fix #129 (#148)`

### Task 3: Whole-PR verification, push, open PR

- [ ] **Step 1: Final gates** — full suite green; `npm run build` clean; `git status` clean except dist/tsbuildinfo churn; 3 commits total (plan + Task 1 + Task 2), messages exact.
- [ ] **Step 2: Push + open PR (stacked on #178 → #179 → #182)** — `git push -u origin refactor/148-pr5-use-theme`; `gh pr create --base main --title "refactor(web): extract useTheme + fixes #129 (App.tsx decomposition, PR 5/7)"` with a body following PR #182's pattern: What (hook + provenance + the two #129 behavior changes called out explicitly), Safety net (7 hook tests + 4 App pins incl. the two new-behavior pins), Test plan (vitest green, tsc clean, manual: toggle persists across reload, trial config does not steal the stored theme, stored light restores on a fresh session before config load).
- [ ] **Step 3: Confirm CI** — `gh pr checks` (3 workflows pending → pass).
