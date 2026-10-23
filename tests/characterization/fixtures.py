"""Characterization fixtures for the scanner / search-parser baseline.

``build_tree`` creates a deterministic fixture tree covering the file
name shapes the pipeline must survive.  ``reference_match_filter`` is a
verbatim copy of the *current* :func:`profiles.utils.search_parser.match_filter`
implementation (and its private helpers) frozen BEFORE any improvement
task runs: later tasks assert parity against it.  Remove it once Task 5
lands and parity is confirmed.

``SCAN_CASES`` enumerates the parameter combinations pinned by the
golden scan baseline (``golden/scan_baseline.json``).
"""

from __future__ import annotations

import re
from pathlib import Path

_FILE_CONTENT = "placeholder\n"


def build_tree(root: Path) -> None:
    """Create the deterministic fixture tree (≥120 files) under *root*.

    Includes ``Projects/Debug_out/`` (matches the ``Debug*`` exclude
    pattern), ``.git/``, ``node_modules/`` and the special names listed
    by the plan (``README``, ``.bashrc``, ``report.``, ``~$lock.docx``, …).
    """
    root.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []

    def put(rel: str) -> None:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_FILE_CONTENT, encoding="utf-8")
        files.append(target)

    # Special names (the shapes the plan cares about)
    for name in (
        "PROD_Tester_V1.mttx.lnk",
        "DEV_Test.mttl",
        "PROD_Tester_DUTID_V1.0.2-beta",
        "README",
        ".bashrc",
        "report.",
        "file.backup.pdf",
        "~$lock.docx",
        "Scan Me.PDF",
        "setup.py",
    ):
        put(name)

    # Excluded-only folders: scanned when no exclude list is in effect
    put("Projects/Debug_out/PROD_Debug_V02.mttl")
    put("Projects/Debug_out/debug_note.txt")
    put(".git/config")
    put(".git/hooks/pre-commit")
    put("node_modules/dep.js")
    put("node_modules/pkg/lib.js")

    # Nested structure (depth ≥ 2 below the root)
    put("Projects/PROD_Tester_V02.mttl")
    put("Projects/PROD_Tester_V03.mttl")
    put("Projects/release/DEV_Release_V01.mttl")
    put("Projects/release/PROD_Display_V01.lnk")
    put("docs/guide.pdf")
    put("docs/spec.v1.pdf")
    put("docs/internal/draft.pdf")
    put("attachments/scan.pdf")
    put("attachments/photo.png")
    put("attachments/deep/nested/PROD_Nested_V01.mttl")
    put("temp/a.tmp")
    put("temp/~$scratch.xlsx")
    put("temp/ST_TEMP_V09.mttl")

    # Generated filler — deterministic names
    for i in range(1, 21):
        put(f"PROD_Filler_{i:02d}_V01.mttl")
        put(f"Projects/DEV_Filler_{i:02d}_V01.mttl")
    for i in range(1, 31):
        put(f"attachments/case_{i:02d}.pdf")
    for i in range(1, 21):
        put(f"temp/tmp_{i:02d}.txt")
    for i in range(1, 11):
        put(f"docs/internal/old_{i:02d}.pdf")

    created = sum(1 for f in files if f.is_file())
    assert created >= 120, f"fixture tree has {created} files, expected ≥ 120"


# ---------------------------------------------------------------------------
# Frozen reference implementation of the current match_filter
# ---------------------------------------------------------------------------


def reference_tokenize(query: str) -> list[str]:
    """Verbatim copy of the pre-change ``tokenize``."""
    return [m.group(1) or m.group(2) for m in re.finditer(r'"([^"]*)"|(\S+)', query)]


def _ref_term_matches(text_lower: str, term: str) -> bool:
    """Verbatim copy of the pre-change ``_term_matches``."""
    return term.lower() in text_lower


def _ref_group_matches(text: str, group_tokens: list[str]) -> bool:
    """Verbatim copy of the pre-change ``_group_matches``."""
    text_lower = text.lower()
    for token in group_tokens:
        if not token:
            continue
        if token.startswith("-"):
            term = token[1:]
            if term and _ref_term_matches(text_lower, term):
                return False
        else:
            term = token[1:] if token.startswith("+") else token
            if term and not _ref_term_matches(text_lower, term):
                return False
    return True


def reference_match_filter(filename: str, query: str) -> bool:
    """Verbatim copy of the pre-change ``match_filter`` (helpers included)."""
    if not isinstance(filename, str):
        raise TypeError(f"filename must be str, not {type(filename).__name__}")
    if not isinstance(query, str):
        raise TypeError(f"query must be str, not {type(query).__name__}")

    stripped = query.strip()
    if not stripped:
        return True

    tokens = reference_tokenize(stripped)
    if not tokens:
        return True

    groups: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token.upper() == "OR":
            groups.append(current)
            current = []
        else:
            current.append(token)
    groups.append(current)

    return any(_ref_group_matches(filename, group) for group in groups)


# ---------------------------------------------------------------------------
# Match corpus (>50 triples with the expected value frozen next to them)
# ---------------------------------------------------------------------------

_NAME_MIXED_CASE = "Scan Me.PDF"
_NAME_LNK = "PROD_Tester_V1.mttx.lnk"
_NAME_BACKUP_PDF = "file.backup.pdf"

# (filename, query, expected) — expected = reference_match_filter(name, query)
MATCH_CORPUS: list[tuple[str, str, bool]] = [
    # plain AND terms
    ("PROD_Tester_V01.mttl", "PROD", True),
    ("DEV_Test.mttl", "PROD", False),
    ("PROD_Tester_V01.mttl", "PROD Tester", True),
    ("PROD_Test_V01.mttl", "PROD Tester", False),
    ("a_b-c_d.mttl", "a_b-c_d", True),
    ("a_b-c_d.mttl", "a_b c_d", True),
    # OR groups
    ("DEV_Test.mttl", "PROD OR DEV", True),
    ("Other.mttl", "PROD OR DEV", False),
    ("a.pdf", "x OR y OR z", False),
    ("b.pdf", "b OR z", True),
    ("DEV_Only.mttl", "PROD OR DEV OR -Only", True),
    ("DEV_Only.mttl", "PROD OR DEV", True),
    ("DEV_Only.mttl", "DEV OR -ENG", True),
    # consecutive OR → empty group is skipped
    ("a.pdf", "a OR OR b", True),
    ("a.pdf", "OR a", True),
    ("a.pdf", "a OR", True),
    # negation
    ("PROD_Tester.mttl", "PROD -Tester", False),
    ("PROD_Test.mttl", "PROD -Tester", True),
    ("-a.pdf", "-a OR b", False),
    ("b.pdf", "-a OR b", True),
    # explicit inclusion
    ("alpha.pdf", "+alpha", True),
    ("beta.pdf", "+alpha", False),
    ("alpha.pdf", "+alpha +pdf", True),
    ("alpha.gif", "+alpha +pdf", False),
    # quoted phrases
    ("PROD_Tester V01.mttl", '"Tester V01"', True),
    ("PROD_Tester_XV01.mttl", '"Tester V01"', False),
    ("file.mttl", '"exact name"', False),
    ('"exact name".mttl', '"exact name"', True),
    ('PROD "Tester V01" test.mttl', 'PROD "Tester V01"', True),
    # case differences
    ("SCAN.PDF", "scan", True),
    ("scan.pdf", "SCAN", True),
    (_NAME_MIXED_CASE, "scan me", True),
    (_NAME_MIXED_CASE, '"Scan Me"', True),
    ("UPPER.MTTL", "upper", True),
    # whitespace-only queries → match everything
    ("anything.pdf", "", True),
    ("anything.pdf", "   ", True),
    ("anything.pdf", "\t\t", True),
    # unmatched quote → the quote is part of a literal token
    ("foo bar.pdf", '"foo bar', reference_match_filter("foo bar.pdf", '"foo bar')),
    ('"foo bar', '"foo bar', reference_match_filter('"foo bar', '"foo bar')),
    ('"foo bar.pdf', '"foo bar', reference_match_filter('"foo bar.pdf', '"foo bar')),
    (
        'PROD "unclosed',
        'PROD "unclosed',
        reference_match_filter('PROD "unclosed', 'PROD "unclosed'),
    ),
    # extension / suffix shaped names
    (_NAME_LNK, "lnk", True),
    ("a.mtx.lnk", "lnk", True),
    (_NAME_BACKUP_PDF, "pdf", True),
    (_NAME_BACKUP_PDF, ".backup.pdf", True),
    (_NAME_BACKUP_PDF, "backup", True),
    (_NAME_MIXED_CASE, "me.pdf", True),
    ("report.pdf", "report.", True),
    (".bashrc", "bashrc", True),
    (".bashrc", ".bashrc", True),
    ("README", "readme", True),
    ("README", "ORG", False),
    ("a..b", "a..b", True),
    ("a..b", ".b", True),
    # combined operators
    ("PROD_Tester_V01.mttl", "PROD -Tester", False),
    ("PROD_Test_V01.mttl", "PROD -Tester V01", True),
    ("PROD_Test_V02.mttl", "PROD -Tester V01", False),
    ("a.pdf", "a OR b -c", True),
    ("b_c.pdf", "a OR b -c", False),
    ("b_c.pdf", "a OR b -x", True),
    ("b_c.d_e.pdf", '"d_e"', True),
    ("d_e.pdf", '"d_e"', True),
    ("dxe.pdf", '"d_e"', False),
    ("PROD_Tester_V1.mttx.lnk", "Tester lnk", True),
    ("PROD_Tester_V1.mttx.lnk", "mttl lnk", False),
]

FULL_CORPUS: list[tuple[str, str, bool]] = MATCH_CORPUS


# ---------------------------------------------------------------------------
# Golden scan cases
# ---------------------------------------------------------------------------

_EXTENSIONS = ("", "All", "pdf", "lnk", "mttx.lnk")
_FILTERS = ("", "PROD", "PROD OR DEV", "-Tester")

# (recursive, extension, filter_text) — 40 combinations
SCAN_CASES: list[tuple[bool, str, str]] = [
    (recursive, extension, filter_text)
    for recursive in (False, True)
    for extension in _EXTENSIONS
    for filter_text in _FILTERS
]

# Additional dynamic-only cases: (extension, column_names, columns)
DYNAMIC_CASES: list[tuple[str, tuple[str, ...], object]] = [
    ("", ("File",), None),
    ("mttl", ("File",), None),
    ("", ("File", "Version"), None),
    ("mttl", ("File", "Version"), None),
]


def case_key(recursive: bool, extension: str, filter_text: str) -> str:
    """Deterministic JSON key for one scan case."""
    return f"recursive={recursive}|ext={extension!r}|filter={filter_text!r}"


def dynamic_case_key(extension: str, column_names: tuple[str, ...], columns: object) -> str:
    """Deterministic JSON key for one dynamic-only case."""
    cols = "None" if columns is None else repr(dict(columns))
    return f"dynamic|ext={extension!r}|colnames={list(column_names)!r}|columns={cols}"
