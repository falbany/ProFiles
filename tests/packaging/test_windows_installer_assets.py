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
