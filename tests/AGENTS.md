# AGENTS.md — Test Suite Guide for AI Agents

This file provides context and instructions for AI agents working on the ProFiles test suite.

## Project Overview

ProFiles is a desktop + web application: the default frontend is web (React in `src/profiles/web`, FastAPI server in `src/profiles/server`, PyWebView shell in `src/profiles/desktop`). The Tkinter GUI (`src/profiles/gui/`) is **deprecated** — its tests are skipped (see *Test File Organization*) pending removal in phase 2 of the deprecation plan.

**Key technical constraints:**
- **Python 3.11+** with `from __future__ import annotations`
- **Runtime dependencies** declared in `pyproject.toml` (pydantic, fastapi, uvicorn, pywebview, ruamel.yaml, …) — briefcase/dev extras are separate
- **Cross‑platform** — `os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux
- **Type hints throughout** — no `Any`, no `# type: ignore`
- **Ruff + Pylint** for linting (both pass at 10/10)

## Testing Principles

1. **Comprehensive coverage** — the suite gate is 85% (`--cov-fail-under`); aim for 90%+ on every module
2. **Mock platform‑specific calls** — always mock `os.startfile`, `subprocess.run`, `socket.socket`, etc.
3. **Test-only dependencies** — pytest, pytest-cov, pytest-mock, plus `httpx` for server-route tests
4. **No Tkinter mainloop** — GUI tests use widget creation but never call `mainloop()`
5. **Reset global state** — the `profiles` logger is module‑level; tests must clean up between runs

## Test File Organization

Test files mirror the `src/profiles/` package tree 1:1 — each source module `X.py` has a matching `test_X.py` at the mirrored path. Every test directory is a package (`__init__.py`), mirroring `src/profiles`, which also lets two directories share a test-file basename (e.g. `tests/test_app.py` for `app.py` and `tests/server/test_app.py` for `server/app.py`).

**Supplementary test files** for the same source module live beside `test_X.py` and are named `test_X_<topic>.py` (e.g. `test_file_utils_launch.py` for `utils/file_utils.py`, `test_config_load.py` under `tests/server/routes/` for `server/routes/config.py`).

```
tests/
├── conftest.py                               # os.startfile polyfill (root)
├── test_app.py                               # ← app.py
├── test_app_backend_selection.py             # ← app.py (supplement: --tkinter/web backend routing)
├── test_app_launch_resolution.py             # ← app.py (supplement: launch config resolution)
├── test_app_log_path.py                      # ← app.py (supplement: CWD-independent log path)
├── test_app_no_tkinter.py                    # ← app.py (supplement: web/headless run with tkinter blocked)
├── test_app_tk_lifecycle.py                  # ← app.py (supplement: deprecated tk branch — module-skipped)
├── test_config.py                            # ← config.py (shim re-exports)
├── characterization/                         # cross-cutting golden baseline (see exceptions)
├── core/
│   ├── test_actions.py                       # ← core/actions.py
│   ├── config/
│   │   ├── test_inheritance.py               # ← core/config/inheritance.py
│   │   ├── test_loader.py                    # ← core/config/loader.py
│   │   ├── test_matcher.py                   # ← core/config/matcher.py
│   │   ├── test_models.py                    # ← core/config/models.py
│   │   ├── test_models_workflow.py           # ← core/config/models.py (supplement: WorkflowStep)
│   │   ├── test_reader.py                    # ← core/config/reader.py
│   │   ├── test_reader_robustness.py         # ← core/config/reader.py (supplement: bad YAML/validation)
│   │   ├── test_reader_workflow.py           # ← core/config/reader.py (supplement: hook steps)
│   │   ├── test_conditions.py                # ← core/config/conditions.py (grammaire if: #8)
│   │   ├── test_schema.py                    # ← core/config/schema.py
│   │   ├── test_schema_coercion.py           # ← core/config/schema.py (supplement: MatchCriteria coercion)
│   │   ├── test_service.py                   # ← core/config/service.py
│   │   ├── test_template.py                  # ← core/config/template.py
│   │   ├── test_validator.py                 # ← core/config/validator.py
│   │   └── io/
│   │       └── test_yaml_io.py               # ← core/config/io/yaml_io.py
│   ├── environment/
│   │   ├── test_execution.py                 # ← core/environment/execution.py
│   │   ├── test_interactions.py              # ← core/environment/interactions.py
│   │   ├── test_matcher.py                   # ← core/environment/matcher.py
│   │   ├── test_message_dialog.py            # ← core/environment/message_dialog.py
│   │   ├── test_render.py                    # ← core/environment/render.py
│   │   ├── test_system.py                    # ← core/environment/system.py
│   │   └── test_workflow.py                  # ← core/environment/workflow.py (+test_workflow_integration.py)
│   ├── processing/
│   │   ├── test_column_extractor.py          # ← core/processing/column_extractor.py (+…_refactored.py)
│   │   ├── test_file_classifier.py           # ← core/processing/file_classifier.py
│   │   ├── test_file_metadata.py             # ← core/processing/file_metadata.py
│   │   ├── test_public_api.py                # ← core/processing/__init__.py re-exports (exception)
│   │   └── test_scanner.py                   # ← core/processing/scanner.py
│   │       (+ _dedupe/_errors/_excludes/_parity/_pushdown supplements)
│   └── telemetry/
│       ├── test_diagnostics.py               # ← core/telemetry/diagnostics.py
│       ├── test_events.py                    # ← core/telemetry/events.py
│       └── test_metrics.py                   # ← core/telemetry/metrics.py
├── desktop/
│   └── test_lifecycle.py                     # ← desktop/lifecycle.py   (launcher.py: no test yet)
├── gui/                                      # DEPRECATED — conftest.py skip-marks everything here
│   ├── conftest.py                           # skip mark: tkinter deprecation
│   ├── test_context_menu.py                  # ← gui/context_menu.py
│   ├── test_i18n.py                          # ← gui/i18n.py
│   ├── test_main_window.py                   # ← gui/main_window.py
│   ├── test_main_window_shortcuts.py         # ← gui/main_window.py (supplement: shortcuts dialog)
│   ├── test_search_bar.py                    # ← gui/search_bar.py
│   ├── test_status_bar.py                    # ← gui/status_bar.py
│   ├── test_styles.py                        # ← gui/styles.py
│   ├── test_theme.py                         # ← gui/theme.py
│   ├── test_ui.py                            # ← gui/ui.py
│   ├── controllers/                          # ← gui/controllers/{directory_manager,scan_controller,window_actions}.py
│   └── presentation/test_row_colors.py       # ← gui/presentation/row_colors.py
├── launch/
│   ├── test_context.py                       # ← launch/context.py
│   ├── test_creation.py                      # ← launch/creation.py
│   └── test_resolution.py                    # ← launch/resolution.py
├── packaging/                                # cross-cutting (no single source module)
│   ├── test_entry_point.py                   # profiles/__init__ lazy main + Briefcase stub
│   ├── test_packaging.py                     # pyproject/briefcase dependency rules
│   └── test_shortcut_launch.py               # ProFiles.pyw launcher stub behavior
├── server/
│   ├── test_app.py                           # ← server/app.py (FastAPI factory + client telemetry)
│   ├── test_barcode_integration.py           # cross-cutting server integration (exception)
│   ├── test_static.py                        # ← server/static.py
│   └── routes/
│       ├── test_actions.py                   # ← server/routes/actions.py
│       ├── test_config.py                    # ← server/routes/config.py (+test_config_load.py)
│       ├── test_fs.py                        # ← server/routes/fs.py
│       ├── test_logs.py                      # ← server/routes/logs.py
│       ├── test_scan.py                      # ← server/routes/scan.py
│       ├── test_system.py                    # ← server/routes/system.py
│       └── test_workflow.py                  # ← server/routes/workflow.py
├── utils/
│   ├── test_file_utils.py                    # ← utils/file_utils.py
│   │   (+ _classify/_errors/_excludes/_launch/_suffix_parity supplements)
│   ├── test_network.py                       # ← utils/network.py
│   ├── test_search_parser.py                 # ← utils/search_parser.py (+_compiled.py supplement)
│   └── test_shortcut.py                      # ← utils/shortcut.py
└── web/
    ├── test_build.py                         # ← web/build.py
    └── test_build_hook.py                    # ← web/build_hook.py
```

**Documented exceptions (cross-cutting, no single source module):**
- `tests/characterization/` — frozen golden baseline for the scanner + search-parser pipeline (`fixtures.py` builds the fixture tree, `generate_golden.py` regenerates `golden/scan_baseline.json`; only regenerate when a pipeline change is intentional).
- `tests/core/processing/test_public_api.py` — tests the `core/processing/__init__.py` re-exports (a package init, not a module).
- `tests/packaging/` — packaging rules, entry-point stub, and `ProFiles.pyw` launcher-stub behavior.
- `tests/server/test_barcode_integration.py` — end-to-end server integration (app + state + routes).

**Known coverage gaps (mirrored test file does not exist yet):**
`core/telemetry/log_viewer.py`, `desktop/launcher.py`, `server/state.py` — `server/state.py` is partially exercised through `tests/server/test_app.py`.

**Deprecated Tkinter isolation:** everything under `tests/gui/` is skip-marked by `tests/gui/conftest.py` with a deprecation reason, and `tests/test_app_tk_lifecycle.py` carries the same module-level skip. These files are deleted together with `src/profiles/gui` in phase 2.

## Writing Tests

### Style Guide

```python
"""Short module description."""

from __future__ import annotations

import pytest

from profiles.module import PublicAPI


class TestFeature:
    """Group of tests for one feature."""

    def test_success_case(self) -> None:
        """What this test verifies."""
        result = PublicAPI()
        assert result == expected
```

### What to Mock

| Function                 | How to Mock                                           |
|--------------------------|-------------------------------------------------------|
| `os.startfile`           | `mocker.patch("os.startfile")`                        |
| `socket.socket`          | `mocker.patch("socket.socket")` with MagicMock        |
| `platform.node()`        | `mocker.patch("platform.node", return_value="...")`   |
| `getpass.getuser()`      | `mocker.patch("getpass.getuser", return_value="...")` |
| `logging.handlers`       | Use `tmp_path` for log file, verify file contents     |
| `tkinter.Tk()`           | Create in fixture, destroy after (only in `tests/gui`) |

### Common Pitfalls

- **Logger state leakage**: The `profiles` logger is global. Always reset handlers between tests using `logging.getLogger("profiles").handlers.clear()`.
- **Tkinter tests are skipped**: `tests/gui/**` and `tests/test_app_tk_lifecycle.py` are skip-marked (deprecated frontend). Do not un-skip them; they are removed in phase 2.
- **Python 3.13 logger reentrancy**: records logged through `Logger.handle` from inside a handler callback are silently dropped (thread-local guard). In-handler telemetry must go through `profiles.core.telemetry.diagnostics.emit_event_through_handlers`.
- **pytest-qt excepthook capture**: pytest-qt (if installed) fails any test routing an exception through `sys.excepthook`. Tests that deliberately exercise the crash hook carry the `qt_no_exception_capture` marker (registered in `pyproject.toml`).
- **Platform‑specific paths**: Use `os.sep` or `pathlib.Path` for cross-platform path handling.
- **Config file encoding**: Always use `encoding="utf-8"` when reading/writing files.

## Configuration Reference

The test configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
pythonpath = [".", "src"]
addopts = [
    "--cov=src/profiles",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=85",
]
markers = [
    "qt_no_exception_capture: disable pytest-qt exception capture for this test",
]
```

`.coveragerc` sets `branch = True`, omits `tests/`, `__main__.py` and the deprecated `profiles/gui/` package, and enforces `fail_under = 85`.

This makes `pytest` discover tests in the `tests/` directory and add both the repo root and `src/` to `sys.path` so imports like `from profiles.config import ...` work without installation.

## Adding a New Test File

1. Create `tests/<mirrored-dir>/test_<module>.py` matching the source path. Example: `src/profiles/core/config/loader.py` → `tests/core/config/test_loader.py`.
2. The test file name must match the source module name: `loader.py` → `test_loader.py`. Supplementary files use `test_<module>_<topic>.py`.
3. Every test directory is a package: keep its `__init__.py` (create one for new directories, mirroring `src/profiles`).
4. Add shared fixtures to root `tests/conftest.py` — auto‑inherited by all subdirs. Subdir‑specific fixtures go in `tests/<subdir>/conftest.py`.
5. Update `tests/README.md` with the new file.
6. Verify with `pytest tests/<mirrored-dir>/test_<module>.py -v`

## Conftest Notes

- Root `tests/conftest.py` polyfills `os.startfile` on non-Windows (needed by launch tests across all subdirs) and provides the `sample_config_path` / `empty_config_path` fixtures.
- `tests/gui/conftest.py` applies the Tkinter-deprecation skip to everything collected under `tests/gui/`.
- `tests/characterization/` manages its own `fixtures.py` module and golden JSON; it manipulates `sys.path` locally, so avoid importing from it elsewhere.
