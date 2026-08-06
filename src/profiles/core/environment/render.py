"""Render escape sequences and Markdown subset into structured RenderTree."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TextSegment:
    """A segment of text with an associated formatting style."""

    text: str
    style: Literal["normal", "bold", "italic", "heading", "code"] = "normal"


RenderTree = list[TextSegment]


def render_text(text: str, headless: bool = False) -> str | RenderTree:
    """Render escape sequences and Markdown subset.

    Args:
        text: Raw text string potentially containing escape sequences (\\n, \\t, etc.)
            and Markdown formatting (*bold*, # heading, etc.).
        headless: If True, returns plain unformatted text with Markdown stripped.

    Returns:
        Plain string if headless=True, else RenderTree (list of TextSegments).
    """
    # Step 1: Process escape sequences
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    text = text.replace('\\"', '"')
    text = text.replace("\\'", "'")
    text = text.replace("\\\\", "\\")

    if headless:
        return _strip_markdown(text)

    return _parse_markdown(text)


def _strip_markdown(text: str) -> str:
    """Remove Markdown syntax for headless mode."""
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text


def _parse_markdown(text: str) -> RenderTree:
    """Parse Markdown string into structured RenderTree."""
    segments: RenderTree = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i > 0:
            segments.append(TextSegment(text="\n", style="normal"))

        if line.startswith("# "):
            segments.append(TextSegment(text=line[2:], style="heading"))
        elif line.startswith("## "):
            segments.append(TextSegment(text=line[3:], style="heading"))
        elif line.startswith("### "):
            segments.append(TextSegment(text=line[4:], style="heading"))
        else:
            _parse_inline_formatting(line, segments)

    return segments


def _parse_inline_formatting(line: str, segments: RenderTree) -> None:
    """Parse inline formatting (**bold**, *italic*, `code`) for a single line."""
    if not line:
        return

    pattern = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`)")
    parts = pattern.split(line)

    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            segments.append(TextSegment(text=part[2:-2], style="bold"))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            segments.append(TextSegment(text=part[1:-1], style="italic"))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            segments.append(TextSegment(text=part[1:-1], style="code"))
        else:
            segments.append(TextSegment(text=part, style="normal"))


__all__ = ["TextSegment", "RenderTree", "render_text"]
