#!/usr/bin/env python3
"""Generate the branded WiX installer BMPs from the ProFiles banner art.

Outputs (committed to the repo — this script is provenance, not part of
any build):

- ``img/installer_background.bmp`` 493x312 — the welcome-dialog art
  (WiX ``WixUIDialogBmp``), derived by cover-cropping
  ``img/ProFiles_banner.png`` (approved "brand gradient" direction).
- ``img/installer_banner.bmp`` 493x58 — the top-strip art on every other
  wizard page (WiX ``WixUIBannerBmp``): the brand gradient, the white
  rounded logo mark, and translucent pill accents. Deliberately text-free:
  WiX overlays the page title on the left of the banner.

WiX requires uncompressed 24-bit BMPs at exactly these sizes; Briefcase
resolves the ``installer_background``/``installer_banner`` config values
with ``with_suffix(".bmp")`` against the project root.

Usage::

    uv run python packaging/windows/generate_bmps.py [--check]

``--check`` exits non-zero when the outputs are missing or older than the
inputs (dev convenience; CI never regenerates the BMPs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "img" / "ProFiles_banner.png"
BACKGROUND_OUT = REPO_ROOT / "img" / "installer_background.bmp"
BANNER_OUT = REPO_ROOT / "img" / "installer_banner.bmp"

# Brand gradient endpoints, sampled from the source banner.
GRADIENT_LEFT = (99, 91, 204)  # #635BCC
GRADIENT_RIGHT = (130, 93, 217)  # #825ED9

BACKGROUND_SIZE = (493, 312)  # WiX WixUIDialogBmp
BANNER_SIZE = (493, 58)  # WiX WixUIBannerBmp

MARK_BOX = (16, 16, 42, 42)  # banner logo mark (x0, y0, x1, y1)
MARK_RADIUS = 7
MARK_BARS = (
    (22, 23, 36, 26),  # (x0, y0, x1, y1) — top bar
    (22, 29, 36, 32),  # middle bar
    (22, 35, 31, 38),  # short bottom bar (logo motif)
)
PILLS = (
    (360, 20, 440, 38),
    (452, 26, 493, 40),
)


def _lerp(start: int, end: int, t: float) -> int:
    """Linear interpolation between two channel values."""
    return round(start + (end - start) * t)


def generate_background() -> Image.Image:
    """Cover-crop the banner art down to the welcome-dialog size."""
    source = Image.open(SOURCE).convert("RGB")
    src_w, src_h = source.size
    dst_w, dst_h = BACKGROUND_SIZE

    # Scale-to-cover: crop the source to the target aspect, centred.
    src_aspect = src_w / src_h
    dst_aspect = dst_w / dst_h
    if src_aspect > dst_aspect:
        crop_w = round(src_h * dst_aspect)
        box = ((src_w - crop_w) // 2, 0, (src_w + crop_w) // 2, src_h)
    else:
        crop_h = round(src_w / dst_aspect)
        box = (0, (src_h - crop_h) // 2, src_w, (src_h + crop_h) // 2)
    return source.crop(box).resize(BACKGROUND_SIZE, Image.LANCZOS)


def generate_banner() -> Image.Image:
    """Draw the banner strip: brand gradient, logo mark, pill accents."""
    width, height = BANNER_SIZE
    banner = Image.new("RGB", BANNER_SIZE)
    draw = ImageDraw.Draw(banner)

    # Horizontal brand gradient, one column at a time.
    r0, g0, b0 = GRADIENT_LEFT
    r1, g1, b1 = GRADIENT_RIGHT
    max_t = max(width - 1, 1)
    for x in range(width):
        t = x / max_t
        column = (_lerp(r0, r1, t), _lerp(g0, g1, t), _lerp(b0, b1, t))
        draw.line([(x, 0), (x, height)], fill=column)

    # Translucent pill accents on an RGBA overlay, composited on top.
    overlay = Image.new("RGBA", BANNER_SIZE, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for box in PILLS:
        overlay_draw.rounded_rectangle(box, radius=9, fill=(255, 255, 255, 40))
    banner = Image.alpha_composite(banner.convert("RGBA"), overlay)

    # The white rounded logo mark with its three line bars.
    mark_draw = ImageDraw.Draw(banner)
    mark_draw.rounded_rectangle(MARK_BOX, radius=MARK_RADIUS, fill=(255, 255, 255, 255))
    for bar in MARK_BARS:
        mark_draw.rectangle(bar, fill=(*GRADIENT_LEFT, 255))

    return banner.convert("RGB")


def main(argv: list[str] | None = None) -> int:
    """Write (or verify) the installer BMPs; see module docstring."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when outputs are missing or older than the inputs",
    )
    args = parser.parse_args(argv)

    inputs = (Path(__file__), SOURCE)
    outputs = (BACKGROUND_OUT, BANNER_OUT)
    if args.check:
        newest_input = max(path.stat().st_mtime for path in inputs)
        for out in outputs:
            if not out.is_file() or out.stat().st_mtime < newest_input:
                print(f"stale or missing: {out}", file=sys.stderr)
                return 1
        return 0

    generate_background().save(BACKGROUND_OUT, format="BMP")
    generate_banner().save(BANNER_OUT, format="BMP")
    for out in outputs:
        print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
