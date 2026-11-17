# Issue #148 PR 7 — LanConfirmDialog + pathToFileUri (closes #148)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the LAN-toggle confirm dialog into `components/LanConfirmDialog.tsx` (owning the observe-and-verify flow), replace the UNC-broken `file://` URI construction with `utils/fileUri.ts:pathToFileUri`, fold the spec's rule-⑥ mechanism erratum, and close issue #148.

**Architecture:** LanConfirmDialog wraps the existing generic `ConfirmDialog` and owns the async confirm flow — `setLanEnabled` → observe toast → `waitForLanState` → outcome toasts, or failure → refetch — importing the api client directly (ConfigEditorModal precedent) and toasting its own outcomes with the current message texts verbatim (showToast injected). App keeps `lanPending` state and maps the observed `SystemInfo` back via `onConfirmed(sys)`. `pathToFileUri` is a pure util; `handleCopyUri` becomes a thin caller.

**Tech Stack:** React 19, TypeScript, vitest + @testing-library/react + jsdom, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md` → "PR 7 — `LanConfirmDialog` + `pathToFileUri` + closes #148". All App.tsx line refs are against `refactor/148-pr6-drag-drop` @ 365e4aa (App.tsx = 1257 lines).

## Global Constraints

- Behavior-preserving, **including quirks**:
  - The confirm flow's exact sequence (App.tsx:1263–1297 today): `const next = lanPending!;` → **clear pending first** (`setLanPending(null)`, today App.tsx:1265 — the dialog closes before the async flow; the flow runs even though the dialog is gone) → `await setLanEnabled(next)` → transitional toast (`"Updating LAN binding…"` / `"Restricting ProFiles to this machine…"`, info) → `await waitForLanState(next)` → `if (sys) setSystemInfo(sys)` → outcome branch: `sys?.lan_enabled === next` → success toast (`"ProFiles is now reachable on the local network."` / `"ProFiles is restricted to this machine."`, info) else failure toast (`"Failed to update LAN binding — the previous address is still active."`, error). Catch: `err instanceof Error ? err.message : "Failed to update LAN binding"` → `` `Failed to update LAN binding: ${msg}` `` error toast → refetch `fetchSystemInfo()` → `setSystemInfo(sys)` (comment "Refetch to restore the actual state" moves with it).
  - With the component owning the flow, "clear pending first" becomes `onCancel()` called at flow start — it is the same close action App already performs (`setLanPending(null)`); App's onCancel body stays `() => setLanPending(null)` (ruling, ledgered).
  - `onConfirmed(sys)` fires on BOTH the observed outcome and the catch-refetch (today both paths call `setSystemInfo(sys)`); App maps it to `setSystemInfo`.
  - The message body stays verbatim JSX: LAN-on renders the intro line + two `CopyableUrl` blocks (hostname URL then IP URL, `http://${...}:${window.location.port}`, labels "Copy hostname URL"/"Copy IP URL", copy toasts "URL copied to clipboard."/"Failed to copy URL." — these stay injected via props since they toast through App's slot); LAN-off renders `"ProFiles will be reachable only on this machine."`. Title/confirmLabel ternaries verbatim (`"Enable LAN access?" : "Restrict to this machine?"` / `"Enable LAN" : "Restrict"`).
  - `pathToFileUri` CHANGES the produced URI for UNC paths and special characters — that is the point (the current construction is wrong for UNC). Required mappings: `C:\a\b.txt` → `file:///C:/a/b.txt`; `C:/a/b.txt` → `file:///C:/a/b.txt`; `\\server\share\a.txt` → `file://server/share/a.txt`; `/home/u/a.txt` → `file:///home/u/a.txt`; spaces / non-ASCII percent-encoded; `#`/`?` escaped. Everything `handleCopyUri` does around it (clipboard write, success/error toasts) is unchanged.
  - The spec erratum fold CHANGES SPEC TEXT ONLY: rewrite the spec's "PR 3" staleness sentence (~lines 257–262, "action callbacks reach the keydown handler through a latest-ref") to subscription-time capture per the PR 3 ruling; add one line noting the PR 3 plan recorded the erratum. No code implications.
- Interfaces (normative — Task 2 imports these exact names):
  ```ts
  // components/LanConfirmDialog.tsx
  import type { SystemInfo } from "../api/types";
  export interface LanConfirmDialogProps {
    pending: boolean | null;
    systemInfo: SystemInfo | null;
    showToast: (msg: string, kind?: "info" | "error") => void;
    onConfirmed: (sys: SystemInfo) => void;
    onCancel: () => void;
  }
  export function LanConfirmDialog(props: LanConfirmDialogProps): ReactElement;
  // utils/fileUri.ts
  export function pathToFileUri(path: string): string;
  ```
  `systemInfo: SystemInfo | null` (App passes `systemInfo` state which is nullable today; the dialog renders `CopyableUrl url={http://${systemInfo?.hostname}...}` with the same optional chaining — null-safety identical to today).
- No new npm dependencies; `dist/` churn uncommitted; conventional commits `(web)`/`(test)`/`(docs)`.
- Branch: `refactor/148-pr7-lan-dialog` off `refactor/148-pr6-drag-drop` @ 365e4aa (**stacked** on unmerged #178 → #179 → #182 → #184 → #185; PR opens with base `main`).
- Tests: `cd src/profiles/web && npx vitest run [file]`; type check `npm run build`. Gate = ALL GREEN (baseline 366; expected end ≈ 380 — use actuals in reports).
- PR body says **"Closes #148"** (not "Part of").
- Carry-forwards (fold-when-touched): the two remaining `handleScanRef` comment sites (useAutoRescanTimer.ts:34, useScanController.ts:70) are NOT touched by this PR — reported as still-open at series end. The pick-seam freshness rerender test (PR 6 final review) touches useDragDropConfig.test.tsx — NOT touched here; also reported. No folds apply.

## Review Focus

1. **Dialog-closes-first quirk** — the flow must run after the dialog closes (pending cleared before `setLanEnabled`), including the toasts firing with no dialog on screen. Pinned by component test "confirm closes the dialog first and still completes the flow".
2. **Failure refetch restores truth** — server error → error toast with the exception message → `fetchSystemInfo` refetch → `onConfirmed(sys)`. Pinned by component test "rejected setLanEnabled toasts the failure and refetches system info".
3. **Observe-then-confirm semantics** — `waitForLanState`'s returned `sys` decides the outcome branch (`sys?.lan_enabled === next`), not the `setLanEnabled` response. Pinned by component test "waitForLanState disagreement toasts the still-active failure" (sys returned with lan_enabled !== next → the failure toast, no refetch).
4. **UNC URIs now correct** — the four required mappings + escaping. Pinned by the utils table test.
5. **handleCopyUri thin-caller** — clipboard + toasts unchanged; only the URI construction swapped. Pinned by the utils table (unit) + App copyUri wiring visible in the diff (no App-level test added; the util table is the pin).

---

### Task 1: `utils/fileUri.ts` — table tests + implementation (TDD)

**Files:**
- Create: `src/profiles/web/src/utils/fileUri.ts`, `src/profiles/web/src/utils/fileUri.test.ts`

**Interfaces:**
- Produces (normative — Task 2 imports): `pathToFileUri(path: string): string`.

- [ ] **Step 1: Write the failing table tests** — it.each rows, exact expectations:
  `C:\a\b.txt` → `file:///C:/a/b.txt`; `C:/a/b.txt` → `file:///C:/a/b.txt`; `\\server\share\a.txt` → `file://server/share/a.txt`; `//server/share/a.txt` → `file://server/share/a.txt`; `/home/u/a.txt` → `file:///home/u/a.txt`; `C:/dir with space/a.txt` → `file:///C:/dir%20with%20space/a.txt`; `C:/rép/a.txt` → percent-encoded non-ASCII; `C:/a#b.txt` → `file:///C:/a%23b.txt`; `C:/a?b.txt` → `file:///C:/a%3Fb.txt`.
- [ ] **Step 2: Run — expected FAIL** (module missing).
- [ ] **Step 3: Implement `pathToFileUri`** — approach: detect UNC (`\\` or `//` prefix) → `file://host/share/...`; else `file:///` + normalized forward slashes; then percent-encode via `encodeURI`-style rules that leave `/` intact but encode space, non-ASCII, `#`, `?` (a short hand-rolled segment encoder is fine — KISS; document the choice in a 3-line comment). File-header doc comment notes it replaces the `new URL("file:///").href + backslash-replace` construction (wrong for UNC, unencoded specials).
- [ ] **Step 4: Run — expected PASS** (new file green; full suite green 366 + N).
- [ ] **Step 5: Commit** — `refactor(web): add pathToFileUri util with UNC + encoding support (#148)`

### Task 2: `components/LanConfirmDialog.tsx` — component tests + implementation (TDD)

**Files:**
- Create: `src/profiles/web/src/components/LanConfirmDialog.tsx`, `src/profiles/web/src/components/LanConfirmDialog.test.tsx`

**Interfaces:**
- Consumes: `ConfirmDialog` (generic, props per its interface), api client `setLanEnabled`/`waitForLanState`/`fetchSystemInfo` (direct import — ConfigEditorModal precedent), `CopyableUrl`, `SystemInfo`.
- Produces (normative — Task 3 imports): `LanConfirmDialogProps` per the Global Constraints block.

- [ ] **Step 1: Write the failing component tests** — render `<LanConfirmDialog pending={…} systemInfo={…} showToast={fn} onConfirmed={fn} onCancel={fn} />`; `vi.mock("../api/client")` for setLanEnabled/waitForLanState/fetchSystemInfo; fixtures makeSystemInfo-style. Test list (exact names):
  1. `renders nothing when pending is null` — `pending={null}` → dialog (`role="dialog"`) absent.
  2. `renders the LAN-on message with copyable URLs when enabling` — `pending={true}`, systemInfo fixture → title "Enable LAN access?", confirm label "Enable", both CopyableUrl labels ("Copy hostname URL", "Copy IP URL") present.
  3. `renders the restrict message when disabling` — `pending={false}` → title "Restrict to this machine?", label "Restrict", text "ProFiles will be reachable only on this machine." present, no CopyableUrl.
  4. `confirm closes the dialog first and still completes the flow` — pending true; `waitForLanState` resolves the fixture (lan_enabled true); click confirm → `onCancel` called (dialog-closes-first ruling) BEFORE `setLanEnabled` (assert with invocationCallOrder); `setLanEnabled(true)` awaited; success toast "ProFiles is now reachable on the local network."; `onConfirmed` called with the fixture sys.
  5. `waitForLanState disagreement toasts the still-active failure` — `waitForLanState` resolves `{ ...sys, lan_enabled: false }` while next=true → failure toast "Failed to update LAN binding — the previous address is still active."; `onConfirmed` called with that sys; NO refetch (fetchSystemInfo not called).
  6. `rejected setLanEnabled toasts the failure and refetches system info` — `setLanEnabled` rejects Error("boom") → error toast "Failed to update LAN binding: boom"; `fetchSystemInfo` called; `onConfirmed` called with the refetched sys; transitional toast "Updating LAN binding…" NOT shown (it comes after the await).
  7. `cancel calls onCancel` — click cancel → onCancel called once, no api calls.
- [ ] **Step 2: Run — expected FAIL** (module missing).
- [ ] **Step 3: Implement `LanConfirmDialog`** — wrap `ConfirmDialog` (`isOpen={pending !== null}`, title/confirmLabel ternaries verbatim, message JSX verbatim with CopyableUrl blocks reading the `systemInfo` prop); `onConfirm` = the flow moved verbatim with `pending!` → `const next = pending!; onCancel();` first, `setSystemInfo(sys)` → `onConfirmed(sys)` (both branches), transitional/outcome/catch toasts verbatim via the injected `showToast`; `onCancel` passes through. File-header doc comment: owns the observe-and-verify flow; api client imported directly (ConfigEditorModal precedent); the dialog-closes-first quirk is preserved via onCancel-at-flow-start.
- [ ] **Step 4: Run — expected PASS** (7/7). Full suite green; `npm run build` clean.
- [ ] **Step 5: Commit** — `refactor(web): add LanConfirmDialog owning the LAN toggle flow (#148)`

### Task 3: Rewire App.tsx + spec erratum fold

**Files:**
- Modify: `src/profiles/web/src/App.tsx` (delete ~65 lines, add ~10), `docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md`

- [ ] **Step 1: Rewire** — App.tsx: replace the LAN ConfirmDialog block (~1236–1299: `{/* LAN toggle confirmation */}` + the whole `<ConfirmDialog isOpen={lanPending !== null} …>`) with `<LanConfirmDialog pending={lanPending} systemInfo={systemInfo} showToast={showToast} onConfirmed={setSystemInfo} onCancel={() => setLanPending(null)} />`; replace the `new URL("file:///").href + file.path.replace(/\\/g, "/")` line in `handleCopyUri` (657) with `pathToFileUri(file.path)` (+ import). Clean up App imports the removed code made unused (setLanEnabled, waitForLanState — fetchSystemInfo STAYS: uses at 237/423 remain; CopyableUrl's only uses are the LAN block (1183/1190) → remove its import — the component imports it now; React imports only if tsc flags).
- [ ] **Step 2: Spec erratum fold** — docs/superpowers/specs/2026-11-16-app-tsx-decomposition-design.md "PR 3" section, the "Staleness profile preserved" bullet (~257–262): replace the latest-ref mechanism sentence with subscription-time capture per the PR 3 ruling (effect captures the deps bag at subscription and re-subscribes on the original dep list; latest-ref applies ONLY to the timer-tick and barcode-timeout fire-time reads), and append "(erratum folded from the PR 3 plan, 2026-11-17)".
- [ ] **Step 3: Verify** — full suite green (366 + N + 7); `npm run build` clean; grep App.tsx: zero `setLanEnabled|waitForLanState`, zero `new URL("file:///")`, `lanPending` exactly 3 uses (state + onCancel + prop), `CopyableUrl` zero hits in App.
- [ ] **Step 4: Commit** — `refactor(web): route LAN toggle through LanConfirmDialog, adopt pathToFileUri (#148)`

### Task 4: Whole-PR verification, push, open PR (closes #148)

- [ ] **Step 1: Final gates** — full suite green; `npm run build` clean; `git status` clean except dist/tsbuildinfo churn; 5 commits (plan + 3 tasks), messages exact.
- [ ] **Step 2: Push + open PR (stacked on #178 → #179 → #182 → #184 → #185)** — `git push -u origin refactor/148-pr7-lan-dialog`; `gh pr create --base main --title "refactor(web): extract LanConfirmDialog + pathToFileUri (App.tsx decomposition, PR 7/7)"` with body starting "Closes #148." (decomposition complete: 7 PRs, App.tsx 1925 → ~1200): What (LanConfirmDialog owns the observe-and-verify flow with verbatim toast texts; pathToFileUri fixes UNC + special chars in copied URIs; spec rule-⑥ erratum folded), Safety net (7 component tests + utils table), Test plan (vitest green, tsc clean, manual: LAN enable/disable toasts, copied URI for a Windows share path).
- [ ] **Step 3: Confirm CI** — `gh pr checks` (3 workflows pending → pass).
