# UI Polish — Design (2026-10-27)

One UI-polish effort for the ProFiles web UI (`src/profiles/web`), landed as a
sequence of commits on the existing branch `fix/web-light-theme-polish`.

## Intent and Why

Five style improvements were identified on 2026-10-26 after fixing the
light-theme modal bugs. They share one root problem: component files re-derive
styling that should live in the design system, so consistency work keeps
requiring file-by-file sweeps. This effort centralizes the missing pieces
(status colors, buttons, focus rings, motion, tooltips) so the next polish pass
is a one-line change, and it finishes the light-theme correctness work.

## Goals

1. **Finish light-theme correctness**: no remaining hard-coded accent colors
   that flip poorly between themes (~70 instances across 20 component files).
2. **One place owns button state**: hover/focus/disabled styling defined once,
   adopted app-wide.
3. **Keyboard focus never disappears**: every interactive element shows a
   consistent visible focus ring.
4. **Quiet motion**: overlays (modals, context menu, toast) enter with a
   subtle transition; theme switches cross-fade instead of snapping.
5. **One tooltip world**: interactive controls use the themed glass `Tooltip`;
   no half-migration.

## Non-Goals / Anti-Goals

- **No exit animations.** Unmounts stay instant; keeping closed modals mounted
  to play exit transitions is complexity a quiet app doesn't earn.
- **No new dependencies** (no tailwindcss-animate or similar plugin).
- **No `Button` React component** (approach B — rejected, see Approaches).
- **No changes to the app frame**: the single outer border stays the only
  border; no cards/borders added around the file list or chrome.
- **No Tailwind `dark:` variants** — theming is `data-theme` attribute tokens
  only (`dark:` follows OS media query, not the in-app toggle).
- **No structural refactors** of components; classNames and wrappers only.

## Constraints

- Quality gates: `npm run build` (tsc + vite) and `npm test` (vitest) green per
  commit; rebuilt `dist/` committed with each change (repo convention).
- pywebview (WKWebView) is the primary runtime; tooltips/motion must work there.
- No React testing library exists; verification is build + tests + manual pass.
- Existing global `prefers-reduced-motion` clamp in `index.css` (0.01ms) covers
  all new keyframes automatically.
- The `glass-panel` / `@layer components` pattern in `index.css` is the house
  style for shared classes.

## Approaches Considered

**A. CSS component classes in `index.css` (CHOSEN).** `.btn*` / `.focus-ring`
in `@layer components` next to `glass-panel`; components keep Tailwind layout
utilities and swap hand-rolled state strings for these classes. The ~15-file
sweep stays mechanical (className exchange, no structure change), matches the
existing pattern, and keeps the diff reviewable in a repo with no component
tests.

**B. Typed `Button` React component with variant props (REJECTED).** Stronger
single-source-of-truth, but turns every file touch into a structural rewrite
(polymorphic handling for icon-only buttons, chips, links), introduces the
app's first shared UI primitive, and its type safety is redundant once styles
are centralized.

**User decisions on record:** one effort, sequenced commits, current branch;
motion "quiet enough that you'd only notice if it disappeared"; approach A.

## Design

### 1. New tokens (`index.css`)

Status tokens, following the exact chip-token convention (translucent fill +
border + light text in dark; solid pastel fill + dark text in light):

| Token | Dark | Light |
|---|---|---|
| `--status-success-bg` | `rgb(16 185 129 / 0.25)` | `#d1fae5` |
| `--status-success-border` | `rgb(52 211 153 / 0.5)` | `#6ee7b7` |
| `--status-success-text` | `#a7f3d0` | `#065f46` |
| `--status-warning-bg` | `rgb(245 158 11 / 0.25)` | `#fef3c7` |
| `--status-warning-border` | `rgb(251 191 36 / 0.5)` | `#fcd34d` |
| `--status-warning-text` | `#fde68a` | `#92400e` |
| `--status-danger-bg` | `rgb(244 63 94 / 0.25)` | `#ffe4e6` |
| `--status-danger-border` | `rgb(251 113 133 / 0.5)` | `#fda4af` |
| `--status-danger-text` | `#fecdd3` | `#9f1239` |

Register all in `@theme inline` as `--color-status-*-bg/border/text`. Values
follow the verified chip pattern (all pairs ≥ 4.5:1 in both themes; chip-amber
light values are reused verbatim).

**Theme-flip rule** (applies to the whole sweep): tokenize a color only when it
must *flip* with theme — text/borders on tinted or transparent fills. Theme-
neutral solids stay hard-coded: `bg-indigo-600 text-white` primary buttons,
spinner `border-indigo-600 border-t-transparent`, ContextMenu's solid
`hover:bg-indigo-600 hover:text-white` menu items.

### 2. Button + focus classes (`index.css` `@layer components`)

- `.btn` — owns shape + state: `inline-flex items-center justify-center gap-1.5
  rounded-md border text-xs font-medium transition-colors` +
  `disabled:opacity-40 disabled:cursor-not-allowed` + the focus-ring styles
  below. Padding/size stay per-instance (footer buttons and tiny chips differ).
- `.btn-primary` — `bg-indigo-600 text-white border-transparent hover:bg-indigo-500`.
  Replaces the footer Close, BarcodeModal Save Image, and similar.
- `.btn-secondary` — `bg-elevated text-ink-secondary border-line
  hover:border-indigo-500 hover:text-ink`. Replaces the idiom currently
  re-spelled in `FileListTable.tsx:421`, `LoadConfigModal`, `DirectoryPickerModal`, etc.
- `.btn-chip` — owns hover (`hover:brightness-95` — works in both themes, unlike
  `hover:bg-x-600/30`), focus ring, disabled state; shape (rounded/padding) and
  color stay per-instance via chip tokens (`bg-chip-sky-bg text-chip-sky-text
  border-chip-sky-border` …).
- `.focus-ring` — `focus-visible:outline-none focus-visible:ring-2
  focus-visible:ring-indigo-500/70`. Composed into `.btn*` and applied
  standalone to non-button interactive elements.

`@apply` or raw CSS is the builder's call; both work in this Tailwind v4 setup
(`glass-panel` uses raw CSS).

### 3. Accent sweep (proposal 1)

Replace hard-coded theme-flipping accents with chip/status/ink tokens.
Inventory (grep counts, 2026-10-26): WorkflowRunnerModal 19, ContextMenu 14,
LogViewerModal 10, FilePropertiesModal 10 (emerald success checks + card
icons), SearchBar 8, LoadConfigModal 8, FileListTable 6, DirectoryPickerModal 6,
TimerModal 4, StatusBar 4, SingleMatchPromptModal 4, HeaderBar 4,
FilterSyntaxHelper 4, CameraBarcodeModal 4, BarcodeModal 3 (error boxes
`text-red-400`), ActionBar 3, ShortcutsModal 2, ScanStatusStrip 2 (incl. the
`text-indigo-300/80` bug class from the RAW PREVIEW fix), InitErrorPanel 1,
DropConfigOverlay 1. Items that are theme-neutral per the flip rule stay.

Semantic mappings: success checks → `status-success`; warnings →
`status-warning`; errors/error boxes → `status-danger`; log levels in
`LogViewerModal` → INFO `status-success`, WARNING `status-warning`,
ERROR/CRITICAL `status-danger`, DEBUG `ink-muted`; tinted action chips →
existing chip tokens.

### 4. Focus-visible completion (proposal 4)

Apply `.focus-ring` everywhere focus is currently invisible:
`BarcodeModal`, `CameraBarcodeModal`, `DropConfigOverlay`, `FilterSyntaxHelper`,
`ScanStatusStrip`, `ShortcutsModal`, `SingleMatchPromptModal`, `Tooltip`
(trigger), plus the 5 StatusBar buttons lacking rings (Shortcuts, Reload,
Export CSV, Load config…, Config — Logs/Export/Theme partially have them;
normalize all). ContextMenu already implements full keyboard nav (arrows,
Home/End, Escape) — no work there beyond any ring normalization.

### 5. Quiet motion (proposal 2)

Keyframes in `index.css`, exposed as utility classes:

- `.animate-modal-in` — opacity 0→1, translateY(4px)→0, scale(0.995)→1,
  ~150 ms ease-out. Applied to dialog panels (FilePropertiesModal, BarcodeModal,
  ShortcutsModal, LogViewerModal, TimerModal, WorkflowRunnerModal,
  LoadConfigModal, DirectoryPickerModal, SingleMatchPromptModal,
  CameraBarcodeModal) and reused at the same spec by ContextMenu.
- `.animate-overlay-in` — opacity only, ~150 ms, on modal backdrops.
- `.animate-toast-in` — opacity 0→1 + translateY(6px)→0, ~120 ms, on the
  ActionBar toast.

Theme cross-fade: `transition-colors` (~200 ms) on the main chrome containers
(App root, HeaderBar, ActionBar, StatusBar/footer, table card, modal panels)
so a theme toggle cross-fades instead of snapping. `backdrop-filter` isn't
transitionable — acceptable; background/border/text colors are.

Easing/timeings are starting points; "quiet" is the acceptance bar: notice
them only when they're gone. The global reduced-motion clamp covers a11y.

### 6. Tooltip unification (proposal 3)

`Tooltip.tsx` (hover **and** keyboard focus, viewport-aware, token-themed) is
used only in `SearchBar`/`HeaderBar`; 27 native `title=` attributes exist.

Migration rule (my call, vetoable): **interactive controls** (buttons, icon
buttons, links) get wrapped in Tooltip — use `block={false}` for inline flex
rows like the StatusBar so the wrapper div doesn't disturb layout.
**Non-interactive** truncation/indicator titles (e.g. `title={directory}` on
truncated spans, the table hook icon) keep native `title` — they reveal
content rather than afford a control, and wrapping table cells would bloat row
DOM. The builder enumerates the interactive subset.

## Sequencing (commits on `fix/web-light-theme-polish`)

1. `feat(web): status tokens, button classes, focus-ring utility` — `index.css` only.
2. `refactor(web): sweep hard-coded accents onto tokens` — the component files
   from the inventory (+ rebuilt `dist/`).
3. `fix(web): consistent focus-visible rings` — `.focus-ring` adoption.
4. `feat(web): quiet motion for overlays and theme cross-fade`.
5. `refactor(web): unify tooltips on glass Tooltip` — interactive-title sweep.

Each commit: `npm run build` + `npm test` green, `dist/` committed with the
change. Full Python suite is untouched but run once at the end as sanity. One
PR from the branch when the sequence lands.

## Manual Verification Checklist (per commit, both themes)

- Open every modal; tab through it — focus always visible.
- Toggle theme repeatedly — cross-fade, no layout shift, nothing unreadable.
- Trigger toast (info + error), open context menu, hover keyboard-focus a
  migrated tooltip.
- Run `pywebview` desktop window once at the end; repeat the checklist there.

## What's Left to the Builder

- `@apply` vs raw CSS for the new classes.
- Exact easing curves/durations within the "quiet" bar.
- The chrome container list for `transition-colors`.
- Enumerating the exact interactive `title=` subset (rule is given above).
- Any theme-neutral cases the sweep rule keeps hard-coded — list them in the
  commit message for review.
