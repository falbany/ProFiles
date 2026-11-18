"""Coherence checks for the Windows MSI installer assets and config.

The Windows packaging (pyproject briefcase config + bundled scripts + BMP
art) is exercised only by CI's build-windows job; these tests catch the
breakages that would otherwise surface only there. See
docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md.
"""

import tomllib
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]


def _windows_config() -> dict:
    """Load the [tool.briefcase.app.profiles.windows] section."""
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        return tomllib.load(fh)["tool"]["briefcase"]["app"]["profiles"]["windows"]


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


SCRIPTS = ("post_install.bat", "pre_uninstall.bat")


def test_bat_scripts_exist_and_exit_clean() -> None:
    """Both scripts exist and always terminate 0 (WiX Return="check")."""
    for name in SCRIPTS:
        body = (REPO_ROOT / "packaging" / "windows" / name).read_bytes()
        assert body.rstrip().endswith(b"exit /b 0")
        assert b"\r\n" in body  # committed via *.bat eol=crlf


def test_post_install_preserves_expand_sz_and_broadcasts() -> None:
    """PATH edit must not expand REG_EXPAND_SZ and must notify shells."""
    body = (REPO_ROOT / "packaging" / "windows" / "post_install.bat").read_text(encoding="utf-8")
    assert "DoNotExpandEnvironmentNames" in body
    assert "ExpandString" in body
    assert "setx" not in body.lower()
    # WM_SETTINGCHANGE broadcast (0x1a) so running shells see the new PATH.
    assert "SendMessageTimeout" in body and "0x1a" in body
    # Driven by the Install Options checkbox and the install scope.
    assert "OPTION_ADD_TO_PATH" in body and "ALLUSERS" in body


def test_pre_uninstall_removes_exactly_its_own_entry() -> None:
    """Cleanup matches the literal install dir in BOTH hives, nothing else."""
    body = (REPO_ROOT / "packaging" / "windows" / "pre_uninstall.bat").read_text(encoding="utf-8")
    # One loop over both hives: per-user uninstall cannot write HKLM, and
    # that must be treated as success (no scope flag reaches this script).
    assert "foreach($s in 'User','Machine')" in body
    assert "DoNotExpandEnvironmentNames" in body
    assert "ExpandString" in body
    assert "setx" not in body.lower()
    assert "SendMessageTimeout" in body


def test_windows_installer_config() -> None:
    """The briefcase windows section matches the approved design."""
    cfg = _windows_config()

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


def test_referenced_installer_files_exist() -> None:
    """Every file the windows section references must resolve on disk."""
    cfg = _windows_config()

    for key in ("installer_background", "installer_banner"):
        # Briefcase resolves with_suffix(".bmp") against the project root.
        assert (REPO_ROOT / f"{cfg[key]}.bmp").is_file()
    for key in ("post_install_script", "pre_uninstall_script"):
        assert (REPO_ROOT / cfg[key]).is_file()


def test_install_dir_apostrophe_quoting_idiom() -> None:
    """The cmd→PowerShell substitution must double apostrophes, not strip.

    %INSTALL_DIR:'=''% replaces ' with '' (valid PowerShell literal for
    dirs like C:\\Users\\O'Brien\\...). The inverted ''=% form strips
    doubled apostrophes and leaves single ones breaking the PS quoting.
    """
    for name in SCRIPTS:
        body = (REPO_ROOT / "packaging" / "windows" / name).read_text(encoding="utf-8")
        # Doubling idiom %INSTALL_DIR:'=''% : cmd replaces ' with ''.
        # The inverted ''=% form strips doubled apostrophes and leaves
        # single ones breaking the PowerShell quoting.
        doubling = "%INSTALL_DIR:" + chr(39) + "=" + chr(39) + chr(39) + "%"
        stripping = "%INSTALL_DIR:" + chr(39) + chr(39) + "=" + "%"
        assert doubling in body
        assert stripping not in body


def test_registry_contracts_are_pinned() -> None:
    """Content pins for the HKLM key and the unwritable-hive swallow."""
    for name in SCRIPTS:
        body = (REPO_ROOT / "packaging" / "windows" / name).read_text(encoding="utf-8")
        assert "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment" in body
    pre = (REPO_ROOT / "packaging" / "windows" / "pre_uninstall.bat").read_text(encoding="utf-8")
    assert "catch{$key=$null}" in pre
