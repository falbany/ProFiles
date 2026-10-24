# Drop-to-Try Configuration (Session-Only) — Design

- **Date:** 2026-10-24
- **Status:** Approved (partner amendments incorporated)
- **Related:** 2026-10-23-native-installer-design.md (log/config conventions), 2026-10-13-launch-and-config-handoff-design.md

## Intent

Dragging a configuration file onto the running ProFiles UI loads that
configuration immediately as a **session-only trial**: nothing is written
to disk, nothing persists across restart. Discarding = restart (or load
another config).

## Decisions from the conversation

- Session-only trial, explicitly **no disk writes** (partner).
- Accepted file names (partner): anything ending in `.profiles`
  (`my.profiles`, `prod.profiles`, `data.profiles`, and the literal
  `.profiles` dotfile), plus `.yaml` / `.yml`.
- On a successful load the UI must refresh with the new configuration:
  apply config state, re-scan the current active directory with the new
  scan settings, re-apply theme — the same post-load flow the existing
  `Load Config` modal uses (`App.tsx` `handleLoadConfig`).

## Behavior

1. Dragging files over the window shows an overlay hint
   ("Drop configuration file").
2. On drop: the first accepted file wins; others are ignored. Accepted =
   filename ends with `.profiles`, `.profiles.yaml`, `.profiles.yml`,
   `.yaml`, or `.yml` (case as-is; includes the literal `.profiles`).
3. Content is parsed **in memory** with the same validation the path-based
   loader uses. `ServerState.config` is swapped; `config_path` and
   `active_directory` stay unchanged (the real path is unknown to the
   backend). The API response marks the config as a session trial.
4. Invalid YAML / invalid schema / wrong file type → 400 with the parse
   error; current config untouched.
5. Clicking the drop overlay opens a file picker (same content flow) as
   an accessibility/browser fallback.

## Non-goals

- No persistence: no file saved anywhere, no write to the active
  `.profiles(.yaml)`.
- No active-directory switch on drop.
- No change to launch-time resolution or the `*.profiles` document
  association.

## Approach

- **Backend:** new `POST /api/config/load-content` in
  `src/profiles/server/routes/config.py` with `{filename, content}`;
  filename must match the accepted suffixes; content parsed through the
  same AppConfig validation as `ConfigReader` (in-memory variant — no
  temp files, honoring the no-disk-write rule); swaps
  `ServerState.config` and returns `_config_response` with a
  `session_trial: true` marker.
- **Frontend:** window-level drag/drop handling in `App.tsx`
  (dragenter/over/leave/drop + overlay component), `File.text()` to read
  content, new API client `loadConfigContent(filename, content)`, then
  the existing post-load refresh flow (config state → rescan → theme).
  Web assets rebuilt (`python -m profiles.web.build`).

## Testing

- Endpoint: valid config applies + `session_trial` marker; invalid YAML
  → 400 and config unchanged; wrong filename → 400; multi-file payload →
  first accepted; **no file created anywhere** (assert no new files in
  tmp dirs).
- Frontend: drop-zone accepts/rejects by suffix; success path calls the
  same refresh flow as Load Config (vitest, matching existing web tests).
