# Tabbed Profiles & Workflows Configuration UI Design

**Date**: 2026-08-26  
**Status**: Approved  
**Target Milestone**: Milestone 6 (Workflow Builder & Tabbed Profile Configuration)

---

## 🎯 Executive Summary & Intent

ProFiles currently manages application defaults, machine-specific scanning profiles, dynamic column definitions, row colors, and launch hooks via a YAML configuration file (`.profiles`). While functional, editing YAML files directly creates friction for non-technical users and introduces risks of syntax or schema errors.

This design introduces an integrated tabbed UI within the ProFiles main window:
1. **Tab 1 — 🚀 Launcher**: The existing file scanner, search bar, treeview, and context menu.
2. **Tab 2 — ⚙️ General Configuration**: An accordion-based editor for global application defaults, machine profiles (`[CONFIGURATION_N]`), dynamic columns, row colors, and file/directory exclusions. Includes the persistent `ConfigFooterBar` for auto-save, save, revert, and validation status.
3. **Tab 3 — 🔀 Workflows Configuration**: A visual workflow builder for configuring launch hooks per file extension, complete with step ordering, action guards, context variable insertion, dry-run test simulation, and live YAML preview. Includes the persistent `ConfigFooterBar`.
4. **Dedicated Tab Modules**: All three tab views are modularized under `src/profiles/gui/tabs/` for clean maintainability.

---

## 🏗️ Architecture & Component Design

### 1. Window Hierarchy

`MainWindow` wraps its primary view inside a top-level `ttk.Notebook` container anchored above the existing `StatusBar`. The configuration tabs (Tabs 2 and 3) include the dedicated `ConfigFooterBar` at their bottom edge, ensuring the main Launcher tab remains uncluttered.

```
+-----------------------------------------------------------------------------------+
|  ProFiles — Production Test Program Launcher                                 [_][X]
+-----------------------------------------------------------------------------------+
| [ 🚀 Launcher ] [ ⚙️ General Configuration ] [ 🔀 Workflows Configuration ]   |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  < Active Tab Content >                                                           |
|                                                                                   |
|  [ In Tabs 2 & 3 ] 💾 ConfigFooterBar:                                             |
|  Status: 🟢 Saved / 🟡 Unsaved Changes*    [x] Auto-save   [ Save ]  [ Revert ]  |
+-----------------------------------------------------------------------------------+
| StatusBar (Config path | Refresh | Log | Theme | Language)                       |
+-----------------------------------------------------------------------------------+
```

### 2. View Components (under `src/profiles/gui/tabs/`)

- **`LauncherTab` (`src/profiles/gui/tabs/launcher_tab.py`)**:
  Encapsulates the existing search bar (`SearchBar`), file treeview, quick action buttons, and context menu (`FileContextMenu`).
- **`GeneralConfigTab` (`src/profiles/gui/tabs/general_config_tab.py`)**:
  Hosts a vertical scrollable canvas containing stacked `CollapsibleFrame` accordion widgets and a bottom-anchored `ConfigFooterBar`:
  - **Panel 1 — Global Defaults**: Title, default search directory, recursive flag, theme (light/dark), language, verbosity, scan metrics logging.
  - **Panel 2 — Machine Profiles (`configs`)**: List of named machine profiles with match criteria (hostname, IP, path), scan directories, extension overrides, filter overrides. Includes Add, Delete, and Duplicate profile controls.
  - **Panel 3 — Dynamic Columns & Row Colors**: Priority-sorted table of dynamic column definitions (header name, regex match, transform, width, stretch) and generic row coloring rules (pattern, hex color with `colorchooser` swatch).
  - **Panel 4 — File & Directory Exclusions**: Lists for `search_exclude_dirs` and `search_exclude_files`.
- **`WorkflowConfigTab` (`src/profiles/gui/tabs/workflow_config_tab.py`)**:
  A 2-column split pane for visual workflow management with a bottom-anchored `ConfigFooterBar`:
  - **Left Pane — Extension Triggers & Step List**: List of file extension targets (`.mttl`, `.exe`, `.lnk`, `*`) and re-orderable workflow steps with action icons (🔔 `notify`, ⚙️ `run`, ⏱️ `run_after`, 🔀 `replace`, 🔍 `check`).
  - **Right Pane — Step Inspector & Live YAML Preview**: Form controls for step properties (`action`, `content`, `ask`, `wait`, `on_failure`), helper buttons to insert context variables (`{{path}}`, `{{filename}}`, `{{directory}}`, `{{hostname}}`, `{{username}}`), dry-run test runner, and a read-only live YAML preview.
- **`ConfigFooterBar` (`src/profiles/gui/widgets/config_footer.py`)**:
  Reusable toolbar component embedded at the bottom of `GeneralConfigTab` and `WorkflowConfigTab`. Displays dirty state ("Saved" / "Unsaved Changes*"), `Auto-save` checkbutton, `Save` button, and `Revert` button.

---

## 🔄 State Management, Validation & Synchronization

### 1. Controller Architecture

A new controller `ConfigStateController` (`src/profiles/core/config/state_controller.py`) manages configuration draft state:

```
[ GUI Form Controls ] ──(field edits)──► [ ConfigStateController ]
                                                  │
                                        (Pydantic Validation)
                                                  │
                                         (Dirty State: True)
                                                  │
                              ┌───────────────────┴───────────────────┐
                              ▼                                       ▼
                     [ ConfigFooterBar ]                   [ Auto-Save Debouncer ]
                     (Status: Unsaved*)                    (500ms timer -> Save)
```

- **Draft Model**: Holds an in-memory `AppConfigYaml` object.
- **Dirty Tracking**: Compares current form values against the last committed state.
- **Debounced Auto-Save**: When `auto_save` is enabled, field updates schedule a 500ms debounced write. If the user continues typing, the timer resets.
- **Validation**: Runs `AppConfigYaml.model_validate()` on every change. If validation fails, auto-save is paused and the footer displays an error indicator with tooltip feedback.

### 2. Application Sync

Upon manual or auto-save:
1. `ConfigStateController` serializes `AppConfigYaml` to YAML and calls `yaml_io.write_config()`.
2. Triggers `MainWindow._reload_config()`, which:
   - Re-applies active theme (`apply_theme`) and language (`set_language`).
   - Updates `AppConfig` runtime data.
   - Refreshes column headers, treeview sorting, row colors, and file scanner options in `LauncherTab`.

---

## 🌐 Internationalisation (i18n) & Themes

- All strings in the tab bar, accordion headers, form field labels, workflow step types, tooltips, and footer messages are registered in `src/profiles/gui/i18n.py` (`en` and `fr`).
- Accordion cards, split panes, entry fields, buttons, and status indicators adhere strictly to `Md3Theme` light/dark color tokens.

---

## 🧪 Testing & Validation Plan

1. **Unit Tests**:
   - `test_state_controller.py`: Test dirty state tracking, validation failures, draft reset, and debounced auto-save scheduling.
   - `test_workflow_builder_model.py`: Test conversion between GUI workflow step objects and Pydantic `WorkflowStepSchema` / `HooksConfig`.
2. **GUI Component Tests**:
   - `test_collapsible_frame.py`: Verify expand/collapse state toggles and child widget geometry.
   - `test_config_tabs.py`: Verify tab switching, widget creation, and data binding without Tkinter errors.
3. **Integration Tests**:
   - `test_config_gui_sync.py`: Test modifying a setting in `GeneralConfigTab`, saving, and asserting that `MainWindow` and `AppConfig` reflect the updated settings immediately.
