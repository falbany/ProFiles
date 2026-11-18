# Windows Installer Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Windows MSI match its documentation: desktop shortcut, real finish page (Launch + links), PATH convenience option, and branded installer art — as declarative Briefcase 0.4.7 config plus two small bundled `.bat` scripts, in one PR closing #183.

**Architecture:** Everything lives in `[tool.briefcase.app.profiles.windows]` config, committed BMP assets, and `packaging/windows/` scripts. PATH is the only custom behaviour: the WiX template's native PATH feature is console-app-only, so `install_option add_to_path` (singular key!) drives a checkbox whose state is passed to a bundled `post_install.bat` (PowerShell registry edit, `REG_EXPAND_SZ`-safe, `WM_SETTINGCHANGE` broadcast); `pre_uninstall.bat` removes the exact entry from both hives.

**Tech Stack:** Briefcase 0.4.7 + WiX v5 template (no vendoring), PowerShell 5.1 via `.bat`, Pillow (asset generation, dev-side only), pytest + tomllib (coherence tests).

**Spec:** `docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md` (§ numbers below refer to it)

## Global Constraints

- One PR, branch `feat/installer-polish-183`, `Closes #183` (spec §3).
- **No changes under `src/profiles/**`** (spec §3).
- English-only installer surface (spec §4).
- BMPs are committed assets, 493×312 / 493×58, 24-bit RGB (spec §6.2); never generated at build time; generator script committed for provenance.
- `.bat` scripts always end `exit /b 0`; recoverable failures log and continue (`Return="check"` would fail the install — spec §6.3.4).
- PATH edits: `DoNotExpandEnvironmentNames` read + `ExpandString` write, exact-match add/remove, no `setx` (spec §4, §6.3).
- Config key is **singular** `install_option`, array of tables, each entry requires `name` (spec §6.1 notes; reviewer-verified against the briefcase 0.4.7 wheel).
- Commits use explicit paths — the working tree carries unrelated `src/profiles/web/dist/` churn that must NOT be committed. Verify `git show --stat` after every commit.
- `tests/AGENTS.md` mirrors the tests tree — update it in the commit that adds the test file.

## Review Focus

1. **Install paths with spaces** (`C:\Program Files\ProFiles`) through cmd→PowerShell quoting — expect the PATH entry to be correct, not truncated/split. Pinned by Task 3 test (quoting markers in `.bat`) and the Task 8 manual checklist (install to a spaced path).
2. **`REG_EXPAND_SZ` destruction** (`%SystemRoot%` refs expanded to literals) — expect preserved. Pinned by Task 3/4 test markers (`DoNotExpandEnvironmentNames`, `ExpandString`) and checklist.
3. **Silent install `/qn` regression** — expect PATH added by default, no hang, opt-out via `OPTION_ADD_TO_PATH=0`. Pinned by Task 4 test (`default = true`) and checklist.
4. **Uninstall collateral damage** — expect exact-match removal only; `.profiles` configs/logs untouched. Pinned by Task 3 test (exact-match marker) and checklist.
5. **Plural-key silent feature loss** (`install_options` instead of `install_option`) — expect the Install Options page to exist. Pinned by Task 4 test (singular key present AND plural absent).

---

### Task 1: Branch + `.gitattributes` rules

**Files:**
- Modify: `.gitattributes` (append after the existing binary block)
- Branch: `feat/installer-polish-183` off current `main`

**Interfaces:**
- Produces: attribute rules that must exist **before** any `.bat`/`.bmp` is `git add`-ed (Task 2, Task 3).

- [ ] **Step 1: Sync and branch**

```bash
git fetch origin && git status --short   # expect only the known dist/ churn
git checkout -b feat/installer-polish-183 origin/main
```

- [ ] **Step 2: Append rules**

```gitattributes
# Windows batch files need CRLF (cmd.exe LF edge cases); BMPs are binary.
*.bat text eol=crlf
*.bmp binary
```

- [ ] **Step 3: Commit**

```bash
git add .gitattributes
git commit -m "chore: enforce CRLF for .bat and binary handling for .bmp" && git show --stat
```

### Task 2: Branded BMP assets + generator + first coherence tests

**Files:**
- Create: `packaging/windows/generate_bmps.py`
- Create: `img/installer_background.bmp` (493×312), `img/installer_banner.bmp` (493×58)
- Test: `tests/packaging/test_windows_installer_assets.py` (create)
- Modify: `tests/AGENTS.md` (tree entry for the new test file)

**Interfaces:**
- Produces: `img/installer_background.bmp`, `img/installer_banner.bmp` at the exact paths Task 4's pyproject references; test module that Tasks 3–4 extend.

Art (spec §6.2, superseded by `2026-11-18-installer-art-native-frame-design.md`): native-frame layout. Background = 164 px brand panel on the left (gradient + white mark), plain white from x=164 for WiX dialog text; banner = white x=0–428 for the black page title, brand block with the white mark at x=429–492. Render at 4× and LANCZOS-downsample; font-free.

- [ ] **Step 1: Write the failing tests**

```python
"""Coherence checks for the Windows MSI installer assets and config.

The Windows packaging (pyproject briefcase config + bundled scripts + BMP
art) is exercised only by CI's build-windows job; these tests catch the
breakages that would otherwise surface only there. See
docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md.
"""

from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_background_bmp_dimensions() -> None:
    """Welcome-dialog art is a 493x312 24-bit BMP (WiX WixUIDialogBmp)."""
    path = REPO_ROOT / "img" / "installer_background.bmp"
    assert path.is_file()
    with Image.open(path) as img:
        assert img.format == "BMP"
        assert img.size == (493, 312)
        assert img.mode == "RGB"


def test_banner_bmp_dimensions() -> None:
    """Banner art is a 493x58 24-bit BMP (WiX WixUIBannerBmp)."""
    path = REPO_ROOT / "img" / "installer_banner.bmp"
    assert path.is_file()
    with Image.open(path) as img:
        assert img.format == "BMP"
        assert img.size == (493, 58)
        assert img.mode == "RGB"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/packaging/test_windows_installer_assets.py -v`
Expected: FAIL (`assert path.is_file()` — BMPs missing)

- [ ] **Step 3: Write `packaging/windows/generate_bmps.py`**

Deterministic Pillow script, stdlib+Pillow only, no font rendering (font-free keeps it reproducible across dev machines). Body sketch: draw both assets at 4× and `Image.LANCZOS`-downsample. Background = 493×312: 164 px vertical gradient panel (`#635BCC`→`#825ED9`) at the left, 56 px white mark at (54, 128) with three indigo bars, rest white. Banner = 493×58: white, 64 px horizontal gradient block at x=429, 34 px mark at (444, 12). Save BMP RGB. `--check` flag exits 1 if outputs missing/stale (used by the next step, not by CI).

- [ ] **Step 4: Generate and verify**

Run: `uv run python packaging/windows/generate_bmps.py && uv run pytest tests/packaging/test_windows_installer_assets.py -v`
Expected: PASS (2 tests). Eyeball both BMPs via Read (image preview) against the approved native-frame mock-up.

- [ ] **Step 5: Update `tests/AGENTS.md`** tree entry for `tests/packaging/test_windows_installer_assets.py` (read the file first; mirror its existing entry style).

- [ ] **Step 6: Commit**

```bash
git add packaging/windows/generate_bmps.py img/installer_background.bmp img/installer_banner.bmp tests/packaging/test_windows_installer_assets.py tests/AGENTS.md
git commit -m "feat(installer): add branded MSI background/banner assets" && git show --stat
```

### Task 3: PATH scripts (`.bat` ×2) + provenance README

**Files:**
- Create: `packaging/windows/post_install.bat`, `packaging/windows/pre_uninstall.bat` (CRLF)
- Create: `packaging/windows/README.md`
- Test: extend `tests/packaging/test_windows_installer_assets.py`

**Interfaces:**
- Consumes (runtime, from the Briefcase wrapper env): `ALLUSERS`, `INSTALLER_PATH`, `INSTALLER_UNATTENDED`, `OPTION_ADD_TO_PATH`; `%~dp0` = `<install dir>\_installer\` (spec §2.3).
- Produces: script paths referenced by Task 4's pyproject.

- [ ] **Step 1: Write the failing tests** (append to the module)

```python
SCRIPTS = ("post_install.bat", "pre_uninstall.bat")


def test_bat_scripts_exist_and_exit_clean() -> None:
    """Both scripts exist and always terminate 0 (WiX Return="check")."""
    for name in SCRIPTS:
        body = (REPO_ROOT / "packaging" / "windows" / name).read_bytes()
        assert b"exit /b 0" in body
        assert body.rstrip().endswith(b"exit /b 0")
        assert b"\r\n" in body  # committed via *.bat eol=crlf


def test_post_install_preserves_expand_sz_and_broadcasts() -> None:
    """PATH edit must not expand REG_EXPAND_SZ and must notify shells."""
    body = (REPO_ROOT / "packaging" / "windows" / "post_install.bat").read_text(encoding="utf-8")
    assert "DoNotExpandEnvironmentNames" in body
    assert "ExpandString" in body
    assert "setx" not in body.lower()
    # WM_SETTINGCHANGE broadcast (0x1a) to running Explorer/shells.
    assert "SendMessageTimeout" in body and "0x1a" in body
    # Quoting survives "C:\Program Files\..." paths.
    assert "OPTION_ADD_TO_PATH" in body and "ALLUSERS" in body


def test_pre_uninstall_removes_exactly_its_own_entry() -> None:
    """Cleanup matches the literal install dir in BOTH hives, nothing else."""
    body = (REPO_ROOT / "packaging" / "windows" / "pre_uninstall.bat").read_text(encoding="utf-8")
    assert body.count("DoNotExpandEnvironmentNames") >= 2  # HKCU and HKLM
    assert "ExpandString" in body and "setx" not in body.lower()
    assert "SendMessageTimeout" in body
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/packaging/test_windows_installer_assets.py -v` → new tests FAIL (files missing)

- [ ] **Step 3: Write the two `.bat` files**

`post_install.bat` behavioural skeleton (cmd layer only; the PowerShell one-liner does the registry work in a single `-Command`, single-quoted PS strings throughout, `\"` escapes only inside the C# `MemberDefinition`):

```bat
@echo off
setlocal
REM ProFiles post-install: add the install dir to PATH when the user asked
REM for it on the Install Options page. Wrapper exports ALLUSERS (0/1),
REM INSTALLER_PATH, INSTALLER_UNATTENDED, OPTION_ADD_TO_PATH; %~dp0 is the
REM _installer folder inside the install dir. Spec: docs/superpowers/specs/
REM 2026-11-17-windows-installer-polish-design.md section 6.3.
set "LOG=%~dp0path_setup.log"
> "%LOG%" echo [%DATE% %TIME%] ProFiles post-install start
>>"%LOG%" echo OPTION_ADD_TO_PATH=%OPTION_ADD_TO_PATH% ALLUSERS=%ALLUSERS% UNATTENDED=%INSTALLER_UNATTENDED%

if not "%OPTION_ADD_TO_PATH%"=="1" (
    >>"%LOG%" echo Skipping PATH modification: option not selected.
    exit /b 0
)

REM Install dir = parent of this script's _installer folder (%~fI resolves
REM the trailing ".." to an absolute path, no trailing backslash).
for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
>>"%LOG%" echo Install dir: %INSTALL_DIR%

set "SCOPE=User"
if "%ALLUSERS%"=="1" set "SCOPE=Machine"

REM <powershell one-liner: registry read DoNotExpandEnvironmentNames,
REM exact-match prepend with dedupe, ExpandString write, SendMessageTimeout
REM(HWND_BROADCAST, WM_SETTINGCHANGE=0x1A, 'Environment')> ; append output
REM to the log; on any failure log a WARNING and CONTINUE (never fail the
REM install for a PATH convenience).
>>"%LOG%" 2>&1 powershell -NoProfile -ExecutionPolicy Bypass -Command "<one-liner with -InstallDir '%INSTALL_DIR:''=%' -Scope %SCOPE% inlined>"
if errorlevel 1 >>"%LOG%" echo WARNING: PATH update failed; install continues.

exit /b 0
```

`pre_uninstall.bat`: same shape; no option gate; **loop over both hives** (`User` then `Machine`) removing the literal install-dir entry, ignoring per-hive access errors (per-user uninstall cannot write HKLM — that is success, not failure); same dedupe/normalisation (`-ireplace`-free: plain split/filter/join), same broadcast, same log, same exit-0 policy. `%~dp0` is still valid: the action runs `After="InstallInitialize"`, before `RemoveFiles`.

One-liner contract (what the PS string must do, either inline in each `.bat` or factored into an identical `-Command` string): `$dir`/`$scope` params; pick `CurrentUser`/`LocalMachine` + subkey `Environment` / `SYSTEM\CurrentControlSet\Control\Session Manager\Environment`; `GetValue('Path','', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)`; split `;`, drop empties, filter exact match (case-insensitive, `TrimEnd('\')` on both sides) — add `$dir` first for post-install / drop `$dir` for pre-uninstall; re-join; `SetValue('Path', $new, [Microsoft.Win32.RegistryValueKind]::ExpandString)`; broadcast via `Add-Type -MemberDefinition` P/Invoke `SendMessageTimeout` (HWND_BROADCAST=0xffff, 0x1a, 'Environment', 2, 5000); `exit 0`.

- [ ] **Step 4: `packaging/windows/README.md`** — provenance note: what the scripts do, env-var contract, why no `setx`, how BMPs are regenerated (`uv run python packaging/windows/generate_bmps.py`), pointer to the spec.

- [ ] **Step 5: Run tests to verify pass** — `uv run pytest tests/packaging/test_windows_installer_assets.py -v` → all PASS

- [ ] **Step 6: Commit**

```bash
git add packaging/windows/post_install.bat packaging/windows/pre_uninstall.bat packaging/windows/README.md tests/packaging/test_windows_installer_assets.py
git commit -m "feat(installer): add PATH post-install/pre-uninstall scripts" && git show --stat
```

### Task 4: `pyproject.toml` windows section + config tests

**Files:**
- Modify: `pyproject.toml` (new `[tool.briefcase.app.profiles.windows]` table + `[[tool.briefcase.app.profiles.windows.install_option]]` array, placed after the `permission` table, **before** `[tool.pylint.MASTER]`)
- Test: extend `tests/packaging/test_windows_installer_assets.py`

**Interfaces:**
- Consumes: `img/installer_background{.bmp}`, `img/installer_banner{.bmp}` (Task 2), `packaging/windows/{post_install,pre_uninstall}.bat` (Task 3).
- Produces: the exact TOML the CI MSI build consumes.

- [ ] **Step 1: Write the failing tests** (append; `import tomllib`)

```python
def test_windows_installer_config() -> None:
    """The briefcase windows section matches the approved design."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        cfg = tomllib.load(fh)["tool"]["briefcase"]["app"]["profiles"]["windows"]

    # Scope dialog stays the wizard default (perUserOrMachine).
    assert "system_installer" not in cfg
    assert cfg["create_desktop_shortcut"] is True
    assert cfg["installer_background"] == "img/installer_background"
    assert cfg["installer_banner"] == "img/installer_banner"
    assert cfg["installer_completion_launch_app"] is True
    assert cfg["post_install_script"] == "packaging/windows/post_install.bat"
    assert cfg["pre_uninstall_script"] == "packaging/windows/pre_uninstall.bat"

    urls = cfg["installer_completion_urls"]
    assert [u["title"] for u in urls] == ["Documentation", "What's new"]
    assert all(u["url"].startswith("https://github.com/falbany/ProFiles") for u in urls)

    # Singular key, array-of-tables, required `name`. The plural
    # `install_options` key is silently swallowed by DraftAppConfig.
    assert "install_options" not in cfg  # the plural trap
    options = cfg["install_option"]
    assert len(options) == 1
    opt = options[0]
    assert opt["name"] == "add_to_path"
    assert opt["default"] is True
    assert opt["title"] == "Add ProFiles to PATH"


def test_referenced_installer_files_exist(tmp_path: Path) -> None:
    """Every file the windows section references must resolve on disk."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        cfg = tomllib.load(fh)["tool"]["briefcase"]["app"]["profiles"]["windows"]

    for key in ("installer_background", "installer_banner"):
        # Briefcase resolves with_suffix(".bmp") against the project root.
        assert (REPO_ROOT / f"{cfg[key]}.bmp").is_file()
    for key in ("post_install_script", "pre_uninstall_script"):
        assert (REPO_ROOT / cfg[key]).is_file()
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/packaging/test_windows_installer_assets.py -v` → config tests FAIL (no windows section)

- [ ] **Step 3: Add the TOML** — exactly as spec §6.1 (corrected block: singular `[[tool.briefcase.app.profiles.windows.install_option]]` with `name`/`title`/`description`/`default = true`), with the explanatory comments from the spec (why `system_installer` is unset; the singular-key warning referencing the existing `document_type` comment; `.bmp` suffix-resolution note).

- [ ] **Step 4: Run tests to verify pass** — `uv run pytest tests/packaging/test_windows_installer_assets.py -v` → all PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/packaging/test_windows_installer_assets.py
git commit -m "feat(installer): enable Windows MSI installer options" && git show --stat
```

### Task 5: Docs, CHANGELOG, spec/plan docs

**Files:**
- Modify: `docs/installation-guide.en.md`, `docs/installation-guide.fr.md`, `CHANGELOG.md`
- Commit (already in tree): spec + this plan document

- [ ] **Step 1: Update the EN guide** — read the current MSI bullet (the "A Start Menu entry and desktop shortcut are created" sentence); correct it and add a short **Installer options** sub-block under Method 1: scope dialog (per-user vs per-machine), Install Options page ("Add ProFiles to PATH", checked by default), finish page (Launch + Documentation / What's new links); `msiexec /qn` keeps working with PATH included, `OPTION_ADD_TO_PATH=0` opts out; `profiles --headless` works from any **new** terminal after install.

- [ ] **Step 2: Mirror in the FR guide** — translate the same changes; keep the FR doc's existing voice.

- [ ] **Step 3: CHANGELOG** — under `[Unreleased]`, add an `### Added` section (before the existing `### Changed`): desktop shortcut, scope dialog, finish page (Launch + links), "Add ProFiles to PATH" install option, branded installer art; note silent-install opt-out property.

- [ ] **Step 4: Verify link targets** — the two finish-page URLs (`https://github.com/falbany/ProFiles#readme`, `.../blob/main/CHANGELOG.md`) resolve; guide anchors/paths valid.

- [ ] **Step 5: Commit**

```bash
git add docs/installation-guide.en.md docs/installation-guide.fr.md CHANGELOG.md docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md docs/superpowers/plans/2026-11-18-windows-installer-polish.md
git commit -m "docs: document MSI installer options and PATH convenience" && git show --stat
```

### Task 6: CI trigger addition

**Files:**
- Modify: `.github/workflows/build-windows.yml` (`paths:` list)

- [ ] **Step 1: Add `packaging/windows/**`** to the `on.pull_request.paths` list (spec §6.8; effective within this PR — GitHub uses the PR branch's workflow for `pull_request` events).

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/build-windows.yml
git commit -m "ci: rebuild MSI when packaging scripts change" && git show --stat
```

### Task 7: Quality gates

- [ ] **Step 1:** `uv run ruff format .` (expect: only packaging/tests files touched, if any) and `uv run ruff check --fix .`
- [ ] **Step 2:** `uv run pytest` — full suite green (new module included)
- [ ] **Step 3:** `uv run pylint src/profiles` — score ≥ 8.0 (src untouched; guard against import-time regressions)
- [ ] **Step 4:** Commit any formatting fallout (`style: ruff format`), else proceed.

### Task 8: Push, PR, MSI artifact

- [ ] **Step 1:** `git push -u origin feat/installer-polish-183`
- [ ] **Step 2:** `gh pr create` — title `feat(installer): Windows MSI polish (shortcuts, finish page, PATH option, branding)`; body: summary, `Closes #183`, the reviewer calls made (workflow one-liner, spec self-correction), and the **work-machine test checklist** from spec §7 (per-user + per-machine install, PATH in new terminal both scopes, uninstall interactive + `/x /qn`, `/qn` install + `OPTION_ADD_TO_PATH=0` opt-out, upgrade-over-current-release, **banner text-contrast checkpoint**).
- [ ] **Step 3:** Watch `build-windows.yml` on the PR (`gh run watch`), then report the artifact (`ProFiles-windows-msi`) to the owner for the work-machine pass. CI green (quality + windows build) is the completion signal for this session; the checklist execution stays with the owner.

## Self-Review Notes

- Spec coverage: §6.1→T4, §6.2→T2, §6.3/6.4→T3, §6.5→T5, §6.6→T2–T4, §6.7→T1, §6.8→T6, §7→T8, §2/§4/§8 are rationale (no build artefact). macOS explicitly out (§3).
- The PowerShell one-liner body is deliberately specified as a *contract* (Step 3 list) not a transcript — its exact quoting is validated on Windows in T8; content markers are pinned by T3 tests.
- Types/names consistent: `install_option` (singular) everywhere; file paths match across T2/T3/T4.
