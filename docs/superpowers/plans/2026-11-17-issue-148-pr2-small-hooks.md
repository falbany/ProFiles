# Issue #148 PR 2 — small hooks: useToast + useExternalEvents + useAutoRescanTimer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the three small low-risk concerns from App.tsx into focused hooks — toast state/timers, the config-handoff notification poll, and the periodic auto-rescan timer — move `useModalA11y` into `hooks/`, and land the three nits deferred from PR 1's final review. Behavior-preserving.

**Architecture:** Each hook is an independent extraction owning its own state + effects; App keeps calling `showToast`/`dismissToast` through the hook's return values so the ~84 toast call sites and the `useScanController({ showToast, … })` dep stay untouched. The `depsRef` pattern in `useScanController` already absorbs `showToast`'s per-render identity (PR 1 final review confirmed no seam change needed). `useAutoRescanTimer` and `useExternalEvents` read their injected callbacks through the same latest-ref pattern so effect dep lists stay verbatim (`[autoRescanInterval]`, `[]`).

**Tech Stack:** React 19 custom hooks, TypeScript, vitest + @testing-library/react (`renderHook`, fake timers), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` → "The PR series → PR 2". All App.tsx line references are against main @ 5c2186c (post-PR-1-merge; App.tsx ≈ 1701 lines).

## Global Constraints

- Behavior-preserving. Exact values carried verbatim into hooks: toast auto-dismiss **3500 ms info / 10000 ms error**; empty-message guard (`showToast("")` is a no-op that never blanks an existing toast); `NOTIFICATION_POLL_MS = 4000`; auto-rescan toasts `"Auto-rescan every ${n}s."` / `"Auto-rescan disabled."`; timer callback reads the latest scan closure (issue #34 semantics).
- No new npm dependencies; React 19 / vitest / testing-library as installed.
- `dist/` churn stays **uncommitted** (`npm run build` is verification only).
- Conventional commits, scope `(web)`. Branch: `refactor/148-pr2-small-hooks` off `main` @ 5c2186c.
- Tests: `cd src/profiles/web && npx vitest run [file]`; type check: `cd src/profiles/web && npm run build`. Gate = ALL GREEN (baseline 291 tests / 21 files; count grows with each hook's new tests — the plan does not pin counts).
- Hook tests use `renderHook` + `act` + fake timers where durations matter; `afterEach` restores real timers (`vi.isFakeTimers()` guard).

## Review Focus

1. **Toast timer reset semantics** — a second `showToast` inside an existing toast's window must replace the pending timer (old dismiss time must not survive). Pinned by `useToast` test "new toast replaces the pending timer".
2. **Poll error paths stay silent** — `fetchNotifications` rejection produces no toast and no throw; `onConfigApplied` rejection is swallowed and the event toast still fires. Pinned by two `useExternalEvents` tests.
3. **Timer replacement without double-tick** — `handleTimerSet` to a new interval replaces (not stacks) the running interval; `handleTimerSet(0)` stops ticking. Pinned by `useAutoRescanTimer` tests.
4. **Latest-ref injection** — a scan/toast callback identity change between renders must not re-subscribe the interval/poll effects nor capture stale closures. Pinned by `useAutoRescanTimer` "uses latest scan closure without re-subscribing" and `useExternalEvents` "re-applies with the latest onConfigApplied".
5. **Unmount hygiene** — unmount during an active poll interval / auto-rescan interval / pending toast timer leaves no live timer. Pinned by one unmount test per hook.

---

### Task 1: PR-1 final-review nits

**Files:**
- Modify: `src/profiles/web/src/hooks/useScanController.ts:148-151` (docstring), `src/profiles/web/src/App.tsx:571` (comment), `src/profiles/web/src/App.scanFlow.test.tsx:218-222` (test fix)

**Interfaces:**
- Produces: none new — this task clears review debt so the rest of the PR lands clean.

- [ ] **Step 1: Fix the `runScan` docstring** — it currently says "the init/reload/directory flows call this and own their catch/finally"; only the **init flow** calls it (reload/directory use `scanWithGeneration`, which owns its error handling internally). Reword: "Execute + load for a pre-claimed generation, WITHOUT error handling or spinner teardown: the init flow calls this and owns its catch (`Initial scan failed` prefix); no spinner here — the init panel owns the feedback."
- [ ] **Step 2: Fix the stale `handleScanRef` comment** (App.tsx:571) — deferred filter-typing rescans no longer go through it (the scan hook's `depsRef` handles those). Reword to: "Latest handleScan for the timer-modal ticks and the barcode 50 ms paths (avoids stale closures)."
- [ ] **Step 3: Fix the vacuous S4 phase-2 gate** (App.scanFlow.test.tsx) — in the "typing schedules a deferred rescan…" test's phase-2 block, the `executeScanSpy.mockClear()` / `scanResultsSpy.mockClear()` pair sits **after** `render(<App />)`, so the following `waitFor(executeScan toHaveBeenCalledTimes(1))` passes on phase-1 residue before the fresh init drains. Move both `mockClear()` calls to **before** the `render(<App />)` line (after `cleanup()`), so the waitFor genuinely gates the fresh init scan. No assertion values change.
- [ ] **Step 4: Verify** — `cd src/profiles/web && npx vitest run src/App.scanFlow.test.tsx` (7/7) then full suite (291/291).
- [ ] **Step 5: Commit** — `git add -A src/profiles/web/src && git commit -m "refactor(web): address PR-1 final-review nits (runScan docs, handleScanRef comment, S4 init gate) (#148)"` (no dist/ files staged).

### Task 2: `useToast`

**Files:**
- Create: `src/profiles/web/src/hooks/useToast.ts`, `src/profiles/web/src/hooks/useToast.test.tsx`
- Modify: `src/profiles/web/src/App.tsx` (delete toast block; wire hook)

**Interfaces:**
- Produces (Tasks 3–4 consume `showToast` through App exactly as they consume it today):

```ts
export type ToastMessage = { message: string; kind: "info" | "error" };
export function useToast(): {
  toastMessage: ToastMessage | null;
  showToast: (msg: string, kind?: "info" | "error") => void;
  dismissToast: () => void;
};
```

- [ ] **Step 1: Write the failing hook tests** (`renderHook`, fake timers) —
  1. `showToast sets an info toast and auto-dismisses after 3500ms`
  2. `error toasts stay for 10000ms` (still present at 3500ms, gone at 10000ms)
  3. `empty messages are ignored` (state stays `null`, no timer armed)
  4. `a new toast replaces the pending timer` (info at t0, error at t+1000 → gone at t+11000, not t+3500)
  5. `dismissToast clears immediately` (even with a pending timer)
  6. `kind defaults to info`
- [ ] **Step 2: Run — expected FAIL** (module missing). Then implement by moving App.tsx's toast code verbatim (state line 84, `toastTimerRef` 141, `showToast` 143–157 with its docstring, `dismissToast` 159–162).
- [ ] **Step 3: Run hook tests — expected PASS**
- [ ] **Step 4: Rewire App.tsx** — delete the moved block; add `const { toastMessage, showToast, dismissToast } = useToast();` **before** the `useScanController({ showToast, … })` call (~line 176–190; `showToast` is a hook dep there — placement must precede it). All other call sites (~84 of them), `ActionBar`'s `toastMessage`/`onToastDismiss={dismissToast}`, and `ContextMenu`'s `showToast` prop keep working unchanged.
- [ ] **Step 5: Verify** — full suite green; `npm run build` clean.
- [ ] **Step 6: Commit** — `refactor(web): extract useToast hook (#148)`

### Task 3: `useExternalEvents`

**Files:**
- Create: `src/profiles/web/src/hooks/useExternalEvents.ts`, `src/profiles/web/src/hooks/useExternalEvents.test.tsx`
- Modify: `src/profiles/web/src/App.tsx` (delete poll block; wire hook)

**Interfaces:**
- Consumes: `fetchNotifications`, `ExternalEvent` from `../api/client` / `../api/types` (the hook imports only these — `fetchConfig` stays in App's injected callback).
- Produces:

```ts
export function useExternalEvents(deps: {
  onConfigApplied: () => Promise<void>;
  showToast: (msg: string, kind?: "info" | "error") => void;
}): void;
```

- [ ] **Step 1: Write the failing hook tests** (`renderHook`, fake timers, `vi.mock("../api/client")` for `fetchNotifications`; deps stubbed with `vi.fn()`s; deps held in a mutable object re-assigned each render to mimic App's fresh closures) —
  1. `polls every 4000ms and toasts each event message`
  2. `config_applied events trigger onConfigApplied before the toast`
  3. `advances lastEventId and passes it to the next poll` (second `fetchNotifications` call receives the max seen id)
  4. `fetch failures are silent` (no toast, no throw; next tick retries)
  5. `onConfigApplied failures are swallowed; the toast still fires`
  6. `uses the latest onConfigApplied identity without re-subscribing` (change deps between renders; interval keeps running with exactly one `setInterval` armed; the new identity is the one invoked)
  7. `unmount stops the poll`
- [ ] **Step 2: Run — expected FAIL.** Implement by moving App.tsx's block verbatim: `NOTIFICATION_POLL_MS = 4000` (App line 58 — the constant moves into the hook file), `lastEventIdRef`/`externalConfigApplyRef` + both effects (360–396) including their comments; deps via latest-ref so the two effects keep their exact dep lists (`[dep-assign]` per-render, `[]` poll).
- [ ] **Step 3: Run hook tests — expected PASS**
- [ ] **Step 4: Rewire App.tsx** — delete the moved block; after `handleConfigLoaded`'s definition add:

```tsx
useExternalEvents({
  onConfigApplied: async () => {
    const cfg = await fetchConfig();
    await handleConfigLoaded(cfg);
  },
  showToast,
});
```

(`fetchConfig` import stays — `runInitialLoad` still uses it. `ExternalEvent` type import moves out of App only if no other use remains — check before deleting.)
- [ ] **Step 5: Verify** — full suite green; `npm run build` clean.
- [ ] **Step 6: Commit** — `refactor(web): extract useExternalEvents hook (#148)`

### Task 4: `useAutoRescanTimer`

**Files:**
- Create: `src/profiles/web/src/hooks/useAutoRescanTimer.ts`, `src/profiles/web/src/hooks/useAutoRescanTimer.test.tsx`
- Modify: `src/profiles/web/src/App.tsx` (delete timer block; wire hook)

**Interfaces:**
- Produces:

```ts
export function useAutoRescanTimer(deps: {
  scan: () => void;
  showToast: (msg: string, kind?: "info" | "error") => void;
}): {
  autoRescanInterval: number;
  handleTimerSet: (intervalSeconds: number) => void;
};
```

- [ ] **Step 1: Write the failing hook tests** (`renderHook`, fake timers; `scan` as `vi.fn()` held in a mutable deps object) —
  1. `interval 0 never ticks` (default state; advance minutes → no scan call)
  2. `handleTimerSet(30) toasts and ticks scan every 30s` (exact toast text; two advances → two calls)
  3. `handleTimerSet(0) stops ticking and toasts "Auto-rescan disabled."`
  4. `changing the interval replaces the running timer` (set 30, advance 20, set 60, advance 40 → exactly one call, at the 60s mark from re-arm — no stacked intervals)
  5. `uses the latest scan closure without re-subscribing` (swap deps identity mid-interval; tick invokes the new closure; assert no interval churn by counting via a marker inside scan)
  6. `unmount stops the interval`
- [ ] **Step 2: Run — expected FAIL.** Implement by moving App.tsx's block verbatim: state 137–139, the interval effect 1038–1053 (dep list `[autoRescanInterval]` verbatim; `scan` read via latest-ref inside the tick), `handleTimerSet` 1055+ with its exact toast texts.
- [ ] **Step 3: Run hook tests — expected PASS**
- [ ] **Step 4: Rewire App.tsx** — delete the moved block; after `handleScanRef`'s declaration (572–575) add `const { autoRescanInterval, handleTimerSet } = useAutoRescanTimer({ scan: () => { void handleScanRef.current(); }, showToast });`. Consumers keep reading the returned values: SearchBar `autoRescanActive={autoRescanInterval > 0}` (1332), TimerModal `currentInterval`/`onSetInterval` (1492/1494).
- [ ] **Step 5: Verify** — full suite green; `npm run build` clean.
- [ ] **Step 6: Commit** — `refactor(web): extract useAutoRescanTimer hook (#148)`

### Task 5: move `useModalA11y` into `hooks/`

**Files:**
- Rename: `src/profiles/web/src/utils/useModalA11y.ts` → `src/profiles/web/src/hooks/useModalA11y.ts`; same for `useModalA11y.test.tsx`
- Modify: import paths only — `BarcodeModal.tsx`, `CameraBarcodeModal.tsx`, `ConfigEditorModal.tsx`, `ConfirmDialog.tsx`, `SaveAsDialog.tsx`, `ShortcutsModal.tsx`, `TimerModal.tsx`, `WorkflowRunnerModal.tsx` (`"../utils/useModalA11y"` → `"../hooks/useModalA11y"`)

**Interfaces:**
- Produces: same exported hook, new path `../hooks/useModalA11y`. Pure file move — zero code changes in the hook or its test (the test's relative `"./useModalA11y"` import stays valid because both files move together).

- [ ] **Step 1: `git mv` both files; update the 8 component imports; grep to confirm no `utils/useModalA11y` reference remains** (also check AGENTS.md tree mentions utils/ generically — no tree edit needed; `tests/AGENTS.md` mirrors only Python tests — verify, expect no change).
- [ ] **Step 2: Verify** — full suite green (all 291+ hook tests incl. the moved a11y tests); `npm run build` clean.
- [ ] **Step 3: Commit** — `refactor(web): move useModalA11y into hooks/ (#148)`

### Task 6: Whole-PR verification, push, open PR

- [ ] **Step 1: Final gates** — full suite green; `npm run build` clean; `git status` shows only `dist/`/`tsbuildinfo` churn (uncommitted); `git log --oneline main..` shows the 5 task commits, nothing unrelated (`git show --stat` each).
- [ ] **Step 2: Push + open PR** — `git push -u origin refactor/148-pr2-small-hooks`, then `gh pr create --base main --title "refactor(web): extract useToast/useExternalEvents/useAutoRescanTimer (App.tsx decomposition, PR 2/7)" --body "$(cat <<'EOF'
Part of #148 (PR 2/7 of the series in docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md).

## What
- New hooks `useToast`, `useExternalEvents`, `useAutoRescanTimer` — toast state/timers, the config-handoff notification poll, and the periodic auto-rescan timer move out of App.tsx; all timing values and toast texts preserved verbatim (3.5s/10s toasts, 4s poll, latest-callback injection for issue #34 semantics).
- `utils/useModalA11y.ts` (+ tests) moved into `hooks/` — utils is stateless-only per AGENTS.md.
- Lands PR-1 final-review nits: runScan docstring, stale handleScanRef comment, S4 phase-2 init gate.

## Safety net
- New hook test suites (useToast, useExternalEvents, useAutoRescanTimer); characterization suite unchanged and green throughout.

## Test plan
- [ ] `cd src/profiles/web && npx vitest run` green
- [ ] `npm run build` (tsc) clean
- [ ] Manual: toast (info/error timing, dismiss), config handoff toast from a second launch, timer modal set/clear
EOF
)"`
- [ ] **Step 3: Confirm CI started** — `gh pr checks` (3 workflows pending → pass).
