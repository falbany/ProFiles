# GUI SOLID Refactor — Design Spec

Date: 2026-08-29
Status: Draft (pending user review)
Scope: `src/profiles/gui/**` — maintainability, SOLID conformance, folder organization

## Problem

`gui/main_window.py` is a 1,526-line god object (60+ methods) that owns all state,
builds UI, handles every event, contains pure-domain helpers, and exposes ~40 widget
attributes that sibling modules (`context_menu.py`, `ui.py`) reach into directly —
hence pervasive `# pylint: disable=protected-access`.

Consequences:
- Any GUI change requires reading the whole file (fails "understand in isolation").
- Components are untestable without constructing a full `MainWindow` + Tk root.
- Pure logic (WCAG contrast math, row-color rules) is buried inside the view class.
- SOLID violations: SRP across the board; ISP (components depend on the entire window
  surface); DIP (concrete widget access instead of abstractions).

## Target Structure

```
gui/
├── __init__.py               # public re-exports (MainWindow)
├── main_window.py            # thin orchestrator, target ≤ ~500 lines
├── components/               # self-contained widgets
│   ├── __init__.py
│   ├── search_bar.py         # moved, internals unchanged
│   ├── status_bar.py         # moved, internals unchanged
│   ├── context_menu.py       # moved, decoupled via TreeSelectionProvider
│   └── shortcuts.py          # keyboard-shortcuts dialog (extracted from MainWindow)
├── controllers/              # coordinators: no widget construction, own flow logic
│   ├── __init__.py
│   ├── scan_controller.py    # scan thread, queue polling, chunked insert, progress
│   ├── directory_manager.py  # dir entries, resolution, auto-select, config overrides
│   └── window_actions.py     # config/log open, refresh, restart
├── presentation/             # pure look & feel
│   ├── __init__.py
│   ├── theme.py              # moved + absorbs _hex_luminance/_contrast_ratio
│   ├── styles.py             # moved; ToolTip stays here
│   ├── ui.py                 # moved (layout builder)
│   └── row_colors.py         # pure filename → tags logic
└── services/
    ├── __init__.py
    └── i18n.py               # moved
```

Tests mirror source: `tests/gui/components/`, `tests/gui/controllers/`, `tests/gui/presentation/`, `tests/gui/services/`.

## Design

### Dependency rule (fixes protected-access coupling)

Controllers/components never receive the whole `MainWindow`. Each takes:

- **State in**: only the specific widgets/vars it needs (`tree: ttk.Treeview`, `dir_var: tk.StringVar`)
- **Callbacks out**: `on_status(text)`, `on_count(n)`, `on_log(...)` — the existing
  `SearchBar`/`StatusBar` callback pattern, generalized.

Each package `__init__.py` re-exports public names so imports read:

```python
from profiles.gui.controllers import ScanController, DirectoryManager, WindowActions
from profiles.gui.presentation import Md3Theme, RowColorRules
```

### Context-menu facade

```python
class TreeSelectionProvider(Protocol):
    def selected_path(self) -> Path | None: ...
    def selected_filename(self) -> str | None: ...
    def current_directory_label(self) -> str: ...
```

`FileContextMenu(window)` becomes `FileContextMenu(provider, on_status, ...)`.
The provider is implemented by a thin adapter owned by `MainWindow`. The 17
pass-through `_action_*` methods in `MainWindow` collapse into direct wiring at
construction.

### Responsibility map

| Unit | Owns | Pure (no Tk needed to test) |
|---|---|---|
| `RowColorManager` (`presentation/row_colors.py`) | rule compilation, `tags_for(filename)` | ✅ |
| `DirectoryManager` | entries, resolution, auto-select, config overrides | mostly ✅ |
| `ScanController` | thread, queue, chunk insert, progress UI | thread+queue ✅; insert needs Tk |
| `WindowActions` | config/log/restart/refresh flows | thin wrappers over `core.actions` |
| `FileContextMenu` | menu building + dispatch | dispatch ✅ via facade |
| `MainWindow` | widget tree, wiring, theme/i18n toggle, `run()` | — |

### Error handling

Controllers never show dialogs. They return results / invoke `on_error` callbacks.
`MainWindow`/`WindowActions` own all `messagebox` calls in one place, consistent
with the existing `core.actions.ActionResult` pattern. No silent failures.

### Color math move

`_hex_luminance` and `_contrast_ratio` move from `main_window.py` to
`presentation/theme.py` as public functions (theme-adjacent by nature). Any
duplication of the same formulas elsewhere in `gui/` is deleted and rerouted.

## Backward compatibility

- `profiles.gui.main_window.MainWindow` keeps its name and public constructor
  `MainWindow(config: AppConfig)` and `.run()`; `profiles/app.py` untouched.
- Old module paths (`profiles.gui.theme`, `profiles.gui.i18n`, …) get
  **no** shims — this is a codebase-internal refactor and all importers live in
  this repo (plus tests, which are updated in the same PR). Verified in each step
  by `grep`/`pylance` reference scan before moving.

## Testing strategy

- New pure unit tests: `RowColorManager` (pattern compile, tag mapping), directory
  formatting/resolution helpers.
- `tests/gui/test_main_window.py` keeps passing after every step; mocks updated
  only where the facade lands.
- `tests/gui/test_search_bar.py`, `test_status_bar.py`, `test_theme.py` move with
  their modules (import updates only).
- Coverage stays >85% after each PR; `ruff format/check` + `pylint` clean per step.

## Execution sequence (one PR per step, all green before the next)

1. **Move color math** → `theme.py`; delete duplicates; reroute call sites.
2. **Extract `row_colors.py`** (`presentation/`) from `_configure_row_colors` /
   `_row_color_tags_for`; MainWindow keeps only wiring.
3. **Extract `scan_controller.py`** — `_refresh_file_list`, `_bg_scan_and_process`,
   `_poll_scan_queue`, `_start_chunked_insert`, `_insert_chunk`.
4. **Extract `directory_manager.py`** — `_populate_directories`, `_format_dir_entry`,
   `_resolve_dir_selection`, `_set_dir_selection`, `_auto_select_directory`,
   `_current_dir_label`, `_find_active_config`, `_apply_config_overrides`.
5. **Extract `window_actions.py`** + `components/shortcuts.py` + context-menu facade —
   `_on_open_config`, `_on_open_log`, `_on_refresh`, `_restart_application`,
   shortcut-dialog flow, collapse pass-throughs.
6. **Folder reorganization** — move `search_bar`, `status_bar`, `context_menu`,
   `theme`, `styles`, `ui`, `i18n` into packages; add `__init__.py` re-exports;
   update all imports; move/mirror test files.
7. **Final slim-down** — remove dead pass-throughs, drop surviving
   `protected-access` disables where the facade now renders them unnecessary.

Order rationale: extraction (steps 1–5) before moves (step 6) keeps each diff about
exactly one concern (logic relocation vs path relocation), which keeps review and
rollback cheap.

## Out of scope (YAGNI)

- No changes to `core/`, `utils/`, `app.py` public behavior.
- No new abstractions beyond the coordinators above (no interfaces "for the future").
- No UI/UX changes; pixel-identical behavior.

## Success criteria

- `main_window.py` ≤ ~500 lines.
- Zero `window._*` attribute access outside `main_window.py` (no remaining
  `disable=protected-access` in `components/`, `controllers/`, `presentation/`).
- All tests green, coverage ≥ current, `ruff`/`pylint` clean.
