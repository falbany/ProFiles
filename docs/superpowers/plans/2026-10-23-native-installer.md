# Native Installer (Briefcase CI) + Tkinter Deprecation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Briefcase native installers (msi/dmg/deb/AppImage) from a GitHub Actions release pipeline, move Tk-only deps to dev extras, and deprecate the Tkinter frontend with lazy imports — while leaving `install.py` and `make install-system` untouched.

**Architecture:** The default GUI backend is already web (pywebview + FastAPI); we make `app.py` import tkinter only inside the `--tkinter` branch so any Python (including Briefcase's Tk-less embeddable) runs the web backend. Briefcase's `[tool.briefcase.app.profiles]` gets real runtime `requires`; a 3-OS CI matrix packages artifacts on version tags; Makefile gains per-platform local build targets; docs reorder native installer first.

**Tech Stack:** Briefcase 0.4.x (WiX/MSI, DMG, deb, AppImage), GitHub Actions, uv, pytest, tomllib (py3.11+).

**Spec:** `docs/superpowers/specs/2026-10-23-native-installer-design.md`

## Global Constraints

- `install.py` and the `make install-system` target stay **byte-for-byte unchanged**.
- Runtime deps (exact, verbatim from `pyproject.toml` today): `sv-ttk>=2.5.0`, `darkdetect>=0.8.0` (move out), `pydantic>=2.0.0`, `fastapi>=0.115.0`, `uvicorn[standard]>=0.30.0`, `pywebview>=5.1.0`, `sse-starlette>=2.1.0`, `qrcode[pil]>=7.5.0`, `ruamel.yaml>=0.18.0` (keep).
- `sv-ttk` and `darkdetect` end up ONLY in `[project.optional-dependencies].dev` and `[dependency-groups].dev` (both lists).
- Deprecation banner text (stdout) and unavailable message (stderr), verbatim:
  - Banner: `⚠  The Tkinter frontend is deprecated (developer/advanced use only) and` + `   will be removed in a future release. The default web GUI replaces it.`
  - Unavailable: `ERROR: The Tkinter frontend requires a full Python installation with Tk` + `       (tkinter). Use the default web GUI instead: profiles`
- Briefcase version stays in sync with `[project].version` = `2026.8.0` (MSI integer triple).
- Quality gates: pytest coverage ≥ 85 %, `ruff check .` clean, `pylint src/profiles` ≥ 8.0, `ruff format .`.
- Ruff config: line-length 100, double quotes, target py311.
- Tag convention: `v2026.8.0` → Briefcase version `2026.8.0` (strip leading `v`).

## Review Focus

Failure modes the spec implies that tests don't fully exercise — each is pinned by the named task:

1. **Bundle on a Python/Tk-less machine** — the web GUI must boot from the MSI on a machine with no Python. Pinned by the Task 1 unit tests (tkinter blocked via `sys.modules`) plus the Task 9 manual smoke (`uv run briefcase build windows` + launch).
2. **`--tkinter` in the bundle** — must print the banner and exit cleanly (code 1, no traceback). Pinned by Task 1 Step 1 test `test_tkinter_clean_error_when_unavailable`.
3. **Version drift** (tag ≠ `[project].version` ≠ `[tool.briefcase].version`) — release must fail fast. Pinned by Task 5 Step 2 (run the guard locally in both match and mismatch scenarios).
4. **Tkinter present but `sv-ttk` absent** (dev env after dep split) — `--tkinter` must still launch using the clam fallback; `gui/theme.py` already try/excepts `import sv_ttk`. Pinned by Task 2 Step 1 test `test_theme_fallback_without_sv_ttk`.
5. **`profiles.main` missing for the Briefcase stub** — stub must find an entry callable without importing the whole app eagerly. Pinned by Task 3 Step 1 test `test_package_exposes_lazy_main`.

---

### Task 1: Lazy tkinter imports + deprecation banner in `app.py`

**Files:**
- Modify: `src/profiles/app.py` (line 13 `import tkinter as tk`; line 22 `from profiles.gui.main_window import MainWindow`; `ProFileApp.__init__` annotation line 98; `_run_gui()` lines 293–319; `main()` tk branch lines 528–533)
- Test: `tests/app/test_lazy_tkinter.py` (new directory)

**Interfaces:**
- Consumes: existing `ProFileApp` (web branch `_run_web_gui()`, tk branch `_run_gui()`), existing `main()`.
- Produces: module constants `_TKINTER_DEPRECATION_BANNER`, `_TKINTER_UNAVAILABLE_MSG` (later tasks and docs reference the wording); `main()` prints the banner before any config load when `gui_backend == "tk"`; `_run_gui()` exits with code 1 when tkinter is missing.

- [ ] **Step 1: Write the failing tests**

Create `tests/app/test_lazy_tkinter.py`:

```python
"""The web backend must run with tkinter unavailable (Briefcase embeddable Python).

Related spec: docs/superpowers/specs/2026-10-23-native-installer-design.md §5.2.
"""

from __future__ import annotations

import importlib
import logging
import sys

import pytest

import profiles.app as app_module


class _StubConfig:
    """Minimal config surface used by ProFileApp.run()."""

    scan_metrics = False
    verbose = "INFO"


@pytest.fixture(autouse=True)
def _restore_app_module():
    """Reload profiles.app normally after each test so other suites are unaffected."""
    yield
    importlib.reload(app_module)


def _reload_with_tkinter_blocked(monkeypatch: pytest.MonkeyPatch) -> object:
    """Put a None sentinel for tkinter, then reload profiles.app.

    ``sys.modules["tkinter"] = None`` makes ``import tkinter`` raise ImportError,
    simulating the Briefcase Windows embeddable distribution.
    """
    monkeypatch.setitem(sys.modules, "tkinter", None)
    monkeypatch.setitem(sys.modules, "profiles.gui.main_window", None)
    return importlib.reload(app_module)


def _stub_app_collaborators(monkeypatch: pytest.MonkeyPatch, app: object) -> None:
    """Replace logging and config loading so run() reaches the backend branch."""
    monkeypatch.setattr(
        type(app), "_setup_logging", lambda self, level=logging.INFO: logging.getLogger("test")
    )
    monkeypatch.setattr(type(app), "_load_configuration", lambda self, logger: _StubConfig())


def test_web_backend_runs_without_tkinter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Import + web run path succeed while tkinter is blocked."""
    mod = _reload_with_tkinter_blocked(monkeypatch)
    called: list[str] = []
    monkeypatch.setattr(mod.ProFileApp, "_run_web_gui", lambda self, **kw: called.append("web"))

    app = mod.ProFileApp(gui_backend="web")
    _stub_app_collaborators(monkeypatch, app)
    app.run()  # must not raise ImportError

    assert called == ["web"]


def test_headless_runs_without_tkinter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Headless mode needs no tkinter either."""
    mod = _reload_with_tkinter_blocked(monkeypatch)
    app = mod.ProFileApp(gui_backend="web", headless=True)
    _stub_app_collaborators(monkeypatch, app)
    monkeypatch.setattr(mod.ProFileApp, "run_headless", lambda self, file_path=None: 0)

    with pytest.raises(SystemExit) as excinfo:
        app.run()

    assert excinfo.value.code == 0


def test_tkinter_banner_printed_when_requested(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With tkinter available, --tkinter prints the deprecation banner and launches tk GUI."""
    mod = app_module  # normal module state
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["profiles", "--tkinter"])
    monkeypatch.setattr(mod.ProFileApp, "_run_gui", lambda self: calls.append("tk"))

    app = mod.ProFileApp(gui_backend="tk")
    _stub_app_collaborators(monkeypatch, app)
    app.run()

    assert calls == ["tk"]
    out = capsys.readouterr().out
    assert "deprecated" in out.lower()
    assert "will be removed" in out.lower()


def test_tkinter_clean_error_when_unavailable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without tkinter, --tkinter prints banner + actionable error and exits 1 (no traceback)."""
    mod = _reload_with_tkinter_blocked(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["profiles", "--tkinter"])

    app = mod.ProFileApp(gui_backend="tk")
    _stub_app_collaborators(monkeypatch, app)

    with pytest.raises(SystemExit) as excinfo:
        app.run()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "deprecated" in captured.out.lower()
    assert "full Python installation" in captured.err
    assert "Traceback" not in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/app/test_lazy_tkinter.py -v --no-cov`
Expected: `test_tkinter_banner_printed_when_requested` FAILS (no banner yet); the tkinter-blocked tests FAIL with ImportError / TypeError (module-level `import tkinter` crashes on reload with the None sentinel).

- [ ] **Step 3: Implement the lazy imports and banner**

In `src/profiles/app.py`:

1. Delete line 13 (`import tkinter as tk`) and line 22 (`from profiles.gui.main_window import MainWindow`).
2. Add `TYPE_CHECKING` import (stdlib block) and guarded import — the annotation `self._window: MainWindow | None` (line 98) keeps working because `from __future__ import annotations` is already at line 7:

```python
import argparse
import logging
import platform
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from profiles.core import AppConfig, actions, load_config
from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME
from profiles.core.environment.system import format_user_host
from profiles.core.processing.scanner import scan_and_process
from profiles.core.telemetry import events
from profiles.core.telemetry.diagnostics import configure_logger, install_crash_hook
from profiles.launch import (
    detect_launch_context,
    resolve_config_path,
    with_explicit_config,
)
from profiles.utils.network import get_hostname, get_username

if TYPE_CHECKING:
    from profiles.gui.main_window import MainWindow

_DEFAULT_PORT = 8088

_TKINTER_DEPRECATION_BANNER = (
    "⚠  The Tkinter frontend is deprecated (developer/advanced use only) and\n"
    "   will be removed in a future release. The default web GUI replaces it."
)
_TKINTER_UNAVAILABLE_MSG = (
    "ERROR: The Tkinter frontend requires a full Python installation with Tk\n"
    "       (tkinter). Use the default web GUI instead: profiles"
)
```

3. In `_run_gui()`, import tkinter and MainWindow lazily:

```python
def _run_gui(self) -> None:
    """Create and run the GUI.

    Handles GUI creation and error cases (e.g., no display available).
    Prints a deprecation banner decision in main(); this method only
    launches the Tk window.

    Exits:
        SystemExit(1) if tkinter is unavailable or GUI initialization fails.
    """
    try:
        import tkinter as tk

        from profiles.gui.main_window import MainWindow
    except ImportError:
        print(_TKINTER_UNAVAILABLE_MSG, file=sys.stderr)
        sys.exit(1)

    try:
        self._window = MainWindow(config=self._config)
    except (RuntimeError, tk.TclError) as exc:
        # ... existing body unchanged (lines 304-317)
```

4. In `main()`, print the banner before creating `ProFileApp`:

```python
    # Determine GUI backend from arguments
    if args.tkinter:
        gui_backend = "tk"
        print(_TKINTER_DEPRECATION_BANNER)
    elif args.web:
        gui_backend = "web"
    else:
        gui_backend = "web"  # Default to web
```

5. Update the `--tkinter` argparse help string (around line 505) to:

```python
    parser.add_argument(
        "--tkinter",
        action="store_true",
        help="Use Tkinter GUI backend (deprecated; developer use only, will be removed)",
    )
```

6. In the epilog text (lines 467-476), replace the `--tkinter` example line with:

```
  profiles --tkinter                Deprecated Tkinter GUI (developer use only)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/app/test_lazy_tkinter.py -v --no-cov`
Expected: 4 PASS.

- [ ] **Step 5: Run the full suite (catch reload side effects)**

Run: `uv run pytest -x -q`
Expected: PASS with coverage ≥ 85 %.

- [ ] **Step 6: Quality gates**

Run: `uv run ruff format src/profiles/app.py tests/app/test_lazy_tkinter.py && uv run ruff check . && uv run pylint src/profiles --fail-under=8.0`
Expected: all clean (pylint `C0415` import-outside-toplevel is already disabled).

- [ ] **Step 7: Commit**

```bash
git add src/profiles/app.py tests/app/test_lazy_tkinter.py
git commit -m "feat(app): lazy tkinter imports; deprecate Tkinter frontend (dev-only)"
```

---

### Task 2: Move Tk-only deps to dev extras (`pyproject.toml`)

**Files:**
- Modify: `pyproject.toml` (`[project] dependencies` lines 11-21; `[project.optional-dependencies] dev` lines 50-61; `[dependency-groups] dev` lines 178-188)
- Test: `tests/app/test_packaging.py` (new)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: runtime `dependencies` without `sv-ttk`/`darkdetect`; both dev lists containing them; `[tool.briefcase.app.profiles].requires` populated (Task 5 CI depends on this).

- [ ] **Step 1: Write the failing tests**

Create `tests/app/test_packaging.py`:

```python
"""Packaging rules: Tk-only deps are dev-only; Briefcase requires are runtime-complete.

Related spec: docs/superpowers/specs/2026-10-23-native-installer-design.md §5.1, §5.3.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _load() -> dict:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_tk_deps_absent_from_runtime_dependencies() -> None:
    deps = " ".join(_load()["project"]["dependencies"]).lower()
    assert "sv-ttk" not in deps
    assert "darkdetect" not in deps


def test_tk_deps_present_in_both_dev_lists() -> None:
    data = _load()
    extras_dev = " ".join(data["project"]["optional-dependencies"]["dev"]).lower()
    groups_dev = " ".join(data["dependency-groups"]["dev"]).lower()
    for where in (extras_dev, groups_dev):
        assert "sv-ttk" in where
        assert "darkdetect" in where


def test_briefcase_requires_runtime_complete_and_tk_free() -> None:
    requires = " ".join(_load()["tool"]["briefcase"]["app"]["profiles"]["requires"]).lower()
    for pkg in ("pydantic", "fastapi", "uvicorn", "pywebview", "sse-starlette", "qrcode", "ruamel"):
        assert pkg in requires
    assert "sv-ttk" not in requires
    assert "darkdetect" not in requires
```

Also append to `tests/app/test_lazy_tkinter.py` (same file, new test) the pinned fallback from Review Focus item 4:

```python
def test_theme_fallback_without_sv_ttk(monkeypatch: pytest.MonkeyPatch) -> None:
    """apply_theme survives sv_ttk absence (clam fallback path in gui/theme.py)."""
    pytest.importorskip("tkinter")
    import tkinter as tk

    from profiles.gui import theme as theme_module

    monkeypatch.setitem(sys.modules, "sv_ttk", None)  # import sv_ttk -> ImportError
    root = tk.Tk()
    root.withdraw()
    try:
        theme_module.apply_theme(root, theme_module.DARK_THEME)
    finally:
        root.destroy()
```

Append it at the end of `tests/app/test_lazy_tkinter.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/app/test_packaging.py tests/app/test_lazy_tkinter.py -v --no-cov`
Expected: the three packaging tests FAIL (deps still runtime; briefcase requires empty), fallback test may PASS already (code unchanged) — record which.

- [ ] **Step 3: Edit `pyproject.toml`**

1. `[project] dependencies` becomes:

```toml
dependencies = [
    "pydantic>=2.0.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pywebview>=5.1.0",
    "sse-starlette>=2.1.0",
    "qrcode[pil]>=7.5.0",
    "ruamel.yaml>=0.18.0",
]
```

2. Add `sv-ttk>=2.5.0` and `darkdetect>=0.8.0` to **both** `[project.optional-dependencies].dev` and `[dependency-groups].dev`, with this comment above the two Tk entries in each list:

```toml
    # Tkinter frontend (deprecated, developer use only; see 2026-10-23-native-installer-design.md)
    "sv-ttk>=2.5.0",
    "darkdetect>=0.8.0",
```

3. Replace `[tool.briefcase.app.profiles]` `requires = []` with:

```toml
# Runtime dependencies installed into the Briefcase bundle. Must mirror
# [project].dependencies minus the deprecated Tk extras (sv-ttk, darkdetect).
requires = [
    "pydantic>=2.0.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pywebview>=5.1.0",
    "sse-starlette>=2.1.0",
    "qrcode[pil]>=7.5.0",
    "ruamel.yaml>=0.18.0",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/app/test_packaging.py tests/app/test_lazy_tkinter.py -v --no-cov`
Expected: all PASS.

- [ ] **Step 5: Refresh the environment and sanity-check the dev experience**

Run: `uv sync && uv run python -c "import sv_ttk, darkdetect; print('dev tk deps OK')" && uv run pytest -x -q`
Expected: sync succeeds (dev group installed), import OK, full suite PASS ≥ 85 %.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/app/test_packaging.py tests/app/test_lazy_tkinter.py uv.lock
git commit -m "feat(packaging): move sv-ttk/darkdetect to dev extras; populate briefcase requires"
```

---

### Task 3: Briefcase stub entry point (`profiles/__init__.py`)

**Files:**
- Modify: `src/profiles/__init__.py` (append module-level `__getattr__` after `__version__`, line ~50)
- Test: `tests/app/test_entry_point.py` (new)

**Interfaces:**
- Consumes: `profiles.app.main` (exists).
- Produces: `profiles.main` attribute, resolved lazily (no eager import of the heavy `profiles.app` module when just importing `profiles`).

- [ ] **Step 1: Write the failing test**

Create `tests/app/test_entry_point.py`:

```python
"""The Briefcase stub resolves ``profiles.main`` lazily (spec §5.3)."""

from __future__ import annotations


def test_package_exposes_lazy_main() -> None:
    import profiles
    from profiles.app import main as real_main

    assert profiles.main is real_main


def test_unknown_attribute_still_raises() -> None:
    import pytest

    import profiles

    with pytest.raises(AttributeError):
        profiles.no_such_thing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/app/test_entry_point.py -v --no-cov`
Expected: `test_package_exposes_lazy_main` FAILS with `AttributeError: module 'profiles' has no attribute 'main'`; the unknown-attribute test PASSES by accident (plain module) — acceptable.

- [ ] **Step 3: Implement**

Append to `src/profiles/__init__.py`:

```python
def __getattr__(name: str):
    """Expose selected callables lazily (PEP 562).

    The Briefcase stub resolves ``profiles.main``; keep it a lazy attribute
    so ``import profiles`` stays cheap for headless/web usage.
    """
    if name == "main":
        from profiles.app import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/app/test_entry_point.py -v --no-cov`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/profiles/__init__.py tests/app/test_entry_point.py
git commit -m "feat(core): lazy profiles.main re-export for Briefcase stub entry point"
```

---

### Task 4: Per-platform local build targets (Makefile)

**Files:**
- Modify: `Makefile` (Briefcase section, lines 49-71; `.PHONY` line 17; new host-detection block)

**Interfaces:**
- Consumes: existing `BRIEFCASE` variable (`uv run briefcase`).
- Produces: targets `briefcase-package-windows`, `briefcase-package-macos`, `briefcase-package-linux-deb`, `briefcase-package-linux-appimage`, `briefcase-package-local` (dispatch variable `HOST_PKG`).

- [ ] **Step 1: Add host detection and targets**

Replace the Briefcase section header area (lines 49-71) — keep `briefcase-dev`, `briefcase-build`, `briefcase-run`, existing generic `briefcase-package`, and `briefcase-clean` exactly as they are; add below them:

```make
# Host detection for local packaging dispatch (Briefcase cannot cross-compile)
ifeq ($(OS),Windows_NT)
    HOST_PKG := briefcase-package-windows
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        HOST_PKG := briefcase-package-macos
    else
        HOST_PKG := briefcase-package-linux-deb
    endif
endif

briefcase-package-windows: ## Package the Windows installer (.msi) — Windows host only
	@echo "📦 Packaging Windows MSI (requires Windows host)..."
	$(BRIEFCASE) package windows -p msi
	@echo "✅ Installer written to dist/"

briefcase-package-macos: ## Package the macOS disk image (.dmg) — macOS host only
	@echo "📦 Packaging macOS DMG (requires macOS host)..."
	$(BRIEFCASE) package macos -p dmg
	@echo "✅ Installer written to dist/"

briefcase-package-linux-deb: ## Package the Linux .deb — Linux host only
	@echo "📦 Packaging Linux .deb (requires Linux host)..."
	$(BRIEFCASE) package linux -p deb
	@echo "✅ Package written to dist/"

briefcase-package-linux-appimage: ## Package the Linux .AppImage — Linux host only
	@echo "📦 Packaging Linux AppImage (requires Linux host)..."
	$(BRIEFCASE) package linux -p appimage
	@echo "✅ AppImage written to dist/"

briefcase-package-local: ## Package for the current host OS (auto-detect)
	@echo "📦 Detected host package target: $(HOST_PKG)"
	$(MAKE) $(HOST_PKG)
```

Also extend `.PHONY` on line 17 to include the five new target names.

- [ ] **Step 2: Verify with dry runs (no build executed)**

Run: `make -n briefcase-package-local` then `make -n briefcase-package-windows` then `make help`
Expected: first shows `$(MAKE) briefcase-package-windows` on this Windows machine; second shows the `uv run briefcase package windows -p msi` command; `help` lists the new targets.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build(make): per-platform briefcase package targets with host auto-detect"
```

---

### Task 5: Release workflow with version guard

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `[tool.briefcase.app.profiles].requires` from Task 2; `profiles.main` from Task 3.
- Produces: release artifacts `ProFiles-<ver>.msi`, `ProFiles-<ver>.dmg`, `profiles_<ver>_amd64.deb`, `ProFiles-<ver>.AppImage` attached to GitHub Releases on `v*` tags.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/release.yml`:

```yaml
name: Release native installers

on:
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Verify tag matches [project] and [tool.briefcase] versions
        env:
          TAG_VERSION: ${{ github.ref_name }}
        run: |
          uv run python - <<'PY'
          import os
          import pathlib
          import tomllib

          data = tomllib.loads(
              pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
          )
          project = data["project"]["version"]
          briefcase = data["tool"]["briefcase"]["version"]
          tag = os.environ["TAG_VERSION"].lstrip("v")
          assert tag == project == briefcase, (
              f"Version mismatch: tag={tag!r} project={project!r} "
              f"briefcase={briefcase!r}"
          )
          print(f"Version guard OK: {tag}")
          PY

  windows:
    needs: guard
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run briefcase package windows -p msi
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/**/*.msi

  macos:
    needs: guard
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run briefcase package macos -p dmg
      - uses: softprops/action-gh-release@v2
        with:
          files: dist/**/*.dmg

  linux:
    needs: guard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run briefcase upgrade linuxdeploy
      - run: uv run briefcase package linux -p deb
      - run: uv run briefcase package linux -p appimage
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/**/*.deb
            dist/**/*.AppImage
```

- [ ] **Step 2: Verify the guard snippet locally (both scenarios)**

Run (match):
```bash
uv run python - <<'PY'
import os, pathlib, tomllib
os.environ["TAG_VERSION"] = "v2026.8.0"
data = tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))
project = data["project"]["version"]; briefcase = data["tool"]["briefcase"]["version"]
tag = os.environ["TAG_VERSION"].lstrip("v")
assert tag == project == briefcase, f"mismatch: {tag} {project} {briefcase}"
print("OK")
PY
```
Expected: `OK`.

Run (mismatch must fail):
```bash
TAG_VERSION=v0.0.1 uv run python -c "import os,pathlib,tomllib; data=tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); tag=os.environ['TAG_VERSION'].lstrip('v'); assert tag==data['project']['version']==data['tool']['briefcase']['version'], 'mismatch'"
```
Expected: exits non-zero with `mismatch` (AssertionError).

Also validate YAML parses:
```bash
uv run python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/release.yml').read_text(encoding='utf-8')); print('yaml OK')"
```
Expected: `yaml OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci(release): 3-OS briefcase packaging pipeline with version guard"
```

---

### Task 6: PR dry-run packaging workflow

**Files:**
- Create: `.github/workflows/build-windows.yml`

**Interfaces:**
- Consumes: same repo state as Task 5 (no artifact upload to releases).
- Produces: a per-PR Windows bundle artifact proving packaging still works.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/build-windows.yml`:

```yaml
name: Windows packaging dry-run

on:
  pull_request:
    paths:
      - "pyproject.toml"
      - "src/**"
      - ".github/workflows/build-windows.yml"
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run briefcase build windows
      - uses: actions/upload-artifact@v4
        with:
          name: ProFiles-windows-bundle
          path: windows/ProFiles/
          retention-days: 7
```

- [ ] **Step 2: Validate YAML and commit**

Run: `uv run python -c "import yaml,pathlib; yaml.safe_load(pathlib.Path('.github/workflows/build-windows.yml').read_text(encoding='utf-8')); print('yaml OK')"`
Expected: `yaml OK`.

```bash
git add .github/workflows/build-windows.yml
git commit -m "ci(pr): windows packaging dry-run on pyproject/src changes"
```

---

### Task 7: Installation docs — EN

**Files:**
- Modify: `docs/installation-guide.en.md` (insert new Methods 1–2 after `## Prerequisites` line 13; renumber existing "Method 1: Installation with Wizard" → "Method 3" and "Method 2: Manual Installation" → "Method 4"; delete the old `## Method 4: Native Installer (Briefcase)` section lines 712-744; add a deprecated-Tk section)

**Interfaces:**
- Consumes: release artifact names from Task 5; `uv tool install` command shape.
- Produces: doc order = native installer → one-line dev install → wizard → manual; Tk marked deprecated.

- [ ] **Step 1: Insert the two new methods after `## Prerequisites`**

```markdown
## Method 1: Native Installer (Recommended — no Python required)

Download the installer for your platform from the
[Releases](../../releases) page and double-click it:

- **Windows**: `ProFiles-<version>.msi` — run it; if SmartScreen warns,
  click **More info → Run anyway**. A Start Menu entry and desktop
  shortcut are created.
- **macOS**: `ProFiles-<version>.dmg` — open it and drag `ProFiles.app`
  to `/Applications`. First launch: right-click → **Open** (builds are
  not signed).
- **Linux**: `profiles_<version>_amd64.deb`
  (`sudo dpkg -i ... && sudo apt-get install -f`) or
  `ProFiles-<version>.AppImage` (`chmod +x`, then double-click — no
  installation required).

Launch ProFiles from your Start Menu (Windows), `/Applications` (macOS),
or your application launcher (Linux). No Python installation is needed.

## Method 2: One-Line Install (Developers)

Requires Python 3.11+ on the machine.

```bash
# Variant A — from PyPI (when published)
uv tool install profiles-app

# Variant B — from a GitHub release wheel
uv tool install profiles-app --from <url-to-profiles_app-<version>-py3-none-any.whl>

# pipx equivalent
pipx install profiles-app
```

Upgrade with `uv tool upgrade profiles-app`. The `profiles` and
`ProFiles` commands land on your PATH automatically.
```

- [ ] **Step 2: Renumber and clean up**

1. Rename `## Method 1: Installation with Wizard (Recommended)` → `## Method 3: Installation with Wizard` (wizard is no longer the recommended path).
2. Rename `## Method 2: Manual Installation` → `## Method 4: Manual Installation`.
3. Delete the entire `## Method 4: Native Installer (Briefcase)` section (lines 712-744) — its content moved to Method 1.
4. Insert this section right after the Usage Modes section:

```markdown
## Tkinter Backend (Deprecated)

The original Tkinter frontend is **deprecated** (developer/advanced use
only) and will be removed in a future release. The web backend
(pywebview + FastAPI, the default) replaces it.

```bash
profiles --tkinter   # prints a deprecation banner, then launches Tk GUI
```

Tk-mode dependencies (`sv-ttk`, `darkdetect`) are dev-only: install with
`pip install -e ".[dev]"` or `uv sync`. Inside Briefcase bundles the
Tkinter backend is not available — use the default web GUI.
```

5. In `### Main Dependencies` (lines 125-130), replace the sv-ttk/darkdetect bullet list with:

```markdown
- `pywebview` + `fastapi`/`uvicorn` — web GUI backend (default)
- `sv-ttk`, `darkdetect` — **dev-only** since 2026.8, for the deprecated Tkinter backend
```

- [ ] **Step 3: Review the rendered flow**

Read the modified file top-to-bottom; confirm ordering (native → one-line → wizard → manual), no duplicated content between old Method 4 and new Method 1, and every internal anchor in the header nav still points at a real heading. Fix any stale anchor.

- [ ] **Step 4: Commit**

```bash
git add docs/installation-guide.en.md
git commit -m "docs(install): native installer first, uv tool second; mark Tk deprecated"
```

---

### Task 8: Installation docs — FR + README

**Files:**
- Modify: `docs/installation-guide.fr.md` (mirror Task 7 changes; the guide already labels Tk "Mode Tkinter Historique (obsolète)" line 269 — strengthen it)
- Modify: `README.md` (`## 🚀 Installation` section, lines 64-124)

**Interfaces:**
- Consumes: same artifact names and commands as Task 7.
- Produces: EN/FR parity; README's install section leads with native installer + one-liner.

- [ ] **Step 1: FR guide**

1. Insert after `## Prérequis` (line 13):

```markdown
## Méthode 1 : Installateur Natif (Recommandé — sans Python)

Téléchargez l'installateur de votre plateforme depuis la page
[Releases](../../releases) et double-cliquez :

- **Windows** : `ProFiles-<version>.msi` — exécutez-le ; si SmartScreen
  vous alerte, cliquez sur **Plus d'infos → Exécuter quand même**.
- **macOS** : `ProFiles-<version>.dmg` — glissez `ProFiles.app` vers
  `/Applications`. Premier lancement : clic droit → **Ouvrir**.
- **Linux** : `profiles_<version>_amd64.deb`
  (`sudo dpkg -i ... && sudo apt-get install -f`) ou
  `ProFiles-<version>.AppImage` (`chmod +x`, puis double-clic).

Aucune installation de Python n'est requise.

## Méthode 2 : Installation en une ligne (Développeurs)

Nécessite Python 3.11+.

```bash
# Variante A — depuis PyPI (une fois publié)
uv tool install profiles-app

# Variante B — depuis une wheel de release GitHub
uv tool install profiles-app --from <url-de-la-wheel>

# équivalent pipx
pipx install profiles-app
```

Mise à jour : `uv tool upgrade profiles-app`.
```

2. Rename `## Méthode 1 : Installation avec l'Assistant (Recommandé)` → `## Méthode 3 : Installation avec l'Assistant`.
3. Rename `## Méthode 2 : Installation Manuelle` → `## Méthode 4 : Installation Manuelle`.
4. In `### Mode Tkinter Historique (obsolète)` (line 269), append:

```markdown
> ⚠ **Déprécié** : usage développeur/avancé uniquement ; sera supprimé
> dans une version future. Dépendances (`sv-ttk`, `darkdetect`)
> désormais en extras dev : `pip install -e ".[dev]"`. Indisponible
> dans les bundles Briefcase — utilisez le mode web par défaut.
```

- [ ] **Step 2: README**

Replace the `## 🚀 Installation` intro + `### Quick Install (Recommended)` block (lines 64-84) with:

```markdown
## 🚀 Installation

### Option 1: Native Installer (Recommended)

Download the installer for your OS from
[Releases](../../releases) and double-click — no Python required:

- Windows: `ProFiles-<version>.msi`
- macOS: `ProFiles-<version>.dmg`
- Linux: `.deb` or `.AppImage`

### Option 2: One-Line Install (Developers)

```bash
uv tool install profiles-app      # or: pipx install profiles-app
```

*(requires Python 3.11+; from GitHub release wheel: add `--from <wheel-url>`)*

### Option 3: Wizard / Manual
```

Keep the existing `python install.py` wizard content and the `pip install .` / `uv sync` / `poetry` options under the new `### Option 3: Wizard / Manual` heading (rename the old `### Manual Install` accordingly and merge duplicate pip/pipx lines).

- [ ] **Step 3: Parity review + commit**

Compare EN and FR section-by-section (same method numbers, same commands); confirm README renders without broken relative links.

```bash
git add docs/installation-guide.fr.md README.md
git commit -m "docs: FR install guide + README native-first reorder (EN/FR parity)"
```

---

### Task 9: Final quality gate + local Briefcase smoke

**Files:**
- No file changes expected (fix-forward if gates fail).

**Interfaces:**
- Consumes: everything above.
- Produces: evidence for spec acceptance criteria §7.2 (bundle boots) and §7.8 (local make target), plus the final commit if any fix was needed.

- [ ] **Step 1: Full quality gate**

Run: `uv run ruff format . && uv run ruff check . && uv run pylint src/profiles --fail-under=8.0 && uv run pytest`
Expected: all green; coverage ≥ 85 %.

- [ ] **Step 2: Verify untouched constraints**

Run: `git diff 0cbe92e..HEAD --stat -- install.py` and `git diff 0cbe92e..HEAD -- Makefile | grep -A2 "install-system:" | head -8`
Expected: first diff shows only the `install.py` line from the spec commit context (empty diff for install.py itself); the `install-system` target body unchanged (`pip install .`).

- [ ] **Step 3: Local Briefcase smoke (manual, may take several minutes)**

Run: `uv run briefcase build windows && uv run briefcase run profiles`
Expected: bundle builds; the app window opens (web GUI in the pywebview shell) — this is the machine-local proof of spec §7.2. Then `make -n briefcase-package-local` to confirm dispatch (spec §7.8 dry-run level).

- [ ] **Step 4: Push the branch**

Run: `git push -u origin feat/web-migration`
Expected: PR CI (`build-windows.yml`) goes green.

---

## Self-Review Notes

- **Spec coverage:** §5.1→Task 2, §5.2→Task 1, §5.3→Tasks 2+3, §5.4→Tasks 4+5+6, §5.5→Tasks 7+8, §5.6→Tasks 1+2+9, §7 criteria 1–9 mapped (1→Task 5, 2→Task 9, 3–4→Task 1, 5→Task 2, 6→Tasks 7+8, 7→Task 9, 8→Task 4, 9→Task 9). PyPI publishing stays optional per spec non-goal — Variant A docs included, Variant B always works.
- **Placeholders:** none — every code step carries real code/YAML/text.
- **Type consistency:** `_TKINTER_DEPRECATION_BANNER` / `_TKINTER_UNAVAILABLE_MSG` names identical across Task 1 steps and tests; `HOST_PKG` defined once (Task 4) and used by `briefcase-package-local`; artifact globs in Task 5 match the names listed in Task 7/8 docs.
- **Review Focus:** all five items pinned (1→Task 1 tests + Task 9 smoke, 2→Task 1, 3→Task 5, 4→Task 2, 5→Task 3).
