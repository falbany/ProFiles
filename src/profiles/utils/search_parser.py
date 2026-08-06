"""Search query parser supporting Google-style operators.

Provides a single public function :func:`match_filter` that checks
whether a filename matches a filter expression with the following
operators (modelled after Google Search):

======================== =====================================================
Expression               Meaning
======================== =====================================================
``term1 term2``          AND — file must contain **both** terms
``term1 OR term2``       OR — file must contain **at least one** term
``-term``                NOT — file must **not** contain the term
``+term``                Explicit inclusion (same as a plain term)
``"exact phrase"``       Exact phrase — the quoted string must appear verbatim
======================== =====================================================

Operator precedence (highest to lowest):

1. Quoted string (``"…"``) — groups words into a single literal
2. Prefix ``-`` / ``+`` — binds to the immediately following term
3. Implicit AND (space) — all terms in a group must match
4. ``OR`` — separates alternative groups; any group may match

Examples::

    >>> match_filter("ST_PRO_Mutest_V01.mttl", "ST_PRO")
    True
    >>> match_filter("ST_ENG_Test.mttl", "ST_PRO OR ST_ENG")
    True
    >>> match_filter("ST_PRO_Mutest.mttl", "ST_PRO -Mutest")
    False
    >>> match_filter("file.mttl", '"exact name"')
    False
    >>> match_filter("ST_PRO_Mutest_V01.mttl", "ST_PRO Mutest V01")
    True
    >>> match_filter("ST_ENG_Only.mttl", "ST_PRO OR ST_ENG OR -Only")
    True
"""

from __future__ import annotations

import re
from collections.abc import Sequence


def tokenize(query: str) -> list[str]:
    """Split a query string into tokens, preserving double-quoted phrases.

    Quoted segments (``"…"``) are returned as single tokens *without* the
    surrounding quotes.  All other whitespace-separated words become
    individual tokens.

    Args:
        query: The raw filter string entered by the user.

    Returns:
        A list of token strings.
    """
    # Match either a quoted string (capture inside quotes) or a non-whitespace token
    return [m.group(1) or m.group(2) for m in re.finditer(r'"([^"]*)"|(\S+)', query)]


def split_or_groups(tokens: Sequence[str]) -> list[list[str]]:
    """Split a token list into OR-separated groups.

    The word ``OR`` (case-insensitive) is used as the separator.  Each
    resulting group is AND-ed internally.

    Args:
        tokens: Tokenised query (output of :func:`tokenize`).

    Returns:
        A list of token groups, each representing one OR alternative.
    """
    groups: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token.upper() == "OR":
            groups.append(current)
            current = []
        else:
            current.append(token)
    groups.append(current)
    return groups


def _term_matches(text_lower: str, term: str) -> bool:
    """Check whether *term* appears in *text_lower* (case-insensitive).

    Args:
        text_lower: The filename (already lowered).
        term: The term to look for (will be lowered internally).

    Returns:
        True if the term is found as a substring.
    """
    return term.lower() in text_lower


def _group_matches(text: str, group_tokens: Sequence[str]) -> bool:
    """Evaluate an AND-group against *text*.

    Every token in the group must match (AND logic).  Tokens prefixed
    with ``-`` are negated (NOT).  Tokens prefixed with ``+`` behave
    identically to plain tokens (explicit AND).

    Args:
        text: The filename to test.
        group_tokens: Tokens belonging to one OR-alternative.

    Returns:
        True if the group (as a whole) matches.
    """
    text_lower = text.lower()
    for token in group_tokens:
        if not token:  # skip empties (consecutive OR, trailing OR, …)
            continue
        if token.startswith("-"):
            term = token[1:]
            if term and _term_matches(text_lower, term):
                return False
        else:
            # Strip explicit + prefix if present
            term = token[1:] if token.startswith("+") else token
            if term and not _term_matches(text_lower, term):
                return False
    return True


def match_filter(filename: str, query: str) -> bool:
    """Check whether *filename* matches the Google-style *query* filter.

    This is the single public entry point for the module.

    Args:
        filename: The filename (or relative path) to test.
        query: The filter expression entered by the user.

    Returns:
        ``True`` if the filename satisfies the filter expression,
        ``False`` otherwise.  An empty or whitespace-only query always
        returns ``True`` (matches everything).

    Raises:
        TypeError: If either argument is not a :class:`str`.
    """
    if not isinstance(filename, str):
        raise TypeError(f"filename must be str, not {type(filename).__name__}")
    if not isinstance(query, str):
        raise TypeError(f"query must be str, not {type(query).__name__}")

    stripped = query.strip()
    if not stripped:
        return True  # empty filter matches everything

    tokens = tokenize(stripped)
    if not tokens:
        return True

    or_groups = split_or_groups(tokens)

    # OR semantics: at least one group must match
    return any(_group_matches(filename, group) for group in or_groups)
