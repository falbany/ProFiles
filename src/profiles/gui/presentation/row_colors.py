"""Pure row-color rule engine — maps a filename to ttk.Treeview tag names.

No Tk dependency. Owns the substring-match logic; the caller is
responsible for configuring ttk tags on the actual Treeview.

Tag naming convention (preserved for back-compat with existing code):
    {tag_prefix}_default                 — always present
    {tag_prefix}_{safe_pattern}_{color}  — per rule, first match wins
"""

from __future__ import annotations

from collections.abc import Iterable


def make_rule_tag_name(
    tag_prefix: str,
    pattern: str,
    color: str,
) -> str:
    """Build a stable tag name for a ``(pattern, color)`` rule.

    Spaces are replaced with underscores so the tag can be passed to ttk.
    The leading ``#`` on the colour is stripped to keep the name short.
    """
    safe_pattern = pattern.replace(" ", "_")
    safe_color = color.lstrip("#").replace(" ", "_")
    return f"{tag_prefix}_{safe_pattern}_{safe_color}"


def default_tag_name(tag_prefix: str) -> str:
    """Return the always-applied default tag name for a given prefix."""
    return f"{tag_prefix}_default"


class RowColorRules:
    """Compiled, ready-to-match set of row-color rules.

    A ``default`` tag is always included; the first rule whose pattern
    is a case-insensitive substring of the filename is appended after.
    """

    def __init__(
        self,
        rules: Iterable[tuple[str, str]],
        tag_prefix: str,
    ) -> None:
        """Initialise from raw ``(pattern, color_hex)`` rules.

        Empty/whitespace patterns or colours are silently skipped.
        """
        self._default_tag = default_tag_name(tag_prefix)
        self._compiled: list[tuple[str, str]] = []
        for pattern, _color in rules:
            if not pattern or not _color:
                continue
            self._compiled.append(
                (pattern.lower(), make_rule_tag_name(tag_prefix, pattern, _color))
            )

    def tags_for(self, filename: str) -> tuple[str, ...]:
        """Return the tags to apply to *filename*.

        Always includes the default tag; appends the first matching rule
        (case-insensitive substring).
        """
        if not self._compiled:
            return (self._default_tag,)
        filename_lower = filename.lower()
        for pattern_lower, tag_name in self._compiled:
            if pattern_lower in filename_lower:
                return (self._default_tag, tag_name)
        return (self._default_tag,)
