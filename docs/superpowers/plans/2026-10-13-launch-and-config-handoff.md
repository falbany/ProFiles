# Implementation Plan — ProFiles Launch & Configuration Handoff

**Spec:** `docs/superpowers/specs/2026-10-13-launch-and-config-handoff-design.md`
**Branch:** create from `main` as `feat/launch-config-handoff`
**Tests:** `.venv/bin/pytest`
**One-line TDD loop per task:** write the test → watch it fail → write the code → watch it pass → commit.

> **Before starting each task, read the spec section named in its title.** The
> plan gives exact file paths, names, signatures and assertions; the spec gives
> why. Where the plan and the spec seem to disagree, the spec is the source of
> truth and the disagreement is a bug in this plan — stop and say so.

## Ground rules for every task

- **TDD.** Tests first. A task is not done until its tests fail for the right
  reason, then pass.
- **Layering (`AGENTS.md`).** No Tk imports in `core`. No business logic in
  `web/` or `desktop/`. The only place OS-specific code may appear is
  `profiles/launch/` and the two guarded `desktop/`/`launch/` helpers.
- **Coverage gate 85%** and the documented baseline failures must not worsen.
- **Semantic tokens only** in the React files — no `slate-*`. The mapping is in
  the repo memory notes.
- **Commit per task.** Message names what changed and why, in the style of
  `git log --oneline -5`.

## File map

| File | Responsibility |
|---|---|
| `src/profiles/launch/__init__.py` | public surface re-exports |
| `src/profiles/launch/context.py` | collect launch signals per OS → `LaunchContext` |
| `src/profiles/launch/resolution.py` | pure ordered decision: which config path wins |
| `src/profiles/launch/creation.py` | propose + write the starter `.profiles` |
| `src/profiles/launch/macos_bundle.py` | interim macOS `.app` generator (**interim**) |
| `src/profiles/launch/association.py` | interim Windows/Linux registration (**interim**) |
| `src/profiles/desktop/appkit_events.py` | macOS `odoc` → path callback (**interim**) |
| `src/profiles/app.py` | use the new resolution; add `--no-config-propose` |
| `src/profiles/server/state.py` | hold `config_path` |
| `src/profiles/server/routes/config.py` | `/api/config` additions + `/load`, `/create` |
| `src/profiles/server/routes/fs.py` | `include_hidden` for config browsing |
| `src/profiles/web/src/api/types.ts`, `client.ts` | new fields + calls |
| `src/profiles/web/src/components/LoadConfigModal.tsx` | new UI |
| `src/profiles/web/src/components/StatusBar.tsx`, `App.tsx` | wire the button |
| `tests/launch/*` | the source of truth for platform behaviour |
| `tests/server/test_routes_config_load.py` | route tests incl. G5 (extends `test_routes_config.py`) |
| `tests/server/test_routes_fs_browse.py` | `include_hidden` behaviour (extends the fs tests) |

---

## Phase 1 — the pure core (no OS, no UI)

Everything here is platform-independent and fully testable. Get it right first.

### Task 1 — `LaunchContext` + signal detection

**Spec:** §1. **Files:** new `src/profiles/launch/__init__.py`,
`src/profiles/launch/context.py`; new `tests/launch/test_context.py`.

**Test cases** (`tests/launch/test_context.py`):

```python
def test_argv_documents_are_parsed(monkeypatch) -> None:
    # sys.argv = ["prog", "/a/my.profiles", "/b/proj.profiles"]
    # => document_paths == (Path("/a/my.profiles"), Path("/b/proj.profiles"))

def test_non_config_argv_ignored() -> None:
    # "prog", "file.mttl" -> document_paths == ()

def test_flag_like_argv_ignored() -> None:
    # "prog", "--server-only" -> document_paths == (), no crash

def test_relative_document_is_resolved_to_absolute() -> None: ...

def test_working_directory_falls_back_to_cwd(monkeypatch) -> None:
    # no osascript available => working_directory == Path.cwd()

def test_finder_probe_failure_is_silent(monkeypatch) -> None:
    # subprocess.run raises TimeoutExpired / OSError => working_directory is None
    # or cwd; NEVER raises

def test_detect_never_raises_on_hostile_argv() -> None:
    # sys.argv = ["prog", "", None-ish strings] => no exception

def test_source_is_documented_enum() -> None:
    # source in {"document", "launcher", "cwd", "explicit"}
```

**Interface to implement:**

```python
# src/profiles/launch/context.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

CONFIG_SUFFIX = ".profiles"          # also matches the legacy ".profiles.yaml"? see note
_FINDER_PROBE_TIMEOUT_S = 2.0

@dataclass(frozen=True)
class LaunchContext:
    document_paths: tuple[Path, ...]
    working_directory: Path | None
    explicit_config: Path | None
    source: str                        # "document" | "launcher" | "cwd" | "explicit"

def detect_launch_context(argv: list[str] | None = None) -> LaunchContext: ...
def _documents_from_argv(argv: list[str]) -> tuple[Path, ...]: ...
def _finder_working_directory() -> Path | None:      # macOS-only, best effort
```

**Notes for the implementer:**
- `_documents_from_argv` accepts a path whose name ends with `.profiles` **or**
  `.profiles.yaml`. Everything else is ignored. Return absolute paths.
- `_finder_working_directory` may only run the probe when `sys.platform ==
  "darwin"`; on other platforms return `None` immediately (no subprocess).
- The probe runs `osascript -e 'tell application "Finder" to get POSIX path of
  (target of front window as alias)'` with `timeout=_FINDER_PROBE_TIMEOUT_S`,
  `capture_output=True`, `check=False`. Wrap in
  `try/except (OSError, subprocess.SubprocessError)`. **Never** let a failure
  escape.
- `explicit_config` is **not** parsed here from `--config`; leave it `None` and
  let the caller set it (Task 3). Keep this function about *inference*.
- Export `LaunchContext`, `detect_launch_context` from `__init__.py`.

**Done when:** the tests above pass, `ruff check src/profiles/launch` is clean.

---

### Task 2 — resolution + creation

**Spec:** §1. **Files:** `src/profiles/launch/resolution.py`,
`src/profiles/launch/creation.py`; new `tests/launch/test_resolution.py`,
`tests/launch/test_creation.py`.

**Test cases** (`test_resolution.py`):

```python
def test_explicit_config_wins_everything() -> None:
    # ctx.explicit_config set AND a document present => the explicit path

def test_document_wins_over_search() -> None:
    # document_paths=("/tmp/x/my.profiles"), working_directory with a real
    # tree => returns the DOCUMENT path

def test_first_document_used_when_several() -> None: ...

def test_tree_search_from_working_directory(tmp_path) -> None:
    # ./.a/.b/.c/my.profiles  (depth 3) => found

def test_no_match_returns_none(tmp_path) -> None:
    # empty tree => None

def test_missing_working_directory_uses_cwd(tmp_path, monkeypatch) -> None:
    # working_directory=None, chdir tmp_path => searches tmp_path

def test_explicit_config_does_not_need_to_exist() -> None:
    # an explicit path is returned verbatim, no existence check here
```

**Test cases** (`test_creation.py`):

```python
def test_starter_written_where_asked(tmp_path) -> None:
    # target == tmp_path/".profiles"; file exists afterwards and is non-empty

def test_no_clobber(tmp_path) -> None:
    # pre-existing content is preserved; returns a "skipped" outcome

def test_template_is_the_project_starter() -> None:
    # assert STARTER_CONFIG_TEMPLATE is used (grep a known comment)
```

**Interface to implement:**

```python
# resolution.py
def resolve_config_path(ctx: LaunchContext) -> Path | None: ...


# creation.py
@dataclass(frozen=True)
class CreationResult:
    status: Literal["CREATED", "SKIPPED", "FAILED"]
    path: Path
    message: str


def propose_creation(target: Path) -> CreationResult: ...
```

**Notes:** `resolve_config_path` order is exactly the spec's: explicit →
first document → `find_config_file(working_directory or cwd, max_depth=5)` →
`None`. Reuse `profiles.core.config.io.yaml_io.find_config_file`; do not
re-write the search. `propose_creation` reuses
`profiles.core.config.template.STARTER_CONFIG_TEMPLATE` and
`actions.write_starter_config`'s existing behaviour — no new template.

**Done when:** all pass, ruff clean, and `find_config_file` semantics are
unchanged (its own tests still green).

---

## Phase 2 — the app uses it

### Task 3 — `--config` explicit + wire resolution into `ProFileApp`

**Spec:** §4, G3. **Files:** `src/profiles/app.py`;
`tests/test_app.py` (extend existing).

Add a module-level helper so it is testable without launching anything:

```python
# src/profiles/app.py
def _resolve_startup_config(explicit: Path | None) -> tuple[Path | None, bool]:
    """Return (config_path, config_is_missing)."""
    ctx = detect_launch_context()
    ctx = replace(ctx, explicit_config=explicit)
    return resolve_config_path(ctx), False
```

**Test cases:**

```python
def test_explicit_config_flag_wins() -> None
def test_no_args_in_dir_with_config_finds_it(monkeypatch, tmp_path) -> None
def test_no_args_no_config_returns_none() -> None
```

Then in `ProFileApp._load_configuration`, call the helper instead of the bare
`load_config(self._config_path)`, and when the result is `None` **and**
`self._server_only is False`, log the offer via `propose_creation`'s message
(no blocking prompt in server mode).

**New CLI flag:** `--no-config-propose` (store_true) — "do not offer to create
a `.profiles` at startup". Add to the argparse block and the epilog examples.
This makes the offer escapable in CI.

**Done when:** the existing `TestRun`/`TestMain` tests still pass, plus the new
ones. Do not touch `_run_gui`, `_run_web_gui`, or `_run_server_only` internals
beyond the resolution call.

---

### Task 4 — `ProFiles.pyw` uses the invoking folder

**Spec:** §4. **Files:** `ProFiles.pyw`; `tests/test_shortcut_launch.py` (new).

Current (the bug):

```python
os.chdir(root)  # root == Path(__file__).parent
```

New behaviour, in `_run()`, **before** the chdir:

```python
from profiles.launch import detect_launch_context

ctx = detect_launch_context()
target = ctx.working_directory or root
if target.is_dir():
    os.chdir(target)
```

Keep `_add_src_to_path(root)` exactly as-is (it must still point at the
*shortcut's* repo root, not the invoking folder — that is how imports resolve).

**Test cases** (unit-test a tiny extracted helper, not the file itself):

```python
def test_shortcut_uses_invoking_folder() -> None
def test_shortcut_falls_back_to_script_folder() -> None
def test_add_src_to_path_still_targets_the_script_repo() -> None
```

Extract the decision into `_choose_working_dir(root: Path) -> Path` in
`ProFiles.pyw` and test it with a stubbed `detect_launch_context`.

**Done when:** the three tests pass; `python3 ProFiles.pyw` from a temp dir with
a `.profiles` beside it still launches.

---

## Phase 3 — server endpoints

### Task 5 — expose `config_path` and add `/load` + `/create`

**Spec:** §6. **Files:** `src/profiles/server/state.py`,
`src/profiles/server/routes/config.py`; new
`tests/server/test_routes_config_load.py` (the existing route tests live in
`tests/server/test_routes_config.py` — follow that file's fixture style).

**State:** add `config_path: Path | None = None` to `ServerState`.

**`GET /api/config`** gains two fields, additive only:

```json
{ "...existing fields...",
  "config_path": "/abs/path/.profiles",
  "config_exists": true }
```

**`POST /api/config/load`** — body `{ "config_path": "..." }`:

```python
class LoadConfigRequest(BaseModel):
    config_path: str


@router.post("/load")
async def load_config_endpoint(payload: LoadConfigRequest, request: Request) -> dict: ...
```

Steps: resolve+validate the path exists and ends with `.profiles`/`.profiles.yaml`
(→ 400 with a clear detail otherwise); `ConfigReader(path).load()`; compute the
active directory with the **G5 rule** below; replace `state.config` and
`state.active_directory`; return the same shape as `GET /api/config`.

**`POST /api/config/create`** — body `{ "directory": "..." }`: writes the
starter into that directory via `launch.creation.propose_creation`, then
returns the `GET /api/config` payload for the freshly created file. Never
overwrites (400 if a config already exists there).

**G5 rule** (spec §6, verbatim in behaviour):

```python
active = (find_configuration_by_hostname(cfg, hostname)
          if cfg.configurations else None)
if active and active.scan:
    active_directory = <first existing path in active.scan>   # machine wins
elif config_parent.is_dir():
    active_directory = config_parent                          # new fallback
else:
    active_directory = <existing auto_select_directory() fallback>
```

Read `select_active_configuration`'s answer through
`find_configuration_by_hostname`; never modify the matcher.

**Test cases** (`tests/server/test_routes_config_load.py`), using the
`httpx.AsyncClient` + `ASGITransport` pattern from
`tests/server/test_routes_config.py` (there is **no** `TestClient` fixture in
this project — do not invent one):

```python
def test_get_config_reports_path_and_existence() -> None
def test_load_valid_file_replaces_state() -> None
def test_load_missing_file_is_400() -> None
def test_load_non_config_suffix_is_400() -> None
def test_load_g5_machine_config_wins() -> None
    # a .profiles whose [CONFIGURATION_*] matches the hostname => active dir
    # is that config's scan path, NOT the file's folder
def test_load_g5_falls_back_to_file_folder() -> None
    # no configurations at all => active dir == the file's parent
def test_create_writes_starter() -> None
def test_create_refuses_overwrite() -> None
```

**Done when:** all pass and `GET /api/config` remains backward compatible for
the existing web UI (old fields untouched).

---

### Task 6 — `fs/browse` can show config files

**Spec:** §6. **Files:** `src/profiles/server/routes/fs.py`;
new `tests/server/test_routes_fs_browse.py`.

Add `include_hidden: bool = Query(default=False)`. When `False`, behaviour is
**byte-identical** to today. When `True`, keep dotfiles **only if** the name ends
with `.profiles` or `.profiles.yaml` — do not dump all of `.git`, `.venv`, etc.
Also return the entry's extension so the UI can highlight config files.

**Test cases:**

```python
def test_default_hides_hidden() -> None
def test_include_hidden_reveals_only_configs() -> None
def test_hidden_config_flagged_as_config() -> None
```

---

## Phase 4 — web UI

### Task 7 — API client + types

**Spec:** §6. **Files:** `src/profiles/web/src/api/types.ts`,
`src/profiles/web/src/api/client.ts`.

Add to `AppConfigData`: `config_path: string;` and `config_exists: boolean;`

```ts
export async function loadConfigFile(configPath: string): Promise<AppConfigData>;
export async function createConfigFile(directory: string): Promise<AppConfigData>;
export async function browseForConfigFiles(path: string): Promise<BrowseResult>;
```

No component changes in this task — just the client and types, so the UI task
is a pure render task.

**Done when:** `npx tsc --noEmit` is clean in `src/profiles/web`.

---

### Task 8 — `LoadConfigModal` + the status-bar button

**Spec:** §6, G3, G4. **Files:** new
`src/profiles/web/src/components/LoadConfigModal.tsx`, plus
`StatusBar.tsx` and `App.tsx`.

**Component contract** (mirror `DirectoryPickerModal`'s prop style and structure
so it is recognisable):

```tsx
export interface LoadConfigModalProps {
  isOpen: boolean;
  activeConfigPath?: string;
  configExists?: boolean;        // false => open in "create" mode
  onClose: () => void;
  onLoaded: (config: AppConfigData) => void;
}
```

Behaviour:
- Browses with `browseForConfigFiles` (which passes `include_hidden=true`).
- Lists directories plus **any** `*.profiles` / `.profiles.yaml` files, the
  config files marked with a `FileCog` icon and selectable; directories stay
  navigable.
- Confirm loads via `loadConfigFile`, then `onLoaded(config)`.
- When `configExists === false`, the modal opens in **create mode**: a single
  prominent button writes the starter into the browsed directory
  (`createConfigFile`) and the wording is a *proposal* ("No configuration file
  was found. Create one here?"), never an overwrite.
- Escape/backdrop closes. Same `fixed inset-0 z-50 … bg-black/60 backdrop-blur-sm`
  shell as `DirectoryPickerModal`.

**StatusBar:** add a "Load config…" button using the `FileCog` lucide icon,
placed next to the existing Config/Reload buttons, following the same
`text-ink-muted hover:text-ink` button style. Show the active config's
filename as the button title when one is loaded
(`title={`Load a different .profiles file (active: ${name})`}`).

**App.tsx:** add `showConfigPicker` state; open the modal from the new button;
on `onLoaded`, `setConfig(cfg)`, then re-run the existing scan path
(`handleScan()`), and toast the result. On startup, if `config.config_exists`
is false, open the modal automatically in create mode.

**Tests:** no test runner is configured for the web app, so verification here is
`npx tsc --noEmit` plus `npm run build`. Assert by hand against the spec's
Success criteria.

**Done when:** typecheck + build pass, and manually: the button loads a chosen
config, the create state appears only when `config_exists` is false, and the
active filename shows in the tooltip.

---

## Phase 5 — interim platform packaging

> Both tasks in this phase are explicitly interim. They are written so that
> deleting them deletes their tests, per spec §2/§3.

### Task 9 — interim macOS bundle + `odoc` receiver

**Spec:** §2, §9. **Files:** `src/profiles/launch/macos_bundle.py`,
`src/profiles/desktop/appkit_events.py`, plus
`tests/launch/test_macos_bundle.py`.

**`macos_bundle.py`** exposes:

```python
@dataclass(frozen=True)
class BundlePlan:
    app_dir: Path
    info_plist: str
    executable: str


def generate_bundle(output_root: Path, interpreter: Path) -> BundlePlan: ...
def register_bundle(app_dir: Path) -> bool: ...  # lsregister -f
def unregister_bundle(app_dir: Path) -> bool: ...  # lsregister -u
```

**Test cases** (`test_macos_bundle.py` — pure, no OS calls; assert on text):

```python
def test_info_plist_lints() -> None
    # plutil -lint if on darwin, else a structural XML/plist parse
def test_info_plist_declares_profiles_extension() -> None
    # 'public.filename-extension' == 'profiles'; LSHandlerRank == 'Owner'
def test_wrapper_passes_through_arguments() -> None
    # the generated script contains '"$@"'
def test_wrapper_resolves_repo_root_relatively() -> None
    # no absolute repo path baked in
def test_bundle_is_relocatable(tmp_path) -> None
    # generate into a different root, no absolute path to the source tree
```

**`appkit_events.py`** (macOS only, importable anywhere):

```python
def install_document_handler(on_documents: Callable[[list[str]], None]) -> bool:
    """Wire macOS 'odoc' into *on_documents*. False when unavailable."""
```

Guard the `AppKit` import in a `try/except ImportError` and return `False` on
any failure, so a Windows/Linux run imports the module without pyobjc. Call it
from `src/profiles/desktop/launcher.py` before `webview.start()`; on `False`,
log at debug and continue — the app must still start.

**Test:** with pyobjc absent the import must succeed and the function must
return `False` (this is the CI case, so it is always exercised).

**Done when:** the bundle builds, registers, and double-clicking a
`my.profiles` opens a ProFiles window whose `GET /api/config` reports that
`config_path`. Record the result in the spec comment for §9.

---

### Task 10 — interim Windows & Linux association CLI

**Spec:** §3. **Files:** `src/profiles/launch/association.py`;
`tests/launch/test_association_*.py` (per-platform, skipped off-platform).

```python
def install() -> list[str]: ...  # returns human-readable actions taken
def status() -> list[str]: ...
def remove() -> list[str]: ...
def main(argv: list[str] | None = None) -> int: ...
```

- **Windows:** `HKCU\Software\Classes\.profiles` → default value
  `ProFiles.profiles`; `…\ProFiles.profiles\shell\open\command` →
  `"<ProFiles.pyw>" "%1"`; `…\Applications\ProFiles.pyw\SupportedTypes`.
  Import `winreg` lazily inside the function.
- **Linux:** `~/.local/share/applications/profiles.desktop` with
  `MimeType=text/x-profiles;` and `%f` in `Exec`; a matching
  `~/.local/mime/packages/text-x-profiles.xml` with the `*.profiles` glob; then
  `update-mime-database` / `update-desktop-database` if they exist. Missing
  tools → warning string, not an exception.
- `remove()` deletes exactly what `install()` wrote, nothing else.
- CLI: `python -m profiles.launch.association {install|status|remove}`.

**Tests:** the Windows and Linux files **skip** unless running on that OS
(`@pytest.mark.skipif(not _IS_WINDOWS, …)`), but the message strings still
exhaustively list every path each one writes — that is how a reviewer verifies
`remove()` mirrors `install()` without owning all three OSes. Add a pure test
that `remove()`'s paths are a subset of `install()`'s paths.

**Done when:** on each OS the install→status→remove cycle runs and leaves the
system as found (assert with `reg query` / `gio mime` by hand and record it).

---

## Phase 6 — verification and handover

### Task 11 — full-suite green + spec cross-check

1. `uv pip install httpx pytest-timeout` (needed by `tests/server/*`).
2. `.venv/bin/pytest tests --timeout=20` — full pass; compare against the
   documented baseline (923 passed, plus the 7 known Tkinter failures).
3. `ruff check .` / `ruff format --check .` (4 pre-existing `I001` findings in
   `tests/` are known; no new ones).
4. `cd src/profiles/web && npx tsc --noEmit && npm run build`.
5. Walk the spec's **Success criteria** list and tick each line by hand,
   recording how it was checked.
6. Update the spec's Status to `Implemented`, note anything that did not match.

### Task 12 — commit and hand over

Commit in logical chunks (one per task, if not already), push the branch, and
open a PR whose body lists: the four user-visible behaviours, the two interim
modules and their deletion criteria, the Briefcase spike as a follow-up, and
the verification evidence from Task 11.

---

## Sequence and risk

| Phase | Risk | Why it is in this order |
|---|---|---|
| 1 (core) | none | pure, fully testable, no dependencies |
| 2 (app/shortcut) | medium | changes startup; gated by the existing `TestRun` tests |
| 3 (server) | medium | additive endpoints; G5 is the only behavioural change |
| 4 (UI) | low | no automated tests; verify by hand, keep the build green |
| 5 (packaging) | high | OS-specific; macOS verified here, Win/Linux need an owner |
| 6 | none | verification only |

**Stop and ask before proceeding if:** a Phase 1 test reveals
`find_config_file`'s semantics differ from the spec; G5's two branches cannot
be satisfied without editing `select_active_configuration`; or the server's
existing `/api/config` response is consumed anywhere the plan has not listed
(a grep for `fetchConfig` is the check).
