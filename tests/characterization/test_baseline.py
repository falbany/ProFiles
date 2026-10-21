"""Characterization baseline: parity and golden snapshot tests.

These tests pin the *current* pipeline behavior before the improvement
tasks run:

* ``TestMatchCorpus`` — production ``match_filter`` must agree with the
  frozen ``reference_match_filter`` on every corpus row (Task 0 pins the
  baseline; Task 5 asserts the compiled path never diverges).
* ``TestGoldenScan`` — ``scan_and_process`` / ``scan_and_process_dynamic``
  outputs on the fixture tree must equal ``golden/scan_baseline.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("profiles")

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import fixtures  # noqa: E402  (local characterization fixture module)

from profiles.core.processing.scanner import (  # noqa: E402
    scan_and_process,
    scan_and_process_dynamic,
)
from profiles.utils.search_parser import match_filter  # noqa: E402

GOLDEN_PATH = _HERE / "golden" / "scan_baseline.json"
GOLDEN = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "query", "expected"), fixtures.FULL_CORPUS)
def test_match_filter_matches_frozen_reference(name: str, query: str, expected: bool) -> None:
    """Production match_filter equals both the frozen reference and the pinned value."""
    assert match_filter(name, query) is bool(fixtures.reference_match_filter(name, query))
    assert match_filter(name, query) == expected


def test_corpus_covers_required_operators() -> None:
    """Sanity: the corpus really covers OR, -, +, quotes, case, whitespace, unmatched quotes."""
    queries = [q for _n, q, _e in fixtures.FULL_CORPUS]
    # Task 1 owns the "" case: it must not appear in this corpus.
    assert not any(q == '""' for q in queries)
    assert any(" OR " in q for q in queries)
    assert any(q.startswith("-") or " -" in q for q in queries)
    assert any(q.startswith("+") or " +" in q for q in queries)
    assert any('"' in q for q in queries)
    assert any(q != q.lower() for q in queries)
    assert any(not q.strip() for q in queries)
    assert any(q.startswith('"') and not q.endswith('"') for q in queries)
    assert len(fixtures.FULL_CORPUS) >= 50


@pytest.fixture(scope="module")
def scan_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One shared fixture tree for all golden cases."""
    root = tmp_path_factory.mktemp("scan_root")
    fixtures.build_tree(root)
    return root


def _static_rows(root: Path, recursive: bool, ext: str, flt: str) -> list[list[object]]:
    results = scan_and_process(
        str(root),
        extension=ext,
        filter_text=flt,
        recursive=recursive,
    )
    return [[r.filename, r.version] for r in results]


def _dynamic_rows(root: Path, recursive: bool, ext: str, flt: str) -> list[list[object]]:
    results = scan_and_process_dynamic(
        str(root),
        extension=ext,
        filter_text=flt,
        recursive=recursive,
    )
    return [[r.rel_path, r.column_values] for r in results]


@pytest.mark.parametrize(
    ("recursive", "ext", "flt"),
    [pytest.param(r, e, f, id=fixtures.case_key(r, e, f)) for r, e, f in fixtures.SCAN_CASES],
)
def test_golden_static_scan(scan_tree: Path, recursive: bool, ext: str, flt: str) -> None:
    """scan_and_process output must equal the frozen golden baseline."""
    expected = GOLDEN["cases"][fixtures.case_key(recursive, ext, flt)]["static"]
    actual = _static_rows(scan_tree, recursive, ext, flt)
    assert actual == expected


@pytest.mark.parametrize(
    ("recursive", "ext", "flt"),
    [pytest.param(r, e, f, id=fixtures.case_key(r, e, f)) for r, e, f in fixtures.SCAN_CASES],
)
def test_golden_dynamic_scan(scan_tree: Path, recursive: bool, ext: str, flt: str) -> None:
    """scan_and_process_dynamic output must equal the frozen golden baseline."""
    expected = GOLDEN["cases"][fixtures.case_key(recursive, ext, flt)]["dynamic"]
    actual = _dynamic_rows(scan_tree, recursive, ext, flt)
    assert actual == expected


@pytest.mark.parametrize(
    ("ext", "column_names", "columns"),
    [
        pytest.param(e, c, cols, id=fixtures.dynamic_case_key(e, c, cols))
        for e, c, cols in fixtures.DYNAMIC_CASES
    ],
)
def test_golden_dynamic_only_cases(
    scan_tree: Path, ext: str, column_names: tuple[str, ...], columns: object
) -> None:
    """Dynamic-only parameter combinations must equal the frozen baseline."""
    results = scan_and_process_dynamic(
        str(scan_tree),
        extension=ext,
        column_names=column_names,
        columns=columns,
        recursive=True,
    )
    expected = GOLDEN["dynamic_case_keys"].get(
        fixtures.dynamic_case_key(ext, column_names, columns)
    )
    assert expected is not None, "dynamic case missing from golden file"
    actual = [[r.rel_path, r.column_values] for r in results]
    assert actual == expected


def test_golden_file_is_self_consistent(scan_tree: Path) -> None:
    """Every golden key must be reproducible case keying, and version field types hold."""
    assert set(GOLDEN["cases"]) == {fixtures.case_key(r, e, f) for r, e, f in fixtures.SCAN_CASES}
    assert len(fixtures.SCAN_CASES) == 40
    # spot check: static and dynamic rows have the same rel-paths per case
    for key, payload in GOLDEN["cases"].items():
        static_paths = [row[0] for row in payload["static"]]
        dynamic_paths = [row[0] for row in payload["dynamic"]]
        assert static_paths == dynamic_paths, f"case {key}: static/dynamic path drift"
