# Tabbed Profiles & Workflow Configuration Implementation Plan

> **For Engineer**: Execute this plan task by task using TDD. All code, commands, tests, and paths are explicitly provided.

---

## 🎯 Overview

This plan implements an integrated tabbed UI inside `MainWindow` with:
- **Tab 1 (`LauncherTab`)**: Existing file launcher, search bar, treeview, and context menu.
- **Tab 2 (`GeneralConfigTab`)**: Accordion sections (`CollapsibleFrame`) for defaults, machine configs (`configs`), columns/row colors, and file exclusions + `ConfigFooterBar`.
- **Tab 3 (`WorkflowConfigTab`)**: Visual workflow step editor, trigger list, inspector, dry-run simulation, and live YAML preview + `ConfigFooterBar`.
- **State Engine (`ConfigStateController`)**: Dirty tracking, 500ms debounced auto-save, Pydantic validation, and disk write/reload sync.

---

## 📁 Proposed File Structure

```
src/profiles/
├── core/
│   └── config/
│       └── state_controller.py      # ConfigStateController state & auto-save engine
├── gui/
│   ├── widgets/
│   │   ├── collapsible_frame.py     # Accordion frame widget
│   │   └── config_footer.py         # Save / Revert / Auto-save footer toolbar
│   └── tabs/
│       ├── __init__.py
│       ├── launcher_tab.py          # Tab 1: File launcher view wrapper
│       ├── general_config_tab.py    # Tab 2: General configuration accordion
│       └── workflow_config_tab.py   # Tab 3: Workflow visual builder view
tests/
├── core/
│   └── config/
│       └── test_state_controller.py # Controller unit tests
└── gui/
    ├── test_collapsible_frame.py    # Accordion widget GUI tests
    ├── test_config_footer.py        # Footer bar GUI tests
    └── test_config_tabs.py          # Tabbed UI integration tests
```

---

## Task 1: Add i18n Translation Strings for Tabs & Configuration UI

### Goal
Add all English and French translation strings for the Tabbed UI, Accordion titles, Workflow builder components, and Footer bar controls.

### Implementation Steps

1. Edit `src/profiles/gui/i18n.py` to include new catalog keys in both `"en"` and `"fr"`.

```python
# Keys to add in src/profiles/gui/i18n.py
"tab.launcher": "🚀 Launcher" / "🚀 Lanceur",
"tab.general": "⚙️ General Configuration" / "⚙️ Configuration Générale",
"tab.workflows": "🔀 Workflows Configuration" / "🔀 Configuration des Workflows",
"footer.saved": "🟢 Saved" / "🟢 Enregistré",
"footer.unsaved": "🟡 Unsaved Changes*" / "🟡 Modifications non enregistrées*",
"footer.autosave": "Auto-save" / "Enregistrement auto",
"footer.save": "Save" / "Enregistrer",
"footer.revert": "Revert" / "Annuler",
"accordion.defaults": "1. Global Application Defaults" / "1. Paramètres par Défaut",
"accordion.configs": "2. Machine Profiles (configs)" / "2. Profils Machine (configs)",
"accordion.columns": "3. Dynamic Columns & Row Colors" / "3. Colonnes Dynamiques & Couleurs",
"accordion.exclusions": "4. File & Directory Exclusions" / "4. Exclusions de Fichiers & Dossiers",
"workflow.triggers": "Extension Triggers" / "Déclencheurs d'Extension",
"workflow.steps": "Step Sequence" / "Séquence d'Étapes",
"workflow.inspector": "Step Inspector" / "Inspecteur d'Étape",
"workflow.yaml_preview": "Live YAML Preview" / "Aperçu YAML",
"workflow.dry_run": "Test Simulation" / "Simulation de Test",
```

2. Run `pytest tests/gui/test_i18n.py` to ensure all translation keys are symmetrical across EN and FR.

---

## Task 2: Implement `ConfigStateController` & Auto-Save Engine

### Goal
Create `src/profiles/core/config/state_controller.py` to manage dirty state tracking, 500ms debounced auto-save execution, validation against `AppConfigYaml`, and file saving.

### Steps
1. Write unit tests in `tests/core/config/test_state_controller.py`:
   - Test initial state (`is_dirty == False`).
   - Test modifying draft marks `is_dirty = True`.
   - Test validation check returns errors for invalid hex colors or invalid action types.
   - Test `save()` writes config to file and resets `is_dirty`.
   - Test `revert()` restores draft from disk state.
2. Implement `ConfigStateController`:
   - Store `draft: AppConfigYaml` and `saved_draft: AppConfigYaml`.
   - Provide `set_field(path: str, value: Any)`.
   - Provide `schedule_autosave(callback: Callable[[], None], delay_ms: int = 500)`.
3. Verify with `pytest tests/core/config/test_state_controller.py`.

---

## Task 3: Implement `CollapsibleFrame` Accordion Widget

### Goal
Create `src/profiles/gui/widgets/collapsible_frame.py` for expandable/collapsible accordion panels in Tab 2.

### Steps
1. Write GUI test in `tests/gui/test_collapsible_frame.py`:
   - Test initializing expanded vs collapsed.
   - Test clicking toggle button toggles visibility of the interior container frame.
2. Implement `CollapsibleFrame`:
   - Header frame with icon button (`▼` / `►`), title label, and badge.
   - Content frame packed/unpacked on toggle.
3. Verify with `pytest tests/gui/test_collapsible_frame.py`.

---

## Task 4: Implement `ConfigFooterBar` Widget

### Goal
Create `src/profiles/gui/widgets/config_footer.py` for the footer bar in Tab 2 and Tab 3.

### Steps
1. Write GUI test in `tests/gui/test_config_footer.py`:
   - Test button callbacks (`on_save`, `on_revert`, `on_autosave_toggle`).
   - Test `set_dirty_status(is_dirty: bool, error_msg: str | None = None)`.
2. Implement `ConfigFooterBar`:
   - Status label (`🟢 Saved` vs `🟡 Unsaved Changes*`).
   - Checkbutton `Auto-save`.
   - Buttons `Save` and `Revert`.
3. Verify with `pytest tests/gui/test_config_footer.py`.

---

## Task 5: Implement `LauncherTab` View Wrapper

### Goal
Create `src/profiles/gui/tabs/launcher_tab.py` to cleanly encapsulate the existing launcher view components.

### Steps
1. Move launcher frame assembly from `MainWindowUI` into `LauncherTab`.
2. Expose search bar, treeview, context menu, and action bar callbacks.
3. Verify launcher tests pass (`pytest tests/gui/test_main_window.py`).

---

## Task 6: Implement `GeneralConfigTab` View

### Goal
Create `src/profiles/gui/tabs/general_config_tab.py` incorporating accordion panels and `ConfigFooterBar`.

### Steps
1. Build scrollable canvas hosting 4 `CollapsibleFrame` sections.
2. Bind input controls to `ConfigStateController`.
3. Embed `ConfigFooterBar` at the bottom of the tab layout.
4. Add unit/GUI test in `tests/gui/test_config_tabs.py`.

---

## Task 7: Implement `WorkflowConfigTab` View

### Goal
Create `src/profiles/gui/tabs/workflow_config_tab.py` for visual workflow step editing.

### Steps
1. Build split-pane layout: Left (Extension list, Step sequence list), Right (Step inspector, Dry-run simulator, Live YAML text view).
2. Add context variable helper buttons (`{{path}}`, `{{filename}}`, etc.).
3. Embed `ConfigFooterBar` at the bottom of the tab layout.
4. Add unit/GUI test in `tests/gui/test_config_tabs.py`.

---

## Task 8: Integrate Notebook Tabs into `MainWindow`

### Goal
Update `src/profiles/gui/main_window.py` and `ui.py` to instantiate `ttk.Notebook` with `LauncherTab`, `GeneralConfigTab`, and `WorkflowConfigTab`.

### Steps
1. Replace single-view root layout with `ttk.Notebook`.
2. Connect `ConfigStateController` save event to `MainWindow._reload_config()`.
3. Run full test suite (`pytest`).
