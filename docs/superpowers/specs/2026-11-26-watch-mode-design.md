# Watch Mode — Rescan on Change via a Dependency-Free Polling Watcher — Design

**Date:** 2026-11-26 · **Issue:** [#223](https://github.com/falbany/ProFiles/issues/223) ·
**Status:** Approved design (brainstorm 2026-11-26, maintainer sign-off; builder review 2026-11-26 folded in)

## Intent and Why

The only way the file list stays current today is the auto-rescan timer: a
full `scan_and_process` walk every N seconds whether or not anything
changed, and still up to N seconds late when something did. On large or
network directories each tick is a visible reload; on a fast bench the
list is never quite in sync. Each tick also resets the selection to the
first row (#218).

Watch mode replaces that with event-driven rescans: a lightweight
filesystem poller detects "something under the active directory changed",
and only then does the client trigger the existing scan flow. Cheaper
between changes, faster to react to them.

Two maintainer decisions taken during brainstorming (2026-11-26) shape
everything below:

1. **Complete coverage — local and SMB/NFS alike.** Native FS events
   (FSEvents, inotify, ReadDirectoryChangesW) do not exist or are
   unreliable over network mounts, so polling is unavoidable for the
   network case. Rather than two engines, we build **one dependency-free
   polling engine used everywhere**. No `watchdog`, no ctypes, no
   per-platform observers.
2. **Probe-only.** The watcher polls **directory mtimes only** — no
   per-file stat snapshot. Create/delete/rename all mutate a parent
   directory's mtime, which is the dominant change pattern on the target
   workload (stations writing batches of files, typically via
   temp-file-then-rename). This makes the watcher nearly trivial:
   a snapshot of directory mtimes, not of every file.

This feature also gives `/api/scan/events` its second consumer (first was
#152) and closes the #143 finding about the endpoint being dead surface.

## Goals

- A **"Watch" toggle** in the search bar beside the timer control:
  always visible; disabled while a scan runs or when no directory is
  active. Watch and timer are **two modes of one "keep current"
  control, mutually exclusive** — enabling one disables the other.
- While watching: a change under the active directory triggers a rescan
  with the client's current parameters, using the existing generation
  protocol. End-to-end latency target ≈1–3 s (poll interval + 500 ms
  debounce + ≤1 s SSE tick), vs. today's fixed N-second full reload.
- On local disks **and** SMB/NFS shares, one code path, same behavior.
- **#218 rides along:** selection is preserved by `path` across *any*
  completed results refresh (timer, watch, manual). If the selected file
  still exists it stays selected and the scroll anchor holds; if it
  vanished, selection clears.
- Where the watch root vanishes (share unmounted, directory deleted),
  the watcher stops itself, the client is informed, and the UI returns
  to the un-watched state with a toast — never silently dead.
- The UI surfaces the effective polling cadence (tooltip/title on the
  toggle, e.g. "Watching · every 2 s") so slow shares are legible.

## Non-goals

- **In-place content edits** (a file rewritten in place with no
  create/delete/rename) do **not** trigger a rescan — a directory mtime
  probe cannot see them. Manual rescan and the timer remain the escape
  hatches. Accepted explicitly by the maintainer 2026-11-26.
- No native FS events, no `watchdog` dependency, no ctypes platform
  code. Dependency set unchanged.
- No configuration-format change. Watch state is **session-only** (same
  as the timer today); a persisted preference stays a possible follow-up.
- No server-initiated scans: the server only *notifies*; clients issue
  the scan (`POST /api/scan`) with their own current parameters. This
  keeps per-client filter/extension semantics and reuses the generation
  protocol unchanged.
- No incremental/differential scan — a triggered rescan is a full
  `scan_and_process`, exactly as today; watch mode changes *when*
  scans happen, not *what* they do.
- No toast per change-triggered rescan (noise); toasts only for
  enable/disable and error transitions.
- Desktop (PyWebView) shell needs no changes — it serves the same web
  UI and the same server.

## Anti-goals (what would make this a failure)

- Overlapping scans: a watch-triggered scan starting while another scan
  runs must coalesce (client-side pending flag → one trailing rescan),
  never stack.
- Selection loss: shipping watch mode while #218 still resets the
  selection every refresh would make the new mode feel worse than the
  timer. #218 is in scope and gates this feature's UX.
- The watcher walking excluded trees: `search_exclude_dirs` must prune
  the walk itself, not filter events afterwards.
- Silent death: a watcher that stopped (unmounted share) while the UI
  still shows "Watching".
- Toast/reconnect spam on flaky SSE (the #152 fallback rules apply
  unchanged: degrade silently, `EventSource` reconnects on its own).

## Decided Design

### Core — `profiles/core/processing/watcher.py`

A pure, UI-free, server-free module:

- `DirectoryWatcher(directory: Path, exclude_dirs: frozenset[str],
  on_change: Callable[[], None], on_error: Callable[[str], None],
  *, max_depth: int | None = None, debounce_s: float = 0.5,
  base_interval_s: float = 1.0, max_interval_s: float = 5.0)` — runs a
  daemon thread with a `threading.Event` stop handle; `start()`,
  `stop()` (idempotent), `retarget(directory)` (restart on a new root,
  re-baselining the snapshot so no false trigger fires), and a read-only
  `interval_s` property for UI display.
  `max_depth` mirrors the scan's effective boundary (`None` = unlimited;
  set from the scan's recursive flag + `max_search_depth`), so a
  non-recursive scan never pays for walking — or watching — the whole
  tree. **Owner call (builder review Q3):** the watcher watches exactly
  what the scan displays; exclude/depth resolution reuses the scanner's
  own merge (`_resolve_scan_config`) at enable/retarget time, and a
  config reload takes effect at the next enable/retarget (staleness
  until then is accepted and documented).
- Each tick: walk the tree (`os.walk`), **pruning** excluded subtrees,
  `stat()` every *directory* only, compare against the snapshot dict
  `{dir_path: mtime}` from the previous tick. Any diff → schedule the
  debounced `on_change` (fired ~500 ms after the *last* diff; a batch of
  200 created files = one notification).
- **Adaptive cadence:** after each walk, the next interval is
  `max(base_interval_s, 3 × measured_walk_duration)`, clamped to
  `max_interval_s`. A local tree walks in milliseconds → ~1 s cadence; a
  slow SMB walk of a few seconds → proportionally sparser probing. No
  walk ever overlaps itself.
- Snapshot is empty on first tick (baseline walk, no notification).
- Root stat fails (ENOENT, share down) → `on_error(message)`, thread
  exits. Transient errors get one retry before erroring out.
- Thread-safety: the watcher owns its state; callbacks are invoked on
  the watcher thread and must be cheap and non-blocking (server side
  only bumps a counter under a lock).

### Server — `profiles/server`

- `POST /api/scan/watch` body `{enabled: bool}` → starts or stops the
  single watcher on `state.active_directory`. Response echoes the
  effective state (`{watching: bool, interval_s: float}`) so the UI can
  display the real cadence.
- One watcher per server (stored on `ServerState`), shared by all LAN
  clients — consistent with the existing single-active-scan model.
  **Watch is server-authoritative** (the issue's own framing: "the
  server owns the single watcher for all LAN clients"): every connected
  client reflects the payload's `watching` state and reacts to
  `watch_seq` bumps. The timer/watch mutual exclusion is necessarily
  **per-client only** — the timer is client-local React state and no
  other client's watch can switch it off. **Retarget policy (owner
  call, builder review Q2):** a scan that changes `active_directory`
  re-targets the watcher onto the new root (re-baselined, no false
  trigger) — including the ping-pong case of two clients scanning
  different roots, which is rare and cheap (each restart is a baseline
  walk). If the new root does not exist (`execute_scan` accepts
  nonexistent directories and returns a warning today), the watcher
  **stops with `watch_error` set** rather than watching a dead root;
  this matches the existing blast radius of the shared-surface model —
  that same broken scan already replaces every client's cached list.
- **Notification channel:** no push hub. The existing SSE endpoint
  streams a `status` tick every second; add `watch` fields to
  `scan_status_payload`:
  `watching: bool`, `interval_s: float`, and `watch_seq: int` — a
  monotone counter bumped (under a lock) by the watcher's `on_change`.
  Clients track the last seq they acted on; a bump means "something
  changed". Edge-triggering survives reconnects and multiple clients
  with no sticky flags.
- `on_error` → set `watching: False`, stop the watcher, record a
  message surfaced in the status payload (`watch_error: str | None`,
  cleared on next enable). Clients toast it once and un-toggle.
- `GET /api/scan/results` gains a `find_path` query parameter
  (maintainer decision 2026-11-26, builder review Q5): returns
  `{offset: int}` — the path's position in the *sorted* cached set,
  under the same `sort_by`/`sort_dir` the client displays — or
  `offset: -1` when the path is gone. This is what lets selection
  survive across the full result set rather than only the rows the
  client has loaded so far (progressive paging: pages of 500, fetched
  on scroll — a batch of new files sorted to the top can push the
  selected row far beyond the loaded window, the exact scenario watch
  mode targets).
- Watch-triggered client scans funnel through the existing
  `POST /api/scan` guard — if a scan is already in progress the route's
  current behavior applies (builder: verify reject-vs-queue and match
  the client pending-flag to it; see "Left to the builder").

### Web client — `src/profiles/web`

- **One shared SSE subscription (owner call, builder review Q6):** the
  #152 client (`useScanProgress`) opens its `EventSource` only while a
  scan is in flight — the wrong lifecycle for watch, which must listen
  while idle. Rather than a second long-lived connection per client,
  the status feed is lifted into one app-level subscription consumed by
  both: `useScanProgress` keeps its external API and behavior (it gates
  *display* on scan activity, not the connection), and watch consumes
  the same stream. One `EventSource` per client, ever.
- New `useWatchMode` hook mirroring `useAutoRescanTimer`'s injected-deps
  shape: `{ watching, watchInterval, handleWatchSet, disabled }`. The
  toggle state is **derived from and reconciled with the server
  payload**: it seeds from the first status tick after connect, so a
  client joining while another enabled watch sees "Watching" and reacts
  to `watch_seq` bumps too. On a bump — while watching and not
  mid-scan — it calls `scan()` (the same `handleScanRef` wrapper the
  timer uses, so current directory/extension/filter always apply).
  Events arriving mid-scan set a pending flag → exactly one trailing
  rescan after the current one completes. Reconciliation rules: a
  payload `watching: false` that the client did not cause (server
  restart, another client's error) un-toggles silently when
  `watch_error` is empty, and un-toggles **with one toast** when
  `watch_error` carries a message (unmounted share, dead root). No
  drift machinery beyond that: the server payload is the truth, the
  toggle renders it.
- **Toggle UI** in the search bar next to the timer control: enabled
  (watchable) / disabled while a scan runs or no directory active;
  mutually exclusive with the timer (setting one turns the other off,
  same toast conventions). Tooltip/title shows live cadence
  ("Watching · every 2 s"). Enabling/disabling toasts once; rescan
  triggers do not toast. SSE-unavailable degrades silently (toggle still
  works for state, but no live triggers — same stance as #152).
- **#218 — selection preservation** (applies to every refresh path:
  timer tick, watch trigger, manual scan): keep the selected row across
  result replacement by matching `path`; keep the scroll anchor. If the
  selected path no longer exists, clear the selection (no neighbor
  auto-select — an invisible re-selection risks an accidental launch).
  **Precise semantics (owner call, builder review Q4):** today
  `selectedIndex` is always ≥ 0 — row 0 is selected from the start and
  the reconcile effect *clamps* the index when the path is gone,
  silently re-selecting a different file. That clamp is removed and
  replaced by the preserve-or-clear rule; a vanished selection becomes
  a real "nothing selected" state (`-1`: no highlight, `Enter`/Execute
  inert, `aria-activedescendant` guarded). The *initial* row-0
  selection after the first scan is unchanged — the fix scopes to what
  happens on refreshes, not to first-paint UX. The client never
  re-selects on the user's behalf. **Beyond the loaded window:** after
  a refresh, matching first runs against the rows already loaded; if
  not found there, the client queries `find_path` (same sort params it
  displays) — a hit beyond the loaded window fetches the page
  containing the row via the existing progressive-paging fetch and
  restores selection + scroll anchor there; `offset: -1` clears.

### Docs

- README: watch mode in the feature list, one paragraph.
- Network guide: one watcher per server; cadence adapts to share speed
  (expect ~1–2 s locally, a few seconds on busy shares); in-place edits
  are not detected (probe-only) — note the temp-then-rename pattern.

### Tests

- Core (pytest): change detection matrix — file create/delete/rename,
  subdirectory create/delete, excluded dirs pruned (a change inside an
  excluded tree does not fire), debounce coalescing (N rapid changes →
  one callback), adaptive interval clamps, baseline walk fires nothing,
  root-vanish → `on_error` + stop, `retarget` moves the snapshot,
  `stop()` idempotent. Use `tmp_path` + real sleeps kept small (tens of
  ms, tuned like existing scanner tests).
- Server (pytest): `POST /api/scan/watch` enable/disable round-trip,
  re-target on active-directory change, dead-root re-target stops with
  `watch_error`, `watch_seq` monotonicity and presence in the status
  payload, error path clears `watching`; `find_path` returns the right
  offset under each sort, `-1` when gone. SSE assertions via a real
  bound uvicorn port (the ASGITransport buffering gotcha from #152 —
  do not test the stream through the transport).
- Web (vitest): `useWatchMode` seq-edge → single scan, pending-flag
  coalescing, mutual exclusion with timer, disabled states, payload
  reconciliation (silent vs toasted un-toggle); selection preservation
  (#218) — same-path refresh keeps selection and scroll, vanished path
  clears to inert nothing-selected, path pushed beyond the loaded
  window is restored via `find_path` + page fetch.

## Scope

Size M. Semver risk low — one additive endpoint
(`POST /api/scan/watch`), one additive query parameter (`find_path` on
the existing `GET /api/scan/results`), additive SSE status fields,
web-only UI otherwise.

- [x] Web UI (`src/profiles/web`)
- [x] Python backend / core (`core/processing/watcher.py`,
      `server/routes/scan.py`, `server/state.py`)
- [ ] Configuration format — intentionally out (session-only preference)
- [x] Documentation — README, network guide
- [ ] Packaging / CI — no changes expected (no new deps)

Resolves #223 and #218. #143 item 1 (dead SSE endpoint) is superseded —
this feature and #152 made it a live surface; #143's remaining items 2–5
are unrelated dead-code cleanup, deliberately not bundled here.

## Left to the builder

Things a sensible builder still settles in code, with the constraints
above held fixed:

- Exact placement/markup of the Watch toggle beside the timer control,
  matching the existing search-bar component's idioms.
- `scan_status_payload` field naming beyond `watching` / `interval_s` /
  `watch_seq` / `watch_error`, kept consistent with the existing payload.
- The precise reject-vs-queue semantics of `POST /api/scan` while a scan
  is in progress, and the client pending-flag logic that matches it.
  (Builder-review fact to plan around: the route currently has *no*
  in-progress guard at all — only generation supersession — so the
  client-side pending flag is the only coalescing mechanism.)
- Interval constants tuning (base 1 s, ×3, cap 5 s) if tests show a
  better clamp — the *shape* (adaptive, clamped, never overlapping) is
  fixed, the numbers are tunable.
- Where the selection-preservation logic lives (App-level results
  application vs. `FileListTable`), following the #148 decomposition's
  boundaries.
- Test file placement per `tests/AGENTS.md` (mirror the source tree 1:1).
