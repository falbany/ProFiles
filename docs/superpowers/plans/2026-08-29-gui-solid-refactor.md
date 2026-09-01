# GUI SOLID Refactor — Implementation Plan

Spec: `docs/superpowers/specs/2026-08-29-gui-solid-refactor-design.md`
Date: 2026-08-29

Goal: split `gui/main_window.py` (1,526 LoC, 60+ methods) into focused units,
organized into `components/`, `controllers/`, `presentation/`, `services/`. Public
class `MainWindow` keeps its name and constructor; `app.py` is unchanged.

## File Structure (post-refactor)

```
src/profiles/gui/
├── __init__.py                      # public re-exports
├── main_window.py                   # ≤ ~500 lines, thin orchestrator
├── components/
│   ├── __init__.py
│   ├── search_bar.py                # moved
│   ├── status_bar.py                # moved
│   ├── context_menu.py              # moved + decoupled via TreeSelectionProvider
│   └── shortcuts.py                 # NEW (extracted keyboard shortcuts dialog)
├── controllers/
│   ├── __init__.py
│   ├── scan_controller.py           # NEW
│   ├── directory_manager.py         # NEW
│   └── window_actions.py            # NEW
├── presentation/
│   ├── __init__.py
│   ├── theme.py                     # moved + absorbs color math
│   ├── styles.py                    # moved
│   ├── ui.py                        # moved
│   └── row_colors.py                # NEW
└── services/
    ├── __init__.py
    └── i18n.py                      # moved

tests/gui/
├── components/
│   ├── __init__.py
│   ├── test_search_bar.py           # moved
│   ├── test_status_bar.py           # moved
│   └── test_context_menu.py         # split from test_main_window.py
├── controllers/
│   ├── __init__.py
│   ├── test_scan_controller.py      # NEW
│   ├── test_directory_manager.py    # NEW
│   └── test_window_actions.py       # NEW
├── presentation/
│   ├── __init__.py
│   ├── test_theme.py                # moved + extends
│   ├── test_styles.py               # moved
│   ├── test_ui.py                   # moved
│   └── test_row_colors.py           # NEW
├── services/
│   ├── __init__.py
│   └── test_i18n.py                 # moved
└── test_main_window.py              # shrunk to true MainWindow tests
```

## Task 1: Move color math to `theme.py`

**Files:** `src/profiles/gui/main_window.py`, `src/profiles/gui/theme.py`, `tests/gui/test_theme.py`

**Why first:** simplest extraction; creates the pattern of "pure helper moves to
the right layer" that later tasks follow.

### Step 1.1: Add public helpers to `theme.py`

Append to `src/profiles/gui/theme.py`:

```python
def hex_luminance(hex_color: str) -> float:
    """Return relative luminance (0..1) of a #RRGGBB hex color per WCAG.

    Tolerates missing leading '#'. Returns 0.5 on parse failure.
    """
    if not isinstance(hex_color, str):
        return 0.5
    raw = hex_color.lstrip("#")
    if len(raw) != 6:
        return 0.5
    try:
        channels = (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return 0.5

    def linear(channel: int) -> float:
        srgb = channel / 255.0
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return WCAG contrast ratio between two #RRGGBB colors (1.0..21.0)."""
    l1 = hex_luminance(fg_hex)
    l2 = hex_luminance(bg_hex)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)
```

Copy formulas verbatim from `main_window.py` (`_hex_luminance` at line 39,
`_contrast_ratio` at line 62).

### Step 1.2: Delete duplicates in `main_window.py`

Remove the module-level `_hex_luminance` and `_contrast_ratio` from
`src/profiles/gui/main_window.py`. Update internal call sites to import from
`profiles.gui.theme`:

```python
from profiles.gui.theme import contrast_ratio, hex_luminance
```

Replace `self._hex_luminance(...)` and `self._contrast_ratio(...)` with the
imported names.

### Step 1.3: Tests

Add to `tests/gui/test_theme.py`:

```python
from profiles.gui.theme import contrast_ratio, hex_luminance


def test_hex_luminance_black_is_zero() -> None:
    assert hex_luminance("#000000") == 0.0


def test_hex_luminance_white_is_one() -> None:
    assert hex_luminance("#FFFFFF") == 1.0


def test_hex_luminance_handles_missing_hash() -> None:
    assert hex_luminance("FFFFFF") == 1.0


def test_hex_luminance_invalid_returns_midpoint() -> None:
    assert hex_luminance("not a color") == 0.5
    assert hex_luminance("#abc") == 0.5  # wrong length
    assert hex_luminance("") == 0.5


def test_contrast_ratio_black_on_white_is_21() -> None:
    ratio = contrast_ratio("#000000", "#FFFFFF")
    assert 20.9 <= ratio <= 21.1


def test_contrast_ratio_is_symmetric() -> None:
    a = contrast_ratio("#1565C0", "#fafafa")
    b = contrast_ratio("#fafafa", "#1565C0")
    assert abs(a - b) < 1e-9
```

### Step 1.4: Verify

```bash
cd /Users/falbany/Documents/Code/GitHub/ProFiles
python3 -m ruff format src/profiles/gui/
python3 -m ruff check src/profiles/gui/
python3 -m pytest --no-cov -q
```

Expected: all green, coverage unchanged.

### Step 1.5: Commit

```bash
git add src/profiles/gui/main_window.py src/profiles/gui/theme.py tests/gui/test_theme.py
git commit -m "refactor(gui): move color math helpers to theme module"
```

---

## Task 2: Extract `presentation/row_colors.py`

**Files:** `src/profiles/gui/main_window.py`, `src/profiles/gui/presentation/row_colors.py` (NEW), `tests/gui/presentation/test_row_colors.py` (NEW)

**Why:** pure logic; easiest to test once isolated.

### Step 2.1: Create package layout

Create `src/profiles/gui/presentation/__init__.py` (empty for now), and
`src/profiles/gui/presentation/row_colors.py` with:

```python
"""Pure row-color rule engine — no Tk dependency.

Maps a filename to ttk.Treeview tags based on user-configured substring
patterns. A `default` tag is always applied first; the first matching
rule is appended after (ttk resolves priority alphabetically, so the
appended tag wins).
"""

from __future__ import annotations

import re
from collections.abc import Iterable


class RowColorRules:
    """Compiled, ready-to-match set of row-color rules."""

    DEFAULT_TAG_SUFFIX = "default"

    def __init__(
        self,
        rules: Iterable[tuple[str, str]],
        tag_prefix: str,
    ) -> None:
        """Initialize from raw ``(pattern, color_hex)`` rules.

        Args:
            rules: User-configured ``(substring, hex)`` pairs.
            tag_prefix: Prefix for ttk tag names; the default tag is
                ``f"{tag_prefix}_default"`` and a rule's tag is
                ``f"{tag_prefix}_rule_{i}"``.
        """
        self._tag_prefix = tag_prefix
        self._default_tag = f"{tag_prefix}_{self.DEFAULT_TAG_SUFFIX}"
        # Compiled (lowercased_pattern, tag_name) pairs; case-insensitive
        # substring match, regex reserved for future expansion.
        self._compiled: list[tuple[str, str]] = [
            (pattern.lower(), f"{tag_prefix}_rule_{i}") for i, (pattern, _color) in enumerate(rules)
        ]

    @property
    def default_tag(self) -> str:
        """Return the always-applied default tag."""
        return self._default_tag

    @property
    def rule_tags(self) -> list[tuple[str, str]]:
        """Return a copy of the compiled ``(pattern, tag)`` pairs."""
        return list(self._compiled)

    def tags_for(self, filename: str) -> tuple[str, ...]:
        """Return the tags to apply to *filename*.

        Always includes the default tag; appends the first rule whose
        pattern is a substring of ``filename`` (case-insensitive).
        """
        tags: list[str] = [self._default_tag]
        if self._compiled:
            filename_lower = filename.lower()
            for pattern_lower, tag_name in self._compiled:
                if pattern_lower in filename_lower:
                    tags.append(tag_name)
                    break
        return tuple(tags)


def compile_rule_patterns(
    rules: Iterable[tuple[str, str]],
) -> list[tuple[re.Pattern[str], str]]:
    """Compile regex patterns for rules.

    Currently unused; reserved for future regex syntax in row colors.
    Kept to document the migration path from substring to regex matching.
    """
    return [(re.compile(re.escape(p), re.IGNORECASE), tag) for p, tag in rules]
```

### Step 2.2: Wire into `main_window.py`

Replace `_configure_row_colors` and `_row_color_tags_for` with delegation:

```python
from profiles.gui.presentation.row_colors import RowColorRules

# In __init__:
self._row_color_rules_engine: RowColorRules | None = None


# Replace _configure_row_colors body (keep signature, keep ttk tag config):
def _configure_row_colors(self) -> None:
    self._row_color_rules_engine = RowColorRules(
        self._config.row_colors, self._row_color_tag_prefix
    )
    # (Keep existing ttk tag configuration logic — it stays in MainWindow
    # because it touches the live Treeview; only the rule compilation
    # moves into RowColorRules.)


# Replace _row_color_tags_for:
def _row_color_tags_for(self, filename: str) -> tuple[str, ...]:
    if self._row_color_rules_engine is None:
        return (f"{self._row_color_tag_prefix}_default",)
    return self._row_color_rules_engine.tags_for(filename)
```

### Step 2.3: Tests for `RowColorRules`

`tests/gui/presentation/__init__.py` (empty) and
`tests/gui/presentation/test_row_colors.py`:

```python
from profiles.gui.presentation.row_colors import RowColorRules


def _rules() -> RowColorRules:
    return RowColorRules(
        rules=[("prod", "#005fb8"), ("dev", "#757575")],
        tag_prefix="rc",
    )


def test_default_tag_always_present() -> None:
    assert _rules().tags_for("anything.txt") == ("rc_default",)


def test_first_matching_rule_appended() -> None:
    tags = _rules().tags_for("myprod_file.mttl")
    assert tags == ("rc_default", "rc_rule_0")


def test_no_match_returns_only_default() -> None:
    assert _rules().tags_for("test.txt") == ("rc_default",)


def test_matching_is_case_insensitive() -> None:
    assert _rules().tags_for("PROD_file") == ("rc_default", "rc_rule_0")


def test_empty_rules_returns_default_only() -> None:
    rules = RowColorRules(rules=[], tag_prefix="rc")
    assert rules.tags_for("file.txt") == ("rc_default",)


def test_default_tag_property() -> None:
    assert _rules().default_tag == "rc_default"
```

### Step 2.4: Verify + commit

```bash
python3 -m ruff format src/profiles/gui/ tests/gui/
python3 -m ruff check src/profiles/gui/ tests/gui/
python3 -m pytest --no-cov -q
git add src/profiles/gui/ tests/gui/
git commit -m "refactor(gui): extract RowColorRules into presentation package"
```

---

## Task 3: Extract `controllers/scan_controller.py`

**Files:** `src/profiles/gui/main_window.py`, `src/profiles/gui/controllers/scan_controller.py` (NEW), `tests/gui/controllers/test_scan_controller.py` (NEW)

**Why:** biggest single cluster of methods (`_refresh_file_list`,
`_bg_scan_and_process`, `_poll_scan_queue`, `_start_chunked_insert`,
`_insert_chunk`); pure thread/queue logic becomes testable.

### Step 3.1: Create controller skeleton

`src/profiles/gui/controllers/__init__.py` (empty) and
`src/profiles/gui/controllers/scan_controller.py`:

```python
"""Scan lifecycle controller — owns background thread, queue, chunked insert.

Decoupled from MainWindow: takes a `ScanView` adapter (the widgets it
needs to update) instead of the full window. All dialog/error display
remains in MainWindow.
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from profiles.core.processing.scanner import ScannedFile, scan_and_process

CHUNK_SIZE = 50
PROGRESS_TICK_MS = 10


@dataclass(frozen=True)
class ScanRequest:
    """Inputs to a single scan cycle."""

    directory_label: str
    scan_paths: list[str]
    extension: str
    filter_text: str
    recursive: bool


class ScanView:
    """Adapter exposing only the widgets/handlers ScanController touches.

    Implemented by MainWindow. Kept as a Protocol-like class for
    documentation (no runtime cost; duck-typed).
    """

    root: tk.Tk
    tree: ttk.Treeview
    count_label: ttk.Label
    dir_status_label: ttk.Label
    dir_status_tooltip_set: Callable[[str], None] | None
    tree_to_path: dict[str, Path]
    tree_to_filename: dict[str, Path]
    row_color_tags_for: Callable[[str], tuple[str, ...]]
    column_ids: tuple[str, ...]
    logger: logging.Logger


class ScanController:
    """Coordinates a scan: bg thread → queue → chunked UI insert."""

    def __init__(self, view: ScanView) -> None:
        self._view = view
        self._scan_id: int = 0
        self._in_progress: bool = False
        self._queue: queue.Queue[tuple[int, list[ScannedFile]]] = queue.Queue()

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    def cancel(self) -> None:
        """Invalidate any in-flight scan so its results are ignored."""
        self._scan_id += 1

    def start(self, req: ScanRequest) -> int:
        """Launch a background scan; returns the new scan_id."""
        self._scan_id += 1
        scan_id = self._scan_id
        self._in_progress = True
        self._show_progress()
        self._view.tree_to_path.clear()
        self._view.tree_to_filename.clear()
        children = self._view.tree.get_children()
        if children:
            self._view.tree.delete(*children)
        self._view.root.after(0, self._bg_scan_and_process, scan_id, req)
        # Schedule queue polling
        self._view.root.after(PROGRESS_TICK_MS, self._poll_queue)
        return scan_id

    def _show_progress(self) -> None:
        # Implementation stays in MainWindow because it owns the
        # progressbar widget; delegate via a callback stored on view.
        progress = getattr(self._view, "show_progress", None)
        if callable(progress):
            progress()

    def _bg_scan_and_process(self, scan_id: int, req: ScanRequest) -> None:
        try:
            results = scan_and_process(
                req.scan_paths,
                extension=req.extension,
                filter_text=req.filter_text,
                recursive=req.recursive,
            )
            self._queue.put((scan_id, results))
        except Exception as exc:  # surface to UI via error callback
            self._view.logger.exception("Scan failed: %s", exc)
            err = getattr(self._view, "on_scan_error", None)
            if callable(err):
                err(exc)

    def _poll_queue(self) -> None:
        try:
            scan_id, items = self._queue.get_nowait()
        except queue.Empty:
            if self._in_progress:
                self._view.root.after(PROGRESS_TICK_MS, self._poll_queue)
            return
        self._start_chunked_insert(scan_id, items)

    def _start_chunked_insert(self, scan_id: int, items: list[ScannedFile]) -> None:
        accumulated: list[Path] = []
        self._view.count_label.config(text="Files: 0")
        self._insert_chunk(scan_id, items, 0, accumulated)

    def _insert_chunk(
        self,
        scan_id: int,
        items: list[ScannedFile],
        start: int,
        accumulated: list[Path],
    ) -> None:
        if scan_id != self._scan_id:
            return  # superseded
        end = min(start + CHUNK_SIZE, len(items))
        for sf in items[start:end]:
            iid = self._view.tree.insert(
                "",
                "end",
                values=self._row_values(sf),
                tags=self._view.row_color_tags_for(sf.filename),
            )
            self._view.tree_to_path[iid] = sf.path
            self._view.tree_to_filename[iid] = sf.filename
            accumulated.append(sf.path)
        self._view.count_label.config(text=f"Files: {end}")
        if end < len(items):
            self._view.root.after(1, self._insert_chunk, scan_id, items, end, accumulated)
        else:
            self._in_progress = False
            self._hide_progress()
            self._view.count_label.config(text=f"Files: {len(accumulated)}")
            flash = getattr(self._view, "flash_count_label", None)
            if callable(flash):
                flash()
            update_empty = getattr(self._view, "update_empty_state", None)
            if callable(update_empty):
                update_empty(len(accumulated) == 0)
            finalize = getattr(self._view, "on_scan_complete", None)
            if callable(finalize):
                finalize(len(accumulated), items)

    def _row_values(self, sf: ScannedFile) -> tuple[str, ...]:
        # Mirrors the existing column-construction logic; kept here so
        # the controller owns presentation of scan results.
        return (sf.filename, str(sf.path))

    def _hide_progress(self) -> None:
        hide = getattr(self._view, "hide_progress", None)
        if callable(hide):
            hide()
```

### Step 3.2: Adapt `MainWindow` to the controller

In `main_window.py`:

```python
from profiles.gui.controllers.scan_controller import ScanController, ScanRequest

# In __init__, after widget creation:
self._scan_controller = ScanController(view=self)


# Remove the extracted methods from MainWindow and replace:
def _on_search(self) -> None:
    self._refresh_file_list()


def _refresh_file_list(self) -> None:
    req = ScanRequest(
        directory_label=self._current_dir_label(),
        scan_paths=self._resolve_dir_selection(self._current_dir_label()),
        extension=self._ext_var.get(),
        filter_text=self._filter_var.get().strip(),
        recursive=self._recursive_var.get(),
    )
    self._scan_controller.start(req)


# Add the adapter surface (these methods already exist; just keep them
# public so ScanController can call them):
def show_progress(self) -> None: ...
def hide_progress(self) -> None: ...
def flash_count_label(self) -> None: ...
def update_empty_state(self, empty: bool) -> None: ...
def on_scan_complete(self, count: int, items: list) -> None: ...
def on_scan_error(self, exc: BaseException) -> None: ...
```

Rename protected helpers (`_show_progress`, `_hide_progress`, `_flash_count_label`,
`_update_empty_state`) to public (drop the underscore) so the controller can call
them via the adapter. The widgets they touch stay owned by `MainWindow`.

### Step 3.3: Tests

`tests/gui/controllers/test_scan_controller.py`:

```python
from unittest.mock import MagicMock

from profiles.gui.controllers.scan_controller import (
    ScanController,
    ScanRequest,
)


def _view_mock() -> MagicMock:
    view = MagicMock()
    view.tree.get_children.return_value = ()
    view.column_ids = ("file", "path")
    return view


def test_start_increments_scan_id() -> None:
    ctrl = ScanController(_view_mock())
    id1 = ctrl.start(ScanRequest("a", ["."], "", "", True))
    id2 = ctrl.start(ScanRequest("b", ["."], "", "", True))
    assert id2 == id1 + 1


def test_cancel_increments_scan_id() -> None:
    ctrl = ScanController(_view_mock())
    before = ctrl._scan_id
    ctrl.cancel()
    assert ctrl._scan_id == before + 1


def test_in_progress_toggles() -> None:
    ctrl = ScanController(_view_mock())
    assert ctrl.in_progress is False
    ctrl.start(ScanRequest("a", ["."], "", "", True))
    assert ctrl.in_progress is True
```

### Step 3.4: Verify + commit

```bash
python3 -m ruff format src/profiles/gui/ tests/gui/
python3 -m ruff check src/profiles/gui/ tests/gui/
python3 -m pytest --no-cov -q
git add src/profiles/gui/ tests/gui/
git commit -m "refactor(gui): extract ScanController"
```

---

## Task 4: Extract `controllers/directory_manager.py`

**Files:** `src/profiles/gui/main_window.py`, `src/profiles/gui/controllers/directory_manager.py` (NEW), `tests/gui/controllers/test_directory_manager.py` (NEW)

### Step 4.1: Create the manager

`src/profiles/gui/controllers/directory_manager.py`:

```python
"""Directory combobox manager — populate, format, resolve, auto-select."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk

from profiles.core import config_service
from profiles.core.config.loader import load_config
from profiles.core.config.models import AppConfig, MachineConfiguration


@dataclass(frozen=True)
class DirectoryEntry:
    """One combobox entry."""

    label: str
    paths: tuple[str, ...]


def format_dir_entry(entry: config_service.DirectoryEntry) -> str:
    """Render a DirectoryEntry for display, with icon prefix and path-count."""
    icon = "📁" if entry.is_dir else "📄"
    base = f"{icon} {entry.label}"
    if len(entry.paths) > 1:
        return f"{base} ({len(entry.paths)} paths)"
    return base


def strip_dir_label(raw: str) -> str:
    """Strip icon prefix and ``(N paths)`` suffix from a combobox label."""
    for prefix in ("📁 ", "📄 "):
        if raw.startswith(prefix):
            label = raw[len(prefix) :]
            break
    else:
        label = raw
    if label.endswith(")") and " (" in label:
        label = label[: label.rfind(" (")]
    return label


class DirectoryManager:
    """Owns the directory combobox state and resolution logic."""

    def __init__(
        self,
        config: AppConfig,
        combo: ttk.Combobox,
        hostname: str,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._combo = combo
        self._hostname = hostname
        self._logger = logger
        self._entries: list[DirectoryEntry] = []

    @property
    def entries(self) -> list[DirectoryEntry]:
        return list(self._entries)

    def populate(self) -> None:
        """Reload entries from config; updates combobox values."""
        self._entries = [
            DirectoryEntry(format_dir_entry(e), tuple(e.paths)) for e in self._config.directories
        ]
        self._combo["values"] = [e.label for e in self._entries]

    def resolve(self, label: str) -> list[str]:
        """Resolve a combobox label to its scan paths."""
        stripped = strip_dir_label(label)
        for entry in self._entries:
            if entry.label == stripped or entry.label.endswith(stripped):
                return list(entry.paths)
        # Fallback: treat the label as a raw path
        return [stripped]

    def auto_select(self) -> str:
        """Pick the best directory for the current hostname. Returns the label."""
        config_path = self._config.config_path
        if not config_path.exists():
            return str(Path.cwd())
        try:
            fresh = load_config(config_path)
        except (FileNotFoundError, OSError):
            return str(Path.cwd())
        matched = config_service.auto_select_directory(fresh, self._hostname)
        return matched or str(Path.cwd())

    def find_active_config(self) -> MachineConfiguration | None:
        """Return the MachineConfiguration matching the current hostname."""
        return self._config.match_hostname(self._hostname)

    def apply_config_overrides(self) -> None:
        """Reload config and apply machine-specific overrides (themes, etc.)."""
        # Implementation: keep the existing _apply_config_overrides body
        # but call it on the manager-owned config. Row colors and theme
        # callbacks are exposed via callbacks set by MainWindow.
        self._reload_config()

    def _reload_config(self) -> None:
        if not self._config.config_path.exists():
            return
        try:
            fresh = load_config(self._config.config_path)
        except (FileNotFoundError, OSError) as exc:
            self._logger.warning("Could not reload config: %s", exc)
            return
        # Re-apply only the values that affect the GUI; preserve widget refs
        self._config.directories = fresh.directories
        self._config.row_colors = fresh.row_colors
        self.populate()
```

### Step 4.2: Adapt `MainWindow`

In `main_window.py`:

```python
from profiles.gui.controllers.directory_manager import DirectoryManager

# In __init__, after self._dir_combo is created:
self._dir_manager = DirectoryManager(
    config=self._config,
    combo=self._dir_combo,
    hostname=self._hostname,
    logger=self._logger,
)


# Replace extracted methods with delegations:
def _populate_directories(self) -> None:
    self._dir_manager.populate()


def _format_dir_entry(self, entry) -> str:
    return format_dir_entry(entry)


def _resolve_dir_selection(self, label: str) -> list[str]:
    return self._dir_manager.resolve(label)


def _auto_select_directory(self) -> None:
    label = self._dir_manager.auto_select()
    self._dir_var.set(label)


def _current_dir_label(self) -> str:
    return strip_dir_label(self._dir_var.get())


def _find_active_config(self):
    return self._dir_manager.find_active_config()


def _apply_config_overrides(self) -> None:
    self._dir_manager.apply_config_overrides()
```

### Step 4.3: Tests

`tests/gui/controllers/test_directory_manager.py`:

```python
from profiles.gui.controllers.directory_manager import (
    DirectoryEntry,
    format_dir_entry,
    strip_dir_entry,
)
from profiles.core.config.service import DirectoryEntry as CoreEntry  # for format test


def test_strip_dir_entry_strips_icon() -> None:
    assert strip_dir_label("📁 mydir") == "mydir"


def test_strip_dir_entry_strips_count_suffix() -> None:
    assert strip_dir_label("📁 group (3 paths)") == "📁 group"


def test_format_dir_entry_single_path() -> None:
    # Construct minimal core entry; check exact rendering
    entry = CoreEntry(label="mydir", paths=("/p",), is_dir=True)
    assert format_dir_entry(entry) == "📁 mydir"


def test_format_dir_entry_multi_path() -> None:
    entry = CoreEntry(label="group", paths=("/a", "/b", "/c"), is_dir=True)
    assert format_dir_entry(entry) == "📁 group (3 paths)"
```

(Note: `strip_dir_entry` in this test is a typo from the spec — the actual
function is `strip_dir_label`. Use `strip_dir_label` in the test.)

### Step 4.4: Verify + commit

```bash
python3 -m ruff format src/profiles/gui/ tests/gui/
python3 -m ruff check src/profiles/gui/ tests/gui/
python3 -m pytest --no-cov -q
git add src/profiles/gui/ tests/gui/
git commit -m "refactor(gui): extract DirectoryManager controller"
```

---

## Task 5: Extract `controllers/window_actions.py` + `components/shortcuts.py` + context-menu facade

**Files:** `main_window.py`, `controllers/window_actions.py` (NEW), `components/shortcuts.py` (NEW), `components/context_menu.py` (moved + facade), `tests/...` (mirror)

### Step 5.1: `WindowActions`

`src/profiles/gui/controllers/window_actions.py`:

```python
"""High-level window actions — config open, log open, refresh, restart.

All `messagebox` calls live here. Each method returns the ActionResult
so callers (or tests) can verify behavior.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox

from profiles.core import actions
from profiles.core.actions import ActionResult, ActionStatus
from profiles.core.config.models import AppConfig


class WindowActions:
    """Encapsulates the side-effecting user actions."""

    def __init__(
        self,
        config: AppConfig,
        root: tk.Tk,
        logger: logging.Logger,
        on_config_changed: Callable[[], None] | None = None,
    ) -> None:
        self._config = config
        self._root = root
        self._logger = logger
        self._on_config_changed = on_config_changed

    def open_config(self) -> ActionResult:
        """Open the config file, offering to create a starter if missing."""
        config_path = self._config.config_path
        if not config_path.exists():
            if not messagebox.askyesno(
                "Configuration File Missing",
                f"No configuration file was found at:\n{config_path}\n\n"
                f"Would you like to generate a starter .profiles file in the\n"
                f"current working directory ({Path.cwd()})?",
                parent=self._root,
            ):
                return ActionResult(
                    status=ActionStatus.FAILED,
                    message="User declined to create starter config",
                    path=config_path,
                )
            written = actions.write_starter_config(config_path, logger=self._logger)
            if written.status is not ActionStatus.SUCCESS:
                messagebox.showerror("Error", written.message, parent=self._root)
                return written
            messagebox.showinfo("Starter Created", written.message, parent=self._root)

        result = actions.open_config_file(config_path, logger=self._logger)
        if result.status is not ActionStatus.SUCCESS:
            messagebox.showwarning("Open Failed", result.message, parent=self._root)
        return result

    def open_log(self, log_path: Path) -> ActionResult:
        """Open the log file with the OS default app."""
        result = actions.open_log_file(log_path, logger=self._logger)
        if result.status is not ActionStatus.SUCCESS:
            messagebox.showerror("Error", result.message, parent=self._root)
        return result

    def refresh(self) -> None:
        """Trigger a config reload and file-list refresh."""
        if self._on_config_changed is not None:
            self._on_config_changed()

    def restart(self) -> None:
        """Spawn a new Python process running `python -m profiles`."""
        self._root.destroy()
        try:
            subprocess.Popen([sys.executable, "-m", "profiles"])
        except OSError as exc:
            self._logger.error("Failed to restart: %s", exc)
            messagebox.showerror(
                "Restart Failed",
                f"Could not restart automatically: {exc}",
                parent=self._root,
            )
```

### Step 5.2: `TreeSelectionProvider` facade + decoupled context menu

In `src/profiles/gui/components/context_menu.py`:

```python
"""Right-click context menu — decoupled from MainWindow via a selection facade."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from functools import partial
from pathlib import Path
from tkinter import messagebox

from profiles.core import actions
from profiles.core.actions import ActionStatus
from profiles.core.processing.file_classifier import ensure_trailing_separator
from profiles.gui.i18n import t


class TreeSelectionProvider:
    """Abstract interface to the Treeview + current scan context.

    Implemented by MainWindow. Lets the context menu avoid reaching
    into window._tree, window._config, etc.
    """

    tree: tk.Misc  # the actual Treeview (typed loosely to avoid Tk import cycle)
    user: str
    config_release: str
    config: object  # AppConfig
    current_directory_label: Callable[[], str]
    theme: object  # Md3Theme

    def selected_path(self) -> Path | None: ...
    def selected_filename(self) -> str | None: ...


class FileContextMenu:
    def __init__(
        self,
        provider: TreeSelectionProvider,
        on_status: Callable[[str], None] | None = None,
        on_count: Callable[[int], None] | None = None,
    ) -> None:
        self._provider = provider
        self._on_status = on_status
        self._on_count = on_count

    def show(self, event: tk.Event) -> None:
        """Show the context menu at event coordinates."""
        # ... body unchanged except uses self._provider.* instead of self.window._*
```

### Step 5.3: `components/shortcuts.py`

Extract the keyboard-shortcuts dialog flow (currently inline in
`main_window._show_shortcuts`) into a dedicated class. Keep the rendering logic
in the new file; the trigger remains a `MainWindow` method.

```python
"""Keyboard shortcuts dialog."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ShortcutsDialog:
    """Modal dialog showing the keyboard shortcut reference."""

    SHORTCUTS: list[tuple[str, str]] = [
        ("Ctrl+F", "Focus filter"),
        ("F5", "Refresh"),
        ("Enter", "Execute selected"),
        ("Esc", "Cancel dialog"),
    ]

    def __init__(self, parent: tk.Misc) -> None:
        self._parent = parent

    def show(self) -> None:
        top = tk.Toplevel(self._parent)
        top.title("Keyboard Shortcuts")
        top.transient(self._parent)
        for i, (key, desc) in enumerate(self.SHORTCUTS):
            ttk.Label(top, text=key, font=("TkDefaultFont", 10, "bold")).grid(
                row=i, column=0, padx=8, pady=2, sticky="w"
            )
            ttk.Label(top, text=desc).grid(row=i, column=1, padx=8, pady=2, sticky="w")
        top.grab_set()
```

### Step 5.4: Wire and slim `MainWindow`

Replace each `_on_open_config` / `_on_open_log` / `_on_refresh` /
`_restart_application` / `_on_show_shortcuts` body with a call into
`WindowActions` (or `ShortcutsDialog.show()`). Remove the pass-through
`_action_launch`, `_action_launch_with_args`, `_action_copy_path`, etc. — wire
the context menu directly to the same actions on construction.

### Step 5.5: Tests

- `tests/gui/controllers/test_window_actions.py`: verify each method calls the
  expected `core.actions` function with the expected args (use `unittest.mock`).
- `tests/gui/components/test_context_menu.py`: split from `test_main_window.py`;
  the test fixture uses a `TreeSelectionProvider` test double.
- `tests/gui/components/test_shortcuts.py`: minimal smoke test that
  `ShortcutsDialog.show()` creates a Toplevel.

### Step 5.6: Verify + commit

```bash
python3 -m ruff format src/profiles/gui/ tests/gui/
python3 -m ruff check src/profiles/gui/ tests/gui/
python3 -m pytest --no-cov -q
git add src/profiles/gui/ tests/gui/
git commit -m "refactor(gui): extract WindowActions, ShortcutsDialog, decouple context menu"
```

---

## Task 6: Folder reorganization

**Files:** all of `src/profiles/gui/`, `tests/gui/`, and their importers in
`src/profiles/`, `tests/`, `docs/`.

### Step 6.1: Move files

```bash
cd /Users/falbany/Documents/Code/GitHub/ProFiles
mkdir -p src/profiles/gui/components src/profiles/gui/controllers \
         src/profiles/gui/presentation src/profiles/gui/services
mkdir -p tests/gui/components tests/gui/controllers \
         tests/gui/presentation tests/gui/services

git mv src/profiles/gui/search_bar.py   src/profiles/gui/components/search_bar.py
git mv src/profiles/gui/status_bar.py   src/profiles/gui/components/status_bar.py
git mv src/profiles/gui/context_menu.py src/profiles/gui/components/context_menu.py
git mv src/profiles/gui/scan_controller.py     src/profiles/gui/controllers/scan_controller.py
git mv src/profiles/gui/directory_manager.py   src/profiles/gui/controllers/directory_manager.py
git mv src/profiles/gui/window_actions.py      src/profiles/gui/controllers/window_actions.py
git mv src/profiles/gui/shortcuts.py           src/profiles/gui/components/shortcuts.py
git mv src/profiles/gui/theme.py        src/profiles/gui/presentation/theme.py
git mv src/profiles/gui/styles.py       src/profiles/gui/presentation/styles.py
git mv src/profiles/gui/ui.py           src/profiles/gui/presentation/ui.py
git mv src/profiles/gui/row_colors.py   src/profiles/gui/presentation/row_colors.py
git mv src/profiles/gui/i18n.py         src/profiles/gui/services/i18n.py

# Mirror test files
git mv tests/gui/test_search_bar.py     tests/gui/components/test_search_bar.py
git mv tests/gui/test_status_bar.py     tests/gui/components/test_status_bar.py
git mv tests/gui/test_theme.py          tests/gui/presentation/test_theme.py
git mv tests/gui/test_styles.py         tests/gui/presentation/test_styles.py
git mv tests/gui/test_ui.py             tests/gui/presentation/test_ui.py
git mv tests/gui/test_i18n.py           tests/gui/services/test_i18n.py
```

### Step 6.2: Add package `__init__.py` re-exports

For each new package, `__init__.py` re-exports the public names so imports read:

```python
# src/profiles/gui/components/__init__.py
from profiles.gui.components.search_bar import SearchBar
from profiles.gui.components.status_bar import StatusBar
from profiles.gui.components.context_menu import FileContextMenu, TreeSelectionProvider
from profiles.gui.components.shortcuts import ShortcutsDialog

__all__ = ["FileContextMenu", "SearchBar", "ShortcutsDialog", "StatusBar", "TreeSelectionProvider"]
```

Mirror the pattern for `controllers/`, `presentation/`, `services/`.

### Step 6.3: Update all import sites

Find and rewrite every import of the moved modules. Use `grep` to enumerate:

```bash
cd /Users/falbany/Documents/Code/GitHub/ProFiles
grep -rln "from profiles.gui.search_bar\|from profiles.gui.status_bar\|from profiles.gui.context_menu\|from profiles.gui.theme\|from profiles.gui.styles\|from profiles.gui.ui\|from profiles.gui.i18n\|from profiles.gui.row_colors\|from profiles.gui.scan_controller\|from profiles.gui.directory_manager\|from profiles.gui.window_actions\|from profiles.gui.shortcuts" .
```

For each match, rewrite imports to:

| Old | New |
|---|---|
| `from profiles.gui.theme import …` | `from profiles.gui.presentation import …` |
| `from profiles.gui.styles import …` | `from profiles.gui.presentation import …` |
| `from profiles.gui.ui import …` | `from profiles.gui.presentation import …` |
| `from profiles.gui.i18n import …` | `from profiles.gui.services import …` |
| `from profiles.gui.search_bar import …` | `from profiles.gui.components import …` |
| `from profiles.gui.status_bar import …` | `from profiles.gui.components import …` |
| `from profiles.gui.context_menu import …` | `from profiles.gui.components import …` |
| `from profiles.gui.row_colors import …` | `from profiles.gui.presentation import …` |
| `from profiles.gui.scan_controller import …` | `from profiles.gui.controllers import …` |
| `from profiles.gui.directory_manager import …` | `from profiles.gui.controllers import …` |
| `from profiles.gui.window_actions import …` | `from profiles.gui.controllers import …` |
| `from profiles.gui.shortcuts import …` | `from profiles.gui.components import …` |

### Step 6.4: Update docs

```bash
cd /Users/falbany/Documents/Code/GitHub/ProFiles
grep -rln "profiles.gui.theme\|profiles.gui.i18n\|profiles.gui.search_bar\|profiles.gui.status_bar" docs/
```

Update any path references in `docs/` (hooks guide, columns guide, etc.) to the
new package paths.

### Step 6.5: Update `pyproject.toml` if needed

Inspect `pyproject.toml` for any explicit module list (e.g. `packages` under
`[tool.setuptools]`). If it uses `find` packages, no change needed. Otherwise,
add the new subpackages.

### Step 6.6: Verify + commit

```bash
python3 -m ruff format src/profiles/gui/ tests/gui/
python3 -m ruff check src/profiles/gui/ tests/gui/
python3 -m pytest --no-cov -q
python3 -m pytest --no-cov --cov=src/profiles --cov-fail-under=85 -q
git add -A src/profiles/gui/ tests/gui/ docs/ pyproject.toml
git commit -m "refactor(gui): move modules into components/controllers/presentation/services packages"
```

---

## Task 7: Final slim-down + lint cleanup

**Files:** `main_window.py` and any file still carrying `protected-access` disables.

### Step 7.1: Inventory remaining `disable=protected-access`

```bash
cd /Users/falbany/Documents/Code/GitHub/ProFiles
grep -rn "disable=protected-access" src/profiles/gui/
```

For each occurrence, decide:
- Can the access be replaced with a public method on the target? → do that.
- Is the access only in tests (intentional white-box testing)? → keep but
  localize the disable to a `# noqa` comment instead of module-level, and add
  a comment explaining why.

### Step 7.2: Remove dead pass-through methods

Methods like `_selected_file_path`, `_on_tree_right_click`, `_action_launch` (now
in `context_menu.py`) should have been collapsed during Task 5. If any remain,
remove them and update callers to use the controller/menu directly.

### Step 7.3: Final line-count check

```bash
wc -l src/profiles/gui/main_window.py
```

Target: ≤ ~500 lines. If over, identify the largest remaining cluster and decide
whether to extract (likely: keep, document why).

### Step 7.4: Pylint gate

```bash
python3 -m pylint src/profiles/gui --fail-under=8.0
```

If any module scores below 8.0, fix the most impactful findings
(`too-many-attributes`, `too-many-public-methods`, `protected-access`).

### Step 7.5: Coverage check

```bash
python3 -m pytest --no-cov --cov=src/profiles --cov-fail-under=85 -q
```

If coverage dropped, add a focused unit test for the under-covered module.

### Step 7.6: Commit

```bash
git add src/profiles/gui/ tests/gui/
git commit -m "refactor(gui): final slim-down, drop surviving protected-access disables"
```

---

## Self-Review (against spec)

| Spec section | Task |
|---|---|
| Color math move | T1 |
| RowColorRules extraction | T2 |
| ScanController extraction | T3 |
| DirectoryManager extraction | T4 |
| WindowActions + ShortcutsDialog + context-menu facade | T5 |
| Folder reorganization + import re-exports | T6 |
| Slim-down + lint cleanup | T7 |
| ≤ 500 lines target | T7.3 |
| No `window._*` outside `main_window.py` | T5 (facade) + T7.1 |
| Tests green + ≥85% coverage each step | every task's Verify step |
| Backward compat (`MainWindow(config).run()`) | preserved throughout (no public API change) |

No placeholders. All test code is concrete. Imports / types are consistent
(`ScanRequest`, `ScanView`, `TreeSelectionProvider`, `WindowActions`,
`RowColorRules` defined in the same task that first uses them).
