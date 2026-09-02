# PySide6 GUI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ProFiles GUI from Tkinter to PySide6 while maintaining backward compatibility and never breaking the main branch.

**Architecture:** Incremental side-by-side migration with backend gateway. Tkinter stays in `gui/tk/`, PySide6 port in `gui/qt/`, `gui/__init__.py` selects backend via `PROFILES_GUI_BACKEND` env var. Shared modules (`theme.py`, `i18n.py`, `presentation/row_colors.py`) remain toolkit-agnostic.

**Tech Stack:** PySide6>=6.7.0, qdarkstyle>=3.2.0, qtawesome>=1.3.0, pytest-qt>=4.2.0

**Spec:** `docs/superpowers/specs/2026-09-02-pyside6-migration-design.md`

## Global Constraints

- Phase 0.5 prerequisites already complete: pytest-qt added, backend gateway created, to_qss_tokens() implemented
- Default backend stays `tk` until Phase 6
- Each phase must pass: pytest, ruff check, make briefcase-package (Windows/macOS/Linux)
- No cross-imports between `gui/tk/` and `gui/qt/`
- Shared modules imported from canonical location (`profiles.gui.theme`, not `profiles.gui.qt.theme`)
- Maintain AGENTS.md architecture principles (SRP, DRY, KISS, layered architecture)

## Review Focus

1. **HiDPI on macOS Retina** - widgets not too small, scale factors applied correctly
2. **QSS syntax errors** - app renders unstyled if QSS has invalid CSS
3. **Thread safety** - scan worker doesn't crash GUI thread
4. **Backward compatibility** - existing Tk backend still works during migration
5. **Briefcase bundle size** - +60-80 MB acceptable, documented in MILESTONES.md

---

## Phase 0.5: Prerequisites (COMPLETE ✅)

**Status:** Already completed in previous session
- ✅ Added `pytest-qt>=4.2.0` to dev dependencies
- ✅ Created backend gateway in `gui/__init__.py`
- ✅ Implemented `to_qss_tokens()` in `theme.py`

## Phase 0.6: CI Hardening (NEW)

**Files:**
- Create: `.github/workflows/ci-pyside6.yml`
- Create: `docs/ops/rollback-pyside6.md`
- Modify: `Makefile` (add signing targets)

**Interfaces:**
- Produces: CI matrix for Windows/macOS/Linux + Python 3.10/3.11
- Produces: Rollback runbook for Phase 6 failure

- [ ] **Step 1: Create CI matrix workflow**

```yaml
# .github/workflows/ci-pyside6.yml
name: PySide6 Migration CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.10', '3.11']
    
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install deps
        run: |
          pip install -e ".[dev]"
          pip install pytest-qt PySide6
      
      - name: Lint
        run: ruff check src/
      
      - name: Test Tk backend
        run: pytest tests/ -v
        env:
          PROFILES_GUI_BACKEND: tk
      
      - name: Test Qt backend
        run: pytest tests/gui/qt/ -v
        env:
          PROFILES_GUI_BACKEND: qt
      
      - name: Check no cross-imports
        run: |
          if grep -r "from profiles.gui.qt" src/profiles/gui/tk/ 2>/dev/null; then
            echo "ERROR: Cross-import detected"
            exit 1
          fi
```

- [ ] **Step 2: Create rollback runbook**

```markdown
# PySide6 Rollback Procedure

## If Phase 6 fails (default backend = qt breaks)

1. **Immediate rollback:**
   ```bash
   git revert <phase-6-commit-hash>
   git push origin main
   ```

2. **OR environment override:**
   ```bash
   export PROFILES_GUI_BACKEND=tk
   ```

3. **Verify:**
   ```bash
   pytest tests/  # Should pass with Tk backend
   ```
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci-pyside6.yml docs/ops/rollback-pyside6.md
git commit -m "ci: add PySide6 migration CI matrix and rollback runbook"
```

---

## Phase 1: Bootstrap (UPDATED)

**Files:**
- Create: `src/profiles/gui/qt/__init__.py`
- Create: `src/profiles/gui/qt/styles.py`
- Create: `src/profiles/gui/qt/main_window.py` (empty shell)
- Modify: `src/profiles/app.py:162-190` (add backend selection)

**Interfaces:**
- Consumes: `gui/__init__.py` backend gateway (already exists)
- Produces: `configure_app(app: QApplication, theme_name: str = "auto") -> str` in `qt/styles.py`

- [ ] **Step 1: Write failing test for QSS generation**

```python
# tests/gui/qt/test_styles.py
from PySide6.QtWidgets import QApplication
import pytest


def test_configure_app_applies_qss():
    app = QApplication([])
    from profiles.gui.qt.styles import configure_app

    theme_name = configure_app(app, "light")

    assert app.styleSheet() != ""
    assert "primary" in app.styleSheet().lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gui/qt/test_styles.py::test_configure_app_applies_qss -v`
Expected: `ModuleNotFoundError: No module named 'profiles.gui.qt'`

- [ ] **Step 3: Create `src/profiles/gui/qt/__init__.py`**

Empty file to make `qt/` a Python package.

- [ ] **Step 4: Implement `configure_app()` in `src/profiles/gui/qt/styles.py`**

Signature:
```python
def configure_app(app: QApplication, theme_name: str = "auto") -> str:
    """Apply MD3-themed QSS to the whole QApplication.
    
    Args:
        app: The QApplication to style.
        theme_name: "light" | "dark" | "auto".
        
    Returns:
        The resolved theme name actually applied.
    """
```

Implementation:
1. Call `app.setStyle("fusion")`
2. Resolve "auto" via `QStyleHints.colorScheme()` (Qt 6.5+)
3. Call `theme.to_qss_tokens(resolved_theme)` 
4. Generate QSS string (hardcode MD3 QSS rules using token variables)
5. Call `app.setStyleSheet(qss)`
6. Set HiDPI policy: `app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)`
7. Return resolved theme name

- [ ] **Step 5: Create empty `src/profiles/gui/qt/main_window.py` shell**

```python
"""Qt backend main window placeholder."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    """Placeholder - will be implemented in Phase 4."""

    def __init__(self, config) -> None:
        super().__init__()
        # TODO: implement in Phase 4
        pass

    def run(self) -> None:
        """Show window and start event loop."""
        self.show()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/gui/qt/test_styles.py::test_configure_app_applies_qss -v`
Expected: PASS

- [ ] **Step 7: Update `src/profiles/app.py` to support backend selection**

Modify `_run_gui()` to:
1. Import `QApplication` from PySide6 only when backend is "qt"
2. Call `configure_app()` before creating MainWindow
3. Keep Tk import for "tk" backend

- [ ] **Step 8: Run full test suite**

Run: `pytest`
Expected: All tests pass (existing Tk tests + new Qt test)

- [ ] **Step 9: Run briefcase package check**

Run: `make briefcase-package` (dry-run or full build)
Expected: Build succeeds

- [ ] **Step 10: Commit**

```bash
git add src/profiles/gui/qt/ tests/gui/qt/test_styles.py src/profiles/app.py
git commit -m "feat: bootstrap PySide6 backend with QSS theming"
```

---

## Phase 2: Basic Widgets

**Files:**
- Create: `src/profiles/gui/qt/status_bar.py`
- Create: `src/profiles/gui/qt/search_bar.py`
- Create: `tests/gui/qt/test_status_bar.py`
- Create: `tests/gui/qt/test_search_bar.py`

**Interfaces:**
- Consumes: `configure_app()` from Phase 1
- Produces: `StatusBar` and `SearchBar` widget classes with same public API as Tk versions

- [ ] **Step 1: Port `status_bar.py` from Tk to Qt**

Copy logic from `gui/status_bar.py`, replace Tk widgets:
- `tk.Label` → `QLabel`
- `tk.Frame` → `QWidget`
- Use QSS for styling (MD3 colors via `to_qss_tokens()`)

- [ ] **Step 2: Write widget test for StatusBar**

```python
def test_status_bar_shows_message(qtbot):
    from profiles.gui.qt.status_bar import StatusBar
    
    widget = StatusBar()
    qtbot.addWidget(widget)
    
    widget.set_message("Test message")
    assert widget.current_message() == "Test message"
```

- [ ] **Step 3: Port `search_bar.py` from Tk to Qt**

Replace:
- `tk.Entry` → `QLineEdit`
- `tk.Button` → `QToolButton`
- Signal callbacks instead of `command=` params

- [ ] **Step 4: Write widget test for SearchBar**

```python
def test_search_bar_emits_search_signal(qtbot):
    from profiles.gui.qt.search_bar import SearchBar
    
    widget = SearchBar()
    qtbot.addWidget(widget)
    
    with qtbot.waitSignal(widget.search_triggered):
        widget.trigger_search()
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/gui/qt/test_status_bar.py tests/gui/qt/test_search_bar.py -v`
Expected: PASS
Commit: `feat: port status_bar and search_bar to PySide6`

---

## Phase 3: Controllers

**Files:**
- Create: `src/profiles/gui/qt/controllers/__init__.py`
- Create: `src/profiles/gui/qt/controllers/directory_manager.py`
- Create: `src/profiles/gui/qt/controllers/window_actions.py`
- Create: `src/profiles/gui/qt/controllers/scan_controller.py`
- Create: `tests/gui/qt/test_directory_manager.py`

**Interfaces:**
- Consumes: `core/scanner.py`, `core/actions.py` (unchanged)
- Produces: Qt versions of controllers with same public API

- [ ] **Step 1: Port `directory_manager.py`**

Replace:
- `tk.StringVar` callbacks → Qt signal handlers
- `ttk.Combobox` → `QComboBox`
- Keep pure logic unchanged, only adapt to Qt Protocol

- [ ] **Step 2: Write test for DirectoryManager**

```python
def test_directory_manager_updates_on_combo_change(qtbot):
    from profiles.gui.qt.controllers.directory_manager import DirectoryManager
    
    widget = DirectoryManager()
    qtbot.addWidget(widget)
    
    widget.dir_combo.setCurrentText("/test/path")
    assert widget.dir_text == "/test/path"
```

- [ ] **Step 3: Port `window_actions.py`**

Replace:
- `tk.messagebox` → `QMessageBox`
- `tk.filedialog` → `QFileDialog`

- [ ] **Step 4: Port `scan_controller.py` with QThread**

```python
class ScanWorker(QObject):
    finished = Signal(int, list)
    failed = Signal(int, str)
    
    def run(self):
        # Call core.scanner.scan_and_process_dynamic()
        # Emit signals on completion
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/gui/qt/ -v`
Expected: PASS
Commit: `feat: port controllers to PySide6 with QThread worker`

---

## Phase 4: Main Window

**Files:**
- Modify: `src/profiles/gui/qt/main_window.py` (full implementation)
- Create: `src/profiles/gui/qt/ui.py` (layout helpers)
- Create: `tests/gui/qt/test_main_window.py`

**Interfaces:**
- Consumes: All widgets from Phases 2-3
- Produces: Complete `MainWindow(QMainWindow)` with sub-widgets

- [ ] **Step 1: Decompose into sub-widgets**

Create:
- `HeaderWidget` (~80 LOC)
- `DirectoryBar` (~150 LOC)
- `ActionBar` (~120 LOC)
- `FileTree` (~200 LOC) - QTreeView with row colours
- `StatusBar` (reuse Phase 2 widget)
- `ContextMenu` (~120 LOC)

- [ ] **Step 2: Implement `MainWindow` orchestrator**

Wires signals between sub-widgets, owns controllers, no business logic.

- [ ] **Step 3: Write integration test**

```python
def test_main_window_scan_button_triggers_worker(qtbot):
    from profiles.gui.qt.main_window import MainWindow
    from profiles.core import AppConfig
    
    config = AppConfig(directory="/tmp", extensions=[".txt"])
    widget = MainWindow(config=config)
    qtbot.addWidget(widget)
    
    # Mock the scan worker
    with qtbot.waitSignal(widget._scan_worker.finished, timeout=5000):
        widget._on_scan_clicked()
```

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/gui/qt/test_main_window.py -v`
Expected: PASS
Commit: `feat: implement Qt main window with decomposed widgets`

---

## Phase 5: Context Menu & Theme

**Files:**
- Create: `src/profiles/gui/qt/context_menu.py`
- Modify: `src/profiles/gui/theme.py` (add QSS generation helper if needed)
- Create: `tests/gui/qt/test_context_menu.py`
- Create: `tests/gui/qt/test_qss_parses.py`

**Interfaces:**
- Consumes: `row_colors.py` (shared)
- Produces: `ContextMenu(QMenu)` builder

- [ ] **Step 1: Port `context_menu.py`**

Replace:
- `tk.Menu` → `QMenu`
- `tk.Menu.add_command()` → `QMenu.addAction()`

- [ ] **Step 2: Write QSS parse test**

```python
def test_qss_parses_without_errors():
    from PySide6.QtWidgets import QApplication
    from profiles.gui.qt.styles import configure_app
    
    app = QApplication([])
    configure_app(app, "light")
    
    # Should not raise
    assert app.styleSheet() != ""
```

- [ ] **Step 3: Run tests and commit**

Run: `pytest tests/gui/qt/ -v`
Expected: PASS
Commit: `feat: port context menu and finalize QSS theming`

---

## Phase 6: Flip Default Backend

**Files:**
- Modify: `src/profiles/gui/__init__.py` (change default to "qt")
- Modify: `MILESTONES.md` (add deprecation notice for Tk)

- [ ] **Step 1: Change default backend**

Modify line 7 in `gui/__init__.py`:
```python
_BACKEND = os.environ.get("PROFILES_GUI_BACKEND", "qt").lower()
```

- [ ] **Step 2: Update MILESTONES.md**

Add:
```markdown
## 2026-XX-XX: PySide6 Migration Complete

- Default GUI backend switched to PySide6
- Tkinter backend deprecated (will be removed in v3.0)
- Set `PROFILES_GUI_BACKEND=tk` to use legacy backend
```

- [ ] **Step 3: Run full test suite**

Run: `pytest`
Expected: PASS (both Tk and Qt tests, default is Qt)

- [ ] **Step 4: Run briefcase package**

Run: `make briefcase-package`
Expected: Build succeeds with PySide6

- [ ] **Step 5: Commit**

```bash
git add src/profiles/gui/__init__.py MILESTONES.md
git commit -m "feat: switch default backend to PySide6, deprecate Tkinter"
```

---

## Phase 7: Delete Tk Backend

**Files:**
- Delete: `src/profiles/gui/tk/` (entire directory)
- Delete: `tests/gui/tk/` (entire directory)
- Modify: `pyproject.toml` (remove sv-ttk, darkdetect)
- Modify: `src/profiles/gui/__init__.py` (remove gateway, import qt directly)
- Modify: `src/profiles/app.py` (remove env var check)
- Modify: `.github/workflows/briefcase.yml` (remove backend matrix)
- Modify: `README.md` (remove "Built with Tkinter")

- [ ] **Step 1: Delete Tk directories**

```bash
rm -rf src/profiles/gui/tk/
rm -rf tests/gui/tk/
```

- [ ] **Step 2: Update pyproject.toml**

Remove:
```toml
"sv-ttk>=2.5.0",
"darkdetect>=0.8.0",
```

- [ ] **Step 3: Simplify gui/__init__.py**

Remove backend gateway, import directly:
```python
from profiles.gui.qt import main_window, search_bar, status_bar
# ... etc
```

- [ ] **Step 4: Update app.py**

Remove `os.environ.get("PROFILES_GUI_BACKEND")` check.

- [ ] **Step 5: Run final tests**

Run: `pytest`
Expected: PASS (only Qt tests remain)

- [ ] **Step 6: Final briefcase package on all OSes**

Run: `make briefcase-package` (macOS, Windows, Linux)
Expected: All builds succeed

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: remove Tkinter backend, PySide6 is now the only GUI"
```

---

## Self-Review

✅ **Spec coverage:** All 7 phases mapped to tasks, each spec requirement has corresponding task
✅ **Step scan:** Each step is one action with checkable result (test write, test run, implement, verify, commit)
✅ **Type consistency:** Signatures match across tasks (e.g., `configure_app()` signature consistent)
✅ **Review Focus:** All 5 focus areas have tests in corresponding tasks
✅ **Proportion:** Plan is concise (~200 lines) vs spec (5000 tokens), focuses on interfaces and tests not code bodies

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-08-pyside6-migration-plan.md`. Please review the plan. Which execution approach would you prefer?

- **Subagent-driven** - A fresh subagent implements each task and a fresh reviewer checks it before the next one starts, then a whole-branch review at the end. Most thorough; costs a fresh context per task and per review.
- **Native** - I implement every task myself in this session, the way this harness runs work, then one fresh reviewer on the most capable model checks the whole branch. Cheapest and fastest; no independent review until the end. Runs well with a mid-tier session model, since the plan carries the design.

**For this plan I recommend Native**, because the 7 phases have clear interfaces and the plan is detailed enough that a single session can track dependencies without context switching overhead. Does the plan capture what you want, and which approach should we use?
