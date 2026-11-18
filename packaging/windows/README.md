# Windows packaging resources

Support files for the Windows MSI built by Briefcase (issue #183). The
installer behaviour itself is configured in `pyproject.toml`
(`[tool.briefcase.app.profiles.windows]`); this directory holds the pieces
that cannot live there.

| File | Role |
| --- | --- |
| `post_install.bat` | Adds the install dir to PATH when the "Add ProFiles to PATH" checkbox is checked (default). |
| `pre_uninstall.bat` | Removes exactly that PATH entry on uninstall; touches nothing else. |
| `generate_bmps.py` | Regenerates the branded installer BMPs (committed under `img/`). |

## Script contract

Briefcase bundles both scripts into the MSI and runs them through its
template wrappers:

- `post_install.bat` runs **before `InstallFinalize`** on fresh installs
  only, elevated for per-machine installs. The wrapper exports
  `ALLUSERS` (1/0), `INSTALLER_PATH`, `INSTALLER_UNATTENDED` (1 in
  `msiexec /qn` mode) and `OPTION_ADD_TO_PATH` (1/0 from the checkbox).
- `pre_uninstall.bat` runs **after `InstallInitialize`** (before
  `RemoveFiles`). The wrapper exports only `INSTALLER_UNATTENDED` — there
  is no scope flag, so it clears the entry from **both** hives and treats
  an unwritable hive as success.

Both scripts: registry edits via PowerShell (`DoNotExpandEnvironmentNames`
read / `ExpandString` write, so `REG_EXPAND_SZ` content survives), exact
case-insensitive matching of the install dir only, `WM_SETTINGCHANGE`
broadcast, a `path_setup.log` written next to the script, and **always
exit 0** — WiX runs them with `Return="check"`, so a non-zero exit would
fail the whole install/uninstall for a PATH convenience.

Why not `setx`: it truncates PATH at 1024 characters and writes the
expanded value, destroying `%…%` references.

## Regenerating the installer art

`img/installer_background.bmp` (493×312, welcome dialog) and
`img/installer_banner.bmp` (493×58, page banner) are committed assets —
they are **not** generated at build time. To tweak them:

```bash
uv run python packaging/windows/generate_bmps.py        # regenerate
uv run python packaging/windows/generate_bmps.py --check  # staleness check
```

The art follows WiX's text-safe zones: the banner stays white left of x=429
(WiX draws the black page title at x≈20) and the background stays white
right of x=169 (dialog text starts at x≈173). Do not add art back into those
zones.

Commit any regenerated BMP together with this script (the provenance
record). Design background:
`docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md`
and `docs/superpowers/specs/2026-11-18-installer-art-native-frame-design.md`.
