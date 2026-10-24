# Drop-to-Try Configuration (Session-Only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dropping a `.profiles`/`.yaml`/`.yml` config file on the running UI applies it as a session-only trial — no disk writes, UI refreshed with the new config.

**Architecture:** New in-memory parse path on `ConfigReader` (strict: raises on invalid content — unlike path `load()` which falls back to defaults), a new `POST /api/config/load-content` endpoint that swaps only `ServerState.config` (config_path/active_directory untouched), and a window-level HTML5 drop-zone in the React UI that reuses the existing post-load refresh flow.

**Tech Stack:** FastAPI + pydantic (existing `AppConfigYaml` schema), React + TS + vitest, pywebview shell (HTML5 drop — pywebview exposes no native drop paths on macOS).

**Spec:** `docs/superpowers/specs/2026-10-24-drop-config-design.md`

## Global Constraints

- **No disk writes, ever, on the drop path** — no temp files, no saving dropped content (partner requirement).
- Accepted filenames (case-insensitive on the suffix): endswith `.profiles`, `.profiles.yaml`, `.profiles.yml`, `.yaml`, `.yml`.
- Session swap touches ONLY `ServerState.config` — `state.config_path` and `state.active_directory` must remain byte-identical.
- Invalid content → HTTP 400 with the parse error; the previously active config stays active.
- Quality gates: `ruff check .`, `ruff format .`, scoped pytest green (full suite minus the 58 known pre-existing failures — see session ledger; coverage 85% gate unmeetable on macOS, recorded-not-enforced).

## Review Focus

1. **Stuck overlay** — dragleave/drop nesting bugs leave the hint overlay visible forever; overlay must hide on drop, on dragleave to outside, and on Escape. Pinned by Task 3 component tests.
2. **Invalid content mid-session** — a dropped broken file must leave the previous config fully active. Pinned by Task 2 endpoint test (config unchanged, 400).
3. **`.profiles` dotfile dropped from Finder** — must be accepted despite being a dotfile. Pinned by Task 2 suffix test.
4. **Generic `config.yaml`** — accepted as a session trial even though the path-based loader rejects non-`*.profiles*` names. Pinned by Task 2 suffix test.
5. **Restart leakage** — the session swap must not change `state.config_path` (restart resolution unaffected) and must create zero files. Pinned by Task 2 endpoint test.

---

### Task 1: Core — `ConfigReader.from_content` (strict in-memory parse)

**Files:**
- Modify: `src/profiles/core/config/reader.py`
- Test: `tests/core/config/test_reader.py`

**Interfaces:**
- Consumes: existing `validate(raw)`, `AppConfigYaml.model_validate`, `_apply_defaults/_apply_columns/_apply_hooks/_build_configurations`, `_build_column_configs` (all already in `reader.py`/module scope).
- Produces: `ConfigReader.from_content(text: str, *, display_name: str = "<dropped config>") -> AppConfig` — classmethod, strict (raises `ValueError` on any parse/schema error), constructs `AppConfig()` with **no** config_path, performs **zero** disk I/O.

- [ ] **Step 1: Write the failing tests** in `tests/core/config/test_reader.py` (follow the file's existing style):

```python
class TestFromContent:
    def test_valid_content_applies_settings(self) -> None:
        text = "defaults:\n  title: Dropped Config\n  theme: dark\n"
        config = ConfigReader.from_content(text)
        assert config.title == "Dropped Config"
        assert config.theme == "dark"

    def test_invalid_yaml_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="dropped"):
            ConfigReader.from_content("defaults: [unclosed")

    def test_empty_content_raises(self) -> None:
        with pytest.raises(ValueError):
            ConfigReader.from_content("")

    def test_schema_violation_raises(self) -> None:
        with pytest.raises(ValueError):
            ConfigReader.from_content("defaults:\n  theme: neon-pink\n")

    def test_creates_no_files(self, tmp_path: Path) -> None:
        before = sorted(p.name for p in tmp_path.iterdir())
        ConfigReader.from_content("defaults:\n  title: X\n")
        assert sorted(p.name for p in tmp_path.iterdir()) == before
```

(Adjust field names to what `AppConfigYaml`/`_apply_defaults` actually map — read `reader.py:118-135` first; the assertions must use real mapped fields, e.g. `title` and `theme`.)

- [ ] **Step 2: Run to verify RED**

Run: `uv run pytest tests/core/config/test_reader.py::TestFromContent -v --no-cov`
Expected: FAIL — `AttributeError: ... has no attribute 'from_content'`.

- [ ] **Step 3: Implement `from_content`** in `reader.py` as a classmethod on `ConfigReader`:

One pipeline, strict at every step (mirror of `load()`'s happy path, lines ~107-124, minus fallback): `yaml.safe_load(text)` → `validate(raw)` → `AppConfigYaml.model_validate(raw)` → `config = AppConfig()` → `_apply_defaults/_apply_columns/_apply_hooks` → `config.configurations = self._build_configurations(schema)` → `_build_column_configs(config)` → return. Empty text / `None` from safe_load → `ValueError`. Wrap every failure as `raise ValueError(f"Invalid dropped configuration ({display_name}): ...") from e`. No `config_path` on the returned config; no disk access anywhere.

- [ ] **Step 4: Run to verify GREEN**

Run: `uv run pytest tests/core/config/test_reader.py -v --no-cov`
Expected: all PASS (new + existing reader tests).

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/reader.py tests/core/config/test_reader.py
git commit -m "feat(config): strict in-memory ConfigReader.from_content for dropped configs"
```

---

### Task 2: Backend — `POST /api/config/load-content`

**Files:**
- Modify: `src/profiles/server/routes/config.py`
- Test: `tests/server/test_routes_config_load.py`

**Interfaces:**
- Consumes: `ConfigReader.from_content(text, display_name=...)` (Task 1), `_config_response(state)`, existing `ServerState` fixtures in `tests/server/test_routes_config_load.py`.
- Produces: `POST /api/config/load-content` with `{"filename": str, "content": str}` → 200 + standard config response + `"session_trial": true`; 400 on bad filename/invalid content. Swap touches only `state.config`.

- [ ] **Step 1: Write the failing tests** in `tests/server/test_routes_config_load.py` (reuse the file's existing client/State fixtures):

```python
VALID = "defaults:\n  title: Dropped\n"

class TestLoadContentEndpoint:
    async def test_valid_content_swaps_config_only(self, ...):  # POST {"filename": "my.profiles", "content": VALID}
        # 200; body["session_trial"] is True; body["title"] == "Dropped"
        # state.config_path identical to before the call (compare captured value)
        # state.active_directory identical to before the call
    async def test_invalid_content_returns_400_and_keeps_config(self, ...):
        # POST {"filename": "broken.profiles", "content": "defaults: [unclosed"}
        # 400; detail mentions the parse problem; state.config is the SAME object as before
    async def test_wrong_filename_rejected(self, ...):
        # POST {"filename": "notes.txt", ...} -> 400
    async def test_accepted_suffixes(self, ...):
        # parametrize: my.profiles, .profiles, prod.profiles.yaml, data.yml, config.yaml -> all 200
    async def test_no_disk_writes(self, tmp_path, ...):
        # snapshot tmp_path + repo-root listing around the call; assert unchanged
```

- [ ] **Step 2: Run to verify RED**

Run: `uv run pytest tests/server/test_routes_config_load.py -v --no-cov`
Expected: FAIL — 404 (route does not exist).

- [ ] **Step 3: Implement the endpoint** in `routes/config.py`:

`LoadContentRequest(filename: str, content: str)` model; suffix check on `filename.lower()` against the five accepted suffixes → 400 otherwise; `ConfigReader.from_content(content, display_name=filename)` → `ValueError` → 400 with the message; `state.config = loaded` (leave `state.config_path`/`active_directory` untouched); `response = _config_response(state)`; `response["session_trial"] = True`; return.

- [ ] **Step 4: Run to verify GREEN**

Run: `uv run pytest tests/server/test_routes_config_load.py tests/server/test_routes_config.py -v --no-cov`
Expected: all PASS (new + existing config route tests).

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/routes/config.py tests/server/test_routes_config_load.py
git commit -m "feat(server): load-content endpoint applies dropped configs as session trial"
```

---

### Task 3: Frontend — drop-zone, client, refresh wiring

**Files:**
- Create: `src/profiles/web/src/components/DropConfigOverlay.tsx`
- Modify: `src/profiles/web/src/api/client.ts`, `src/profiles/web/src/api/types.ts` (`session_trial?: boolean` on `AppConfigData`), `src/profiles/web/src/App.tsx`
- Test: follow the existing vitest layout for components (see `vitest.config.ts` + any `*.test.tsx` under `src/profiles/web/src`)

**Interfaces:**
- Consumes: `POST /api/config/load-content` (Task 2); the existing post-load refresh block in `App.tsx` (~lines 320-355: apply config fields, toast, rescan with new settings, theme re-apply at ~407-410) — read it and reuse, do not duplicate.
- Produces: `loadConfigContent(filename: string, content: string): Promise<AppConfigData>` in `api/client.ts`.

- [ ] **Step 1: Write failing component tests** (vitest, existing patterns): overlay hidden by default; shown while a file drag is over the window; hidden after drop and after dragleave-to-outside; suffix filter accepts `my.profiles`, `.profiles`, `x.yaml`, `x.yml` and rejects `notes.txt`; success path calls the refresh callback with the fetched config.

- [ ] **Step 2: Run to verify RED**

Run: `cd src/profiles/web && npx vitest run` (or the repo's configured invocation)
Expected: FAIL — component/client function missing.

- [ ] **Step 3: Implement** — `DropConfigOverlay` (visual hint + click-to-open file input fallback), window-level dragenter/over/leave/drop listeners in `App.tsx` with an enter/leave counter (overlay hides on drop, outside-leave, Escape), suffix filter, `File.text()` → `loadConfigContent` → existing refresh flow, toast `Session config applied: <filename>`; rejected files → error toast.

- [ ] **Step 4: Run to verify GREEN**

Run: web vitest suite + `uv run pytest tests/app -q --no-cov`
Expected: all PASS.

- [ ] **Step 5: Rebuild web assets and commit**

```bash
uv run python -m profiles.web.build
git add src/profiles/web/src src/profiles/web/dist
git commit -m "feat(ui): drop a config file on the window to try it (session-only)"
```

---

### Task 4: Final gate + manual smoke

- [ ] **Step 1:** Scoped suite: `uv run pytest -q --deselect <58 known pre-existing failures — regenerate the list from a plain run and deselect by node id>` → all green; `ruff check . && ruff format .` clean.
- [ ] **Step 2:** Manual smoke: `uv run briefcase run macOS` (or `make briefcase-run`) → drop `my.profiles` on the window → toast "Session config applied", table refreshes, `~/.profiles/profiles.log` shows `CONFIG_LOADED`… expected: mode="auto" line for launch stays; confirm `ls` before/after shows **no new files** anywhere.
- [ ] **Step 3:** `git push origin dev`.

## Self-Review Notes

- Spec coverage: accepted suffixes (partner list) → Tasks 2+3; no-disk-write → Task 1 test + Task 2 test; UI refresh with new config → Task 3 reuses existing post-load flow; session-only (config_path/active_directory untouched) → Task 2 test; invalid-content safety → Task 1 + Task 2 tests.
- Type consistency: `from_content(text, *, display_name)` used identically in Tasks 1→2; `loadConfigContent(filename, content)` in Task 3 matches the endpoint payload; `session_trial` response key named identically in Task 2 endpoint and Task 3 type.
- Review Focus: all five pinned (tasks 2 and 3).
