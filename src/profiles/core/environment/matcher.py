"""Glob pattern matcher — selects the most specific matching pattern.

Single Responsibility: pick the most specific glob pattern from a set
that matches a given filename. No I/O, no UI dependencies. Pure stdlib.

Specificity priority (most specific wins):

1. Exact match (no wildcards): ``toto.mttl``
2. Question mark patterns: ``test?.txt``
3. Star patterns: ``*.mttl``, ``report_*.pdf``
4. Extension-only patterns: ``.pdf`` (treated as ``.*.pdf`` for matching)

This is the core building block for the workflow engine to pick
which hook config applies to a given file (e.g. ``*.mttl`` vs ``toto.mttl``).
"""

from __future__ import annotations

import fnmatch
from typing import Iterable

_SPECIFICITY_EXACT = 3
_SPECIFICITY_QUESTION = 2
_SPECIFICITY_STAR = 1

def _normalize_pattern(pattern: str) -> str:
    """Normalize extension-only patterns (``.pdf`` → ``*.pdf``).

    Extension patterns like ``.pdf`` are rewritten to ``*.pdf`` so that
    ``fnmatch`` treats them as glob-star and they participate correctly
    in specificity ranking.
    """
    if pattern.startswith(".") and "*" not in pattern and "?" not in pattern:
        return "*" + pattern
    return pattern

def _pattern_specificity(pattern: str) -> tuple[int, int]:
    """Return specificity score (higher = more specific).

    Scored as (category_tier, non_wildcard_literal_length) so that longer
    literal prefixes (e.g. 'report_*.pdf' vs '*.pdf') win among star patterns.
    """
    has_star = "*" in pattern
    has_question = "?" in pattern
    
    # Calculate non-wildcard literal length
    literal_len = len(pattern.replace("*", "").replace("?", ""))
    
    if not has_star and not has_question:
        tier = _SPECIFICITY_EXACT
    elif has_question and not has_star:
        tier = _SPECIFICITY_QUESTION
    else:
        tier = _SPECIFICITY_STAR
        
    return (tier, literal_len)

def select_most_specific_pattern(
    patterns: Iterable[str],
    filename: str,
) -> str | None:
    """Select the most specific pattern that matches *filename*.

    Args:
        patterns: Iterable of glob patterns to consider. Patterns may
            include ``*`` and ``?`` wildcards, or be plain substrings.
        filename: Filename (not full path) to test against the patterns.

    Returns:
        The most specific pattern that matches, or ``None`` if no
        pattern matches. On ties (same specificity), the first one
        encountered wins so declaration order is preserved.
    """
    matches: list[str] = []
    for raw in patterns:
        pattern = _normalize_pattern(raw)
        if fnmatch.fnmatch(filename, pattern):
            matches.append(raw)

    if not matches:
        return None

    return max(matches, key=lambda p: _pattern_specificity(_normalize_pattern(p)))

__all__ = [
    "select_most_specific_pattern",
]
