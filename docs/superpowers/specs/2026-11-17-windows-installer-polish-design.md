# Windows Installer Polish Design (MSI options, PATH convenience, branding)

- **Date:** 2026-11-17 (finalised 2026-11-18)
- **Status:** Approved design — awaiting implementation
- **Author:** ProFiles team
- **Implements:** [Issue #183](https://github.com/falbany/ProFiles/issues/183) (Windows MSI scope only)

---

## 1. Problem Statement

The Windows MSI (`ProFiles-<version>.msi`) is built with Briefcase defaults:

- **No desktop shortcut** — the installation guide promises "a Start Menu entry
  and desktop shortcut are created" (`docs/installation-guide.en.md`), but the
  current config produces no desktop shortcut. The docs are ahead of reality.
- **Bare finish page** — no "Launch ProFiles" convenience, no links to docs /
  what's new after install.
- **No PATH convenience** — `profiles --headless` automation is a documented
  usage mode, but the packaged app is not on PATH, so terminal use requires
  typing the full install path.
- **Stock installer branding** — plain WiX look, while the project has brand
  assets (indigo-violet gradient, `img/ProFiles_banner.png`, white logo mark).

## 2. Ground truth — Briefcase 0.4.7 Windows MSI backend

All of the following was verified directly against the **Briefcase v0.4.7**
source (the version pinned in `uv.lock`) and the **`briefcase-windows-app-template`**
WiX template it uses. The issue's premise that "all installer options are
unused" stands, but its assumption that most features need custom machinery
was based on pre-0.4 docs: **nearly everything is native declarative config**.

### 2.1 Native config inventory (`[tool.briefcase.app.profiles.windows]`)

| Config key | Effect | Verified behaviour |
| --- | --- | --- |
| `system_installer` *(unset)* | Wizard asks per-user vs per-machine | `install_scope = "perUserOrMachine"` → WiX `InstallScopeDlg` in the wizard |
| `create_desktop_shortcut = true` | Desktop shortcut, checked by default | `DesktopFolder` component; visible as a feature checkbox in the customize flow |
| `installer_background` | Welcome-dialog art | Path is `with_suffix(".bmp")`-resolved against project root; **file must be a 493×312 BMP** |
| `installer_banner` | Top strip art on every other dialog | Same mechanism; **file must be a 493×58 BMP** |
| `installer_completion_launch_app` | "Launch ProFiles" checkbox on finish page | `COMPLETION_LAUNCH` property preset to `1` (checked by default); launch honoured interactively only |
| `installer_completion_text` | Custom install-finish text | Rendered on `ExitDialog` (install case) |
| `uninstaller_completion_text` | Custom uninstall-finish text | Rendered on `ExitDialog` (uninstall case) |
| `installer_completion_urls` | Up to 5 hyperlinks on the finish page | List of `{title = …, url = …}`; install case only |
| `install_option` *(singular!)* | Real checkboxes on a dedicated **Install Options** wizard page | **Array of tables** `[[…install_option]]`, each with required `name`, `title`, `description`, optional `default`/`system` → becomes `OPTION_<NAME>` public property; `default = true` ⇒ checked; `system` unset ⇒ visible in both scopes. Same plural-vs-singular trap as `document_type` (see pyproject comment): the plural `install_options` key is silently swallowed by `**kwargs` and overwritten in `DraftAppConfig` — use the singular key. |
| `post_install_script` / `pre_uninstall_script` | Bundled `.bat` hooks | Must be `.bat`, path relative to project root; copied to `<bundle>/extras/_installer/{post_install,pre_uninstall}.bat` |

### 2.2 Wizard flow (interactive, with our config)

```
Welcome → License → Install Scope (per-user / per-machine)
        → Install dir → Install Options ("Add ProFiles to PATH" ✔)
        → Ready → Progress → Finish (Launch ✔ + Documentation / What's new links)
```

The Install Options page is **first-class** — `CustomInstallDirDlg.Next` →
`InstallOptionsDlg` → `VerifyReadyDlg`. No "Advanced" detour.

### 2.3 Script mechanics (verified)

- **Post-install**: scheduled `Before="InstallFinalize"`, deferred,
  `Impersonate="no"` (elevated on per-machine installs), condition
  `NOT Installed` (runs on fresh install and major-upgrade installs; **not**
  on repair). A template wrapper (`run_post_install.bat`) exports:
  - `ALLUSERS` = `1` (per-machine) / `0` (per-user)
  - `INSTALLER_PATH` = path of the MSI being installed
  - `INSTALLER_UNATTENDED` = `1` in quiet mode (`UILevel < 3`), else `0`
  - `OPTION_ADD_TO_PATH` = `1`/`0` (from the checkbox / property default)
  …then `CALL`s our `post_install.bat`, whose `%~dp0` resolves to
  `<install dir>\_installer\` — **the install dir is `%~dp0\..`**.
- **Pre-uninstall**: scheduled `After="InstallInitialize"` (before
  `RemoveFiles`; files and `%~dp0` still valid), condition `REMOVE="ALL"`,
  impersonated (user context; elevated when the uninstall is elevated).
  Wrapper exports `INSTALLER_UNATTENDED` only — **no scope flag**, so the
  cleanup script must inspect both registry hives and remove wherever the
  entry matches.
- **Failure semantics**: both actions use `Return="check"` — a non-zero exit
  **fails the install/uninstall**. Our scripts must therefore be defensive:
  log-and-continue on recoverable errors, and always `exit /b 0` unless the
  situation is unrecoverable.
- **Silent installs** (`msiexec /qn`): quiet variants of both actions run;
  option properties apply their defaults (`add_to_path` ⇒ `1`), overridable
  on the command line via the public property
  `msiexec /i ProFiles.msi /qn OPTION_ADD_TO_PATH=0`.
- **PATH via native WiX `<Environment>`**: exists in the template but is
  gated behind `console_app = true` (CLI apps). ProFiles is a GUI app, so the
  custom post-install route below is required and by design.

## 3. Scope

- **Windows MSI only.** macOS DMG branding (issue items 7–8) is explicitly
  **out of scope** (owner decision, 2026-11-18). Note: the DMG volume icon is
  already effectively covered by Briefcase's app-icon fallback
  (`img/profiles.icns`); only a DMG background PNG would remain — deferred to
  a future issue.
- **One PR** (owner decision, 2026-11-18): pyproject config + scripts +
  branding BMPs + `.gitattributes` rules + a one-line CI trigger addition +
  docs + CHANGELOG + a config-coherence test. The spec file itself is part of
  the PR and is amended in the same commit as its §6.1 correction, so the
  committed spec stays truthful.
- No changes to `src/profiles/**` — everything is packaging, assets and docs.

## 4. Goals / Non-goals

**Goals**

1. The installation guide's shortcut claim becomes true.
2. Finish page: "Launch ProFiles" (checked) + Documentation / What's new
   links + custom completion text.
3. `profiles --headless` works from any terminal after a default install
   (install dir on PATH), per-user and per-machine.
4. Uninstall removes exactly the PATH entry it added — nothing else.
5. Branded welcome dialog + banner (direction **A** — brand gradient,
   approved in the 2026-11-18 brainstorming session).
6. Silent installs keep working (`msiexec /qn`), PATH included by default.

**Non-goals / anti-goals**

- No user-data deletion on uninstall (`.profiles` configs, logs untouched).
- No non-English installer surface (English-first app).
- No vendoring/patching of the Briefcase WiX template — config + bundled
  scripts only, staying upstream-aligned.
- No `setx` (1024-char truncation) and no reading PATH via expanded-string
  APIs (would destroy `REG_EXPAND_SZ` references like `%SystemRoot%`).

## 5. Decision Summary

| Feature | Mechanism | Native / custom |
| --- | --- | --- |
| Scope dialog | `system_installer` unset (wizard default) | Native |
| Desktop shortcut | `create_desktop_shortcut = true` | Native |
| Finish page (launch + text + links) | `installer_completion_*` keys | Native |
| **Add to PATH** | `install_options.add_to_path` + `post_install.bat` (PowerShell registry edit) | **Custom script on native hooks** |
| PATH cleanup on uninstall | `pre_uninstall.bat` (exact-match removal, both hives) | **Custom script on native hook** |
| Installer art | Committed 493×312 / 493×58 BMPs, direction A | Assets |

## 6. Detailed Design

### 6.1 `pyproject.toml`

New section (appended after the existing `permission` table), with comments
explaining the *why* of each key (Briefcase 0.4.7 dropped the MSI reference
docs — these comments are the in-repo documentation):

```toml
[tool.briefcase.app.profiles.windows]
# system_installer deliberately unset: the wizard asks per-user vs
# per-machine at install time ("perUserOrMachine").
create_desktop_shortcut = true
installer_background = "img/installer_background"   # 493x312 BMP on disk
installer_banner = "img/installer_banner"           # 493x58 BMP on disk
installer_completion_launch_app = true
installer_completion_text = """\
ProFiles has been installed successfully. Launch it now, or find it in \
your Start Menu."""
uninstaller_completion_text = """\
ProFiles has been removed. Your configurations and logs were left \
untouched."""
installer_completion_urls = [
    { title = "Documentation", url = "https://github.com/falbany/ProFiles#readme" },
    { title = "What's new", url = "https://github.com/falbany/ProFiles/blob/main/CHANGELOG.md" },
]

# NOTE: singular `install_option`, array-of-tables, each entry requires
# `name`. The plural `install_options` key is silently swallowed by
# **kwargs and overwritten in DraftAppConfig — same trap as
# `document_type` (see comment above in this file).
[[tool.briefcase.app.profiles.windows.install_option]]
name = "add_to_path"
title = "Add ProFiles to PATH"
description = "Run 'profiles' (including --headless automation) from any terminal."
default = true

post_install_script = "packaging/windows/post_install.bat"
pre_uninstall_script = "packaging/windows/pre_uninstall.bat"
```

Notes:

- Briefcase resolves `installer_background`/`installer_banner` with
  `with_suffix(".bmp")` — the extension in the config value is irrelevant;
  the **committed file must be `.bmp`**.
- `install_option` uses the **singular** key and array-of-tables shape with a
  required `name` (verified against the Briefcase 0.4.7 wheel:
  `DraftAppConfig.__init__` takes `install_option`; `validate_install_options_config`
  expects each element to be a dict carrying `name`/`title`/`description`).
  No `system` key ⇒ checkbox shown in both scopes; `default = true` ⇒ checked,
  and the default also applies to `/qn` silent installs.
- `OPTION_ADD_TO_PATH` is an uppercase (public) MSI property ⇒ overridable on
  the `msiexec` command line.

### 6.2 Installer branding BMPs (direction A)

Two committed assets derived from existing brand art (one-off generation,
then versioned like any other asset — **never regenerated at build time**):

| File | Size | Content |
| --- | --- | --- |
| `img/installer_background.bmp` | 493×312, 24-bit BMP | Diagonal indigo-violet gradient (~`#635BCC` → `#825ED9`, 125°), white rounded logo mark, "ProFiles" wordmark + tagline "The Highly Configurable, Multi-Purpose File Launcher", translucent pill accents on the right — direct adaptation of `img/ProFiles_banner.png`. WiX overlays the dialog title (top-left) and welcome text (bottom-left) + buttons (bottom-right); keep those zones free of high-contrast detail. |
| `img/installer_banner.bmp` | 493×58, 24-bit BMP | Same gradient, small logo mark + "ProFiles Setup" wordmark left, faint pills right. WiX overlays the page title (e.g. "Select Installation Folder") — left 60% stays smooth gradient. |

Generation: one-off Python/PIL script (committed under
`packaging/windows/generate_bmps.py` for provenance/reproducibility), run
locally, output committed. A note in `packaging/windows/README.md` records
provenance and the regeneration command.

**Open visual checkpoint** (verified on the first CI artifact): the WiX UI
theme's title/text color over branded art. If the template renders dark text
over the art, mitigation is to lighten the text zones in the BMPs (not a
template patch). Decide from the artifact screenshot, not speculation.

### 6.3 `packaging/windows/post_install.bat`

Behavioural contract (implementation is the builder's, within these rules):

1. Honours the env vars exported by the template wrapper: `OPTION_ADD_TO_PATH`,
   `ALLUSERS`, `INSTALLER_UNATTENDED`. Skips silently (exit 0) when
   `OPTION_ADD_TO_PATH` ≠ `1`.
2. Install dir = parent of `%~dp0` (the `_installer` folder), trailing
   backslash normalised away.
3. PATH edit via one `powershell -NoProfile -ExecutionPolicy Bypass -Command …`
   invocation (PowerShell 5.1 is present on all supported Windows):
   - **Per-user** (`ALLUSERS=0`): `HKCU\Environment` `Path`.
   - **Per-machine** (`ALLUSERS=1`): `HKLM\SYSTEM\CurrentControlSet\Control\
     Session Manager\Environment` `Path`.
   - Read with `DoNotExpandEnvironmentNames`; write back as `ExpandString` —
     preserves `REG_EXPAND_SZ` and unexpanded `%…%` references (this is why
     `setx` is banned).
   - Prepend the install dir if not already present (case-insensitive,
     backslash-normalised comparison); de-duplicate any existing identical
     entry.
   - Broadcast `WM_SETTINGCHANGE` (`SendMessageTimeout`, `HWND_BROADCAST`)
     so new shells pick up PATH without logoff — `setx`'s other raison
     d'être, handled natively.
4. Failure policy: append findings to `<install dir>\_installer\path_setup.log`
   and **exit 0** on recoverable errors (registry permission denied, PowerShell
   unavailable). A non-zero exit fails the whole install (`Return="check"`) —
   reserved for truly unrecoverable states (in practice: never).
5. `exit /b 0` at the end, always.

### 6.4 `packaging/windows/pre_uninstall.bat`

1. No scope flag exists — remove the exact entry from **both** hives,
   ignoring access-denied on the one that isn't writable in the current
   context (per-user uninstall → HKLM write fails silently = correct).
2. Exact-literal match only (same normalisation as 6.3): removes precisely
   the entry added at install time; anything else in PATH is untouched.
3. Never touches `.profiles` configs, logs or any user data (anti-goal).
4. Same PowerShell approach (`DoNotExpandEnvironmentNames` + `ExpandString`
   + `WM_SETTINGCHANGE`), same log file, same exit-0 failure policy.

### 6.5 Docs & CHANGELOG

- `docs/installation-guide.en.md` (+ `.fr.md` mirror):
  - The shortcut claim becomes true — verify wording against reality.
  - Document the new wizard flow: scope choice, **Install Options** page with
    "Add ProFiles to PATH" (checked by default), finish page.
  - Document `msiexec` escape hatches: `/qn` (PATH included by default),
    `OPTION_ADD_TO_PATH=0` opt-out.
  - Note that `profiles --headless` now works from any terminal after a
    default install (new terminal windows pick up PATH; already-open ones
    don't).
- `CHANGELOG.md` under `[Unreleased]` → `### Added`: installer polish bullets
  (desktop shortcut, finish page, PATH option, branded installer).

### 6.6 Config-coherence test

`tests/packaging/test_windows_installer_assets.py` (new module inside the
**existing** `tests/packaging/` package):

- pyproject parses (tomllib) and the windows section contains the expected keys.
- The PATH option is declared under the **singular** `install_option` key as
  an array-of-tables entry with `name = "add_to_path"` and `default = true`
  (regression guard for the plural-key trap — the plural key would silently
  disable the feature).
- `installer_background`/`installer_banner` resolve to committed files that
  are **BMPs of exactly 493×312 / 493×58** (regression guard: someone replacing
  a BMP with a PNG otherwise only breaks CI packaging, not tests).
- `post_install_script`/`pre_uninstall_script` files exist and end with
  `exit /b 0` (the `Return="check"` guard).
- Pure-Python, no Windows dependency, runs in the existing CI matrix.

### 6.7 Line endings & binary rules (gotcha)

The repo enforces `eol=lf` via `.gitattributes`. Batch files with LF-only
line endings hit known `cmd.exe` edge cases. Add to `.gitattributes` in the
same PR:

```gitattributes
*.bat text eol=crlf
*.bmp binary
```

### 6.8 CI trigger addition

`.github/workflows/build-windows.yml` builds the MSI on PRs via a `paths:`
filter (`pyproject.toml`, `src/**`, `img/**`, itself). The iteration loop of
§7 requires fresh artifacts when only `packaging/windows/*.bat` changes, so
add `packaging/windows/**` to that filter (one-line, additive).

## 7. Verification Plan

1. PR ⇒ `build-windows.yml` builds the MSI and uploads it as an artifact —
   no local Windows needed for iteration. (The §6.8 `paths:` addition takes
   effect within the PR itself: for `pull_request` events GitHub uses the
   workflow file from the PR branch, so later pushes that only touch
   `packaging/windows/**` still get fresh artifacts.)
2. Owner tests the artifact on the professional Windows machine:
   - Per-user install: wizard flow (License → Scope → Dir → **Install Options**
     → Ready → Finish); desktop shortcut created; finish page shows Launch
     (checked) + both links; **banner/welcome art + text contrast checkpoint**.
   - New terminal: `profiles --headless` resolves (per-user scope).
   - Per-machine install (admin): same checks; PATH lands in HKLM.
   - Uninstall (interactive + `/x /qn`): PATH entry gone from the right
     hive(s); Start Menu / desktop shortcut gone; `.profiles` configs & logs
     intact.
   - `msiexec /i ProFiles.msi /qn`: silent install works; PATH added;
     `OPTION_ADD_TO_PATH=0` opt-out respected.
   - Upgrade over the currently released version: fresh-install semantics
     (`NOT Installed` ⇒ post-install runs once).
3. macOS / Linux release jobs unaffected (no config outside the windows
   table except docs/CHANGELOG).

## 8. Alternatives Considered

- **Declarative-only** (no scripts): simplest, but loses the PATH convenience
  (native WiX PATH feature is console-app-only in 0.4.7).
- **Native WiX `<Environment>` PATH**: rejected — gated to `console_app = true`;
  enabling it for ProFiles would change the stub binary behaviour.
- **`setx` in the post-install script**: rejected — 1024-char truncation and
  expanded-string writes destroy `REG_EXPAND_SZ` content.
- **Aggressive uninstall cleanup** (checkbox to delete config/logs): rejected —
  uninstall options don't display in the standard Add/Remove Programs flow
  (upstream quirk), and user-data deletion is risky.
- **`starter_config` install option**: dropped — an installer cannot know
  where the test-programs tree lives; `ProFiles.exe --init` stays available.
- **macOS PKG instead of DMG / DMG branding**: out of scope per §3.
- **Vendoring the WiX template**: rejected — upstream template already
  provides every hook we need; staying aligned keeps future Briefcase bumps
  cheap.

## 9. Left to the Builder

- Exact PowerShell one-liner composition and `.bat` quoting/escaping.
- BMP pixel work (PIL drawing details, anti-aliasing, text zone layout).
- Test file naming details beyond §6.6 and doc phrasing polish.
- Branch/PR naming per repo conventions (single PR, `Closes #183`).
