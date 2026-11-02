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
    """Remove Markdown syntax for headless mode.

    Inline syntax is stripped; links/images degrade to ``label (url)`` so the
    target survives in stdout and logs. Fenced code blocks keep their content
    but lose the ``` / ~~~ marker lines (and runs of blank lines collapse to
    a single paragraph break); other block-level structures (lists, tables,
    blockquotes) stay as literal text lines, which remains readable in a
    terminal.
    """
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Fence marker lines first: left in place, the inline-code strip would
    # chew the ``` ticks into stray backticks around the content.
    text = re.sub(r"^(?:```|~~~)[a-zA-Z0-9_-]*\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Images first: the link pattern would otherwise eat the label and leave
    # the leading "!" behind.
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", r"\1 (\2)", text)
    text = re.sub(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", r"\1 (\2)", text)
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
