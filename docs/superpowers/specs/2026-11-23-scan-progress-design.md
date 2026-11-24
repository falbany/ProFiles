# Live Scan Progress via `/api/scan/events` — Design

**Date:** 2026-11-23 · **Issue:** [#152](https://github.com/falbany/ProFiles/issues/152) · **Status:** Approved design (brainstorm + builder review 2026-11-23)

## Intent and Why

During a scan of a large directory — typically a network share — the web UI
shows only a spinner with an elapsed-seconds counter (`ScanStatusStrip`).
There is no way to tell "is it stuck?" from "is it working?". The server
already streams a status SSE endpoint (`GET /api/scan/events`) every second,
but no client consumes it (flagged as dead surface in #143).

The issue as filed assumed a web-only change ("no server changes needed").
That premise is false: `state.cached_results` is only assigned after the
entire scan completes (`routes/scan.py:70`), so during a scan the SSE
`count` field holds the *previous* scan's results — wiring it as-is would
display stale, misleading numbers. The scope therefore widens to core +
server + web (approved by the maintainer 2026-11-23). Implementing this
turns the dead endpoint into a live feature and resolves the #143 finding.

## Goals

- While any server scan **this window initiated** runs, `ScanStatusStrip`
  shows a live file count: `Scanning <dir> — 1,234 files — 42s` (count
  updates at the 1s SSE tick; thousands-separated; elapsed timer stays).
  Cache-only operations that show the spinner (sort reloads) keep the
  elapsed-only display — no fake numbers.
- The strip also appears during the **initial load scan** (startup), which
  today gets no progress feedback at all and is typically the longest scan
  of a session on a network share.
- The SSE endpoint becomes a consumed, live surface (resolves the #143
  dead-endpoint finding).
- Fallback: if the SSE stream errors or is unavailable, the strip degrades
  to exactly today's elapsed-only display — silently, no toasts, no retry
  machinery (`EventSource` auto-reconnects on its own).

## Non-goals

- No percentage / ETA (the total is unknowable before the walk finishes).
- No visibility for scans started from *other* LAN devices/windows — the
  strip follows client-initiated work only. (Possible follow-up if real
  multi-device use appears; explicitly deferred.)
- No server-side cancel, no changes to scan semantics, sort reloads, or
  auto-rescan timing.
- Not touching the misleading "Select a directory and scan to find files"
  empty state shown during initial load (`FileListTable.tsx`) — pre-existing
  concern, separate issue if ever.
- No change to the desktop (PyWebView) shell: it serves the same web UI and
  inherits the feature for free.

## Anti-goals (what would make this a failure)

- Showing stale numbers as if they were progress (the reason web-only was
  rejected).
- A progress display that spams toasts or reconnect noise when degraded.
- Regressing existing feedback: the strip must still appear instantly on
  click (not wait for the first SSE tick), and sort reloads (which show the
  spinner without any server scan) must keep their current indicator.

## Decided Design

### Trigger semantics (decided with the maintainer)

The strip is visible when `scanning || initialScanActive`, where both are
client-owned state:

- `scanning` — existing `useScanController` flag (explicit scans,
  auto-rescans, directory changes, sort reloads).
- `initialScanActive` — new App-level flag set around the
  `scan.runScan(...)` call inside `initializeFromConfig` (`App.tsx:418-429`),
  cleared in a `finally`. It covers only the scan portion of startup, not
  the system-info/config fetches before it. The retry path
  (`runInitialLoad` → same code) is covered automatically.

Server truth (`in_progress` from SSE) is **not** used for strip
*visibility* — one source of truth (client state), and the strip
appears/disappears exactly when today's spinner semantics say it should.

The count *segment*, however, is gated on the payload's `in_progress`
(amendment from the builder review, maintainer-approved 2026-11-23): sort
reloads turn the spinner on without running any server scan, so without
that gate the strip would paint the previous scan's final count as if it
were progress for the whole reload — the stale-numbers anti-goal. The
hook therefore consumes `progress` **and** `in_progress`; `count` and
`directory` in the payload are ignored by the client (directory comes
from existing App state). Net effect: numbers only paint while the server
is actually scanning; visibility stays instant and client-owned.

### Core: optional progress callback

`scan_and_process_dynamic` gains an optional keyword parameter:

```python
on_progress: Callable[[int], None] | None = None
```

Threading it through to the shared `_run_scan_pipeline` (`scanner.py:359`),
which invokes it at the consumption point of the `_scan_and_filter`
generator (`scanner.py:412-423`) with the running count of
**filter-passing candidates** — files that pass the extension filter and,
when one is active, the `filter_text` expression.

**Count semantics (decided; wording fixed after builder review):** the
callback reports candidates yielded by `_scan_and_filter`, single-threaded,
no locking. Because the pipeline collects all candidates *before*
processing begins, the count rests at its final value during the
processing phase — and it converges to the count the results table is
about to show, so during a filtered auto-rescan the user watches matches
appear ("3 files"), not raw walk discoveries ("50,000 files"). The strip
label stays generic ("N files"), so the phase shift is invisible and
monotonic.

- Existing callers pass nothing; zero behavior change (pure-function
  contract intact).
- The callback is documented as "must not raise"; the server's callback is
  a trivial int write, so no defensive wrapping (KISS).
- Exposed on `scan_and_process_dynamic` only (the server's entry point);
  `_run_scan_pipeline` takes the parameter internally. `scan_and_process`
  (non-dynamic) is untouched — no speculative API surface.

### Server: progress in state and SSE payload

- `ServerState` gains `scan_progress_count: int = 0` (`state.py`).
- `execute_scan` (`routes/scan.py`): reset `state.scan_progress_count = 0`
  at the **top** of the handler, immediately after the
  `state.scan_generation += 1` bump and *before* the `exists()` early
  return — so every exit path, including the missing-directory early
  return (`routes/scan.py:43-51`), starts the strip from zero (builder
  review: resetting only alongside `scan_in_progress = True` would leave a
  previous scan's count visible on that path). Pass a callback that
  writes the latest value, **generation-guarded** like the existing checks
  (`if scan_generation == state.scan_generation:`), so a superseded scan's
  late callbacks cannot pollute a newer scan's counter. (Int read/write
  under the GIL; the SSE generator only reads the latest value — no
  locking.)
- **Known limitation (accepted, maintainer 2026-11-23):** the counter is
  server-global, so two windows scanning simultaneously would see each
  other's numbers. This inherits the existing single-active-scan state
  model (`scan_generation`, shared `cached_results`, shared
  `active_directory`) rather than adding a new flaw; a scan-id echo would
  fix only progress while the rest stays shared. If multi-client use ever
  becomes real, the fix is a broader scan-session design.
- `scan_events` SSE payload gains `"progress": state.scan_progress_count`;
  event name stays `"status"`, tick stays 1s. New payload:
  `{in_progress, count, progress, directory}`.

### Web: hook + strip

- New `useScanProgress(active: boolean)` hook in `src/profiles/web/src/hooks/`
  (per the issue's sketch, per-file test included):
  - When `active` flips true: open one `EventSource("/api/scan/events")`,
    listen to the named `status` events, expose `progress: number | null`
    from `data.progress` and the latest `in_progress` flag from the
    payload (the count segment only renders when `in_progress` is true
    and `progress != null`).
  - When `active` flips false or on unmount: close it.
  - On stream error: set `progress` to `null` (degraded fallback), let the
    browser's auto-reconnect do its thing; next successful event resumes.
- App passes `scanProgress` down through `ActionBar` → `ScanStatusStrip`.
  `ActionBar`'s strip gate becomes `scanning || initialScanActive`
  (directory label continues to come from existing App state).
- `ScanStatusStrip` renders the count segment only when `in_progress` is
  true and `progress != null`; anything else renders byte-identical to
  today's output (including during sort reloads, which keep the instant
  elapsed-only indicator). Format: `1,234 files` (locale thousands
  separator) between the directory and the elapsed timer.

### Tests

Following the repo's one-test-file-per-module pattern:

- **Core:** `on_progress` invocation for `scan_and_process_dynamic` —
  called with monotonic counts during the walk, not called when `None`
  (existing home: tests under `tests/core/processing/`).
- **Server:** SSE payload includes `progress` (existing
  `tests/server/routes/test_scan.py`); counter reset at the top of the
  handler — covering the missing-directory early return; generation guard
  (stale callback from a superseded scan doesn't write).
- **Web:** hook test with a mocked `EventSource` (open/close lifecycle,
  progress updates, error → null fallback, `in_progress` gating);
  `ScanStatusStrip` test for the count rendering + fallback byte-identical
  output (including the `in_progress: false` sort-reload case);
  ActionBar/App wiring covered by existing suites.

## Constraints

- Architecture rules: core stays UI-free (a `Callable` callback is pure
  inversion of control); server keeps delegating to core; web keeps all UI
  in the presentation layer. No circular imports.
- Quality gates per AGENTS.md: ruff format/check, pylint > 8.0, pytest
  coverage > 85%, type hints + docstrings on public functions.
- No new dependencies (SSE client is the browser-native `EventSource`).

## Left to the Builder

- Exact mechanics of counting the `_scan_and_filter` generator consumption
  (wrapper generator vs. explicit loop) — semantics pinned above, mechanism
  free.
- Test case selection and fixtures within the pinned coverage points.
- Any micro-refactors needed to keep functions under the project's
  complexity limits, as long as behavior matches this document.
