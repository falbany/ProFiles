# Log Format & Telemetry Design

Date: 2026-08-29
Status: Draft (pending user review)
Scope: `src/profiles/core/telemetry/**` + all 77 log call sites across the codebase

## Problem

`profiles.log` is currently a flat human-readable text file. After ~1 hour of typical use
(599 lines / 81 KB), the file accumulates:

- 17 distinct event types emitted as free-text English
- 77 log call sites across 16 modules, each formatting messages with `f"…{var}…"` or `%s`
- 63 repeated WCAG contrast warnings (one per theme switch × theme pair)
- 98 `Scan metrics: {…}` records serialized as Python `repr()` — not parseable without regex
- 197 `Configuration loaded` events (mix of `loaded`, `loaded successfully`, `reloaded`)
- 6 `USER=…,PROFILE_VERSION=…,LAUNCH=…` audit lines formatted as a single `info()` call

Consequences:

1. **No machine-readability**: any analytics, dashboards, or regression detection
   requires custom regex per event type.
2. **No consistency**: pipe-delimited (`|`) for scans, Python `repr()` for metrics,
   `key=val` for the audit line, English prose for everything else.
3. **No observability of telemetry itself**: there is no record of *which log calls fired*,
   so a user reading the file can't distinguish "the app didn't do that" from "the app
   did that but the call site was silent".
4. **No session correlation**: a `Configuration reloaded` at 23:18 cannot be tied to
   a specific app run or the `ProFiles started` event of that run.
5. **WCAG noise**: every theme switch logs the same contrast ratios for the same
   surface pairs — log volume is dominated by static facts.

## Goals (in priority order)

1. Make every log line **parseable** by a single, documented grammar.
2. Make every event **structurally consistent**: an event name, a fixed set of named fields.
3. Reduce log volume by **deduplicating** static-per-session events (WCAG ratios).
4. Preserve **human readability** for interactive debugging.
5. Avoid breaking the public log surface that other tools (log openers, test assertions)
   may depend on — keep the same timestamp + level + source prefix.

## Non-goals

- Telemetry upload / remote collection. The log stays local; this spec is format-only.
- Replacing the rotating file logger with a different library.
- New log levels (TRACE / NOTICE) — stick to standard Python levels.
- Backward-compatible parse of the old pipe-delimited format (the log is rotated, not
  appended forever; users can read old `profiles.log.1` files manually).

## Target Log Format

Every line emitted to `profiles.log` follows this grammar:

```
<timestamp> - <LEVEL>  - <source>: <event> <field>=<value> <field>=<value> ...
```

- `timestamp` — existing format: `YYYY-MM-DD HH:MM:SS`
- `LEVEL` — `DEBUG` / `INFO` / `WARNING` / `ERROR` (existing 4-space pad, no change)
- `source` — hostname (existing, set via `SourceFilter` at logger creation)
- `event` — short, stable, **UPPER_SNAKE_CASE** identifier (the new field)
- `field=value` — quoted strings (`"value"`) for anything containing spaces or `=`; bare
  tokens for booleans, integers, floats

Example lines (final form):

```
2026-08-29 13:01:15 - INFO  - MACBOOKFA.LOCAL: APP_STARTED version="2026.7.0" headless=false
2026-08-29 13:01:15 - DEBUG - MACBOOKFA.LOCAL: SCAN_COMPLETE dir="base" ext="*" filter="" files=284 duration_ms=25.6 rate=7366 recursive=true errors=0
2026-08-29 13:01:51 - INFO  - MACBOOKFA.LOCAL: APP_CLOSED uptime_s=36
2026-08-29 01:08:12 - INFO  - MACBOOKFA.LOCAL: THEME_SWITCHED value=auto warnings=2
2026-08-29 12:36:06 - INFO  - MACBOOKFA.LOCAL: FILE_LAUNCHED path="/Users/falbany/.../README.md"
2026-08-28 23:49:22 - WARNING - MACBOOKFA.LOCAL: WCAG_CONTRAST_FAINT pair=border/surface ratio=4.22 fg=#7A7680 bg=#121212
```

### Grammar (formal)

```
line        = timestamp SP level SP source COLON event (SP field)*
timestamp   = \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}
level       = DEBUG | INFO | WARNING | ERROR
source      = [A-Za-z0-9._-]+
event       = [A-Z][A-Z0-9_]+
field       = key EQ value
key         = [a-z][a-z0-9_]*
value       = bare | quoted
bare        = [^\s"=]+
quoted      = '"' [^"]* '"'
```

Spaces inside `quoted` values are preserved. No escaping needed (paths and messages in
this codebase never contain `"`; if a future event needs it, raise an issue rather than
extending the grammar inline).

## Event Catalogue (17 event types)

Every log call site maps to exactly one event name. The table below is normative —
implementation must use these names, and adding a new name requires updating this spec.

| Old message (representative) | New event | Fields (after event) | Level |
|---|---|---|---|
| `ProFiles started` | `APP_STARTED` | `version`, `headless` | INFO |
| `ProFiles closed` | `APP_CLOSED` | `uptime_s` | INFO |
| `Restarting application...` | `APP_RESTARTING` | — | INFO |
| `New instance launched via module: %s` | `APP_LAUNCHED` | `command` | INFO |
| `Failed to create GUI: %s` | `APP_GUI_FAILED` | `error` | ERROR |
| `Configuration loaded: %s (release=%s)` | `CONFIG_LOADED` | `path`, `mode`, `release` | INFO |
| `Configuration loaded successfully: %s` | _(merged into `CONFIG_LOADED`)_ | | |
| `Configuration reloaded` | `CONFIG_RELOADED` | `path` | INFO |
| `Configuration file created: %s` | `CONFIG_CREATED` | `path` | INFO |
| `Wrote starter configuration: %s` | _(merged into `CONFIG_CREATED`)_ | | |
| `Failed to reload configuration: %s` | `CONFIG_RELOAD_FAILED` | `error` | ERROR |
| `Invalid configuration: %s` | `CONFIG_INVALID` | `error` | ERROR |
| `Scanned directory: base \| Extension: …` | `SCAN_COMPLETE` | `dir`, `ext`, `filter`, `files`, `recursive` | INFO |
| `Scan metrics: {…}` | _(merged into `SCAN_COMPLETE`)_ | `duration_ms`, `rate`, `errors` (DEBUG) | DEBUG |
| `Error scanning directory %s: %s` | `SCAN_FAILED` | `dir`, `error` | WARNING |
| `Theme switched to: %s` | `THEME_SWITCHED` | `value`, `warnings` (count) | INFO |
| `Language switched to: %s` | `LANG_SWITCHED` | `value` | INFO |
| `Opening configuration file: %s` | `FILE_OPEN_CONFIG` | `path` | INFO |
| `Opening log file: %s` | `FILE_OPEN_LOG` | `path` | INFO |
| `File not found: %s` | `FILE_NOT_FOUND` | `path` | WARNING |
| `Not a file: %s` | `FILE_NOT_A_FILE` | `path` | WARNING |
| `Failed to launch file: %s` | `FILE_LAUNCH_FAILED` | `path`, `error` | ERROR |
| `File deleted: %s` | `FILE_DELETED` | `path` | INFO |
| `Failed to delete file %s: %s` | `FILE_DELETE_FAILED` | `path`, `error` | ERROR |
| `Failed to create config file: %s` | `CONFIG_CREATE_FAILED` | `error` | ERROR |
| `WCAG contrast below AA threshold: …` | `WCAG_CONTRAST_FAINT` | `pair`, `ratio`, `fg`, `bg` | WARNING |
| `USER=…,PROFILE_VERSION=…,LAUNCH=…,ARGS=…` | `FILE_LAUNCHED` | `path`, `version`, `user`, `args` | INFO |
| `Command timed out after %ss: %s` | `COMMAND_TIMEOUT` | `timeout_s`, `command` | WARNING |
| `Command exited with code %d` | `COMMAND_EXIT` | `code`, `command` | DEBUG |
| `Command execution failed: %s` | `COMMAND_FAILED` | `error`, `command` | ERROR |
| `Step N/M (action: %s)` … 12 workflow messages | `WORKFLOW_STEP` | `index`, `total`, `action`, `result` | INFO |
| `Step failed (failmode=…).` | `WORKFLOW_STEP_FAILED` | `failmode`, `action` | WARNING |
| `Step failed and … Aborting.` | `WORKFLOW_ABORTED` | `reason` | ERROR |
| `Error processing file %s: %s` | `PROCESSING_FAILED` | `path`, `error` | ERROR |
| 25+ debug messages | preserved at DEBUG, no event name needed (use `event=DEBUG` or drop the event token for `DEBUG`-level only lines) | | |

**Rule**: for the rare one-off `logger.info("Wrote starter configuration: %s", target)`
with no obvious home, it merges into `CONFIG_CREATED` rather than getting its own event.
The catalogue is intentionally short.

## Architecture

### New module: `core/telemetry/events.py`

A small set of typed helpers that emit structured events. Each helper is a thin wrapper
that:

1. Formats the `event` token + named fields into a single message string.
2. Calls the appropriate `logger.<level>(...)` exactly once.

```python
# src/profiles/core/telemetry/events.py

def app_started(logger, *, version: str, headless: bool) -> None:
    """Emit APP_STARTED."""
    logger.info('APP_STARTED version="%s" headless=%s', version, _bool(headless))

def scan_complete(
    logger,
    *,
    directory: str,
    extension: str,
    filter_text: str,
    files: int,
    recursive: bool,
    duration_ms: float,
    errors: int = 0,
) -> None:
    """Emit SCAN_COMPLETE at INFO and metrics at DEBUG."""
    logger.info(
        'SCAN_COMPLETE dir="%s" ext="%s" filter="%s" files=%d recursive=%s',
        directory, extension, filter_text, files, _bool(recursive),
    )
    if logger.isEnabledFor(logging.DEBUG):
        rate = files / (duration_ms / 1000) if duration_ms > 0 else 0
        logger.debug(
            'SCAN_METRICS dir="%s" duration_ms=%.3f rate=%.2f errors=%d',
            directory, duration_ms, rate, errors,
        )

# ... ~25 helpers, one per event in the catalogue
```

**Why helpers, not `extra={...}`**: `extra` works for arbitrary fields but the formatter
still produces `"%(message)s"` text, so the message string *is* the wire format. Helpers
keep the wire format in one place and make the call sites read like English.

### Module: `core/telemetry/diagnostics.py` — minimal changes

- Add `EVENT_FORMAT` to complement the existing `LOG_FORMAT` (which stays for any
  out-of-band messages that still use the legacy English form during the transition).
- Add `_bool(b: bool) -> str` returning `"true"` / `"false"` (lowercase, parseable).
- No change to `LoggerFactory`, `SourceFilter`, `RotatingFileHandler` config.

### Module: `core/telemetry/metrics.py` — single call site updated

`ScanTimer.__exit__` currently calls `logger.debug("Scan metrics: %s", metrics.to_dict())`.
Replace with `events.scan_metrics(logger, metrics)`. The dataclass is unchanged.

### Call-site migration

77 call sites. Mechanical sed-style refactor (one event helper per site, parameters
extracted). Two patterns:

```python
# Before
self._logger.info("ProFiles started")

# After
events.app_started(self._logger, version=__version__, headless=self._headless)
```

```python
# Before
logger.info(
    "Scanned directory: %s | Extension: %s | Filter: %r | Files found: %d",
    directory, extension, filter_text, file_count,
)

# After
events.scan_complete(
    logger,
    directory=directory,
    extension=extension,
    filter_text=filter_text,
    files=file_count,
    recursive=recursive,
    duration_ms=metrics.duration_ms,
    errors=metrics.error_count,
)
```

### Test surface

Existing tests under `tests/core/telemetry/` cover the legacy format. Two changes:

1. **Update format tests** to match the new grammar. They must assert the event token
   and key fields, not full string equality.
2. **Add `test_events.py`** — one test per helper, asserting:
   - Event name is the first token after the source colon
   - Field names match the catalogue
   - Quoted vs bare value rules are respected (e.g., paths with spaces get quoted)
   - `ScanTimer` integration still produces a `SCAN_METRICS` line at DEBUG

A **regression fixture** holds 5-10 golden lines (one per major event type) — the test
parses each line and checks the catalogued fields, ensuring no future change breaks the
grammar.

### Documentation

Add a 30-line page at `docs/operations/log-format.md` showing:

- The grammar
- The full event catalogue
- Two `grep` examples: "find all failed scans" / "find all themes that had contrast warnings"

## Error Handling

- **Logger never raises**: `events.*` helpers do not catch; if the underlying logger fails,
  the exception propagates (current behavior).
- **Malformed values**: `events.scan_complete(..., files="not-an-int")` will fail at the
  `%d` format spec — fail fast at the call site, never silently emit a wrong value.
- **Backward-incompatible**: the log file format changes. Users who tail `profiles.log`
  in another tool will need to update parsers. Documented in CHANGELOG.

## Testing Strategy

1. **Unit tests** — `test_events.py`: one test per helper (~25 tests), plus a parser test
   that reads 5 sample lines and reconstructs the field dict.
2. **Golden-line regression** — `test_log_format_golden.py` reads `tests/fixtures/sample.log`
   and asserts the new grammar parses cleanly and matches the catalogue.
3. **Integration smoke** — run the GUI in test mode, capture 1 minute of logs, assert at
   least one of each: `APP_STARTED`, `SCAN_COMPLETE`, `THEME_SWITCHED`, `APP_CLOSED`.
4. **No regressions** in existing telemetry tests; they will be updated in the same PR.

## Rollout

1. Land the catalogue + `events.py` + helper signatures in one PR (no call-site changes yet).
2. Migrate call sites in **2-3 PRs by module area**: app lifecycle first, then scanning,
   then workflow / config. Each PR updates tests for the affected module.
3. Delete legacy code paths once all call sites are migrated.
4. Bump the `PROFILE_VERSION` log field to `2026.8.0` to mark the new format.

## Out of Scope (explicit)

- Log shipping / SIEM integration.
- Per-user PII redaction (no PII is currently logged).
- Changing the rotation policy (5 MB × 5 backups is fine).
- A GUI viewer for the new format (defer; `grep` is sufficient for now).
