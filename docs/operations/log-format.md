# Log Format

ProFiles writes structured telemetry to `profiles.log` using a key=value grammar.

## Grammar

Every line follows this shape:

```
<timestamp> - <LEVEL>  - <hostname>: <EVENT_NAME> key="value" key=value ...
```

| Token | Format | Example |
|---|---|---|
| `timestamp` | `YYYY-MM-DD HH:MM:SS` | `2026-08-29 13:01:15` |
| `LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` (4-char pad) | `INFO ` |
| `hostname` | short machine name | `MACBOOKFA.LOCAL` |
| `EVENT_NAME` | UPPER_SNAKE_CASE | `SCAN_COMPLETE` |
| `key` | lowercase_snake_case | `dir` |
| `value` | quoted if it contains spaces or `=`; bare otherwise | `"base"` / `284` |

## Event Catalogue

| Event | When emitted | Fields |
|---|---|---|
| `APP_STARTED` | App startup | `version`, `headless` |
| `APP_CLOSED` | App shutdown | `uptime_s` |
| `APP_RESTARTING` | About to spawn new instance | — |
| `APP_LAUNCHED` | New process spawned | `command` |
| `APP_GUI_FAILED` | Tk root creation or restart failed | `error` |
| `CONFIG_LOADED` | Config file parsed successfully | `path`, `mode`, `release` |
| `CONFIG_RELOADED` | Config reloaded after file change | `path` |
| `CONFIG_CREATED` | Starter config written | `path` |
| `CONFIG_INVALID` | YAML/validation error | `error` |
| `CONFIG_RELOAD_FAILED` | Reload raised | `error` |
| `CONFIG_CREATE_FAILED` | Starter write failed | `error` |
| `SCAN_COMPLETE` | Directory scan finished (INFO) | `dir`, `ext`, `filter`, `files`, `recursive` |
| `SCAN_METRICS` | Same scan, DEBUG only | `dir`, `duration_ms`, `rate`, `errors` |
| `SCAN_FAILED` | Scan exception | `dir`, `error` |
| `THEME_SWITCHED` | User changed theme | `value`, `warnings` |
| `LANG_SWITCHED` | User changed language | `value` |
| `WCAG_CONTRAST_FAINT` | Theme pair below AA ratio | `pair`, `ratio`, `fg`, `bg` |
| `FILE_OPEN_CONFIG` | User opened config file | `path` |
| `FILE_OPEN_LOG` | User opened log file | `path` |
| `FILE_NOT_FOUND` | Launch target missing | `path` |
| `FILE_NOT_A_FILE` | Path is not a file | `path` |
| `FILE_LAUNCHED` | User launched a file (audit) | `path`, `version`, `user`, `args` |
| `FILE_LAUNCH_FAILED` | Launch raised | `path`, `error` |
| `FILE_DELETED` | File removed | `path` |
| `FILE_DELETE_FAILED` | Delete raised | `path`, `error` |
| `WORKFLOW_STEP` | Workflow step ran | `index`, `total`, `action`, `result` |
| `WORKFLOW_STEP_FAILED` | Step raised (failmode=warn/skip) | `failmode`, `action` |
| `WORKFLOW_ABORTED` | Step raised (failmode=abort) | `reason` |
| `PROCESSING_FAILED` | Per-file error | `path`, `error` |
| `COMMAND_TIMEOUT` | Exec timeout | `timeout_s`, `command` |
| `COMMAND_EXIT` | Exec finished (DEBUG) | `code`, `command` |
| `COMMAND_FAILED` | Exec exception | `error`, `command` |
| `FILE_REVEALED` | Right-click → Reveal | `path`, `status`, `error` |
| `EXTERNAL_OPENED` | Right-click → Open folder / Open terminal | `kind`, `path`, `status`, `reason`, `error` |
| `FILTER_CHANGED` | Right-click → Filter applied | `kind`, `value` |
| `FILTER_REJECTED` | Right-click → Filter pre-check failed | `kind`, `reason`, `value` |
| `HASH_COMPUTED` | Right-click → Hash computed | `algorithm`, `path`, `status`, `duration_ms`, `error`, `reason` |
| `HASH_VERIFIED` | Right-click → Hash verified against clipboard | `algorithm`, `path`, `match`, `status`, `reason`, `error` |

## Examples

```
2026-08-29 13:01:15 - INFO  - MACBOOKFA.LOCAL: APP_STARTED version="2026.8.0" headless=false
2026-08-29 13:01:15 - DEBUG - MACBOOKFA.LOCAL: SCAN_COMPLETE dir="base" ext="*" filter="" files=284 recursive=true
2026-08-29 13:01:15 - DEBUG - MACBOOKFA.LOCAL: SCAN_METRICS dir="base" duration_ms=25.657 rate=11082.31 errors=0
2026-08-29 13:01:22 - INFO  - MACBOOKFA.LOCAL: THEME_SWITCHED value=dark warnings=2
2026-08-29 13:01:22 - WARNING - MACBOOKFA.LOCAL: WCAG_CONTRAST_FAINT pair="border/surface" ratio=4.22 fg=#7A7680 bg=#121212
2026-08-29 13:01:30 - INFO  - MACBOOKFA.LOCAL: FILE_LAUNCHED path="/Users/falbany/.../README.md" version="2026.8.0" user="falbany" args="-"
2026-08-29 13:01:51 - INFO  - MACBOOKFA.LOCAL: APP_CLOSED uptime_s=36
```

## Useful Grep Examples

**All failed scans:**
```bash
grep 'SCAN_FAILED' profiles.log
```

**Themes that produced contrast warnings:**
```bash
grep 'THEME_SWITCHED.*warnings=[1-9]' profiles.log
```

**Largest scans by file count:**
```bash
grep 'SCAN_COMPLETE' profiles.log | awk -F'files=' '{print $2 " " $0}' | sort -nr | head
```

**Slowest scans (DEBUG only):**
```bash
grep 'SCAN_METRICS' profiles.log | awk -F'duration_ms=' '{print $2}' | sort -nr | head
```

**Audit trail (who launched what):**
```bash
grep 'FILE_LAUNCHED' profiles.log
```

**All right-click filter changes:**
```bash
grep 'FILTER_CHANGED' profiles.log
```

**All hash verifications that mismatched (WARNING):**
```bash
grep 'HASH_VERIFIED.*match=false' profiles.log
```

**All right-click reveal/launch failures:**
```bash
grep -E '(FILE_REVEALED.*status="failed"|FILE_LAUNCH_FAILED)' profiles.log
```

## See Also

- `docs/superpowers/specs/2026-08-29-log-format-and-telemetry-design.md` — full spec
- `docs/superpowers/specs/2026-08-29-context-menu-telemetry-design.md` — context menu events
- `src/profiles/core/telemetry/events.py` — event helper source of truth
- `tests/core/telemetry/test_events.py` — one test per event
