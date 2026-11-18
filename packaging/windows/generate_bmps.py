#!/usr/bin/env python3
"""Generate the brand-native WiX installer BMPs.

Outputs (committed to the repo — this script is provenance, not part of
any build):

- ``img/installer_background.bmp`` 493x312 — the welcome/finish dialog art
  (WiX ``WixUIDialogBmp``). A 164 px brand-gradient panel on the left with
  the white logo mark; plain white on the right. WiX draws the dialog text
  from x≈173, so everything right of the panel must stay free of art.
- ``img/installer_banner.bmp`` 493x58 — the top-strip art on banner pages
  (WiX ``WixUIBannerBmp``). White from x=0 to x=428 because WiX draws the
  black page title at x≈20; the brand-gradient block with the logo mark
  sits at x=429..492.

Both assets are drawn at 4x and LANCZOS-downsampled: WiX renders the
493x58 banner in a 370x44 control, so the mark needs clean edges at that
scale (and at 125–150 % DPI).

WiX requires uncompressed 24-bit BMPs at exactly these sizes; Briefcase
resolves the ``installer_background``/``installer_banner`` config values
with ``with_suffix(".bmp")`` against the project root.

Usage::

    uv run python packaging/windows/generate_bmps.py [--check]

``--check`` exits non-zero when the outputs are missing or older than this
script (dev convenience; CI never regenerates the BMPs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_OUT = REPO_ROOT / "img" / "installer_background.bmp"
BANNER_OUT = REPO_ROOT / "img" / "installer_banner.bmp"

# Brand gradient endpoints, sampled from the source banner art.
GRADIENT_LEFT = (99, 91, 204)  # #635BCC
GRADIENT_RIGHT = (130, 93, 217)  # #825ED9
WHITE = (255, 255, 255)

BACKGROUND_SIZE = (493, 312)  # WiX WixUIDialogBmp
BANNER_SIZE = (493, 58)  # WiX WixUIBannerBmp

# Native-frame zones: WiX draws the page title at x≈20 of 493 on banner
# pages, and body text from x≈173 on the welcome/finish dialogs.
PANEL_WIDTH = 164  # background brand panel; text zone starts at x≈173
BANNER_BRAND_X = 429  # banner brand block start; title box ends at x≈420
BANNER_BRAND_WIDTH = 64

# Render at 4x then downsample with LANCZOS for clean rounded edges.
SCALE = 4


def _lerp(start: int, end: int, t: float) -> int:
    """Linear interpolation between two channel values."""
    return round(start + (end - start) * t)


def _gradient(size: tuple[int, int], *, horizontal: bool) -> Image.Image:
    """Draw the brand gradient, one line per column (or row)."""
    width, height = size
    gradient = Image.new("RGB", size)
    draw = ImageDraw.Draw(gradient)
    span = max((width if horizontal else height) - 1, 1)
    for step in range(span + 1):
        color = tuple(
            _lerp(a, b, step / span) for a, b in zip(GRADIENT_LEFT, GRADIENT_RIGHT, strict=False)
        )
        if horizontal:
            draw.line([(step, 0), (step, height)], fill=color)
        else:
            draw.line([(0, step), (width, step)], fill=color)
    return gradient


def _mark(
    size: int,
    radius: int,
    bar_width: int,
    bar_height: int,
    gap: int,
    pad: int,
    third_width: int,
) -> Image.Image:
    """White rounded square with three brand bars, at SCALE× size."""
    side = size * SCALE
    mark = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mark)
    draw.rounded_rectangle(
        (0, 0, side - 1, side - 1),
        radius=radius * SCALE,
        fill=(*WHITE, 255),
    )
    y = pad * SCALE
    for width in (bar_width, bar_width, third_width):
        draw.rectangle(
            (pad * SCALE, y, (pad + width) * SCALE - 1, y + bar_height * SCALE - 1),
            fill=(*GRADIENT_LEFT, 255),
        )
        y += (bar_height + gap) * SCALE
    return mark


def generate_background() -> Image.Image:
    """Draw the 493x312 art: left brand panel, white dialog-text zone."""
    width, height = BACKGROUND_SIZE
    canvas = Image.new("RGB", (width * SCALE, height * SCALE), WHITE)
    panel = _gradient((PANEL_WIDTH * SCALE, height * SCALE), horizontal=False)
    canvas.paste(panel, (0, 0))

    mark = _mark(
        size=56,
        radius=14,
        bar_width=30,
        bar_height=6,
        gap=4,
        pad=13,
        third_width=19,
    )
    canvas.paste(mark, (54 * SCALE, 128 * SCALE), mark)
    return canvas.resize(BACKGROUND_SIZE, Image.LANCZOS)


def generate_banner() -> Image.Image:
    """Draw the 493x58 banner: white title zone, brand block on the right."""
    width, height = BANNER_SIZE
    canvas = Image.new("RGB", (width * SCALE, height * SCALE), WHITE)
    block = _gradient((BANNER_BRAND_WIDTH * SCALE, height * SCALE), horizontal=True)
    canvas.paste(block, (BANNER_BRAND_X * SCALE, 0))

    mark = _mark(
        size=34,
        radius=9,
        bar_width=18,
        bar_height=4,
        gap=2,
        pad=8,
        third_width=11,
    )
    canvas.paste(mark, (444 * SCALE, 12 * SCALE), mark)
    return canvas.resize(BANNER_SIZE, Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    """Write (or verify) the installer BMPs; see module docstring."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when outputs are missing or older than this script",
    )
    args = parser.parse_args(argv)

    outputs = (BACKGROUND_OUT, BANNER_OUT)
    if args.check:
        script_mtime = Path(__file__).stat().st_mtime
        for out in outputs:
            if not out.is_file() or out.stat().st_mtime < script_mtime:
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
