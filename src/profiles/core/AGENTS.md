# AGENTS.md — `src/profiles/core/` Guide

Context for AI agents working on the **core domain layer** of ProFiles.
Read this before editing any file in `src/profiles/core/`.

---

## 🎯 What lives here

The `core/` package contains **all domain logic** — zero GUI / Tkinter
dependencies, pure stdlib, reusable by GUI, CLI, and any future TUI.

The package is split into SOLID-aligned sub-packages so that each one
owns a single responsibility:

| Sub-package / file       | Responsibility (SRP)                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------ |
| `config/__init__.py`     | Single point of egress for the configuration subsystem (high-level API)              |
| `config/models.py`       | Pure dataclasses (`AppConfig`, `MachineConfiguration`, `ColumnConfiguration`, `HookSpec`) |
| `config/service.py`      | Domain operations over `AppConfig` — find, merge, auto-select directories            |
| `config/template.py`     | `STARTER_CONFIG_TEMPLATE` string — canonical starter `.profiles` body                |
| `config/loader.py`       | Top-level entry points: `load_config`, `propose_config_creation`                     |
| `config/reader.py`       | `ConfigReader` class — composes io primitives + models, knows INI structure           |
| `config/io/__init__.py`  | Egress for low-level INI serialization layer                                          |
| `config/io/ini_primitives.py` | Pure INI primitives (`parse_bool`, `find_config_file`) — no AppConfig coupling    |
| `config/io/writer.py`    | Pure INI writer (`_write_config_value`, `save_config_bool`, `save_config_str`)        |
| `environment/__init__.py` | Egress for OS environment & process spawn                                            |
| `environment/system.py`  | System info collection (`SystemInfo`, `collect_system_info`)                         |
| `environment/execution.py` | Launch hooks engine (`HookOutcome`, `parse_hook_entries`, `run_hooks_for_file`, …)  |
| `processing/__init__.py` | Egress for file scanning / classification / column extraction                        |
| `processing/scanner.py`  | File scanning + filtering pipeline (`scan_and_process`, `ScannedFile`, …)             |
| `processing/column_extractor.py` | Regex-based dynamic column extraction (`ColumnRule`, `ColumnExtractor`, …)     |
| `processing/file_classifier.py` | File-level domain helpers (`get_file_info`, `extract_version`, …)              |
| `telemetry/__init__.py`  | Egress for logging & diagnostics                                                     |
| `telemetry/diagnostics.py` | `LoggerFactory`, `SourceFilter`, `configure_logger`, `get_logger`                 |
| `actions.py`             | Domain actions — file launch, config open, log open (returns `ActionResult`, never raises) |
| `__init__.py`            | Re-exports the public core API for callers (`from profiles.core import …`)            |

---

## 🚫 Hard rules — never break

| Rule | Reason |
| --- | --- |
| **NO Tkinter imports** | Core must stay reusable from CLI / TUI |
| **NO imports from `profiles.gui.*`** | Breaks the layered architecture |
| **Pure functions where possible** | Testability, referential transparency |
| **Return typed structures** — never `None` for collections | Callers can iterate without `if x is not None` |
| **Type hints on every public signature** | Project standard (`py.typed` shipped) |
| **Docstrings on every public function/class** | Project standard (see AGENTS.md at repo root) |
| **`from __future__ import annotations`** at top of every file | PEP 563 forward refs |

---

## ✅ Adding a new module to `core/`

1. **Place it under the right sub-package** — does it configure, scan, log, or run OS-level actions?
2. **One responsibility** — if you need "and", split into two modules.
3. **No GUI / CLI coupling** — pure domain only.
4. **Re-export public API** from the appropriate sub-package `__init__.py`
   so callers can do `from profiles.core.config import …` (etc.).
5. **Add a test** in `tests/test_<module>.py` (see `tests/AGENTS.md`).
6. **Update this file** with the new module's row in the table above.

---

## 🔄 Configuration pipeline (how the sub-packages fit together)

```
Caller (GUI / CLI)
        │
        ▼
core.config.load_config(path)         ← top-level entry point
        │
        ├── core.config.io.find_config_file      ← discovers .profiles
        │
        └── core.config.reader.ConfigReader(path).load()
                │
                ├── core.config.io.parse_bool
                ├── core.config.models.AppConfig / MachineConfiguration / …
                └── (writes populated AppConfig back to caller)
                        │
                        ▼
                core.config.service.*             ← pure operations over AppConfig
                        │
                        ├── find_active_config
                        ├── find_configuration_by_hostname
                        ├── merge_config_overrides
                        ├── auto_select_directory
                        └── get_unique_directories
```

---

## ✏️ Editing conventions

- **Constants** at module top in `UPPER_SNAKE_CASE` (`_COLUMN_SECTION_PREFIX_LEN`).
- **Default sentinel values** as module-level constants when reused
  (e.g. `_DEFAULT_FILE_COLUMN_WIDTH = 600`).
- **Static methods** on `ConfigReader` are reserved for *thin wrappers* over
  primitives in `config.io.ini_primitives` (back-compat shims) — real parsing
  logic lives in the primitive module.
- **`@staticmethod` vs free function** — prefer free function in the dedicated
  module; only add a `staticmethod` wrapper on `ConfigReader` when preserving
  back-compat for downstream callers (e.g. `ConfigReader._parse_bool`).
- **Logging** via `logging.getLogger("profiles")` — never configure handlers
  here; that lives in `telemetry/diagnostics.py`.

---

## 🧪 Quick verification

```bash
# Lint + format
ruff check src/profiles/core/
ruff format --check src/profiles/core/

# Pylint must stay ≥ 9.88/10
pylint src/profiles/core/

# Targeted tests
pytest tests/test_config.py -v

# Full suite (skips GUI clipboard tests on headless macOS)
pytest tests/ --ignore=tests/test_context_menu.py -q
```

A change here is **done** only when: ruff clean, pylint ≥ 9.88, full pytest green,
**and** `from profiles.config import <symbol>` still works (`src/profiles/config.py`
re-exports the public config API for convenience).
