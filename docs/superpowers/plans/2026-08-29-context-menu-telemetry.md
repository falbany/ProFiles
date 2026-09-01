# Context Menu Telemetry — Implementation Plan

> **For Engineer**: Execute this plan task by task using TDD. All code, commands, and paths are explicitly provided. Start each task with the existing tests passing, end each task with them passing again.

---

## 🎯 Overview

Add 6 new event helpers to `core/telemetry/events.py` and migrate all 9 right-click
actions in `gui/context_menu.py` to emit them. The launch failure path gains a new
emission (the existing `FILE_LAUNCH_FAILED` event).

**New wire format examples** (one per new event):
```
DEBUG FILE_REVEALED path=/Users/test/README.md status=ok
DEBUG EXTERNAL_OPENED kind=folder path=/Users/test status=ok
INFO  FILTER_CHANGED kind=folder value=/Users/test
DEBUG FILTER_REJECTED kind=extension reason=no_extension value=".gitignore"
INFO  HASH_COMPUTED algorithm=sha256 path=/Users/test/big.iso duration_ms=1823
WARN  HASH_VERIFIED algorithm=md5 path=/Users/test/file.zip match=false
ERROR FILE_LAUNCH_FAILED path=/Users/test/old.mttl error="not found"
```

---

## 📁 File Map

```
src/profiles/core/telemetry/
├── events.py          MOD  — add 6 new helpers + re-export
└── __init__.py        MOD  — add 6 new symbols to __all__

src/profiles/gui/
└── context_menu.py    MOD  — 9 actions migrated to events

tests/
├── core/telemetry/
│   └── test_events.py            MOD  — 6 new test classes (~12 tests)
└── gui/
    └── test_context_menu.py      MOD  — smoke tests for each action (new file)

docs/operations/
└── log-format.md       MOD  — add 6 new events to catalogue
```

---

## Phase 1 — Infrastructure (events.py + tests)

### Task 1: Add 6 new event helpers to `core/telemetry/events.py`

**File**: `src/profiles/core/telemetry/events.py`

Add these 6 helpers at the end of the module, before the existing closing
comments. Follow the exact pattern of existing helpers (use `_quote`, only emit
conditional fields when provided).

```python
# ---------------------------------------------------------------------------
# Context menu — right-click actions
# ---------------------------------------------------------------------------


def file_revealed(logger: logging.Logger, *, path: str, status: str, error: str = "") -> None:
    """Emit FILE_REVEALED. status is "ok" or "failed"."""
    if error:
        logger.debug(
            'FILE_REVEALED path=%s status="%s" error="%s"',
            _quote(path),
            status,
            error,
        )
    else:
        logger.debug('FILE_REVEALED path=%s status="%s"', _quote(path), status)


def external_opened(
    logger: logging.Logger, *, kind: str, path: str, status: str, reason: str = "", error: str = ""
) -> None:
    """Emit EXTERNAL_OPENED. kind is "folder" or "terminal"."""
    parts = [f'kind="{kind}"', f"path={_quote(path)}", f'status="{status}"']
    if reason:
        parts.append(f'reason="{reason}"')
    if error:
        parts.append(f'error="{error}"')
    logger.debug("EXTERNAL_OPENED %s", " ".join(parts))


def filter_changed(logger: logging.Logger, *, kind: str, value: str) -> None:
    """Emit FILTER_CHANGED. kind is "folder" or "extension"."""
    logger.info('FILTER_CHANGED kind="%s" value=%s', kind, _quote(value))


def filter_rejected(logger: logging.Logger, *, kind: str, reason: str, value: str) -> None:
    """Emit FILTER_REJECTED. reason describes why the filter was not applied."""
    logger.debug(
        'FILTER_REJECTED kind="%s" reason="%s" value=%s',
        kind,
        reason,
        _quote(value),
    )


def hash_computed(
    logger: logging.Logger,
    *,
    algorithm: str,
    path: str,
    status: str,
    duration_ms: float = 0.0,
    reason: str = "",
    error: str = "",
) -> None:
    """Emit HASH_COMPUTED. status is "ok", "failed", or "rejected"."""
    if status == "ok":
        logger.info(
            'HASH_COMPUTED algorithm="%s" path=%s status="ok" duration_ms=%.3f',
            algorithm,
            _quote(path),
            duration_ms,
        )
    elif status == "failed":
        logger.debug(
            'HASH_COMPUTED algorithm="%s" path=%s status="failed" error="%s"',
            algorithm,
            _quote(path),
            error,
        )
    else:  # rejected
        logger.debug(
            'HASH_COMPUTED algorithm="%s" path=%s status="rejected" reason="%s"',
            algorithm,
            _quote(path),
            reason,
        )


def hash_verified(
    logger: logging.Logger,
    *,
    algorithm: str,
    path: str,
    match: bool | None = None,
    status: str = "",
    reason: str = "",
    error: str = "",
) -> None:
    """Emit HASH_VERIFIED. match is True/False for verification outcomes;
    pass status="rejected" or status="failed" with reason/error for pre-checks."""
    if match is True:
        logger.info(
            'HASH_VERIFIED algorithm="%s" path=%s match=true',
            algorithm,
            _quote(path),
        )
    elif match is False:
        logger.warning(
            'HASH_VERIFIED algorithm="%s" path=%s match=false',
            algorithm,
            _quote(path),
        )
    elif status == "failed":
        logger.debug(
            'HASH_VERIFIED algorithm="%s" path=%s status="failed" error="%s"',
            algorithm,
            _quote(path),
            error,
        )
    else:  # rejected
        logger.debug(
            'HASH_VERIFIED algorithm="%s" path=%s status="rejected" reason="%s"',
            algorithm,
            _quote(path),
            reason,
        )
```

**Verify**: `python3 -c "from profiles.core.telemetry import events; assert all(hasattr(events, n) for n in ['file_revealed', 'external_opened', 'filter_changed', 'filter_rejected', 'hash_computed', 'hash_verified'])"`

---

### Task 2: Update `core/telemetry/__init__.py` re-exports

**File**: `src/profiles/core/telemetry/__init__.py`

Add the 6 new symbols to the import block and `__all__`.

```python
from profiles.core.telemetry.events import (
    # ...existing...
    external_opened,
    file_revealed,
    filter_changed,
    filter_rejected,
    hash_computed,
    hash_verified,
)

__all__ = [
    # ...existing...
    "external_opened",
    "file_revealed",
    "filter_changed",
    "filter_rejected",
    "hash_computed",
    "hash_verified",
]
```

**Verify**: `python3 -c "from profiles.core.telemetry import file_revealed, external_opened, filter_changed, filter_rejected, hash_computed, hash_verified; print('OK')"`

---

### Task 3: Add tests for the 6 new helpers

**File**: `tests/core/telemetry/test_events.py`

Add 6 new test classes (one per helper) at the end of the file. Follow the
existing test style (assert against `caplog.text`).

```python
# Add to the import block at the top of the file:
from profiles.core.telemetry.events import (
    # ...existing...
    external_opened,
    file_revealed,
    filter_changed,
    filter_rejected,
    hash_computed,
    hash_verified,
)


# Add new test classes at the end of the file:


class TestFileRevealed:
    def test_ok(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_file_revealed_ok")
        file_revealed(logger, path="/a.txt", status="ok")
        assert 'FILE_REVEALED path=/a.txt status="ok"' in caplog.text

    def test_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_file_revealed_failed")
        file_revealed(logger, path="/a.txt", status="failed", error="denied")
        assert 'FILE_REVEALED path=/a.txt status="failed" error="denied"' in caplog.text


class TestExternalOpened:
    def test_folder_ok(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_external_folder_ok")
        external_opened(logger, kind="folder", path="/abs/parent", status="ok")
        assert 'EXTERNAL_OPENED kind="folder" path=/abs/parent status="ok"' in caplog.text

    def test_terminal_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_external_terminal_failed")
        external_opened(
            logger,
            kind="terminal",
            path="/abs/parent",
            status="failed",
            error="no shell",
        )
        assert (
            'EXTERNAL_OPENED kind="terminal" path=/abs/parent status="failed" error="no shell"'
            in caplog.text
        )

    def test_rejected_with_reason(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_external_rejected")
        external_opened(
            logger,
            kind="folder",
            path="/abs/parent",
            status="rejected",
            reason="not_found",
        )
        assert (
            'EXTERNAL_OPENED kind="folder" path=/abs/parent status="rejected" reason="not_found"'
            in caplog.text
        )


class TestFilterChanged:
    def test_folder(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_filter_folder")
        filter_changed(logger, kind="folder", value="/abs/dir")
        assert 'FILTER_CHANGED kind="folder" value=/abs/dir' in caplog.text

    def test_extension(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_filter_extension")
        filter_changed(logger, kind="extension", value=".mttl")
        assert 'FILTER_CHANGED kind="extension" value=.mttl' in caplog.text


class TestFilterRejected:
    def test_already_active(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_filter_rej_already")
        filter_rejected(
            logger,
            kind="folder",
            reason="already_active",
            value="/abs/dir",
        )
        assert 'FILTER_REJECTED kind="folder" reason="already_active" value=/abs/dir' in caplog.text

    def test_no_extension(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_filter_rej_ext")
        filter_rejected(
            logger,
            kind="extension",
            reason="no_extension",
            value=".gitignore",
        )
        assert (
            'FILTER_REJECTED kind="extension" reason="no_extension" value=.gitignore' in caplog.text
        )


class TestHashComputed:
    def test_ok_with_duration(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_hash_ok")
        hash_computed(
            logger,
            algorithm="sha256",
            path="/a.bin",
            status="ok",
            duration_ms=12.5,
        )
        assert (
            'HASH_COMPUTED algorithm="sha256" path=/a.bin status="ok" duration_ms=12.500'
            in caplog.text
        )

    def test_failed(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_hash_failed")
        hash_computed(
            logger,
            algorithm="md5",
            path="/a.bin",
            status="failed",
            error="permission denied",
        )
        assert (
            'HASH_COMPUTED algorithm="md5" path=/a.bin status="failed" error="permission denied"'
            in caplog.text
        )

    def test_rejected(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_hash_rejected")
        hash_computed(
            logger,
            algorithm="md5",
            path="/a.bin",
            status="rejected",
            reason="not_found",
        )
        assert (
            'HASH_COMPUTED algorithm="md5" path=/a.bin status="rejected" reason="not_found"'
            in caplog.text
        )


class TestHashVerified:
    def test_match_true(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_verify_match")
        hash_verified(logger, algorithm="md5", path="/a.zip", match=True)
        assert 'HASH_VERIFIED algorithm="md5" path=/a.zip match=true' in caplog.text

    def test_match_false(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_verify_mismatch")
        hash_verified(logger, algorithm="sha256", path="/a.zip", match=False)
        assert 'HASH_VERIFIED algorithm="sha256" path=/a.zip match=false' in caplog.text

    def test_rejected_empty_clipboard(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = logging.getLogger("test_verify_rejected")
        hash_verified(
            logger,
            algorithm="md5",
            path="/a.zip",
            status="rejected",
            reason="empty_clipboard",
        )
        assert (
            'HASH_VERIFIED algorithm="md5" path=/a.zip status="rejected" reason="empty_clipboard"'
            in caplog.text
        )
```

**Run**: `python3 -m pytest tests/core/telemetry/test_events.py -v --no-cov 2>&1 | tail -25`

Expected: 12 new tests pass on top of the existing 45.

---

### Phase 1 commit

```bash
git add src/profiles/core/telemetry/ tests/core/telemetry/test_events.py
git -c user.email=falbany@local -c user.name=falbany commit -m "feat(telemetry): 6 new context-menu event helpers

FILE_REVEALED, EXTERNAL_OPENED, FILTER_CHANGED, FILTER_REJECTED,
HASH_COMPUTED, HASH_VERIFIED — all with TDD coverage (12 new tests)."
```

---

## Phase 2 — context_menu.py migration

### Task 4: Add import to context_menu.py

**File**: `src/profiles/gui/context_menu.py`

Add the events import alongside the existing imports:

```python
from profiles.core import actions
from profiles.core.actions import (
    ActionStatus,
    open_terminal_in_directory,
    reveal_in_file_manager,
)
from profiles.core.processing.file_classifier import ensure_trailing_separator
from profiles.core.processing.file_metadata import get_file_metadata
from profiles.core.telemetry import events  # NEW
from profiles.gui.i18n import t
```

Add `import time` to the standard library block:

```python
import time
import tkinter as tk
```

---

### Task 5: Migrate `action_reveal`

**File**: `src/profiles/gui/context_menu.py`

Replace the body of `action_reveal` to emit `FILE_REVEALED` on both paths.

```python
def action_reveal(self, file_path: Path) -> None:
    """Reveal the file in the OS file explorer."""
    result = reveal_in_file_manager(file_path)
    if result.status is ActionStatus.NOT_FOUND:
        events.file_revealed(
            self.window._logger,
            path=str(file_path),
            status="failed",
            error=result.message,
        )
        messagebox.showwarning("File Not Found", result.message)
        return
    if result.status is ActionStatus.FAILED:
        events.file_revealed(
            self.window._logger,
            path=str(file_path),
            status="failed",
            error=result.message,
        )
        # Last-resort fallback: open the parent folder.
        open_file_explorer(file_path.parent)
        return
    events.file_revealed(
        self.window._logger,
        path=str(file_path),
        status="ok",
    )
```

The `NOT_FOUND` path emits `status="failed"` with the error message — same as
the existing `FAILED` path. Both go through the same `failed` status in the
event catalogue.

---

### Task 6: Migrate `action_open_folder`

```python
def action_open_folder(self, file_path: Path) -> None:
    """Open the directory that contains *file_path*."""
    parent = file_path.parent
    if not parent.is_dir():
        events.external_opened(
            self.window._logger,
            kind="folder",
            path=str(parent),
            status="rejected",
            reason="not_found",
        )
        messagebox.showwarning(
            "Folder Not Found",
            f"The folder does not exist:\n{parent}",
        )
        return
    if not open_file_explorer(parent):
        events.external_opened(
            self.window._logger,
            kind="folder",
            path=str(parent),
            status="failed",
            error="open_file_explorer returned False",
        )
        messagebox.showerror(
            "Open Folder Error",
            f"Failed to open folder:\n{parent}",
        )
        return
    events.external_opened(
        self.window._logger,
        kind="folder",
        path=str(parent),
        status="ok",
    )
```

---

### Task 7: Migrate `action_open_terminal`

```python
def action_open_terminal(self, file_path: Path) -> None:
    """Open a terminal session in the file's parent directory."""
    result = open_terminal_in_directory(file_path.parent)
    if result.status is ActionStatus.SUCCESS:
        events.external_opened(
            self.window._logger,
            kind="terminal",
            path=str(file_path.parent),
            status="ok",
        )
        return
    if result.status is ActionStatus.NOT_FOUND:
        events.external_opened(
            self.window._logger,
            kind="terminal",
            path=str(file_path.parent),
            status="rejected",
        )
        messagebox.showwarning("Folder Not Found", result.message)
        return
    events.external_opened(
        self.window._logger,
        kind="terminal",
        path=str(file_path.parent),
        status="failed",
        error=result.message,
    )
    messagebox.showerror("Open Terminal Error", result.message)
```

---

### Task 8: Migrate `action_filter_to_folder`

```python
def action_filter_to_folder(self, file_path: Path) -> None:
    """Switch the directory combobox to the file's parent folder."""
    parent = file_path.parent
    current_paths = self.window._dir_manager.resolve(
        self.window._dir_var.get(),
    )
    current = Path(current_paths[0]) if current_paths else None
    if current is not None and parent == current:
        events.filter_rejected(
            self.window._logger,
            kind="folder",
            reason="already_active",
            value=str(parent),
        )
        return
    if not parent.is_dir():
        events.filter_rejected(
            self.window._logger,
            kind="folder",
            reason="not_found",
            value=str(parent),
        )
        messagebox.showwarning(
            "Folder Not Found",
            f"The folder does not exist:\n{parent}",
        )
        return
    self.window._dir_var.set(str(parent))
    self.window._apply_config_overrides()
    self.window._refresh_file_list()
    events.filter_changed(
        self.window._logger,
        kind="folder",
        value=str(parent),
    )
```

---

### Task 9: Migrate `action_filter_by_extension`

```python
def action_filter_by_extension(self, file_path: Path) -> None:
    """Set the extension filter to ``.<ext>`` and re-scan the current folder."""
    ext = file_path.suffix
    if not ext:
        events.filter_rejected(
            self.window._logger,
            kind="extension",
            reason="no_extension",
            value=file_path.name,
        )
        messagebox.showwarning(
            "No Extension",
            f"Selected file has no extension:\n{file_path.name}",
        )
        return
    self.window._ext_var.set(ext)
    self.window._refresh_file_list()
    events.filter_changed(
        self.window._logger,
        kind="extension",
        value=ext,
    )
```

---

### Task 10: Migrate `action_hash` (add timing + event)

```python
def action_hash(self, file_path: Path, algorithm: str, *, copy_only: bool = False) -> None:
    """Compute the file's hash, show a dialog, and optionally copy it."""
    if not file_path.exists():
        events.hash_computed(
            self.window._logger,
            algorithm=algorithm,
            path=str(file_path),
            status="rejected",
            reason="not_found",
        )
        messagebox.showwarning(
            "File Not Found",
            f"The selected file does not exist:\n{file_path}",
        )
        return
    start = time.perf_counter()
    try:
        digest = hash_file(file_path, algorithm)
    except (OSError, ValueError) as exc:
        events.hash_computed(
            self.window._logger,
            algorithm=algorithm,
            path=str(file_path),
            status="failed",
            error=str(exc),
        )
        messagebox.showerror("Hash Error", f"Failed to hash file:\n{exc}")
        return
    duration_ms = (time.perf_counter() - start) * 1000
    events.hash_computed(
        self.window._logger,
        algorithm=algorithm,
        path=str(file_path),
        status="ok",
        duration_ms=duration_ms,
    )

    if copy_only:
        self.action_copy(digest)
        return

    messagebox.showinfo(
        f"{algorithm.upper()} Hash",
        f"File: {file_path.name}\nPath: {file_path}\n\n{algorithm.upper()}: {digest}",
    )
```

---

### Task 11: Migrate `action_verify_hash`

```python
def action_verify_hash(self, file_path: Path, algorithm: str) -> None:
    """Compute the file's *algorithm* hash and compare it to the clipboard."""
    if not file_path.exists():
        events.hash_verified(
            self.window._logger,
            algorithm=algorithm,
            path=str(file_path),
            status="rejected",
            reason="not_found",
        )
        messagebox.showwarning(
            "File Not Found",
            f"The selected file does not exist:\n{file_path}",
        )
        return
    try:
        expected_clip = self.window._root.clipboard_get().strip()
    except tk.TclError:
        expected_clip = ""
    if not expected_clip:
        events.hash_verified(
            self.window._logger,
            algorithm=algorithm,
            path=str(file_path),
            status="rejected",
            reason="empty_clipboard",
        )
        messagebox.showinfo(
            f"Verify {algorithm.upper()}",
            "Clipboard is empty — copy a hash first, then try again.",
        )
        return
    try:
        digest = hash_file(file_path, algorithm)
    except (OSError, ValueError) as exc:
        events.hash_verified(
            self.window._logger,
            algorithm=algorithm,
            path=str(file_path),
            status="failed",
            error=str(exc),
        )
        messagebox.showerror("Hash Error", f"Failed to hash file:\n{exc}")
        return

    match = digest.casefold() == expected_clip.casefold()
    events.hash_verified(
        self.window._logger,
        algorithm=algorithm,
        path=str(file_path),
        match=match,
    )
    if match:
        messagebox.showinfo(
            f"Verify {algorithm.upper()}",
            f"✅ Match!\n\n{algorithm.upper()}: {digest}",
        )
    else:
        messagebox.showerror(
            f"Verify {algorithm.upper()}",
            f"❌ Mismatch\n\nFile: {digest}\nClipboard: {expected_clip}",
        )
```

---

### Task 12: Migrate `action_launch` (add FILE_LAUNCH_FAILED)

```python
def action_launch(self, file_path: Path) -> None:
    """Launch the given file using the OS default association."""
    result = actions.launch_selected_file(
        directory=str(file_path.parent),
        filename=file_path.name,
        release=self.window._config.release,
        username=get_username(),
        logger=self.window._logger,
        config=self.window._config,
    )
    if result.status is ActionStatus.NOT_FOUND:
        events.file_launch_failed(
            self.window._logger,
            path=str(file_path),
            error=result.message,
        )
        messagebox.showwarning(
            "File Not Found",
            f"The selected file does not exist:\n{file_path}",
        )
        return
    if result.status is ActionStatus.SUCCESS:
        if self.window._close_var.get():
            self.window._root.after(500, self.window._on_close)
        return
    events.file_launch_failed(
        self.window._logger,
        path=str(file_path),
        error=result.message,
    )
    messagebox.showerror("Execution Error", result.message)
```

Note: `action_launch_with_args` already routes through `actions.launch_selected_file`
which emits `FILE_LAUNCHED` on success. It does **not** need a direct event
emission in context_menu.py — but **verify** during execution that the nested
`MainWindow._action_launch_with_args` method also emits `FILE_LAUNCH_FAILED`
on its failure paths. If not, add the same emission there. (Test in Task 14.)

---

### Task 13: Migrate `action_clear_file` (replace legacy calls)

```python
def action_clear_file(self, file_path: Path) -> None:
    """Delete the given file from the filesystem."""
    if not file_path.exists():
        messagebox.showwarning(
            "File Not Found",
            f"The selected file does not exist:\n{file_path}",
        )
        return

    # Confirm before deleting
    if not messagebox.askyesno(
        "Delete File",
        f"Are you you want to delete this file?\n\n{file_path}\n\nThis action cannot be undone.",
    ):
        return

    try:
        file_path.unlink()
        events.file_deleted(self.window._logger, path=str(file_path))
        messagebox.showinfo(
            "File Deleted",
            f"File deleted successfully:\n{file_path}",
        )
        self.window._refresh_file_list()
    except OSError as exc:
        events.file_delete_failed(
            self.window._logger,
            path=str(file_path),
            error=str(exc),
        )
        messagebox.showerror(
            "Delete File Error",
            f"Failed to delete file:\n{file_path}\n\n{exc}",
        )
```

Pre-check rejections (file not found, user said no) stay silent — messagebox
explains the cancellation to the user.

---

### Task 14: Verify no leftover `self.window._logger.*` calls in context_menu.py

```bash
grep -n "self.window._logger\." /Users/falbany/Documents/Code/GitHub/ProFiles/src/profiles/gui/context_menu.py
```

Expected: no output (all 6 legacy lines replaced).

If `action_launch_with_args` indirectly calls a path that needs `FILE_LAUNCH_FAILED`:
check `MainWindow._action_launch_with_args` — add the same emission if missing.

---

### Task 15: Add smoke tests for context_menu actions

**File**: `tests/gui/test_context_menu.py` (new file)

```python
"""Smoke tests for FileContextMenu — verify each action emits the right event."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from profiles.core.actions import ActionResult, ActionStatus
from profiles.core.telemetry import events
from profiles.gui.context_menu import FileContextMenu


@pytest.fixture
def mock_window(tmp_path: Path) -> MagicMock:
    """Build a minimal MainWindow mock that the context menu can talk to."""
    root = tk.Tk()
    root.withdraw()  # don't show window during tests
    window = MagicMock()
    window._root = root
    window._logger = logging.getLogger("test_context_menu")
    window._config = MagicMock()
    window._config.release = "2026.8.0"
    window._close_var = MagicMock(get=MagicMock(return_value=False))
    window._dir_var = MagicMock(get=MagicMock(return_value=str(tmp_path)))
    window._dir_manager = MagicMock()
    window._dir_manager.resolve = MagicMock(return_value=[str(tmp_path)])
    window._ext_var = MagicMock(set=MagicMock())
    window._tree = MagicMock()
    window._tree_to_path = {}
    window._theme = MagicMock(
        surface="white", on_surface="black", primary="blue", on_primary="white"
    )
    window._refresh_file_list = MagicMock()
    window._apply_config_overrides = MagicMock()
    window._on_close = MagicMock()
    window._action_launch_with_args = MagicMock()
    yield window
    root.destroy()


def test_action_reveal_success_emits_event(caplog, mock_window, tmp_path):
    """action_reveal emits FILE_REVEALED status=ok on success."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("x")
    mock_window._dir_var.get = MagicMock(return_value=str(tmp_path))
    caplog.set_level(logging.DEBUG, logger="test_context_menu")

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "profiles.gui.context_menu.reveal_in_file_manager",
        return_value=ActionResult(status=ActionStatus.SUCCESS, message="ok"),
    ):
        FileContextMenu(mock_window).action_reveal(file_path)

    assert any("FILE_REVEALED" in r.message and 'status="ok"' in r.message for r in caplog.records)


def test_action_open_folder_success_emits_event(caplog, mock_window, tmp_path):
    """action_open_folder emits EXTERNAL_OPENED kind=folder status=ok on success."""
    subdir = tmp_path / "sub"
    subdir.mkdir()
    file_path = subdir / "test.txt"
    file_path.write_text("x")
    caplog.set_level(logging.DEBUG, logger="test_context_menu")

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "profiles.gui.context_menu.open_file_explorer",
        return_value=True,
    ):
        FileContextMenu(mock_window).action_open_folder(file_path)

    assert any(
        "EXTERNAL_OPENED" in r.message
        and 'kind="folder"' in r.message
        and 'status="ok"' in r.message
        for r in caplog.records
    )


def test_action_filter_to_folder_emits_event(caplog, mock_window, tmp_path):
    """action_filter_to_folder emits FILTER_CHANGED kind=folder on success."""
    target = tmp_path / "other"
    target.mkdir()
    file_path = target / "test.txt"
    file_path.write_text("x")
    # Mock the resolve to return a *different* path so the "already_active"
    # pre-check does not fire.
    mock_window._dir_manager.resolve = MagicMock(return_value=[str(tmp_path / "different")])
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_filter_to_folder(file_path)

    assert any(
        "FILTER_CHANGED" in r.message and 'kind="folder"' in r.message for r in caplog.records
    )


def test_action_filter_by_extension_emits_event(caplog, mock_window, tmp_path):
    """action_filter_by_extension emits FILTER_CHANGED kind=extension on success."""
    file_path = tmp_path / "test.mttl"
    file_path.write_text("x")
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_filter_by_extension(file_path)

    assert any(
        "FILTER_CHANGED" in r.message and 'kind="extension"' in r.message for r in caplog.records
    )


def test_action_hash_success_emits_event(caplog, mock_window, tmp_path):
    """action_hash emits HASH_COMPUTED status=ok with duration_ms on success."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_hash(file_path, "md5")

    assert any(
        "HASH_COMPUTED" in r.message and 'status="ok"' in r.message and "duration_ms=" in r.message
        for r in caplog.records
    )


def test_action_verify_hash_match_emits_event(caplog, mock_window, tmp_path):
    """action_verify_hash emits HASH_VERIFIED match=true on a match."""
    import hashlib

    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")
    expected = hashlib.md5(b"hello world").hexdigest()
    mock_window._root.clipboard_get = MagicMock(return_value=expected)
    caplog.set_level(logging.INFO, logger="test_context_menu")

    FileContextMenu(mock_window).action_verify_hash(file_path, "md5")

    assert any("HASH_VERIFIED" in r.message and "match=true" in r.message for r in caplog.records)
```

**Run**: `python3 -m pytest tests/gui/test_context_menu.py -v --no-cov 2>&1 | tail -15`

---

### Phase 2 commit

```bash
git add src/profiles/gui/context_menu.py tests/gui/test_context_menu.py
git -c user.email=falbany@local -c user.name=falbany commit -m "feat(telemetry): migrate context menu to structured events

All 9 right-click actions now emit events:
- action_reveal → FILE_REVEALED
- action_open_folder / action_open_terminal → EXTERNAL_OPENED
- action_filter_* → FILTER_CHANGED / FILTER_REJECTED
- action_hash → HASH_COMPUTED (with duration_ms)
- action_verify_hash → HASH_VERIFIED
- action_launch failure paths → FILE_LAUNCH_FAILED (new emission)
- action_clear_file → FILE_DELETED / FILE_DELETE_FAILED

6 smoke tests cover the happy paths."
```

---

## Phase 3 — Documentation

### Task 16: Update `docs/operations/log-format.md`

Add the 6 new events to the catalogue table and the example block. Find the
existing table and append:

```markdown
| `FILE_REVEALED` | Right-click → Reveal | `path`, `status`, `error` |
| `EXTERNAL_OPENED` | Right-click → Open folder / Open terminal | `kind`, `path`, `status`, `reason`, `error` |
| `FILTER_CHANGED` | Right-click → Filter to folder/extension | `kind`, `value` |
| `FILTER_REJECTED` | Right-click → Filter pre-check failure | `kind`, `reason`, `value` |
| `HASH_COMPUTED` | Right-click → Compute hash | `algorithm`, `path`, `status`, `duration_ms`, `error`, `reason` |
| `HASH_VERIFIED` | Right-click → Verify hash against clipboard | `algorithm`, `path`, `match`, `status`, `reason`, `error` |
| `FILE_LAUNCH_FAILED` | Right-click → Launch failure (new emission) | `path`, `error` |
```

Add to the example block:

```
2026-08-29 22:00:01 - DEBUG - MACBOOKFA.LOCAL: FILE_REVEALED path=/Users/test/README.md status=ok
2026-08-29 22:00:02 - DEBUG - MACBOOKFA.LOCAL: EXTERNAL_OPENED kind=folder path=/Users/test status=ok
2026-08-29 22:00:05 - INFO  - MACBOOKFA.LOCAL: FILTER_CHANGED kind=folder value=/Users/test
2026-08-29 22:00:08 - DEBUG - MACBOOKFA.LOCAL: FILTER_REJECTED kind=extension reason=no_extension value=".gitignore"
2026-08-29 22:00:11 - INFO  - MACBOOKFA.LOCAL: HASH_COMPUTED algorithm=sha256 path=/Users/test/big.iso duration_ms=1823
2026-08-29 22:00:14 - WARNING - MACBOOKFA.LOCAL: HASH_VERIFIED algorithm=md5 path=/Users/test/file.zip match=false
2026-08-29 22:00:17 - ERROR - MACBOOKFA.LOCAL: FILE_LAUNCH_FAILED path=/Users/test/old.mttl error="not found"
```

Add to the "Useful Grep Examples" section:

```bash
# All right-click filter changes
grep 'FILTER_CHANGED' profiles.log

# All hash verifications that mismatched
grep 'HASH_VERIFIED.*match=false' profiles.log

# All file reveal/launch failures
grep -E '(FILE_REVEALED.*status="failed"|FILE_LAUNCH_FAILED)' profiles.log
```

---

### Task 17: Bump version to `2026.8.1`

**File**: `pyproject.toml`

```toml
version = "2026.8.1"
```

**File**: `tests/test_app.py` (and `tests/core/config/test_models.py` if it asserts the version)

```python
assert profiles.__version__ == "2026.8.1"
```

---

### Task 18: Final verification

```bash
python3 -m pytest tests/ --no-cov -q
python3 -m ruff check src/profiles/
```

Expected: all tests pass, 0 new lint errors.

```bash
# Live smoke: launch ProFiles, right-click a file, verify events appear
rm /Users/falbany/Documents/Code/GitHub/ProFiles/profiles.log
(ProFiles 2>&1 &) >/dev/null 2>&1
sleep 3
pkill -f "ProFiles" 2>/dev/null
sleep 1
grep -E "FILE_REVEALED|EXTERNAL_OPENED|FILTER_|HASH_|FILE_LAUNCH" /Users/falbany/Documents/Code/GitHub/ProFiles/profiles.log
```

(Manual user-driven test; no automated end-to-end test in this plan.)

---

### Phase 3 commit

```bash
git add docs/operations/log-format.md pyproject.toml tests/test_app.py tests/core/config/test_models.py
git -c user.email=falbany@local -c user.name=falbany commit -m "docs(telemetry): context menu events in log-format guide; bump to 2026.8.1

Adds 6 new events to docs/operations/log-format.md (FILE_REVEALED,
EXTERNAL_OPENED, FILTER_CHANGED, FILTER_REJECTED, HASH_COMPUTED,
HASH_VERIFIED, FILE_LAUNCH_FAILED) with examples and grep recipes.
Bumps version to 2026.8.1 to mark the catalogue extension."
```

---

## Test Command Reference

| Phase / Task | Command |
|---|---|
| Task 1-3 | `python3 -m pytest tests/core/telemetry/test_events.py -v --no-cov` |
| After Phase 1 | `python3 -m pytest tests/ --no-cov -q` |
| Task 15 | `python3 -m pytest tests/gui/test_context_menu.py -v --no-cov` |
| After Phase 2 | `python3 -m pytest tests/ --no-cov -q` |
| Final | `python3 -m pytest tests/ --no-cov -q && python3 -m ruff check src/profiles/` |

---

## Commit Strategy

| Commit | Scope | Files |
|---|---|---|
| Phase 1 | events.py + tests | `core/telemetry/{events,__init__}.py`, `tests/core/telemetry/test_events.py` |
| Phase 2 | context_menu migration | `gui/context_menu.py`, `tests/gui/test_context_menu.py` (new) |
| Phase 3 | Docs + version bump | `docs/operations/log-format.md`, `pyproject.toml`, test version assertions |

3 commits total. Each commit: working tests, no lint errors, one logical change.

---

## Out of Scope (explicit)

- Logging `action_properties` (read-only, low-signal)
- Logging `action_copy*` (5 variants) — high-frequency, low-signal
- Logging the pre-check messagebox warnings in `action_clear_file` (user said "no", not an event)
- New i18n strings for log messages
- Refactoring the menu construction loop
- Performance impact — 7 helper calls per right-click is negligible (<10 µs total)
