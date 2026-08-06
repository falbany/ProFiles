# AGENTS.md — Test Suite Guide for AI Agents

This file provides context and instructions for AI agents working on the ProFiles test suite.

## Project Overview

ProFiles is a pure-stdlib Python application (no external dependencies beyond `pytest`). It uses Tkinter for GUI, `configparser` for INI file reading, and `os.startfile` / `open` / `xdg-open` for file launching on Windows / macOS / Linux respectively.

**Key technical constraints:**
- **Python 3.11+** with `from __future__ import annotations`
- **No external runtime dependencies** — only pytest family for testing
- **Cross‑platform** — `os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux
- **Type hints throughout** — no `Any`, no `# type: ignore`
- **Ruff + Pylint** for linting (both pass at 10/10)

## Testing Principles

1. **Comprehensive coverage** — aim for 90%+ statement coverage on every module
2. **Mock platform‑specific calls** — always mock `os.startfile`, `subprocess.run`, `socket.socket`, etc.
3. **No external dependencies** — tests use only `pytest`, `pytest-cov`, `pytest-mock`
4. **No Tkinter mainloop** — GUI tests use widget creation but never call `mainloop()`
5. **Reset global state** — the `profiles` logger is module‑level; tests must clean up between runs

## Test File Organization

Test files mirror the `src/profiles/` package tree 1:1 — each source module `X.py` has a matching `test_X.py` at the mirrored path.

```
tests/
├── conftest.py                              # os.startfile polyfill + pytest_configure
├── test_app.py                              # ← src/profiles/app.py
├── core/
│   ├── test_actions.py                      # ← src/profiles/core/actions.py
│   ├── config/
│   │   ├── test_models.py                   # ← core/config/models.py
│   │   ├── test_service.py                  # ← core/config/service.py
│   │   ├── test_loader.py                   # ← core/config/loader.py
│   │   ├── test_reader.py                   # ← core/config/reader.py
│   │   └── io/
│   │       ├── test_ini_primitives.py       # ← core/config/io/ini_primitives.py
│   │       └── test_writer.py               # ← core/config/io/writer.py
│   ├── environment/
│   │   ├── test_system.py                   # ← core/environment/system.py
│   │   └── test_execution.py                # ← core/environment/execution.py
│   ├── processing/
│   │   ├── test_scanner.py                  # ← core/processing/scanner.py
│   │   ├── test_file_classifier.py          # ← core/processing/file_classifier.py
│   │   └── test_column_extractor.py         # ← core/processing/column_extractor.py
│   └── telemetry/
│       └── test_diagnostics.py              # ← core/telemetry/diagnostics.py
├── gui/
│   ├── test_main_window.py                  # ← gui/main_window.py (+ context menu, restart, no-config, key bindings)
│   ├── test_ui.py                           # ← gui/ui.py
│   ├── test_styles.py                       # ← gui/styles.py
│   ├── test_theme.py                        # ← gui/theme.py
│   ├── test_search_bar.py                   # ← gui/search_bar.py
│   └── test_status_bar.py                   # ← gui/status_bar.py
└── utils/
    ├── test_file_utils.py                   # ← utils/file_utils.py
    ├── test_network.py                      # ← utils/network.py
    └── test_search_parser.py                # ← utils/search_parser.py
```

Source modules without dedicated tests: `config.py` (shim re‑exporting core.config), `core/config/template.py` (indirect via actions), `core/config/io/__init__.py`, `gui/context_menu.py` (helpers consumed by MainWindow, tested via test_main_window.py), `utils/shortcut.py`.

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
| `tkinter.Tk()`           | Create in fixture, destroy after (only for styles)    |

### Common Pitfalls

- **Logger state leakage**: The `profiles` logger is global. Always reset handlers between tests using `logging.getLogger("profiles").handlers.clear()`.
- **Tkinter in headless CI**: Tests that create Tk widgets should be minimal and never call `mainloop()`. The `test_styles.py` tests create/destroy Tk roots in fixtures.
- **Platform‑specific paths**: Use `os.sep` or `pathlib.Path` for cross‑platform path handling.
- **Config file encoding**: Always use `encoding="utf-8"` when reading/writing INI files.

## Configuration Reference

The test configuration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
pythonpath = ["src"]
```

This makes `pytest` discover tests in the `tests/` directory and add `src/` to `sys.path` so imports like `from profiles.config import ...` work without installation.

## Adding a New Test File

1. Create `tests/<mirrored-dir>/test_<module>.py` matching the source path. Example: `src/profiles/core/config/loader.py` → `tests/core/config/test_loader.py`.
2. The test file name must match the source module name: `loader.py` → `test_loader.py`.
3. Add shared fixtures to root `tests/conftest.py` — auto‑inherited by all subdirs. Subdir‑specific fixtures go in `tests/<subdir>/conftest.py`.
4. Update `tests/README.md` table with the new file.
5. Verify with `pytest tests/<mirrored-dir>/test_<module>.py -v --cov=profiles.<module>`

## Conftest Notes

Root `tests/conftest.py` polyfills `os.startfile` on non‑Windows (needed by launch tests across all subdirs) and registers the `requires_tkinter` pytest marker. The fixture functions `sample_profile_conf`, `sample_files`, `config_with_profile` are currently unused — slated for cleanup in a separate commit.
