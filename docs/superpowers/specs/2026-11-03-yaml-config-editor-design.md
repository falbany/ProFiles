# YAML Config Editor — Design

Date: 2026-11-03
Status: Approved (brainstorming session, same day)

## Intent

Edit the active `.profiles` YAML configuration file directly in the web
front-end, with a two-step safety model: edits are first applied **in
memory** (session trial, reusing the drop-config pipeline), and written to
disk only through an explicit **Save** that is gated by server-side
compliance validation.

## Decisions made

- **Editor technology**: CodeMirror 6 (`codemirror`, `@codemirror/lang-yaml`)
  — lightweight (~150 KB), fits the PWA, themed from the existing
  `data-theme` tokens (both light and dark). Monaco (~2 MB) rejected as too
  heavy; plain textarea rejected (no highlighting).
- **UX**: full-screen modal, same pattern as the barcode/camera modals
  (z-scale token convention).
- **Save model**: apply-in-memory first, save-to-disk as an explicit second
  step (option B).

## Backend — new endpoints on `/api/config`

1. `GET /content` — raw YAML text + filename + `config_path`;
   `session_trial: true` when the active config came from a drop (no disk
   path).
2. `POST /validate` — body `{content, filename}` → `200 {valid, issues:
   [{severity, message}]}`. Always 200; validity carried in the body so the
   modal renders issues and buttons uniformly. Parses via
   `ConfigReader.from_content`; no state change. Powers the **Test** button
   and the save gates.
   - Note: the reader currently only produces *errors* (one `ValueError`
     message); `issues` is shaped for future severity levels. The
     error/force flow works on errors today.
3. `POST /template` — returns `STARTER_CONFIG_TEMPLATE.format(cwd=active
   directory)` rendered in memory; nothing written. Powers **New** (same
   content as `--init`).
4. `POST /save` — validate → optional `force` flag → write to
   `config_path`. 400 for session-trial configs (no path). Bad YAML never
   touches the file without `force`.
5. `POST /save-as` — `{content, filename, directory, overwrite}`.
   - `filename` restricted to `.profiles` / `.profiles.yaml` extensions.
   - Validated content first; refuses an existing target unless
     `overwrite: true` (client confirms "Replace?" first).
   - On success it **also applies** the saved config and re-derives the
     active directory (`_choose_active_directory`, same path as `/load`).

**Apply** reuses the existing `POST /load-content` unchanged.

## Frontend — full-screen modal

Toolbar: **New** (template; confirms if dirty) · **Test** (badge ✓ valid /
✗ with inline issue list) · **Apply** (session-trial apply via
`load-content`; 400 message shown inline) · **Save** · **Save as** (dialog:
directory browse via existing `/api/fs` + filename input, extension
constraint) · **Revert** (reload from server). Dirty dot in the title;
Escape/✕ warns on unsaved edits; `Cmd/Ctrl+S` → Save (falls back to Apply
when there is no disk path).

**Save / Save as compliance gate**: server validate first → if issues,
show the issue list and offer "Go back and fix" / "Force save anyway";
force skips the gate and writes.

**Save as overwrite**: existing target → "Replace?" confirmation; endpoint
requires explicit `overwrite: true`.

## Non-goals

- No form-based GUI editor.
- No schema autocomplete for v1 (server-validated lint feedback is enough).
- No file picker for arbitrary configs (edits the active config only).

## Tests

- pytest route tests for the 5 new endpoints (valid/invalid/force/overwrite/
  extension restriction/session-trial refusal).
- vitest for the modal component: open/load, Test error path, Apply,
  Save gating, force-save path, Save-as dialog, dirty-escape warning.

## Documentation (en + fr)

- User guide: Config Editor section (toolbar, two-step model, compliance
  gate, force-save, allowed Save-as extensions).
- `--init` / starter-template docs: pointer to **New** in the UI.
- `docs/advanced/guide-avance.fr.md` + en counterpart: the new
  `/api/config/*` endpoints for alternative front-ends.
- README feature bullet (en/fr).

## Left to the builder

- Exact split of validation helpers shared between `validate` / `save` /
  `save-as` routes (DRY: one helper on top of `ConfigReader.from_content`).
- CodeMirror theme mapping to existing tokens.
- Route test fixtures consistent with `tests/AGENTS.md`.
