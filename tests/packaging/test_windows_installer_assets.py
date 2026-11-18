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
