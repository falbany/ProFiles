# Design Spec: PySide6 GUI Migration

**Date**: 2026-09-02
**Status**: Draft — pending review
**Author**: Brainstorming (vscode-copilot / superpowers)
**Supersedes**: — (no prior spec)
**Related**: `2026-08-29-gui-solid-refactor-design.md`, `2026-09-01-briefcase-installer-design.md`

---

## Context

ProFiles ships a Tkinter GUI (`src/profiles/gui/`, 8 files, ~4,580 LOC) that
looks dated despite the `sv-ttk` Material Design 2 skin. Tkinter rendering
varies across macOS, Windows, and Linux, and the ecosystem offers no good
path to a true native look-and-feel on each platform. The team wants:

- **Modern look & feel** (rounded widgets, MD3 colour tokens, native style per OS)
- **Cross-platform visual consistency** (pixel-consistent layouts, predictable HiDPI)
- **Briefcase compatibility** (no special-casing for the `make briefcase-package` pipeline)

The existing code is layered (`core` / `gui` / `utils`) and the `core/` layer
is GUI-toolkit-agnostic, so this migration is a presentation-layer rewrite,
not a from-scratch project. We are replacing the renderer, not the
architecture.

### Goals

- **G1**: Replace Tkinter presentation with PySide6 (Qt for Python) without
  changing `core/`, `utils/`, or any business logic.
- **G2**: Keep Briefcase packaging working at every phase.
- **G3**: Ship a working app at the end of each phase; never break `main`.
- **G4**: Preserve the MD3 colour system (the 688 lines in `gui/theme.py`) as
  the source of truth, translated to QSS for the Qt renderer.
- **G5**: End state: zero Tk imports, zero `sv-ttk`/`darkdetect` deps, one
  `gui/` package, one backend.

### Non-Goals

- **NG1**: No iOS / Android support. Briefcase's mobile backends require
  Toga; not in scope.
- **NG2**: No Glassmorphism / Mica / WinUI-Fluent effects in v1. The only
  mature libraries (qfluentwidgets, PySide6-Frameless-Window) are GPLv3,
  which is incompatible with the MIT project license. Custom QSS is
  possible later if a real need arises.
- **NG3**: No widget-by-widget `QWidget` subclasses for the world. Only
  wrap widgets that need a custom API (e.g. `DirectoryManager` controller,
  `Tree` with row colours). Plain `QPushButton`, `QLabel`, etc. stay plain.
- **NG4**: No rewrite of `core/`, `utils/`, `app.py` (lifecycle), or
  `config.py`. Migration stops at the presentation boundary.

---

## Decision

### Migration strategy: incremental, side-by-side, with backend selection

Keep Tkinter under `gui/tk/`, build the Qt port under `gui/qt/`, and let
`gui/__init__.py` re-export the active backend based on an environment
variable. Default to Tk for now, flip to Qt when the port is complete
and stable.

```
PROFILES_GUI_BACKEND=tk  (default until Phase 6)
PROFILES_GUI_BACKEND=qt  (default from Phase 6)
```

This:

- Keeps `make briefcase-package` green at every commit.
- Lets each Qt widget land as a working release.
- Allows A/B testing in production by end users who set the env var.
- Makes deletion trivial: `rm -rf src/profiles/gui/tk` at the end.

### File tree (target end state, after `tk/` deletion)

```
src/profiles/gui/
├── __init__.py           # Backend gateway: re-exports active backend
├── main_window.py        # QMainWindow subclass (split from 1,343 lines)
├── search_bar.py         # QLineEdit + QToolButton wrapper
├── status_bar.py         # QStatusBar subclass
├── context_menu.py       # QMenu builder (replaces tk.Menu)
├── ui.py                 # Layout helpers (QVBoxLayout, QSplitter, ...)
├── styles.py             # configure_app() entry point (fusion + QSS)
├── theme.py              # MD3 token tables (shared, toolkit-agnostic)
├── i18n.py               # Translation loader (shared, toolkit-agnostic)
├── controllers/
│   ├── __init__.py
│   ├── directory_manager.py   # QComboBox wrapper
│   ├── scan_controller.py     # QObject + Signal worker
│   └── window_actions.py      # QMessageBox wrapper
└── presentation/
    ├── __init__.py
    └── row_colors.py     # Pure rule engine (already shared, unchanged)
```

### File tree (during migration, Phases 1-6)

```
src/profiles/gui/
├── __init__.py           # Reads PROFILES_GUI_BACKEND, re-exports
├── tk/                   # ← existing files moved here
│   ├── __init__.py
│   ├── main_window.py
│   ├── search_bar.py
│   ├── status_bar.py
│   ├── context_menu.py
│   ├── ui.py
│   ├── styles.py
│   ├── theme.py          # (shared; re-exported from gui.theme)
│   ├── i18n.py           # (shared; re-exported from gui.i18n)
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── directory_manager.py
│   │   ├── scan_controller.py
│   │   └── window_actions.py
│   └── presentation/
│       ├── __init__.py
│       └── row_colors.py  # (shared; re-exported)
├── qt/                   # ← new
│   ├── __init__.py
│   ├── main_window.py
│   ├── search_bar.py
│   ├── status_bar.py
│   ├── context_menu.py
│   ├── ui.py
│   ├── styles.py
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── directory_manager.py
│   │   ├── scan_controller.py
│   │   └── window_actions.py
│   └── presentation/
│       ├── __init__.py
│       └── row_colors.py   # (re-exports the shared module)
```

**Shared module rule**: `gui/theme.py`, `gui/i18n.py`, and
`gui/presentation/row_colors.py` are pure-Python (zero Tk / Qt imports).
They are imported from `gui/qt/` directly, never duplicated.

**No cross-imports**: `gui/qt/*` never imports from `gui/tk/*` and
vice-versa. Only `gui/__init__.py` bridges them.

---

## Components

### 1. Backend gateway — `gui/__init__.py`

```python
"""GUI entry point. Selects active backend based on PROFILES_GUI_BACKEND."""
from __future__ import annotations

import os

_BACKEND = os.environ.get("PROFILES_GUI_BACKEND", "tk").lower()

if _BACKEND == "qt":
    from profiles.gui.qt import main_window, search_bar, status_bar
    from profiles.gui.qt import context_menu, styles, ui
    from profiles.gui.qt.controllers import (
        directory_manager, scan_controller, window_actions,
    )
else:
    from profiles.gui.tk import main_window, search_bar, status_bar
    from profiles.gui.tk import context_menu, styles, ui
    from profiles.gui.tk.controllers import (
        directory_manager, scan_controller, window_actions,
    )

# Shared, always imported from the canonical location.
from profiles.gui import theme, i18n
from profiles.gui.presentation import row_colors
```

### 2. `qt/styles.py` — application-level styling

Public API:

```python
def configure_app(app: QApplication, theme_name: str = "auto") -> str:
    """Apply MD3-themed QSS to the whole QApplication.

    Args:
        app: The QApplication to style.
        theme_name: "light" | "dark" | "auto". "auto" follows the
            OS via QStyleHints.colorScheme() (Qt 6.5+).

    Returns:
        The resolved theme name actually applied.
    """
```

Behaviour:

1. Call `app.setStyle("fusion")` for cross-platform consistency.
2. Resolve `theme_name` against `QStyleHints.colorScheme()` for "auto".
3. Load the MD3 token table from `gui.theme.to_qss_tokens(resolved)`.
4. Generate a QSS string and call `app.setStyleSheet(qss)`.
5. Set HiDPI policy: `app.setHighDpiScaleFactorRoundingPolicy(
   Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)`.

Rounded-corner look is achieved via QSS:

```css
QPushButton {
    border-radius: 6px;
    padding: 6px 16px;
    background-color: <md3.primaryContainer>;
    color: <md3.onPrimaryContainer>;
    border: none;
}
QPushButton:hover { background-color: <md3.secondaryContainer>; }
QPushButton:pressed { background-color: <md3.tertiaryContainer>; }
QLineEdit, QComboBox {
    border-radius: 4px;
    padding: 4px 8px;
    border: 1px solid <md3.outline>;
}
```

The full QSS block lives in `qt/styles.py` and is data-driven from the
token table — no colour literals in the QSS.

### 3. `qt/main_window.py` — split from 1,343 lines

Decomposition targets (from the 2026-08-29 GUI-solid refactor design):

| Class / responsibility | Estimated LOC |
|---|---|
| `MainWindow(QMainWindow)` — orchestrator | ~250 |
| `HeaderWidget` — title + author label | ~80 |
| `DirectoryBar` — directory + ext + filter comboboxes | ~150 |
| `ActionBar` — recursive checkbox + scan + execute buttons | ~120 |
| `FileTree` — QTreeView with row colours | ~200 |
| `StatusBar` — status + config/log/shortcuts/theme links | ~150 |
| `ContextMenu` — right-click menu on the tree | ~120 |
| Total | ~1,070 (vs. 1,343 today; less code, more focus) |

`MainWindow` instantiates the sub-widgets, wires signals, and owns the
controllers. Sub-widgets do not know about each other — they expose
signals that `MainWindow` connects.

### 4. `qt/controllers/scan_controller.py` — QThread + QObject

```python
class ScanWorker(QObject):
    """Runs a scan off the GUI thread; emits results via Qt signals."""
    finished = Signal(int, list)        # (scan_id, results)
    failed = Signal(int, str)           # (scan_id, error_msg)
    progress = Signal(int, int)         # (scan_id, current_count)

    def __init__(self, *, config, directory_label, scan_paths,
                 extension, filter_text, recursive, scan_id, logger):
        super().__init__()
        # ... mirror of run_scan() args, no queue

    def run(self) -> None:
        try:
            results = scanner.scan_and_process_dynamic(...)
            self.finished.emit(self._scan_id, results)
        except Exception as exc:
            self.failed.emit(self._scan_id, str(exc))


def start_scan(parent: QObject, **kwargs) -> ScanWorker:
    """Spawn a QThread, move the worker, connect signals, return worker."""
    thread = QThread(parent)
    worker = ScanWorker(**kwargs)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return worker
```

The pure worker function (`scanner.scan_and_process_dynamic` and the
existing `run_scan()` helper in `gui/controllers/scan_controller.py`)
stays unchanged. The Qt version is a thin `QObject` wrapper.

### 5. `qt/controllers/directory_manager.py` — QComboBox protocol

```python
class DirectoryView(Protocol):
    """Same shape as the Tk version, but Qt types."""
    @property
    def dir_combo(self) -> QComboBox: ...
    @property
    def dir_text(self) -> str: ...
    def set_dir_text(self, value: str) -> None: ...
    # ... ext_combo, filter_combo
```

The `DirectoryManager` class body is otherwise identical (pure logic).
Only the `DirectoryView` shape and the slot-method signatures differ
(`tk.StringVar` callbacks become Qt signal handlers).

### 6. `gui/theme.py` — additive change

`theme.py` keeps its existing public surface. One new function:

```python
def to_qss_tokens(theme: Md3Theme) -> dict[str, str]:
    """Flatten an Md3Theme into QSS-compatible variable names.

    Example: {"primary": "#6750A4", "onPrimary": "#FFFFFF", ...}
    """
```

No existing function is removed or changed. Tk and Qt both call into the
same token table.

### 7. `qt/search_bar.py` / `qt/status_bar.py` / `qt/context_menu.py`

Each is a thin widget wrapper that exposes the same public API as the Tk
version (method names, return types, signal names). They use the shared
`i18n` and `theme` modules.

### 8. `pyproject.toml` — dependency changes

```diff
 dependencies = [
-    "sv-ttk>=2.5.0",
-    "darkdetect>=0.8.0",
+    "PySide6>=6.7.0",
+    "qdarkstyle>=3.2.0",
+    "qtawesome>=1.3.0",
     "ruamel.yaml>=0.18.0",
     "pydantic>=2.0.0",
 ]
```

`[tool.briefcase.app.profiles]`:

```diff
-requires = []
+requires = [
+    "PySide6>=6.7.0",
+    "qdarkstyle>=3.2.0",
+    "qtawesome>=1.3.0",
+]
```

`make briefcase-package` is re-verified in every phase.

### 9. `app.py` — minimal change

`src/profiles/app.py` currently does `import tkinter as tk`. After the
migration, the import goes through `from profiles.gui import main_window`.
No other change to `app.py`. Headless mode still works.

---

## Data Flow

### Scan lifecycle (Qt)

```
[User clicks "Scan"]
   ↓
MainWindow._on_scan_clicked()
   ↓
ScanWorker created with kwargs
   ↓
QThread started, worker.run() executes scanner.scan_and_process_dynamic
   ↓ (on success)
worker.finished(scan_id, results) → MainWindow._on_scan_finished
   ↓
MainWindow calls FileTree.populate(results)
   ↓
FileTree applies row-colour tags via row_colors.RowColorRules
   ↓
StatusBar.set_message(f"{len(results)} files found")
```

### Config change lifecycle

Identical to today — `DirectoryManager` reacts to `dir_combo.currentTextChanged`,
`ext_combo.currentTextChanged`, etc. The signal names are Qt-native but the
flow is the same.

### Telemetry

The `events` module in `core/telemetry/` is unchanged. `ScanWorker` emits
the same `events.scan_started` / `events.scan_completed` events as the
Tk worker did.

---

## Error Handling

The migration does not change the `ActionResult` pattern in `core/actions`.
The only changes are at the GUI boundary:

| Tk | Qt |
|---|---|
| `messagebox.showerror(title, msg)` | `QMessageBox.critical(self, title, msg)` |
| `messagebox.showinfo(title, msg)` | `QMessageBox.information(self, title, msg)` |
| `messagebox.askyesno(title, msg)` | `QMessageBox.question(self, title, msg, QMessageBox.Yes \| QMessageBox.No)` |
| `filedialog.askdirectory()` | `QFileDialog.getExistingDirectory(self, ...)` |
| `filedialog.askopenfilename()` | `QFileDialog.getOpenFileName(self, ...)` |

A small `gui/qt/dialogs.py` module provides thin wrappers so the call sites
read uniformly.

Uncaught exceptions in slots: `QApplication.notify` is overridden in
`qt/styles.py` to log + show a `QMessageBox.critical` instead of crashing
the process. (Same behaviour as the Tk version's `tk.Tk.report_callback_exception`.)

---

## Testing

### Layer 1 — Pure unit (existing pytest, no new deps)

- `gui/presentation/row_colors.py` — already tested, no change.
- `gui/theme.py::to_qss_tokens()` — new tests, pure data.
- `core/processing/scanner.py` — already tested, reused.

### Layer 2 — Widget unit (new dep: `pytest-qt`)

Each widget in `qt/` gets a test file that:

1. Creates an offscreen `QApplication` (pytest-qt's `qtbot` fixture).
2. Instantiates the widget.
3. Drives interactions (`qtbot.mouseClick`, `qtbot.keyClicks`).
4. Asserts on emitted signals, `widget.text()`, etc.

Files: `tests/gui/qt/test_search_bar.py`, `test_status_bar.py`,
`test_context_menu.py`, `test_directory_manager.py`.

### Layer 3 — Headless integration (pytest-qt `qtbot`)

`tests/gui/qt/test_main_window.py` builds a `MainWindow` with a fake
`AppConfig`, simulates a click on the "Scan" button, feeds a mock
`ScanWorker.finished` signal, and asserts on the `FileTree` state.

No screenshot-based testing. Visual QA is manual, by the maintainer,
once per release, on each of the three target platforms.

### Layer 4 — Smoke (Briefcase)

`make briefcase-package` is run in CI on macOS, Windows, and Linux at
every phase. The packaged binary is launched, the window opens, the
"Scan" button responds, and the app is closed. No further automation.

### CI matrix

`.github/workflows/briefcase.yml` adds a `strategy.matrix.os` block:

```yaml
strategy:
  matrix:
    os: [macos-latest, windows-latest, ubuntu-latest]
```

Each OS runs `make briefcase-package` + the smoke test. This is added at
Phase 1, not deferred to Phase 6, so cross-platform issues are caught
early.

---

## Rollout Phases

| Phase | Scope | Default backend | Branch |
|---|---|---|---|
| 0 | This spec | tk | `spec/pyside6-migration` |
| 1 | Bootstrap: `qt/__init__.py`, `qt/styles.py`, empty `qt/main_window.py` (QMainWindow shell), `gui/__init__.py` gateway, env var read | tk | `feat/qt-bootstrap` |
| 2 | Port `status_bar.py` + `search_bar.py` | tk | `feat/qt-widgets-basic` |
| 3 | Port `controllers/directory_manager.py`, `window_actions.py`, `scan_controller.py` (QThread + QObject) | tk | `feat/qt-controllers` |
| 4 | Port `main_window.py` fully (split into HeaderWidget, DirectoryBar, ActionBar, FileTree, StatusBar, ContextMenu) | tk | `feat/qt-main-window` |
| 5 | Port `context_menu.py` + finalize `theme.py::to_qss_tokens()` QSS generation | tk | `feat/qt-context-menu-and-theme` |
| 6 | Flip default backend to qt; ship one release; mark tk as deprecated in `MILESTONES.md` | qt | `feat/qt-default` |
| 7 | Delete `tk/`, remove `sv-ttk`/`darkdetect`/env var | qt | `chore/remove-tk` |

Each phase ends with:

- `pytest` green (existing + new Qt tests)
- `ruff check .` clean
- `make briefcase-package` green on all three OSes
- Manual launch screenshot saved to `docs/screenshots/` (Phase 6+ only)
- One-line update to `MILESTONES.md`

---

## Deletion Plan (Phase 7 checklist)

- [ ] `rm -rf src/profiles/gui/tk/`
- [ ] `rm -rf tests/gui/tk/`
- [ ] Update `pyproject.toml` — remove `sv-ttk`, `darkdetect`; keep `PySide6`, `qdarkstyle`, `qtawesome`
- [ ] Update `src/profiles/gui/__init__.py` — remove backend gateway, import `qt/` directly
- [ ] Update `src/profiles/app.py` — drop the `os.environ.get` check
- [ ] Update `.github/workflows/briefcase.yml` — drop the `PROFILES_GUI_BACKEND` matrix env var
- [ ] Update `makefile` — drop the `gui-backend=` make-variable if present
- [ ] Update `docs/` — any Tkinter screenshots in `installation-guide.{en,fr}.md`, `configuration-profile.{en,fr}.md`
- [ ] Update `MILESTONES.md` — note the switch, link to this spec
- [ ] Update `README.md` — drop "Built with Tkinter" mentions
- [ ] One final `make briefcase-package` on all three OSes, full smoke test

---

## Risks and Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | macOS HiDPI looks tiny on retina | Medium | Medium | Set `HighDpiScaleFactorRoundingPolicy.PassThrough` in `configure_app()`. Test on M1/M2 macs in CI. |
| R2 | Briefcase bundle size +60-80 MB | High | Low | Document the size change in `MILESTONES.md`. Acceptable for a desktop installer. |
| R3 | Cocoa event-loop fights with Toga | Low | High | `toga-demo` lives outside `profiles.gui`; we never import Toga from the GUI. Add a `tests/test_no_toga_in_gui.py` guard. |
| R4 | QSS string has syntax errors, app renders unstyled | Medium | Medium | Add a `tests/gui/qt/test_qss_parses.py` that calls `setStyleSheet` and checks `QApplication.instance().styleSheet()` round-trips. |
| R5 | `darkdetect` / `sv-ttk` (the `sv-ttk` PyPI package) import is hard-coded in `app.py` and `__init__.py` | Low | Medium | Phase 7 includes `grep -r "sv_ttk\|darkdetect" src/ tests/` to confirm no leftovers. The import name is `sv_ttk` (underscore) even though the PyPI package is `sv-ttk` (dash). |
| R6 | Phase 4's `main_window.py` rewrite regresses behaviour | High | High | TDD: write `tests/gui/qt/test_main_window.py` against the current Tk behaviour first, then port against the new tests. |
| R7 | Cross-platform differences in QSS rendering (esp. macOS) | High | Medium | CI matrix on all three OSes from Phase 1. Manual QA per release. |
| R8 | `pytest-qt` not available on all CI runners | Low | Low | `pytest-qt` is pip-installable on macOS, Windows, Linux. Add to `[dev]` extras. |

---

## Open Questions

None. All design decisions are resolved:

- ✅ Migration: incremental, side-by-side
- ✅ Theming: fusion + QDarkStyle + custom QSS for rounded widgets
- ✅ Threading: QThread + QObject signals from the start
- ✅ Icons: `qtawesome` (MIT) from the start
- ✅ Testing: pytest-qt for widget tests, no screenshot tests
- ✅ Rollout: 7 phases, each shippable

---

## Out of Scope (later)

- Glassmorphism / Mica / WinUI-Fluent custom QSS (license barriers)
- Mobile (iOS / Android) via Toga — would require its own spec
- Animated transitions between themes (dark ↔ light) — possible with
  `QPropertyAnimation`; defer to v2
- Plugin system for user-defined widgets — defer to v2
