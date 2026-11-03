# YAML Config Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Edit the active `.profiles` YAML in the web UI via a full-screen CodeMirror 6 modal, applying in memory first and saving to disk only through a validated, explicit save.

**Architecture:** 5 new routes on the existing `/api/config` FastAPI router, all funneling validation through one helper on top of `ConfigReader.from_content`; the frontend adds a `ConfigEditorModal` reusing the drop-config `load-content` endpoint for Apply.

**Tech Stack:** FastAPI (existing router), CodeMirror 6 (`codemirror`, `@codemirror/lang-yaml`), React 19 + vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-11-03-yaml-config-editor-design.md`

## Global Constraints

- Extension whitelist for Save As: exactly `.profiles` and `.profiles.yaml` (spec value).
- `POST /validate` always returns HTTP 200; validity is carried in the body.
- Bad YAML never touches disk unless the request carries `force: true`.
- Save As refuses an existing target unless `overwrite: true` is present.
- New code imports from `profiles.core` / its subpackages, not the `config.py` shim.
- Web theming via `data-theme` tokens only (never Tailwind `dark:`); new overlays use z-scale tokens.
- `dist/` rebuilt (`npm run build` in `src/profiles/web`) and committed in the final task.
- Python style: type hints, docstrings on public functions, ruff format/check clean, pytest green.

## Review Focus

1. **Session-trial save refusal** — active config from a drop has no disk path; Save must 400, not silently write to a CWD-resolved path. (Task 2 pins `_has_disk_path`.)
2. **Overwrite without flag** — Save As onto an existing file must fail (409) without `overwrite: true`. (Task 4)
3. **Force-save writes invalid content** — the file is written verbatim; a later `GET /content` returns it and Test/Apply report the errors. (Task 2 + Task 5)
4. **Template round-trip** — `STARTER_CONFIG_TEMPLATE.format(...)` output must pass the project's own `/validate` (brace-escaping history — see memory "config template escaping gotchas"). (Task 3)
5. **Dirty-escape guard** — closing with unsaved edits warns instead of losing them. (Task 6)

---

### Task 1: Validation helper + `POST /api/config/validate`

**Files:**
- Modify: `src/profiles/server/routes/config.py`
- Test: `tests/server/routes/test_config_editor.py` (create; fixture pattern follows `tests/server/routes/test_config_reload.py`)

**Interfaces:**
- Produces: `validate_issues(content: str, display_name: str) -> list[dict[str, str]]` in `routes/config.py` — returns `[]` when `ConfigReader.from_content` parses, else `[{"severity": "error", "message": <str(exc)>}]`. Tasks 2–4 consume it.

- [ ] **Step 1: Write failing tests** — `test_validate_returns_valid_true_for_starter_template` (template rendered with `STARTER_CONFIG_TEMPLATE.format(cwd=str(tmp_path))`, expect `{"valid": True, "issues": []}`), `test_validate_returns_issues_for_bad_yaml` (`content="defaults: [unclosed"`, expect `valid=False` and `issues[0]["severity"] == "error"` with a non-empty message), `test_validate_does_not_change_state` (assert `state.config` is unchanged after the call).
- [ ] **Step 2: Run** `pytest tests/server/routes/test_config_editor.py -v` — expect FAIL (404 / unknown route).
- [ ] **Step 3: Implement** `validate_issues` + route `POST /validate` with pydantic `ValidateRequest(content: str, filename: str)` returning `{"valid": not issues, "issues": issues}`.
- [ ] **Step 4: Run tests** — PASS. Also run `pytest tests/server/routes/test_config.py -v` (no regression).
- [ ] **Step 5: Commit** `feat(server): config validate endpoint for the YAML editor`

### Task 2: `GET /api/config/content` + session-trial detection

**Files:**
- Modify: `src/profiles/server/routes/config.py`
- Test: `tests/server/routes/test_config_editor.py`

**Interfaces:**
- Produces: `has_disk_path(state: ServerState) -> bool` — True iff `state.config_path` or `state.config.config_path` is set (i.e. NOT a drop-config session trial). Response shape: `{"filename": str, "content": str, "config_path": str | null, "session_trial": bool}`.

- [ ] **Step 1: Failing tests** — `test_content_returns_active_config_text` (load a real temp `.profiles` via `ConfigReader` into state; assert content matches file text and `session_trial is False`), `test_content_flags_session_trial` (state where only `state.config` is set, no path anywhere; assert `session_trial is True` and `config_path is None`), `test_content_for_missing_file_returns_text_or_error` (path recorded but file deleted — decide + pin one behavior: 404 with detail).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** `has_disk_path` + `GET /content` reading `state.active_config_path().read_text(encoding="utf-8")` when it exists.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(server): config content endpoint + session-trial detection`

### Task 3: `POST /api/config/save` (validate → force → write)

**Files:**
- Modify: `src/profiles/server/routes/config.py`
- Test: `tests/server/routes/test_config_editor.py`

**Interfaces:**
- Consumes: `validate_issues`, `has_disk_path` (Tasks 1–2).
- Produces: `SaveRequest(content: str, force: bool = False)`; success → `{"status": "SAVED", "path": str, "config": <config_response>}`; re-reads the saved file via `_apply_config_from_disk` so the live config equals what is on disk.

- [ ] **Step 1: Failing tests** — `test_save_refused_for_session_trial` (no disk path → 400, nothing written), `test_save_rejects_invalid_content_without_writing` (file bytes unchanged after 400), `test_save_force_writes_invalid_content` (`force=True` → 200, file contains the invalid text), `test_save_writes_and_applies_valid_config` (valid content → 200, file written, `state.config` reflects new content).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** the route; gate order: `has_disk_path` check → `validate_issues` → if issues and not `force`: return 400 with the issues list → write → `_apply_config_from_disk`.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(server): validated config save endpoint with force escape hatch`

### Task 4: `POST /api/config/save-as`

**Files:**
- Modify: `src/profiles/server/routes/config.py`
- Test: `tests/server/routes/test_config_editor.py`

**Interfaces:**
- Consumes: `validate_issues` (Task 1), `_apply_config_from_disk` (existing).
- Produces: `SaveAsRequest(content: str, filename: str, directory: str, force: bool = False, overwrite: bool = False)`; success → same shape as save. Extension whitelist constant `SAVE_AS_EXTENSIONS = (".profiles", ".profiles.yaml")`.

- [ ] **Step 1: Failing tests** — `test_save_as_rejects_bad_extension` (`.yml` → 400), `test_save_as_rejects_existing_target_without_overwrite` (409 or 400 — pin 409), `test_save_as_overwrite_replaces_file`, `test_save_as_rejects_invalid_content` (no file created), `test_save_as_force_saves_invalid_content`, `test_save_as_applies_new_config` (after success, `state.active_directory` re-derived, `state.config_path == target`).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — path via `normalize_user_path`; validation gate identical to save; on success write then `_apply_config_from_disk(state, target)`.
- [ ] **Step 4: Run** — PASS + full `pytest tests/server/routes -q` green.
- [ ] **Step 5: Commit** `feat(server): save-as endpoint with extension whitelist and overwrite guard`

### Task 5: Web API client + types

**Files:**
- Modify: `src/profiles/web/src/api/types.ts`, `src/profiles/web/src/api/client.ts`
- Test: `src/profiles/web/src/api/client.test.ts` (extend)

**Interfaces:**
- Consumes: the five routes (Tasks 1–4). Error convention matches existing client helpers (400 detail surface).
- Produces: `fetchConfigContent(): Promise<ConfigContentData>`; `validateConfigContent(filename: string, content: string): Promise<{valid: boolean; issues: ValidationIssue[]}>`; `fetchConfigTemplate(): Promise<{content: string; filename: string}>`; `saveConfigFile(content: string, force: boolean): Promise<AppConfigData>`; `saveConfigFileAs(params: {content: string; filename: string; directory: string; force: boolean; overwrite: boolean}): Promise<AppConfigData>`. New types: `ConfigContentData`, `ValidationIssue {severity: "error" | "warning"; message: string}`.

- [ ] **Step 1: Failing client tests** — one per function asserting method + URL + body passthrough (same mock style as existing `client.test.ts`).
- [ ] **Step 2: Run** `npx vitest run src/api/client.test.ts` (from `src/profiles/web`) — FAIL.
- [ ] **Step 3: Implement** functions + types.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(web): API client for config editor endpoints`

### Task 6: `ConfigEditorModal` — CodeMirror shell, load, dirty/escape guard

**Files:**
- Create: `src/profiles/web/src/components/ConfigEditorModal.tsx`
- Modify: `src/profiles/web/package.json` (add `codemirror`, `@codemirror/lang-yaml`)
- Test: `src/profiles/web/src/components/ConfigEditorModal.test.tsx`

**Interfaces:**
- Consumes: `fetchConfigContent` (Task 5).
- Produces: `ConfigEditorModalProps {open: boolean; onClose: () => void; onApplied?: (data: AppConfigData) => void}` — Tasks 7–8 extend this component; App integration is Task 9. Full-screen overlay using the existing modal z-scale token class (pattern from `BarcodeModal.tsx`).

- [ ] **Step 1: Install deps** — `npm install codemirror @codemirror/lang-yaml` in `src/profiles/web`.
- [ ] **Step 2: Failing component tests** — `test_renders_fullscreen_overlay_when_open`, `test_loads_content_on_open` (mock `fetchConfigContent`, assert editor text set), `test_dirty_indicator_and_escape_warning` (simulate change; press Escape; expect confirm dialog instead of close; decline → stays open), `test_clean_close_without_warning`.
- [ ] **Step 3: Implement** — CodeMirror 6 `EditorView` with `yaml()` language; theme object built from CSS variable tokens (read via `getComputedStyle` of the mounted root or hardcode token var() references in the theme spec); toolbar placeholder row (buttons wired in Tasks 7–8); Escape/✕ handler comparing current doc to loaded text. Modal header bar includes an **"Open in OS"** button calling the existing `openConfigFile()` client function (spec addition 2026-11-03: user asked for an OS-launch button in the modal head bar); test step 2 adds `test_header_open_in_os_calls_open_config_file`.
- [ ] **Step 4: Run** `npx vitest run` — all web tests PASS.
- [ ] **Step 5: Commit** `feat(web): config editor modal shell with CodeMirror and dirty guard`

### Task 7: Toolbar — New, Test, Revert, Apply

**Files:**
- Modify: `src/profiles/web/src/components/ConfigEditorModal.tsx`
- Test: `src/profiles/web/src/components/ConfigEditorModal.test.tsx`

**Interfaces:**
- Consumes: `fetchConfigTemplate`, `validateConfigContent`, `loadConfigContent` (Task 5 + existing).
- Produces: internal state contract reused by Task 8: `status` banner (`{kind: "ok" | "error"; text: string} | null`), `issues: ValidationIssue[]`, `dirty: boolean`.

- [ ] **Step 1: Failing tests** — `test_new_loads_template_after_confirm` (dirty → ConfirmDialog first), `test_new_without_dirty_loads_immediately`, `test_test_shows_valid_badge`, `test_test_shows_issue_list` (mock invalid result; assert each issue message rendered), `test_apply_calls_load_content_and_reports_success` (assert `onApplied` fired with response), `test_apply_error_shows_server_message`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** the four buttons + inline banner + issue list above the editor.
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `feat(web): editor toolbar actions New/Test/Revert/Apply`

### Task 8: Toolbar — Save, Save As with compliance gate and force

**Files:**
- Modify: `src/profiles/web/src/components/ConfigEditorModal.tsx`
- Create: `src/profiles/web/src/components/SaveAsDialog.tsx`
- Test: `src/profiles/web/src/components/ConfigEditorModal.test.tsx`, `SaveAsDialog.test.tsx`

**Interfaces:**
- Consumes: `saveConfigFile`, `saveConfigFileAs`, `browseDirectory` (existing, for the directory picker).
- Produces: `SaveAsDialogProps {open; onCancel; onConfirm(params: {filename: string; directory: string; overwrite: boolean})}`; gate helper in ConfigEditorModal: validate → if issues, render issue list + "Go back and fix" / "Force save anyway" buttons.

- [ ] **Step 1: Failing tests** — modal: `test_save_validates_then_saves`, `test_save_invalid_shows_gate_with_force_option`, `test_force_save_proceeds`, `test_save_disabled_without_disk_path` (session trial → Save hidden/disabled, tooltip explains; `Cmd/Ctrl+S` falls back to Apply). Dialog: `test_lists_directories_via_browse`, `test_filename_extension_restricted` (input accepts only `.profiles`/`.profiles.yaml` suffix — append/normalize on confirm), `test_overwrite_confirmation` (existing file in browse result → "Replace?" confirm before `onConfirm(..., overwrite: true)`), `test_cancel`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — Save button + gate UI; `SaveAsDialog` reusing the browse-result pattern from `DirectoryPickerModal.tsx`; keyboard binding `Mod-s`.
- [ ] **Step 4: Run** — PASS (full vitest suite).
- [ ] **Step 5: Commit** `feat(web): save/save-as with compliance gate, force option and replace confirmation`

### Task 9: App integration + documentation + dist

**Files:**
- Modify: `src/profiles/web/src/App.tsx` — the editor opens from the **existing StatusBar config button** (the `onOpenConfig` prop currently OS-launching the file at `App.tsx:1550`): repurpose it to `setShowConfigEditor(true)`; OS-launch moves into the modal header ("Open in OS", Task 6).
- Modify: `docs/configuration-profile.en.md`, `docs/configuration-profile.fr.md`, `docs/advanced/guide-avance.en.md`, `docs/advanced/guide-avance.fr.md`, `README.md`, `README.fr.md`
- Test: `src/profiles/web/src/components/ConfigEditorModal.test.tsx` (one integration test)

**Interfaces:**
- Consumes: `ConfigEditorModal` (Tasks 6–8), `AppConfigData.onConfigChanged` path used by `LoadConfigModal.tsx` for refreshing the app after config swaps.

- [ ] **Step 1: Failing integration test** — `test_status_bar_config_button_opens_editor_and_apply_refreshes_app`: click the StatusBar config button, modal opens, Apply → app state refresh callback invoked.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** the StatusBar entry (repurposed `onOpenConfig`) + wire `onApplied` to the same refresh path `LoadConfigModal` uses.
- [ ] **Step 4: Docs** — user-guide section (toolbar incl. "Open in OS", two-step model, gate/force, Save-as extensions); `--init` docs pointer to **New**; advanced guide endpoint list; README bullets (en/fr, keep the 🇬🇧/🇫🇷 switcher pattern).
- [ ] **Step 5: Run** vitest suite PASS; run `uv run pytest -q` full suite PASS; `uv run ruff format . && uv run ruff check .` clean.
- [ ] **Step 6: Build + commit** — `npm run build` in `src/profiles/web`; commit `feat(web): YAML config editor in the UI` including `dist/`.

---

## Self-Review Notes

- Spec coverage: all 5 endpoints (Tasks 1–4 + reuse), 6 toolbar actions (Tasks 7–8), gate/force (Task 8), overwrite confirm (Task 8), dirty guard (Task 6), docs (Task 9), dist (Task 9).
- `GET /content` on a deleted file: behavior pinned in Task 2 Step 1 (404) rather than left open.
- Severity model: `issues` carries `severity` from day one; only `"error"` is produced today (spec note honored).
