# Native-First Installation Design (Briefcase CI + Tkinter Deprecation)

- **Date:** 2026-10-23
- **Status:** Approved design — awaiting implementation
- **Author:** ProFiles team

---

## 1. Problem Statement

ProFiles currently ships three install paths, all aimed at people who
already know Python:

| Path | Command | Audience |
| --- | --- | --- |
| Wizard | `python install.py` | Multi-step, requires Python knowledge |
| Make | `make install-system` (`pip install .`) | Requires Python + pip + terminal |
| Briefcase | *(planned)* | Config exists in `pyproject.toml` but no CI, no artifacts |

Actual users are **colleagues and non-technical end users**. None of the
current paths is acceptable for them: each requires a Python 3.11+
installation and terminal fluency.

The Briefcase integration was started (config in `pyproject.toml`,
`make` targets, "Method 4" in the installation guide) but never
finished: the referenced spec doc is absent from the repo, there are no
GitHub Actions workflows, and `requires = []` in the app config would
produce a broken bundle (no runtime dependencies installed).

## 2. Goals

1. **End users** install ProFiles by downloading one file from GitHub
   Releases and double-clicking: `.msi` (Windows), `.dmg` (macOS),
   `.deb` / `.AppImage` (Linux). No Python required on the target
   machine.
2. **Developers** install with a single command:
   `uv tool install profiles-app` (or `pipx install profiles-app`).
3. **Deprecate the Tkinter frontend** clearly: developer/advanced use
   only, removal planned in a future release.
4. **Keep `install.py` and `make install-system` unchanged** — they
   remain available as-is.

## 3. Non-Goals

- Code signing / notarization (SmartScreen and Gatekeeper warnings stay;
  the existing documentation already explains the bypass steps).
- Removing the Tkinter frontend code (deprecation marking only; removal
  is a separate future task).
- Publishing to PyPI (decided at implementation time; the docs cover
  both `uv tool install` from PyPI and from a GitHub-built wheel).
- Cross-compilation (Briefcase builds per-OS in a CI matrix, standard
  practice).

## 4. Decision Summary

**Briefcase is the primary end-user distribution channel, driven by a
GitHub Actions release pipeline. `uv tool` / `pipx` is the developer
channel. The Tkinter backend becomes developer-only and is explicitly
deprecated.**

Rationale (from the 2026-10-23 research spike):

- **Briefcase 0.4.5 (Sept 2026)** is actively maintained (Python 3.14
  support, CVE-2026-33430 MSI permission fix, uv/conda Python backends)
  and produces native installers with Start Menu / Applications
  integration, uninstallers, and `*.profiles` document-type registration
  (already configured via `document_types`).
- **PyInstaller** bundles Tk well but produces a bare `.exe` — no
  installer, no Start Menu entry, no uninstall, no multi-OS artifacts —
  and has documented crash issues with `pywebview` + `pythonnet` on
  Windows. Building a real installer on top would re-create what
  Briefcase already provides.
- **pipx / uv tool** is ideal for developers but requires Python 3.11+
  on the user machine — unacceptable for the target audience alone.
- All ProFiles runtime dependencies publish wheels on all three OSes;
  no packaging blockers.

**Key insight that unlocks Briefcase on Windows:** the default GUI
backend is now **web** (`--tkinter` is opt-in since the pywebview
migration), and the only Tk-era pip dependencies (`sv-ttk`,
`darkdetect`) are used exclusively by `gui/theme.py`. Moving them to
dev dependencies + making Tkinter imports lazy means the Briefcase
Windows bundle — whose embeddable Python **does not ship Tkinter** —
works with no workarounds.

## 5. Detailed Design

### 5.1 Dependency split (`pyproject.toml`)

- Move `sv-ttk>=2.5.0` and `darkdetect>=0.8.0` out of
  `[project] dependencies` into **both** `[project.optional-dependencies].dev`
  and `[dependency-groups] dev` (these two lists must stay in sync).
- Remaining runtime dependencies: `fastapi`, `uvicorn[standard]`,
  `pywebview`, `sse-starlette`, `qrcode[pil]`, `pydantic`, `ruamel.yaml`.
- Add a comment marking the Tkinter backend deprecated.
- Developers keep full functionality via `uv sync` /
  `pip install -e ".[dev]"`, so `profiles --tkinter` still works locally.
- **Briefcase compatibility:** Briefcase installs only what is listed in
  `[tool.briefcase.app.profiles] requires`; it never reads
  `[project.optional-dependencies]`. Moving the Tk deps out therefore
  shrinks the bundle and removes the Tk trap.

### 5.2 Lazy imports + deprecation marking (`src/profiles/app.py`)

Current problems: `app.py` line 13 has `import tkinter as tk` and line
22 imports `profiles.gui.main_window` at module level, so **every**
invocation — web backend, headless, `--init` — requires Tkinter to be
importable.

Changes:

1. Remove the module-level `import tkinter as tk` and the
   `from profiles.gui.main_window import MainWindow` import.
2. Import tkinter and `MainWindow` **only inside the tk-backend branch**
   of `main()` / `ProFileApp`.
3. When `--tkinter` is passed, print a deprecation banner:

   ```
   ⚠ The Tkinter frontend is deprecated (developer/advanced use only)
     and will be removed in a future release. The default web GUI
     replaces it.
   ```

4. If tkinter (or `sv_ttk`) is unavailable — e.g., inside a Briefcase
   bundle — fail with an actionable one-line message
   ("The Tkinter frontend requires a full Python installation with Tk;
   use the default web GUI instead") instead of a stack trace.
5. Behavior in all other modes is unchanged. `install.py` and the
   Makefile targets are **not modified**.
6. The `--tkinter` help text and the `--help` epilog are updated to
   carry the deprecation notice.

### 5.3 Briefcase configuration fix (`pyproject.toml`)

- Populate `[tool.briefcase.app.profiles] requires` with the runtime
  dependency list from §5.1 (transitive deps resolve automatically via
  pip).
- Keep `document_types = ["profiles"]`, `icon`, and the macOS section
  unchanged.
- **Entry point:** the Briefcase stub launches the app package's
  `main()` callable. `profiles/__init__.py` currently exports no
  `main()`. Add a thin re-export (`from profiles.app import main`) so
  the stub resolves to `profiles.app:main`, and verify with
  `briefcase dev` / `briefcase run` locally.
- **Version sync:** Briefcase does not read PEP 621 metadata; keep the
  existing manual-sync comment, and add a CI guard (§5.4).

### 5.4 GitHub Actions release pipeline

New file `.github/workflows/release.yml`, triggered on version tags
(`v*`):

| Runner | Output | Notes |
| --- | --- | --- |
| `windows-latest` | `ProFiles-<ver>.msi` | WiX via Briefcase |
| `ubuntu-latest` | `profiles_<ver>_amd64.deb` + `ProFiles-<ver>.AppImage` | |
| `macos-latest` | `ProFiles-<ver>.dmg` | unsigned; Gatekeeper note in docs |

- Each job: check out, install `uv`, `uv sync`, `uv run briefcase
  package <platform>`, upload artifacts to the GitHub Release.
- **Version guard job:** a small job (or first step of the pipeline)
  running an inline Python snippet that parses both `[project].version`
  and `[tool.briefcase].version` from `pyproject.toml` and fails the
  pipeline on mismatch. `2026.8.0` is a valid MSI integer triple, so no
  version translation is needed.
- Tag convention: `v2026.8.0` → Briefcase version `2026.8.0` (strip the
  leading `v` in the workflow).
- New file `.github/workflows/build-windows.yml` (PR dry-run): Windows
  build only, fastest lane, so packaging regressions surface before a
  release tag.

### 5.5 Developer channel documentation

Update `README.md`, `docs/installation-guide.en.md`, and
`docs/installation-guide.fr.md`. New ordering:

1. **Method 1 — End users (native installer):** download from GitHub
   Releases; platform-specific install steps (existing "Method 4"
   content moves up and becomes primary).
2. **Method 2 — Developers (one command):** `uv tool install
   profiles-app` — variant A from PyPI (if published), variant B from a
   GitHub-built wheel asset (documented command using the release
   URL).
3. **Existing methods unchanged:** the wizard (`python install.py`) and
   `make install-system` documentation remain as-is, listed after the
   two primary methods.
4. A "Tkinter backend (deprecated)" section documents `--tkinter`,
   its deprecation status, and the dev-only dependency requirement.

### 5.6 Testing & verification

| Test | What it proves |
| --- | --- |
| New unit test: run `profiles.app.main()` web-backend path with `tkinter` blocked via `sys.modules` | Lazy imports hold; default backend needs no tkinter |
| New unit test: `--tkinter` prints the deprecation banner and yields a clean error when tkinter is unavailable | Graceful degradation, no stack trace |
| New CI step: inline Python snippet inside the release workflow (no extra script file) | `[tool.briefcase] version == [project] version` |
| Existing pytest suite | ≥ 85 % coverage, no regressions |
| `ruff check .` + `ruff format --check .` + `pylint src/profiles` | Quality gates |
| Manual smoke: `uv run briefcase build windows`, then launch the built app | Bundle actually runs on this machine before CI is trusted |

### 5.7 Out of Scope (restated)

Code signing; Tkinter code removal; PyPI publishing; auto-update story.

## 6. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Briefcase stub entry-point mismatch (`main()` not found) | §5.3 re-export + local `briefcase run` smoke test before wiring CI |
| First launch blocked by SmartScreen/Gatekeeper | Already documented in installation guide (§5.5 moves that content to Method 1) |
| Version drift between `[project]` and `[tool.briefcase]` | CI guard job fails the release on mismatch |
| Tk users (e.g., X11 forwarding workflows) lose their path after the move | Tk remains installable via dev extras; deprecation banner names the web GUI replacement; removal is deferred to a future release with its own migration note |
| AppImage tooling flakiness in CI (linuxdeploy) | `briefcase upgrade linuxdeploy` step in the Ubuntu job; deb remains the primary Linux artifact |

## 7. Acceptance Criteria

1. Pushing tag `v2026.8.0` produces a GitHub Release containing
   `ProFiles-2026.8.0.msi`, `ProFiles-2026.8.0.dmg`,
   `profiles_2026.8.0_amd64.deb`, and `ProFiles-2026.8.0.AppImage`.
2. The Windows MSI installs, adds a Start Menu entry with the ProFiles
   icon, and launches the web GUI on a machine **without** Python or
   Tkinter.
3. `--tkinter` prints the deprecation banner; a clean, actionable error
   is shown when tkinter is unavailable.
4. `import profiles.app` and the web/headless paths succeed with
   tkinter blocked (unit-tested).
5. `sv-ttk` and `darkdetect` appear only under dev extras /
   dependency-groups in `pyproject.toml`.
6. Installation docs show native installer first, `uv tool install`
   second, existing methods unchanged below.
7. `install.py` and the `make install-system` target are byte-for-byte
   unchanged.
8. Full quality gate passes: pytest ≥ 85 % coverage, ruff, pylint ≥ 8.0.
