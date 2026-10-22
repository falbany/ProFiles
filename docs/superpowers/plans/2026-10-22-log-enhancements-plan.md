# Implementation Plan — Log enhancements (approved design, 2026-10-22)

Source spec: chat design, approved 2026-10-22 by human partner (all items).

## Tasks (TDD — failing test first for each Python change)

- [x] 1. **ScanTimer ext/filter** — `ScanTimer(extension=…, filter_text=…)` thread
      through `finish()` → `scan_complete()`; `scanner.py` passes real values.
      Tests: `tests/core/telemetry/test_metrics.py` (4 new tests, RED→GREEN).
- [x] 2. **user@host source** — `format_user_host(username, hostname)` in
      `core/environment/system.py`, re-exported from `core` + `environment`;
      used by `app.py::_setup_logging` and `gui/main_window.py`.
      Tests: `tests/core/environment/test_system.py` (4 new) + `tests/test_app.py`.
- [x] 3. **APP_ENV** — `APP_STARTED` extended with optional
      `python="…" os="…"` fields; both call sites pass `platform` values.
      Tests: `tests/core/telemetry/test_events.py`.
- [x] 4. **LOG_ROTATED** — `TelemetryRotatingFileHandler` emits
      `LOG_ROTATED old_size_bytes=…` as first line of each fresh rotation
      (temporarily disables shouldRollover to avoid recursion).
      Tests: `tests/core/telemetry/test_diagnostics.py` (2 new).
- [x] 5. **SLOW_SCAN** — `scan_complete()` emits WARNING
      `SLOW_SCAN dir=… duration_ms=…` above `SLOW_SCAN_THRESHOLD_MS` (5000).
      Tests: `tests/core/telemetry/test_events.py` (2 new).
- [x] 6. **WEB_CLIENT** — HTTP middleware in `server/app.py` logs
      `WEB_CLIENT event="connected" ip=… path=… ua=…` once per client IP.
      Tests: `tests/server/test_web_client.py` (2 new; `httpx` installed
      from the project dev extra).
- [x] 7. **UNCAUGHT_EXCEPTION** — `install_crash_hook(logger)` in
      diagnostics; chains previous excepthook; emits CRITICAL
      `type="…" error="…"`. Call sites: app + main_window startup.
      Tests: `tests/core/telemetry/test_diagnostics.py` (2 new).
- [x] 8. **LogViewerModal** — source column (`w-[150px] truncate`, title attr)
      showing `entry.source` (e.g. `f.albany@ST-465`).
- [x] 9. **LogViewerModal width** — `w-[clamp(560px,85vw,1500px)]`.
- [x] 10. Verification: ruff clean, ruff formated, pylint core 9.99/10,
      new tests + affected suites green (141 passed), web `npm run build` OK.
      Full pytest: 1244 passed, 61 failures pre-existing (identical on the
      stashed baseline; Windows-only environment issues).
      `install_crash_hook` wired into `ProFileApp._setup_logging`
      (TDD: `tests/test_app.py::TestSetupLogging::test_installs_crash_hook`).

## Extras

- Parser regression test for `user@host` sources in
  `tests/server/test_routes_logs.py` (characterization: parser already handles).
- End-to-end sanity script validated the full pipeline: emit → file → parse.

## Verification results (2026-10-22)

| Gate | Result |
| --- | --- |
| ruff check / format | All checks passed / formatted |
| pylint core (`--fail-under=9.88`) | 9.99/10 (only pre-existing R0913 in workflow.py) |
| Targeted pytest | 141 passed |
| Full pytest (minus pre-broken Windows file) | +17 passing vs baseline, no new failures |
| `npm run build` (tsc + vite + PWA) | OK |
