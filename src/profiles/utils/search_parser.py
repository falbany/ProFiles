"""Search query parser supporting Google-style operators.

Provides the public entry points :func:`match_filter` (substring-only
filtering), :func:`match_file` (substring + attribute operators) and
:func:`query_needs_attributes` (precheck telling callers whether file
attributes must be collected before matching).

Substring operators (modelled after Google Search):

======================== =====================================================
Expression               Meaning
======================== =====================================================
``term1 term2``          AND — file must contain **both** terms
``term1 OR term2``       OR — file must contain **at least one** term
``-term``                NOT — file must **not** contain the term
``+term``                Explicit inclusion (same as a plain term)
``"exact phrase"``       Exact phrase — the quoted string must appear verbatim
======================== =====================================================

Attribute operators (only evaluated by :func:`match_file`; sizes use binary
units, durations compare the file's age, dates anchor to local midnights,
decimal operands are floored):

========================== ====================================================
Expression                 Meaning
========================== ====================================================
``size:>10mb``             Size strictly greater than 10 MiB (binary units)
``size:<500kb``            Size strictly less than 500 KiB
``size:1048576``           Size equal to the operand (bare magnitude)
``size:1kb..1mb``          Size range — inclusive on both ends
``modified:<7d``           Modified within the last 7 days (units s m h d w)
``modified:>7d``           Modified more than 7 days ago
``modified:1d..7d``        Age between 1 and 7 days — inclusive
``modified:>2026-11-01``   Modified on/after the local midnight of that date
``modified:<2026-11-01``   Modified strictly before that local midnight
``modified:2026-11-01``    Modified during that local day (bare date)
``modified:today``         Same, anchored to the local midnight of *now*
``created:…``              Same grammar as ``modified``, on the birth time
``-size:>10mb``            Negation — flips the outcome of the operator
``"size:>10mb"``           Quoted — literal substring, never an operator
========================== ====================================================

Keys and units are case-insensitive (``SIZE:>10MB``). Malformed operators
(``size:abc``, ``modified:7d``, unknown keys) are **not** errors: they fall
back to literal substring matching. Attribute terms without attribute data
(``attrs=None``) evaluate to ``False`` while substring terms still apply.
``now`` is read at match time and can be injected for deterministic tests.

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
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from functools import lru_cache
from typing import Protocol


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


# ── Attribute operators (field comparisons) ───────────────────────────────
#
# Grammar: ``key:value`` where *key* is one of ``size``/``size_bytes``,
# ``modified``, ``created`` (case-insensitive) and *value* is a magnitude
# (``10``, ``10mb``, ``1.5kb`` — binary units, floored), a duration
# (``7d``, ``12h`` — units s m h d w, floored), a calendar date
# (``2026-11-01``) or ``today``, optionally prefixed by ``>``/``<`` or
# expressed as an inclusive ``a..b`` range. Anything that does not parse
# as an operator is matched as a literal substring instead.

_SIZE_FIELD = "size_bytes"

_ATTR_FIELD: dict[str, str] = {
    "size": _SIZE_FIELD,
    "size_bytes": _SIZE_FIELD,
    "modified": "mtime",
    "created": "birthtime",
}

_SIZE_UNITS: dict[str, int] = {
    "": 1,
    "b": 1,
    "kb": 1024,
    "mb": 1024**2,
    "gb": 1024**3,
    "tb": 1024**4,
}

_DURATION_UNITS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}

_DAY_SECONDS = 86400

# Magnitude: optional decimal number + optional binary unit; the number is
# required for a valid operand (checked via group(1)).
_MAGNITUDE_RE = re.compile(r"(\d+(?:\.\d+)?)?(b|kb|mb|gb|tb)?", re.IGNORECASE)
# Duration: number with a mandatory unit letter.
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)([smhdw])", re.IGNORECASE)
# Calendar date in ISO order, validated by datetime() construction.
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


class FileAttrsProtocol(Protocol):
    """Structural snapshot required by attribute operators.

    Satisfied by :class:`profiles.core.processing.file_metadata.FileAttrs`;
    defined here so the utils layer stays independent of the core layer.
    """

    size_bytes: int
    mtime: float
    birthtime: float


@dataclass(frozen=True)
class _Comparator:
    """One field comparison extracted from an attribute operator token."""

    field: str
    op: str
    operand: float | str


@dataclass(frozen=True)
class AttrTerm:
    """Parsed attribute operator: canonical key plus its comparators.

    Exported for tests (and mirrored by the web front-end's grammar port).
    """

    key: str
    comparators: tuple[_Comparator, ...]


@dataclass(frozen=True)
class _AttrGroupTerm:
    """One token of an AND-group in operator mode."""

    negated: bool
    text: str
    attr_term: AttrTerm | None


def _tokenize_spans(query: str) -> list[tuple[str, bool]]:
    """Split a query into ``(token, was_quoted)`` pairs.

    Mirrors :func:`tokenize` exactly (same regex, same dropping of empty
    tokens) while additionally reporting whether each token came from a
    quoted phrase. Quoted tokens are never attribute operators.

    Args:
        query: The raw filter string entered by the user.

    Returns:
        A list of ``(token, was_quoted)`` tuples; every token is a
        non-empty, non-whitespace :class:`str`.
    """
    spans: list[tuple[str, bool]] = []
    for m in re.finditer(r'"([^"]*)"|(\S+)', query):
        if m.group(1) is not None:
            token, quoted = m.group(1), True
        else:
            token, quoted = m.group(2), False
        if token and token.strip():
            spans.append((token, quoted))
    return spans


def _resolve_size(text: str) -> int | None:
    """Parse a magnitude operand (``10``, ``10mb``, ``1.5kb``) into bytes.

    Args:
        text: Candidate magnitude operand (no ``>``/``<`` prefix).

    Returns:
        Whole bytes (binary units, floored), or ``None`` when *text* is
        not a magnitude (a number is required).
    """
    m = _MAGNITUDE_RE.fullmatch(text)
    if m is None or m.group(1) is None:
        return None
    unit = m.group(2).lower() if m.group(2) else ""
    # Operands are non-negative, so int() truncation equals floor().
    return int(float(m.group(1)) * _SIZE_UNITS[unit])


def _resolve_duration(text: str) -> int | None:
    """Parse a duration operand (``7d``, ``12h``, ``0.5w``) into seconds.

    Args:
        text: Candidate duration operand (unit letter required).

    Returns:
        Whole seconds (floored), or ``None`` when *text* is not a duration.
    """
    m = _DURATION_RE.fullmatch(text)
    if m is None:
        return None
    unit = m.group(2).lower()
    # Operands are non-negative, so int() truncation equals floor().
    return int(float(m.group(1)) * _DURATION_UNITS[unit])


def _resolve_date(text: str) -> str | None:
    """Return *text* when it is a valid calendar date (``YYYY-MM-DD``).

    Args:
        text: Candidate date operand.

    Returns:
        The operand string, or ``None`` when the shape or the calendar
        values are invalid (e.g. ``2026-13-45``).
    """
    m = _DATE_RE.fullmatch(text)
    if m is None:
        return None
    try:
        datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return text


def _local_midnight(operand: float | str, now: float) -> float:
    """Resolve a temporal operand to a timestamp.

    Numbers pass through unchanged; ``"today"`` anchors to the local
    midnight of *now*; ``"YYYY-MM-DD"`` anchors to that day's local
    midnight.

    Args:
        operand: Numeric operand, ``"today"`` or a ``YYYY-MM-DD`` date.
        now: Reference time used to resolve ``"today"``.

    Returns:
        The timestamp the operand anchors to.
    """
    if not isinstance(operand, str):
        return float(operand)
    if operand == "today":
        local = datetime.fromtimestamp(now)
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.timestamp()
    year, month, day = operand.split("-")
    return datetime(int(year), int(month), int(day)).timestamp()


def _date_comparators(operand: str, op_char: str) -> list[_Comparator]:
    """Build comparators for a date/today operand with optional prefix.

    ``>date`` → on/after the day start; ``<date`` → strictly before the
    day start (the whole day is excluded); a bare date → the whole local
    day (start inclusive, end exclusive).
    """
    if op_char == ">":
        return [_Comparator("mtime", "since_day_start", operand)]
    if op_char == "<":
        # ``<date`` excludes the entire day: t < midnight(date).
        return [_Comparator("mtime", "lt", operand)]
    return [
        _Comparator("mtime", "since_day_start", operand),
        _Comparator("mtime", "before_day_end", operand),
    ]


def _parse_single(text: str) -> list[_Comparator] | None:
    """Parse one operand with optional ``>``/``<`` prefix.

    Magnitudes yield ``gt``/``lt``/``eq`` on ``size_bytes``; dates and
    ``today`` yield day-window comparators on ``mtime``; prefixed
    durations yield age comparators on ``mtime``. Bare durations are not
    valid operands.

    Args:
        text: Candidate operand (no ``-``/``+`` prefix, no ``..`` range).

    Returns:
        The comparator list, or ``None`` when *text* is not a valid
        operand.
    """
    op_char = ""
    value = text
    if value[:1] in (">", "<"):
        op_char = value[0]
        value = value[1:]
    if not value:
        return None
    size = _resolve_size(value)
    if size is not None:
        if op_char == ">":
            return [_Comparator(_SIZE_FIELD, "gt", size)]
        if op_char == "<":
            return [_Comparator(_SIZE_FIELD, "lt", size)]
        return [_Comparator(_SIZE_FIELD, "eq", size)]
    date = _resolve_date(value)
    if date is not None:
        return _date_comparators(date, op_char)
    if value.lower() == "today":
        return _date_comparators("today", op_char)
    duration = _resolve_duration(value)
    if duration is not None:
        if op_char == ">":
            return [_Comparator("mtime", "age_gt", duration)]
        if op_char == "<":
            return [_Comparator("mtime", "age_lt", duration)]
        return None  # bare duration is not a valid operand
    return None


def _parse_range_side(text: str, *, lower: bool) -> _Comparator | None:
    """Parse one side of an ``a..b`` range into its bound comparator.

    Sides are prefix-less: sizes map to ``ge``/``le``, dates and
    ``today`` to ``since_day_start``/``before_day_end``, durations to
    ``age_ge``/``age_le`` (age between both bounds).

    Args:
        text: One range side.
        lower: ``True`` for the left (lower) bound, ``False`` for the
            right (upper) bound.

    Returns:
        The bound comparator, or ``None`` when *text* is invalid.
    """
    size = _resolve_size(text)
    if size is not None:
        return _Comparator(_SIZE_FIELD, "ge" if lower else "le", size)
    date = _resolve_date(text)
    if date is not None:
        op = "since_day_start" if lower else "before_day_end"
        return _Comparator("mtime", op, date)
    if text.lower() == "today":
        op = "since_day_start" if lower else "before_day_end"
        return _Comparator("mtime", op, "today")
    duration = _resolve_duration(text)
    if duration is not None:
        return _Comparator("mtime", "age_ge" if lower else "age_le", duration)
    return None


def _parse_range(text: str) -> list[_Comparator] | None:
    """Parse an ``a..b`` range into an inclusive pair of comparators.

    Both sides must be prefix-less operands of the same kind (sizes, or
    dates/durations which may be mixed — each side resolves by its own
    kind). More than one ``..`` or an empty side is a parse failure.

    Args:
        text: Candidate range value.

    Returns:
        The two bound comparators, or ``None`` on parse failure.
    """
    sides = text.split("..")
    if len(sides) != 2 or not sides[0] or not sides[1]:
        return None
    lower = _parse_range_side(sides[0], lower=True)
    upper = _parse_range_side(sides[1], lower=False)
    if lower is None or upper is None:
        return None
    if (lower.field == _SIZE_FIELD) != (upper.field == _SIZE_FIELD):
        return None  # mixed size / temporal bounds are invalid
    return [lower, upper]


def _parse_attr_token(term: str) -> AttrTerm | None:
    """Parse a ``key:value`` token into an :class:`AttrTerm`.

    Any leading ``-``/``+`` prefix must already be stripped by the caller.
    Unknown keys, missing separators, malformed values, kind mismatches
    (e.g. ``modified:>10mb``) and bare durations are parse failures.

    Args:
        term: Candidate operator token without ``-``/``+`` prefix.

    Returns:
        The parsed term with its canonical key, or ``None`` when *term*
        does not parse as an attribute operator.
    """
    key, sep, value = term.partition(":")
    if not sep or not value:
        return None
    canonical = key.lower()
    field = _ATTR_FIELD.get(canonical)
    if field is None:
        return None
    comparators = _parse_range(value) if ".." in value else _parse_single(value)
    if comparators is None:
        return None
    resolved: list[_Comparator] = []
    for comparator in comparators:
        is_size = comparator.field == _SIZE_FIELD
        if is_size != (field == _SIZE_FIELD):
            return None  # operand kind does not match the attribute kind
        resolved.append(replace(comparator, field=field))
    return AttrTerm(canonical, tuple(resolved))


def _comparator_matches(comparator: _Comparator, attrs: FileAttrsProtocol, now: float) -> bool:
    """Evaluate one comparator against *attrs* at time *now*.

    Comparison ops resolve string operands (dates / ``today``) to local
    midnight timestamps. Age ops follow the GNU-find reading: the operand
    bounds the file's *age*, e.g. ``age_lt(x)`` ⇔ ``t > now - x`` (recent).

    Args:
        comparator: The comparator to evaluate.
        attrs: The file attribute snapshot.
        now: Reference time for age and ``today`` resolution.

    Returns:
        True if the attribute value satisfies the comparison.
    """
    value = float(getattr(attrs, comparator.field))
    op = comparator.op
    if op == "gt":
        return value > _local_midnight(comparator.operand, now)
    if op == "lt":
        return value < _local_midnight(comparator.operand, now)
    if op == "ge":
        return value >= _local_midnight(comparator.operand, now)
    if op == "le":
        return value <= _local_midnight(comparator.operand, now)
    if op == "eq":
        return value == _local_midnight(comparator.operand, now)
    if op == "since_day_start":
        return value >= _local_midnight(comparator.operand, now)
    if op == "before_day_end":
        return value < _local_midnight(comparator.operand, now) + _DAY_SECONDS
    if op == "age_lt":  # age < operand  ⇔  timestamp > now - operand
        return value > now - float(comparator.operand)
    if op == "age_gt":  # age > operand  ⇔  timestamp < now - operand
        return value < now - float(comparator.operand)
    if op == "age_le":  # age <= operand ⇔  timestamp >= now - operand
        return value >= now - float(comparator.operand)
    # op == "age_ge": age >= operand ⇔ timestamp <= now - operand
    return value <= now - float(comparator.operand)


@lru_cache(maxsize=256)
def _compile_attr_groups(query: str) -> list[list[_AttrGroupTerm]]:
    """Compile *query* into OR-groups of operator-mode tokens (memoized).

    Mirrors :func:`compile_query`'s tokenization and OR splitting; quoted
    tokens always carry ``attr_term=None`` (never operators).

    Args:
        query: The filter expression.

    Returns:
        OR-groups of :class:`_AttrGroupTerm` (read-only for callers).
    """
    groups: list[list[_AttrGroupTerm]] = []
    current: list[_AttrGroupTerm] = []
    for token, quoted in _tokenize_spans(query):
        if token.upper() == "OR":
            groups.append(current)
            current = []
            continue
        negated = False
        text = token
        if text.startswith("-"):
            negated = True
            text = text[1:]
        elif text.startswith("+"):
            text = text[1:]
        attr_term = None if quoted else _parse_attr_token(text)
        current.append(_AttrGroupTerm(negated=negated, text=text, attr_term=attr_term))
    groups.append(current)
    return groups


def _attr_group_matches(
    filename_lower: str,
    group: Sequence[_AttrGroupTerm],
    attrs: FileAttrsProtocol | None,
    now: float,
) -> bool:
    """Evaluate one AND-group in operator mode (mirrors ``_group_matches``).

    Attribute terms require *attrs* (they evaluate to ``False`` without
    data); every other token is a case-insensitive substring test.
    Negation flips the token's outcome, exactly like ``-term``.

    Args:
        filename_lower: The filename, already lowered.
        group: Tokens belonging to one OR-alternative.
        attrs: Attribute snapshot, or ``None`` when unavailable.
        now: Reference time for age and ``today`` resolution.

    Returns:
        True if the group (as a whole) matches.
    """
    for term in group:
        if not term.text:  # skip empties (bare "-", consecutive OR, …)
            continue
        if term.attr_term is not None:
            if attrs is None:
                outcome = False  # operator mode without data → term fails
            else:
                outcome = all(
                    _comparator_matches(comparator, attrs, now)
                    for comparator in term.attr_term.comparators
                )
        else:
            outcome = _term_matches(filename_lower, term.text)
        if term.negated:
            if outcome:
                return False
        elif not outcome:
            return False
    return True


def match_file(
    filename: str,
    query: str,
    attrs: FileAttrsProtocol | None,
    *,
    now: float | None = None,
) -> bool:
    """Check whether *filename* matches *query* with attribute operators.

    Operator mode: tokens shaped ``key:value`` with a known key
    (``size``, ``modified``, ``created``) and a parseable value are
    evaluated against *attrs*; all other tokens — quoted tokens and
    malformed operators included — are matched as literal substrings,
    exactly like :func:`match_filter`.

    Args:
        filename: The filename (or relative path) to test.
        query: The filter expression entered by the user.
        attrs: The file attribute snapshot, or ``None`` when unavailable.
            Attribute terms evaluate to ``False`` without data while
            substring terms still apply.
        now: Anchor for ``today`` and duration (age) comparisons;
            defaults to the current time at call.

    Returns:
        ``True`` if the filename satisfies the filter expression. An
        empty or whitespace-only query always returns ``True``.

    Raises:
        TypeError: If *filename* or *query* is not a :class:`str`.
    """
    if not isinstance(filename, str):
        raise TypeError(f"filename must be str, not {type(filename).__name__}")
    if not isinstance(query, str):
        raise TypeError(f"query must be str, not {type(query).__name__}")
    resolved_now = time.time() if now is None else now
    filename_lower = filename.lower()
    return any(
        _attr_group_matches(filename_lower, group, attrs, resolved_now)
        for group in _compile_attr_groups(query)
    )


@lru_cache(maxsize=256)
def query_needs_attributes(query: str) -> bool:
    """Report whether *query* contains at least one attribute operator.

    Callers use this to decide whether file attributes must be collected
    before matching. Quoted tokens, ``OR`` separators and malformed
    operators do not count.

    Args:
        query: The filter expression.

    Returns:
        ``True`` if any unquoted, non-``OR`` token parses as an attribute
        operator.
    """
    for token, quoted in _tokenize_spans(query):
        if quoted or token.upper() == "OR":
            continue
        bare = token[1:] if token[:1] in ("-", "+") else token
        if bare and _parse_attr_token(bare) is not None:
            return True
    return False
