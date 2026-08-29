# Context Menu Telemetry Design

Date: 2026-08-29
Status: Draft (pending user review)
Scope: `src/profiles/gui/context_menu.py` + 7 new event helpers in `src/profiles/core/telemetry/events.py`

## Problem

`context_menu.py` has 9 right-click actions. Logging is inconsistent:

- 3 actions log nothing (launch success, launch-with-args, open-folder, properties, copy actions, hash compute, hash verify)
- 6 actions log via legacy `self.window._logger.info` / `.error` with free-text messages:
  - `Reveal failed: %s` (line 277)
  - `Filtered list to folder: %s` (line 341)
  - `Filtered list by extension: %s` (line 386)
  - `Open terminal failed: %s` (line 432)
  - `File deleted: %s` (line 455)
  - `Failed to delete file %s: %s` (line 462)

Consequences:
1. **Inconsistent audit trail** — launching a file is invisible, but filtering is logged. A support engineer reading the log cannot reconstruct what the user did.
2. **Legacy format** — the 6 existing log lines don't follow the new `key=value` grammar from the log format spec.
3. **No pre-check context** — messagebox warnings ("File Not Found", "No Extension", "Clipboard is empty") leave no trace, so it's impossible to correlate a user complaint with what they tried.

## Goals

1. Every right-click action emits at least one event (success, failure, or rejection).
2. State-changing actions at INFO, read-only actions at DEBUG.
3. Pre-check failures (file not found, no extension, empty clipboard, user cancelled) at DEBUG.
4. Reuse existing events where possible (`FILE_LAUNCHED`, `FILE_DELETED`, `FILE_DELETE_FAILED`).
5. New events follow the same grammar as the existing catalogue.

## Non-goals

- Logging menu browsing / hover events (too noisy).
- Logging the 5 copy actions separately (collapse to no event; users don't need a copy audit trail in 99% of cases).
- Refactoring menu construction or the `_make_menu` helper.
- Changing the i18n strings or menu labels.

## Target Log Behaviour

| Action | Pre-check | Outcome | Event | Level |
|---|---|---|---|---|
| `action_launch` | — | success | `FILE_LAUNCHED` *(existing)* | INFO |
| `action_launch` | — | not_found | none (legacy `actions.launch_selected_file` emits the warning box only) | — |
| `action_launch_with_args` | — | success | `FILE_LAUNCHED` *(existing, via nested call)* | INFO |
| `action_reveal` | — | success | `FILE_REVEALED` *(new)* | DEBUG |
| `action_reveal` | — | failed | `FILE_REVEALED` *(new, `status=failed`)* | DEBUG |
| `action_open_folder` | folder not found | pre-check | `FOLDER_OPENED` *(new, `status=rejected`)* | DEBUG |
| `action_open_folder` | — | success | `FOLDER_OPENED` *(new, `status=ok`)* | DEBUG |
| `action_open_folder` | — | failed | `FOLDER_OPENED` *(new, `status=failed`)* | DEBUG |
| `action_open_terminal` | — | success | `TERMINAL_OPENED` *(new, `status=ok`)* | DEBUG |
| `action_open_terminal` | — | not_found | `TERMINAL_OPENED` *(new, `status=rejected`)* | DEBUG |
| `action_open_terminal` | — | failed | `TERMINAL_OPENED` *(new, `status=failed`)* | DEBUG |
| `action_filter_to_folder` | already in folder | pre-check | `FILTER_REJECTED` *(new, `kind=folder, reason=already_active`)* | DEBUG |
| `action_filter_to_folder` | folder not found | pre-check | `FILTER_REJECTED` *(new, `kind=folder, reason=not_found`)* | DEBUG |
| `action_filter_to_folder` | — | applied | `FILTER_CHANGED` *(new, `kind=folder`)* | INFO |
| `action_filter_by_extension` | no extension | pre-check | `FILTER_REJECTED` *(new, `kind=extension, reason=no_extension`)* | DEBUG |
| `action_filter_by_extension` | — | applied | `FILTER_CHANGED` *(new, `kind=extension`)* | INFO |
| `action_properties` | file not found | pre-check | none (read-only, low-signal) | — |
| `action_properties` | — | success | none (read-only, low-signal) | — |
| `action_copy*` (5 variants) | — | — | none (high-frequency, low-signal) | — |
| `action_hash` | file not found | pre-check | `HASH_COMPUTED` *(new, `status=rejected`)* | DEBUG |
| `action_hash` | hash raises | failure | `HASH_COMPUTED` *(new, `status=failed`)* | DEBUG |
| `action_hash` | — | success | `HASH_COMPUTED` *(new, `status=ok`)* | INFO |
| `action_verify_hash` | file not found | pre-check | `HASH_VERIFIED` *(new, `status=rejected`)* | DEBUG |
| `action_verify_hash` | empty clipboard | pre-check | `HASH_VERIFIED` *(new, `status=rejected`)* | DEBUG |
| `action_verify_hash` | hash raises | failure | `HASH_VERIFIED` *(new, `status=failed`)* | DEBUG |
| `action_verify_hash` | — | match | `HASH_VERIFIED` *(new, `match=true`)* | INFO |
| `action_verify_hash` | — | mismatch | `HASH_VERIFIED` *(new, `match=false`)* | WARNING |
| `action_clear_file` | file not found | pre-check | `FILE_DELETED` *(existing, `status=rejected`)* | DEBUG |
| `action_clear_file` | user said no | pre-check | `FILE_DELETED` *(existing, `status=cancelled`)* | DEBUG |
| `action_clear_file` | — | success | `FILE_DELETED` *(existing)* | INFO |
| `action_clear_file` | — | failed | `FILE_DELETE_FAILED` *(existing)* | ERROR |

Notes on `FILE_DELETED` extension: the existing event has no `status` field. To avoid a backwards-incompatible field, we keep the success case as a plain `FILE_DELETED path=…` and the rejected cases emit nothing (pre-check at the call site, the messagebox already explains the cancellation to the user). This drops the `FILE_DELETED` row above from 4 cases to 1 — the spec simplifies to: success uses existing event, everything else is silent.

## New Events (7)

All follow the grammar: `<event> key=value …`

### `FILE_REVEALED`

Emitted by `action_reveal`. Replaces legacy `Reveal failed: %s`.

```
FILE_REVEALED path=/abs/path status=ok
FILE_REVEALED path=/abs/path status=failed error="..."
```

Fields:
- `path` (string, quoted if spaces)
- `status` (one of: `ok`, `failed`)
- `error` (string, optional, only when `status=failed`)

Level: DEBUG.

### `FOLDER_OPENED`

Emitted by `action_open_folder`. Replaces silent behaviour.

```
FOLDER_OPENED path=/abs/parent status=ok
FOLDER_OPENED path=/abs/parent status=rejected reason=not_found
FOLDER_OPENED path=/abs/parent status=failed error="..."
```

Fields:
- `path` (string) — the folder path, not the file path
- `status` (one of: `ok`, `rejected`, `failed`)
- `reason` (string, optional, only when `status=rejected`)
- `error` (string, optional, only when `status=failed`)

Level: DEBUG.

### `TERMINAL_OPENED`

Emitted by `action_open_terminal`. Replaces legacy `Open terminal failed: %s`.

```
TERMINAL_OPENED path=/abs/parent status=ok
TERMINAL_OPENED path=/abs/parent status=rejected
TERMINAL_OPENED path=/abs/parent status=failed error="..."
```

Fields: same as `FOLDER_OPENED`.

Level: DEBUG.

### `FILTER_CHANGED`

Emitted by `action_filter_to_folder` and `action_filter_by_extension`. Replaces
legacy `Filtered list to folder: %s` and `Filtered list by extension: %s`.

```
FILTER_CHANGED kind=folder value=/abs/parent
FILTER_CHANGED kind=extension value=.mttl
```

Fields:
- `kind` (one of: `folder`, `extension`)
- `value` (string)

Level: INFO.

### `FILTER_REJECTED`

Emitted on pre-check failure for filter actions.

```
FILTER_REJECTED kind=folder reason=already_active value=/abs/parent
FILTER_REJECTED kind=folder reason=not_found value=/abs/parent
FILTER_REJECTED kind=extension reason=no_extension value=filename
```

Fields:
- `kind` (one of: `folder`, `extension`)
- `reason` (one of: `already_active`, `not_found`, `no_extension`)
- `value` (string)

Level: DEBUG.

### `HASH_COMPUTED`

Emitted by `action_hash`.

```
HASH_COMPUTED algorithm=md5 path=/abs/file status=ok duration_ms=12
HASH_COMPUTED algorithm=sha256 path=/abs/file status=failed error="..."
HASH_COMPUTED algorithm=md5 path=/abs/file status=rejected reason=not_found
```

Fields:
- `algorithm` (one of: `md5`, `sha256`)
- `path` (string)
- `status` (one of: `ok`, `failed`, `rejected`)
- `duration_ms` (float, only when `status=ok`)
- `error` (string, only when `status=failed`)
- `reason` (string, only when `status=rejected`)

Level: INFO on success, DEBUG otherwise.

### `HASH_VERIFIED`

Emitted by `action_verify_hash`.

```
HASH_VERIFIED algorithm=md5 path=/abs/file match=true
HASH_VERIFIED algorithm=sha256 path=/abs/file match=false
HASH_VERIFIED algorithm=md5 path=/abs/file status=rejected reason=empty_clipboard
HASH_VERIFIED algorithm=md5 path=/abs/file status=rejected reason=not_found
HASH_VERIFIED algorithm=md5 path=/abs/file status=failed error="..."
```

Fields:
- `algorithm`
- `path`
- `match` (only when status is implicit success — `true` or `false`)
- `status` (only on rejection/failure — `rejected` or `failed`)
- `reason` (only when `status=rejected`)
- `error` (only when `status=failed`)

Level: INFO on `match=true`, WARNING on `match=false`, DEBUG on rejection/failure.

## Wire Format Examples

```
2026-08-29 22:00:01 - DEBUG - MACBOOKFA.LOCAL: FILE_REVEALED path=/Users/test/README.md status=ok
2026-08-29 22:00:02 - DEBUG - MACBOOKFA.LOCAL: FOLDER_OPENED path=/Users/test status=ok
2026-08-29 22:00:05 - INFO  - MACBOOKFA.LOCAL: FILTER_CHANGED kind=folder value=/Users/test
2026-08-29 22:00:08 - DEBUG - MACBOOKFA.LOCAL: FILTER_REJECTED kind=extension reason=no_extension value=".gitignore"
2026-08-29 22:00:11 - INFO  - MACBOOKFA.LOCAL: HASH_COMPUTED algorithm=sha256 path=/Users/test/big.iso duration_ms=1823
2026-08-29 22:00:14 - WARNING - MACBOOKFA.LOCAL: HASH_VERIFIED algorithm=md5 path=/Users/test/file.zip match=false
2026-08-29 22:00:17 - INFO  - MACBOOKFA.LOCAL: FILE_DELETED path=/Users/test/old.log
```

## Architecture

### Module: `core/telemetry/events.py` — 7 new helpers

Add to the existing module. Pattern mirrors existing helpers:

```python
def file_revealed(
    logger: logging.Logger, *, path: str, status: str, error: str = ""
) -> None:
    if error:
        logger.debug('FILE_REVEALED path=%s status="%s" error="%s"', _quote(path), status, error)
    else:
        logger.debug('FILE_REVEALED path=%s status="%s"', _quote(path), status)


def folder_opened(
    logger: logging.Logger, *, path: str, status: str, reason: str = "", error: str = ""
) -> None:
    parts = [f'path={_quote(path)}', f'status="{status}"']
    if reason:
        parts.append(f'reason="{reason}"')
    if error:
        parts.append(f'error="{error}"')
    logger.debug("FOLDER_OPENED %s", " ".join(parts))


def terminal_opened(
    logger: logging.Logger, *, path: str, status: str, reason: str = "", error: str = ""
) -> None:
    # same shape as folder_opened
    ...


def filter_changed(
    logger: logging.Logger, *, kind: str, value: str
) -> None:
    logger.info('FILTER_CHANGED kind="%s" value=%s', kind, _quote(value))


def filter_rejected(
    logger: logging.Logger, *, kind: str, reason: str, value: str
) -> None:
    logger.debug('FILTER_REJECTED kind="%s" reason="%s" value=%s', kind, reason, _quote(value))


def hash_computed(
    logger: logging.Logger, *,
    algorithm: str, path: str, status: str,
    duration_ms: float = 0.0, reason: str = "", error: str = ""
) -> None:
    if status == "ok":
        logger.info(
            'HASH_COMPUTED algorithm="%s" path=%s status="ok" duration_ms=%.3f',
            algorithm, _quote(path), duration_ms,
        )
    elif status == "failed":
        logger.debug(
            'HASH_COMPUTED algorithm="%s" path=%s status="failed" error="%s"',
            algorithm, _quote(path), error,
        )
    else:  # rejected
        logger.debug(
            'HASH_COMPUTED algorithm="%s" path=%s status="rejected" reason="%s"',
            algorithm, _quote(path), reason,
        )


def hash_verified(
    logger: logging.Logger, *,
    algorithm: str, path: str,
    match: bool | None = None,  # None means pre-check failure
    status: str = "", reason: str = "", error: str = ""
) -> None:
    if match is True:
        logger.info('HASH_VERIFIED algorithm="%s" path=%s match=true', algorithm, _quote(path))
    elif match is False:
        logger.warning('HASH_VERIFIED algorithm="%s" path=%s match=false', algorithm, _quote(path))
    elif status == "failed":
        logger.debug('HASH_VERIFIED algorithm="%s" path=%s status="failed" error="%s"',
                     algorithm, _quote(path), error)
    else:  # rejected
        logger.debug('HASH_VERIFIED algorithm="%s" path=%s status="rejected" reason="%s"',
                     algorithm, _quote(path), reason)
```

Add to `__all__` and to `core/telemetry/__init__.py` re-exports.

### Module: `gui/context_menu.py` — call-site updates

Three changes:

1. **Import** `from profiles.core.telemetry import events` at the top.
2. **Migrate 6 legacy `self.window._logger.*` calls** to the new event helpers.
3. **Add new emissions** to the actions that currently log nothing.

Concrete before/after for each method:

```python
# action_reveal
- self.window._logger.error("Reveal failed: %s", result.message)
+ if result.status is ActionStatus.FAILED:
+     events.file_revealed(
+         self.window._logger, path=str(file_path),
+         status="failed", error=result.message,
+     )
  # Last-resort fallback: open the parent folder.
  open_file_explorer(file_path.parent)
+ events.file_revealed(self.window._logger, path=str(file_path), status="ok")
```

```python
# action_open_folder
  if not parent.is_dir():
+     events.folder_opened(
+         self.window._logger, path=str(parent),
+         status="rejected", reason="not_found",
+     )
      messagebox.showwarning(...)
      return
  if not open_file_explorer(parent):
+     events.folder_opened(
+         self.window._logger, path=str(parent),
+         status="failed", error="open_file_explorer returned False",
+     )
      messagebox.showerror(...)
      return
+ events.folder_opened(self.window._logger, path=str(parent), status="ok")
```

```python
# action_open_terminal
  result = open_terminal_in_directory(file_path.parent)
  if result.status is ActionStatus.SUCCESS:
+     events.terminal_opened(
+         self.window._logger, path=str(file_path.parent), status="ok",
+     )
      return
  if result.status is ActionStatus.NOT_FOUND:
+     events.terminal_opened(
+         self.window._logger, path=str(file_path.parent), status="rejected",
+     )
      messagebox.showwarning(...)
      return
- self.window._logger.error("Open terminal failed: %s", result.message)
+ events.terminal_opened(
+     self.window._logger, path=str(file_path.parent),
+     status="failed", error=result.message,
+ )
  messagebox.showerror(...)
```

```python
# action_filter_to_folder
  if current is not None and parent == current:
+     events.filter_rejected(
+         self.window._logger, kind="folder",
+         reason="already_active", value=str(parent),
+     )
      return
  if not parent.is_dir():
+     events.filter_rejected(
+         self.window._logger, kind="folder",
+         reason="not_found", value=str(parent),
+     )
      messagebox.showwarning(...)
      return
  self.window._dir_var.set(str(parent))
  self.window._apply_config_overrides()
  self.window._refresh_file_list()
- self.window._logger.info("Filtered list to folder: %s", parent)
+ events.filter_changed(
+     self.window._logger, kind="folder", value=str(parent),
+ )
```

```python
# action_filter_by_extension
  ext = file_path.suffix
  if not ext:
+     events.filter_rejected(
+         self.window._logger, kind="extension",
+         reason="no_extension", value=file_path.name,
+     )
      messagebox.showwarning(...)
      return
  self.window._ext_var.set(ext)
  self.window._refresh_file_list()
- self.window._logger.info("Filtered list by extension: %s", ext)
+ events.filter_changed(
+     self.window._logger, kind="extension", value=ext,
+ )
```

```python
# action_hash (replaces silent behaviour)
  if not file_path.exists():
+     events.hash_computed(
+         self.window._logger, algorithm=algorithm,
+         path=str(file_path), status="rejected", reason="not_found",
+     )
      messagebox.showwarning(...)
      return
+ start = time.perf_counter()
  try:
      digest = hash_file(file_path, algorithm)
  except (OSError, ValueError) as exc:
+     events.hash_computed(
+         self.window._logger, algorithm=algorithm,
+         path=str(file_path), status="failed", error=str(exc),
+     )
      messagebox.showerror(...)
      return
+ duration_ms = (time.perf_counter() - start) * 1000
+ events.hash_computed(
+     self.window._logger, algorithm=algorithm,
+     path=str(file_path), status="ok", duration_ms=duration_ms,
+ )
```

```python
# action_verify_hash (replaces silent behaviour)
  if not file_path.exists():
+     events.hash_verified(
+         self.window._logger, algorithm=algorithm,
+         path=str(file_path), status="rejected", reason="not_found",
+     )
      ...
  try:
      expected_clip = self.window._root.clipboard_get().strip()
  except tk.TclError:
      expected_clip = ""
  if not expected_clip:
+     events.hash_verified(
+         self.window._logger, algorithm=algorithm,
+         path=str(file_path), status="rejected", reason="empty_clipboard",
+     )
      ...
  try:
      digest = hash_file(file_path, algorithm)
  except (OSError, ValueError) as exc:
+     events.hash_verified(
+         self.window._logger, algorithm=algorithm,
+         path=str(file_path), status="failed", error=str(exc),
+     )
      ...
- match = digest.casefold() == expected_clip.casefold()
- if match: ...
- else: ...
+ match = digest.casefold() == expected_clip.casefold()
+ events.hash_verified(
+     self.window._logger, algorithm=algorithm,
+     path=str(file_path), match=match,
+ )
```

```python
# action_clear_file (pre-checks stay silent; user said "yes" → existing event)
  # Existing: self.window._logger.info("File deleted: %s", file_path)
  # Existing: self.window._logger.error("Failed to delete file %s: %s", ...)
  # Replace with existing event helpers; no new logic.
- self.window._logger.info("File deleted: %s", file_path)
+ events.file_deleted(self.window._logger, path=str(file_path))
- self.window._logger.error("Failed to delete file %s: %s", file_path, exc)
+ events.file_delete_failed(self.window._logger, path=str(file_path), error=str(exc))
```

```python
# action_launch (no change — actions.launch_selected_file already emits
# FILE_LAUNCHED on success. Failures are silent in the menu (messagebox only).
# Leave as-is.)
```

## Testing Strategy

### `tests/core/telemetry/test_events.py`

Add one test class per new helper (7 classes, ~14 tests total — each helper has
the success path and at least one failure/reject path). Follow the same
pattern as the existing tests in the file (assertion against `caplog.text`).

Example:
```python
class TestFileRevealed:
    def test_ok(self, caplog):
        file_revealed(logger, path="/a.txt", status="ok")
        assert 'FILE_REVEALED path=/a.txt status="ok"' in caplog.text

    def test_failed(self, caplog):
        file_revealed(logger, path="/a.txt", status="failed", error="denied")
        assert 'FILE_REVEALED path=/a.txt status="failed" error="denied"' in caplog.text
```

### `tests/gui/test_context_menu.py`

Add smoke tests that drive each action through the menu's code path and assert
the event was emitted. Use a minimal MainWindow mock. The existing test
infrastructure (if any) in `tests/gui/` should be reused; otherwise use
`unittest.mock.MagicMock`.

```python
def test_filter_to_folder_emits_filter_changed(self):
    main_window = _make_mock_window()
    FileContextMenu(main_window).action_filter_to_folder(Path("/some/dir"))
    events = [r for r in caplog.records if "FILTER_" in r.message]
    assert any("FILTER_CHANGED" in r.message for r in events)
```

## Documentation

Update `docs/operations/log-format.md` — add the 7 new events to the catalogue table
with their fields and example log lines.

## Rollout

1. Add 7 helpers to `events.py` + 7 test classes to `test_events.py`. Land as one PR.
2. Migrate `context_menu.py` — 9 actions updated, ~50 lines of code. Land as a second PR.
3. Update `docs/operations/log-format.md`. Land as a third PR (docs only).
4. Bump `pyproject.toml` to `2026.8.1` to mark the catalogue extension.

## Out of Scope (explicit)

- Logging `action_properties` (read-only, low-signal)
- Logging `action_copy*` (5 variants) — high-frequency, low-signal
- Logging the 5 pre-check messagebox warnings in `action_clear_file` (user said "no", not an event)
- New i18n strings for log messages (logs stay English; the user-facing messageboxes are already i18n'd)
- Refactoring the menu construction loop
- Performance impact — 7 helper calls per right-click is negligible (<10 µs total)
