# ProFiles Launch & Configuration Handoff — Design Spec

Date: 2026-10-13
Status: Draft (pending user review)
Scope: `ProFiles.pyw`, `src/profiles/app.py`, `src/profiles/desktop/**`,
`src/profiles/server/**`, `src/profiles/web/src/**`, new `src/profiles/launch/`,
`pyproject.toml` (`[tool.briefcase]`)

> **Platform reality.** ProFiles is a multi-OS application (Windows, macOS,
> Linux — see the classifiers in `pyproject.toml`). Every decision below is
> stated for all three. Where a platform's behaviour is stated from convention
> rather than measurement, that is called out explicitly.

## Problem

Double-clicking a `.profiles` file does nothing: macOS has no registered handler
for the extension (verified — `LSCopyApplicationURLsForBundleIdentifier` and a
plain `open <file>` both fail with `kLSApplicationNotFoundErr` / `-10814` for a
`*.profiles` file today). Windows has no registry entry and Linux no MIME type,
so the same holds there by construction.

Double-clicking `ProFiles.pyw` launches the app, but the `.profiles` file
sitting next to it is not used. Two distinct causes, both verified:

1. **The shortcut's CWD is the shortcut's own directory.**
   `ProFiles.pyw::_run()` calls `os.chdir(root)` where `root` is
   `Path(__file__).resolve().parent`. A copy on `~/Desktop` therefore searches
   for config starting at `~/Desktop` — never the folder the user
   double-clicked *from*. Simulated exactly that case: `config_path` resolved to
   `~/Desktop/.profiles` (absent), `search_dir` came back **empty**, and only
   the default `('All', '.lnk')` extensions were available. The repo's real
   `.profiles` (with `Z:/Projects/Engineering`, `~/Downloads`, …) was never
   consulted.

2. **No in-app way to load a chosen `.profiles`.**
   The web UI can pick a *directory* (`POST /api/config/select-directory`) and
   rescan it, but there is no control that points the app at a specific
   configuration file, and no code path that offers to create one when none is
   found. The Tk GUI has this behaviour (`MainWindow._check_config_file()`
   → `_create_config_file()`), the web app does not.

The user's requirement, verbatim:

- Double-click a `.profiles` file → the web app starts based on that file.
- Launch via `ProFiles.pyw` → analyse the tree (5 subfolder deep), find a
  `.profiles`, load it.
- No `.profiles` found → propose to create one.
- A button in the web app loads a `.profiles` file.
- The shortcut uses **the folder it was double-clicked from** (Finder's current
  folder), and finds the `.profiles` **next to the shortcut**.
- When a `.profiles` is opened by double-click, its **own folder becomes the
  active scan directory** *if and only if* no `[CONFIGURATION_*]` machine config
  matches.

## Verified platform facts (measured on this macOS, not assumed)

Every claim below was established with throwaway bundles, since removed:

- A `.app` bundle registered with `lsregister` **does** claim `*.profiles`
  files: `open my.profiles` launches the bundle and returns exit 0.
- The double-clicked path **does** reach a Python launcher, via the
  `NSApplication` delegate method `application:openFiles:`. A probe bundle
  received `['/Users/…/pfa2/my.profiles']`. (An earlier test appeared to show
  no delivery; that was my own bug — wrong AppleEvent class constant and a
  missing PyObjC delegate prototype — not a platform limitation.)
- **Dotfiles are not openable.** `open .profiles` exits 0 but launches nothing
  and delivers nothing. macOS treats the whole `.profiles` name as the
  extension, so it never resolves to the claimed type. `*.profiles`
  (e.g. `my.profiles`) works; a literally-named `.profiles` cannot be
  double-clicked by the user either.
- An arm64 Mach-O executable receives **no** `argv`; a plain C launcher gets
  nothing. Delivery only works through the AppKit delegate, so the launcher
  must be a real `NSApplication`.
- `pyobjc` is already in the venv (`objc`, `Cocoa`, `AppKit`, `Foundation` all
  import), as is `webview`/pywebview. No new dependency is required.

**Cross-platform reality.** The macOS rows above are measured. The Windows and
Linux rows below are designed from platform convention — they are the kind of
statement that must be verified on the target OS before it is trusted, and the
tests in §7 are written so that verification is possible.

| Platform | Association mechanism | Document path arrives how | CWD on double-click |
|---|---|---|---|
| macOS | `.app` + `CFBundleDocumentTypes`, activated by `lsregister` | AppKit `application:openFiles:` (and `sys.argv`) | the shortcut's **own** directory — hence the probe |
| Windows | Per-user registry `HKCU\Software\Classes` + `.profiles` → `ProFiles.pyw "%1"` (no admin needed) | `sys.argv[1]` | the invoking **file's** directory |
| Linux | `.desktop` file + `mimeapps.list`, with a `*.profiles` glob in `~/.local/mime/packages` | `sys.argv[1]` | the invoking file's directory |

The Windows/Linux CWD note is why no Finder-equivalent probe exists there: the
OS already supplies the invoking folder. The probe is macOS-specific because
macOS *removes* it.

## Goals

- **G1** — Double-clicking any `*.profiles` file opens the ProFiles web app
  configured from that exact file, on all three platforms.
- **G2** — Double-clicking the shortcut (or `.pyw`) starts config discovery
  from the folder the user was in (Finder's current folder on macOS, the
  OS-supplied CWD on Windows/Linux), falling back sanely.
- **G3** — When no `.profiles` is found anywhere in the 5-level tree, the app
  offers to create a starter file instead of silently using defaults.
- **G4** — A "Load config…" button in the web UI loads any `.profiles` file,
  using the same resolution path as the double-click.
- **G5** — Opening a `.profiles` by double-click sets **its folder** as the
  active scan directory when no `[CONFIGURATION_*]` matches; when a machine
  config *does* match, that config wins and the folder is only offered in the
  directory picker.
- **G6** — Everything keeps working unchanged when launched from a terminal
  (`python -m profiles`, `--server-only`, `--config`, `--init`) on all three
  platforms.

## Non-goals

- **NG1** — No Briefcase build this change, no installer artefacts, no code
  signing. The `document_types` declaration is *written down* (packaging decision
  preamble) but not built; signing and notarisation are Briefcase's, deferred to
  §9.
- **NG2** — No assumption that the literally-named `.profiles` dotfile can be
  double-clicked (macOS cannot deliver it, and a Linux MIME `glob` for it
  matches nothing). Named files (`my.profiles`, `project.profiles`) are the
  double-click target. The dotfile still loads fine through the shortcut, the
  CLI, and the "Load config…" button.
- **NG3** — No signed `.app` bundle, no ad-hoc/Developer-ID codesigning, and
  no notarisation. An unsigned bundle registered with `lsregister` claims the
  extension and receives documents; signing is a packaging concern that
  Briefcase will own.
- **NG4** — No change to how `[CONFIGURATION_*]` matching works; this adds a
  fallback *around* the existing matcher, never inside it.
- **NG5** — No rewrite of the config model. `AppConfig.config_path` already
  carries the file path; it is reused as-is.
- **NG6** — No change to how `find_config_file` searches (depth 5, primary
  `.profiles` then the `.profiles.yaml` fallback).

## Constraints

- **C1 — Layering must hold** (`AGENTS.md`): no Tk imports in `core`, no
  business logic in the web/desktop shells.
- **C2 — Briefcase cannot build in this repo folder today.** The repo is inside
  an iCloud-synced tree (`CLOUDDESKTOP` active; path under `~/Documents`).
  Everything in §2/§3 must therefore work *without* Briefcase, and must be
  deletable when Briefcase becomes available.
- **C3 — Multi-OS.** Nothing introduced may assume macOS-only behaviour. Any
  OS-specific code is isolated behind the platform dispatch in §1 and tested
  against the branch it takes; Windows/Linux behaviour stated from convention is
  marked as such and needs on-OS verification before it is trusted.
- **C4 — Quality gates unchanged.** The 85% coverage gate and the pre-existing
  Tkinter test failures baseline must not grow.

## Packaging decision: Briefcase first, interim bundle second

**Briefcase is the target.** The project already ships a `[tool.briefcase]`
block in `pyproject.toml` and three `make briefcase-*` targets, and Briefcase
supports document types as a first-class, cross-platform setting:

```toml
[tool.briefcase.app.profiles]
document_types = ["profiles"]

[tool.briefcase.app.profiles.macOS]
CFBundleTypeRole = "Editor"
LSHandlerRank = "Owner"
```

That one declaration generates, per platform, what §2 and §3 would otherwise
build by hand: the `Info.plist` document type on macOS, the registry entry on
Windows, the `.desktop` MIME registration on Linux. It also brings code signing
and notarization, which a hand-built unsigned bundle cannot.

**But Briefcase cannot be used to build this project yet.** From Briefcase's own
platform docs:

> iCloud … prevents apps from being signed and notarized, and app signing is a
> requirement for all apps on macOS. As a result, Briefcase cannot be used to
> generate macOS apps in a folder that is synchronized with iCloud.

Verified on this machine: `CLOUDDESKTOP` (Desktop & Documents sync) is **active**
and the repo lives at `/Users/falbany/Documents/Code/GitHub/ProFiles`, inside the
synchronized tree. `briefcase create` will fail regardless of configuration.
This is recorded as constraint **C2** below, not discovered during the build.

**Two further reasons the interim bundle is still written:**

- Briefcase bundles its **own** Python and dependencies; the interim bundle
  execs the project's `.venv`, so it keeps working from a clone with zero build.
- Briefcase's documented document-type examples are all Toga. This app uses
  pywebview, so how the path reaches a non-Toga `main()` is **unverified** — it
  needs a spike (see §9). The interim path is verified today.

**Migration is therefore one-way and clean.** When the repo moves to a
non-synchronized folder: run `briefcase create`, confirm path delivery against
the spike's findings, then delete §2 and §3. Nothing else in the design changes,
because §1, §4, §5, §6 and §7 are delivery-agnostic — they consume a path
wherever it came from.

### 1. New package: `src/profiles/launch/`

Single responsibility: *decide which config file and which starting directory
this process should use*, given every signal available on each platform.
It is pure core-layer logic — no Tk, no FastAPI, no AppKit.

```
src/profiles/launch/
├── __init__.py          # public surface
├── context.py           # launch-context detection (per OS)
├── resolution.py        # ordered resolution: explicit > document > finder > cwd
└── creation.py          # "should we propose creating a .profiles?" + write it
```

**`context.py`** — `LaunchContext` dataclass, the single source of truth:

```python
@dataclass(frozen=True)
class LaunchContext:
    document_paths: tuple[Path, ...]  # *.profiles handed over by the OS
    working_directory: Path | None  # where the OS says the user was
    explicit_config: Path | None  # --config
    source: str  # "document" | "launcher" | "cwd" | "explicit"
```

Detection, in order of trust:

| Signal | macOS | Windows / Linux |
|---|---|---|
| `document_paths` | AppKit `application:openFiles:` (bundle) **and** `sys.argv` (so `open -a … file`, and the `.pyw "%1"` registry form, both work) | `sys.argv` |
| `working_directory` | Finder window target, via a tiny `osascript` probe with a hard timeout | `Path.cwd()` — the OS already sets it to the invoking file's folder |
| `explicit_config` | `--config` | same |

Two points that matter for reliability:

- **`sys.argv` is read on every platform, always.** It is the one channel that
  works everywhere and requires no registration at all. The AppKit delegate and
  the registry are *additions* on top, not prerequisites. A user who runs
  `ProFiles.pyw my.profiles` from a terminal gets the documented behaviour on
  all three OSes today.
- **The Finder probe is macOS-only and best-effort.** 2-second timeout,
  swallows every failure, returns `None`, never prompts, never blocks startup.
  It is a fallback: the bundle supplies the authoritative answer for a
  double-clicked document, and the probe only matters for the shortcut.

**`resolution.py`** — the decision order, one function, no side effects:

```python
def resolve_config_path(ctx: LaunchContext) -> Path | None
```

1. `--config` (explicit always wins — unchanged CLI behaviour)
2. a `*.profiles` document, if any
3. `find_config_file(5)` from the working directory
4. `None`

Step 3 covers "find the `.profiles` next to the shortcut": the shortcut's own
directory is seeded into `working_directory` when the probe yields nothing, so
a shortcut sitting beside a config still finds it.

**`creation.py`** — `plan_config_creation(target: Path) -> Path`, wrapping the
existing `STARTER_CONFIG_TEMPLATE` write that `MainWindow._create_config_file`
and `actions.write_starter_config` already use. No new template, no new YAML
logic; this is the one place that decides *whether* to offer creation.

### 2. Interim macOS bundle: `launch/macos_bundle.py` (delete when Briefcase lands)

A generator, not a checked-in artifact:

```
build/macos/ProFiles.app/
└── Contents/
    ├── Info.plist      # CFBundleDocumentTypes → *.profiles, Owner rank
    ├── MacOS/ProFiles  # shell wrapper → exec .venv/bin/python -m profiles --gui
    └── Resources/…     # icon if present
```

The `Info.plist` content mirrors what Briefcase generates from the
`document_types` block above, so the briefcase and interim paths produce an
equivalent declaration.

- The wrapper is a **relocatable shell script** that resolves the repo root by
  walking up from its own location, then execs the venv Python. It passes
  through `"$@"` so a double-clicked document path arrives on `sys.argv` — the
  one channel that needs no registration at all.
- Registration: `lsregister -f` on the built bundle, with a clear "restart
  Finder or log out" note. Re-runnable and idempotent.

The AppKit launcher (`src/profiles/desktop/`) becomes the document receiver:

```python
# desktop/appkit_events.py
def install_document_handler(on_documents: Callable[[list[str]], None]) -> None:
    """Route macOS 'odoc' AppleEvents into on_documents (list of paths)."""
```

Installed before `webview.start()`, converting `application:openFiles:` into the
same `LaunchContext.document_paths` the rest of the app consumes. If the extra
registration fails (older macOS, unexpected runtime), the app still starts
normally with argv/CWD-based resolution — the handler is strictly additive.
This module is **guarded to macOS** and is a no-op import elsewhere, since
pyobjc is not installed on Windows or Linux (C3).

### 3. Interim Windows & Linux association: `launch/association.py` (delete when Briefcase lands)

The same "click a config → ProFiles opens it" behaviour, per-OS. All of it is
**per-user, no administrator rights needed**:

- **Windows** — write `HKCU\Software\Classes\.profiles` (default value
  `ProFiles.profiles`) plus `HKCU\Software\Classes\ProFiles.profiles\shell\\open\command`
  with value `"C:\…\ProFiles.pyw" "%1"`, and the matching `HKCU\…\Applications\ProFiles.pyw\SupportedTypes`.
  Uses `winreg`, which the repo can import only on Windows (guard with the
  existing `_IS_WINDOWS` pattern from `utils/file_utils.py`).
- **Linux** — write a `~/.local/share/applications/profiles.desktop` with
  `MimeType=text/x-profiles;` and `%f` in the `Exec` line, a matching
  `~/.local/mime/packages/text-x-profiles.xml` declaring the `*.profiles` glob
  (the literally-named dotfile is unreachable here too — a `glob` for
  `.profiles` matches nothing), then run `update-mime-database` and
  `update-desktop-database` if present. Missing tools are a warning, not a
  failure.

One module, three commands behind a single CLI:

```
python -m profiles.launch.association install   # register for this user
python -m profiles.launch.association status    # what is registered now
python -m profiles.launch.association remove    # undo, cleanly
```

`install` is idempotent and safe to re-run; `remove` deletes exactly what
`install` wrote and nothing else. Both print what they touched, because the
user is expected to run them by hand before Briefcase takes over. The
`HKCU`-based registry writes are stated from Windows convention, not measured
(C3).

### 4. `ProFiles.pyw` — stop chdir'ing to itself

Today:

```python
os.chdir(root)  # root == Path(__file__).parent   ← always the copy's dir
```

New:

```python
ctx = detect_launch_context()  # launch/context.py
os.chdir(ctx.working_directory or root)
```

Order: the folder the user double-clicked from (Finder probe / argv) if it is a
real directory, else the shortcut's own directory, else `Path.cwd()`. The
existing "`src/` at the front of `sys.path`" behaviour is untouched. This fix
is what makes the Desktop copy work on **all three** platforms — on Windows
and Linux the OS-set CWD already carries the invoking folder, so no probe is
involved.

### 5. Server: config becomes loadable at runtime

`ServerState` holds `config` and `active_directory`. Two changes:

- **`GET /api/config`** gains `config_path` (currently `AppConfig.config_path`
  exists but is never exposed) so the UI can show *which* file is in force.
- **`POST /api/config/load`** — `{ config_path: str, set_folder_active?: bool }`.
  Re-runs `ConfigReader(path).load()`, computes the active directory per
  **G5** below, replaces `ServerState.config` + `active_directory`, and returns
  the same payload as `GET /api/config` so the UI just re-renders. Invalid path
  → `400` with the reason.

**G5's rule**, implemented in `server/routes/config.py` (it is resolution
policy, so it lives beside the other resolution and stays testable):

```python
active = find_configuration_by_hostname(cfg, hostname) if cfg.configurations else None
if active and active.scan:
    active_directory = <first existing scan path>     # machine config wins
elif config_folder_exists:
    active_directory = <the opened .profiles's folder> # the new fallback
else:
    <existing auto_select_directory() fallback>
```

This never touches `select_active_configuration`; it reads its answer.

### 6. Web UI: the load button + the offer

- A **"Load config…"** button in the status bar (next to the existing
  Config/Log buttons) opening `LoadConfigModal`.
- `LoadConfigModal` reuses **`DirectoryPickerModal`**'s shape but browses
  files: it lists entries and highlights `*.profiles` / `.profiles.yaml`,
  showing `.profiles` files that the current picker deliberately hides
  (`fs/browse` skips names starting with `.`; the loader sends
  `include_hidden` or a dedicated `/api/fs/config-files` route — one small
  addition, hidden dotfiles only when explicitly asked for).
- On success it replaces `config` state and re-scans, and the button label
  shows the active file name.
- **No config found**: on startup, if `GET /api/config` reports
  `config_exists: false`, the modal opens in a "create one here" state with a
  single action that writes the starter file (`POST /api/config/create`) and
  reloads. The wording is a proposal, never a forced overwrite.

Theming follows the repo rules (semantic tokens only — `bg-surface`,
`border-line`, `text-ink*`; no `slate-*`), and icons come from `lucide-react`
(`FileCog`/`FolderOpen`) as the rest of the UI already does.

### 7. Tests

| Area | Test |
|---|---|
| `launch/resolution` | explicit `--config` wins; document beats finder; 5-level search; `None` when nothing found |
| `launch/context` | argv passthrough; Finder probe honoured when valid; probe failure → `None` without raising |
| `app.py` | shortcut CWD is Finder folder, else own dir, else cwd |
| `routes/config` | `load` happy path; bad path → 400; **G5** both branches (machine config matches → its scan path; none matches → the config's own folder) |
| web | `LoadConfigModal` filters to config files; "create" state appears when `config_exists` is false |
| bundle | generated `Info.plist` lints (`plutil -lint`) and declares the `profiles` extension |
| declaration | the `document_types` block is present in `pyproject.toml` and parses as valid TOML |

The two source-of-truth files for the platform assumptions are
`tests/launch/test_context.py` and `tests/launch/test_resolution.py` — the
place to look when platform behaviour ever changes.

Because §2 and §3 are interim and must be deletable, the platform-specific
modules get their own test files so deleting them deletes their tests:
`tests/launch/test_macos_bundle.py`, `tests/launch/test_association_windows.py`
(skipped unless on Windows, so it documents intent without asserting
unverifiable behaviour), `tests/launch/test_association_linux.py` (same).

## 9. Briefcase spike (blocked by C2, run when the repo is off iCloud)

When the repo moves to a non-synchronized folder, one spike decides whether
§2/§3 can be deleted. It is a throwaway, not part of this change:

1. Add the `document_types` block shown above to `pyproject.toml`.
2. `briefcase create macOS` (then Windows/Linux as hosts allow).
3. Register the generated `.app` with `lsregister -f`, double-click a named
   `my.profiles`.
4. **The question:** does the path arrive? Briefcase's docs cover Toga apps;
   this app is pywebview. Check `sys.argv`, and if argv is empty, whether the
   stub forwards the document at all. If argv does not carry it, the AppKit
   handler from §2 must be ported into the Briefcase-launched bundle instead
   of being deleted, and that changes the migration plan (the module stays).
5. Record the answer in the spec. If delivery works, delete §2, §3, and their
   tests.

Until step 4 has an answer recorded, §2 and §3 stay.

## Out of scope

- Per-user "always open with" UI (macOS handles this once the bundle is
  registered; `open -a` / Finder's Get Info is the documented path).
- Changing `find_config_file`'s depth or precedence.
- Code signing, notarization, and `.dmg`/`.msi`/`.deb` installers — Briefcase
  territory, deferred with the spike in §9.

## Success criteria

Stated per platform; each line must hold on Windows, macOS and Linux unless
marked otherwise.

- Double-clicking `my.profiles` (named file) opens the web app with that
  config, and its `config_path` is reported by `GET /api/config`.
- Double-clicking the shortcut from a folder containing a `.profiles` uses it;
  from a folder with none, but with one 3 levels deep, uses that one; with
  none anywhere, proposes creation.
- A folder whose machine config does *not* match, opened by double-click,
  scans the `.profiles` file's own folder.
- `python -m profiles --server-only`, `--config`, and `--init` behave exactly
  as before.
- `python -m profiles.launch.association install` then `status` reports the
  registration on all three, and `remove` leaves the system exactly as found.
- Nothing in the change imports Tk, and the coverage gate and baseline test
  failures are unchanged.
