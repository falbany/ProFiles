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

    >>> match_filter("PROD_Tester_V01.mttl", "PROD")
    True
    >>> match_filter("DEV_Test.mttl", "PROD OR DEV")
    True
    >>> match_filter("PROD_Tester.mttl", "PROD -Tester")
    False
    >>> match_filter("file.mttl", '"exact name"')
    False
    >>> match_filter("PROD_Tester_V01.mttl", "PROD Tester V01")
    True
    >>> match_filter("DEV_Only.mttl", "PROD OR DEV OR -Only")
    True
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache


def tokenize(query: str) -> list[str]:
    """Split a query string into tokens, preserving double-quoted phrases.

    Quoted segments (``"…"``) are returned as single tokens *without* the
    surrounding quotes.  All other whitespace-separated words become
    individual tokens.

    Args:
        query: The raw filter string entered by the user.

    Returns:
        A list of token strings. Tokens that are empty or whitespace-only
        (e.g. from empty quoted phrases) are dropped, so every element is
        a non-empty, non-whitespace :class:`str`.
    """
    # Match either a quoted string (capture inside quotes) or a non-whitespace token.
    # An empty grouped phrase (`""`, `"   "`) yields group(1) == "" → dropped.
    tokens: list[str] = []
    for m in re.finditer(r'"([^"]*)"|(\S+)', query):
        token = m.group(1) if m.group(1) is not None else m.group(2)
        if token and token.strip():
            tokens.append(token)
    return tokens


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

    This is the single public entry point for the module.  The query is
    compiled once per distinct *query* string and memoized (256 entries).

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
    return compile_query(query)(filename)


def _match_all(_name: str) -> bool:
    """Matcher for empty / whitespace-only queries: match everything."""
    return True


@lru_cache(maxsize=256)
def compile_query(query: str) -> Callable[[str], bool]:
    """Compile *query* into a reusable ``name -> bool`` predicate.

    Tokenization and OR-group splitting run once per distinct query;
    repeated calls with the same query reuse the compiled closure
    (memoized via :func:`functools.lru_cache`, 256 entries).

    Args:
        query: The filter expression.

    Returns:
        A predicate callable taking a filename and returning bool.
    """
    stripped = query.strip()
    tokens = tokenize(stripped)
    if not tokens:
        return _match_all

    or_groups = split_or_groups(tokens)

    def matcher(name: str) -> bool:
        # OR semantics: at least one group must match
        return any(_group_matches(name, group) for group in or_groups)

    return matcher
