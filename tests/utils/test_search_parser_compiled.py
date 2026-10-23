"""Tests for the compiled query path — Task 5.

``compile_query`` tokenizes and splits OR groups once and remembers the
result (lru_cache, 256 entries); ``match_filter`` delegates to it and
must stay behaviorally identical to the frozen pre-task reference.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

from profiles.utils.search_parser import compile_query, match_filter

_HERE = Path(__file__).resolve().parents[1]
_CH_DIR = _HERE / "characterization"
if str(_CH_DIR) not in sys.path:
    sys.path.insert(0, str(_CH_DIR))

import fixtures as ch  # noqa: E402


class TestCompileQueryParity:
    """The compiled pipeline matches the frozen reference everywhere."""

    @pytest.mark.parametrize(("name", "query", "expected"), ch.FULL_CORPUS)
    def test_corpus_parity(self, name: str, query: str, expected: bool) -> None:
        assert match_filter(name, query) == expected
        assert compile_query(query)(name) == expected

    def test_randomized_parity_2000_pairs(self) -> None:
        """2000 seeded random (name, query) pairs agree with the frozen reference."""
        rng = random.Random(20261021)
        token_pool = [
            "PROD",
            "ENG",
            "OR",
            "-Tester",
            "+V01",
            '"exact name"',
            "x",
            "mttl",
            "-V02",
            "Scan Me",
            "PDF",
            "_DUT-ID",
        ]
        names = [
            "PROD_Tester_V01.mttl",
            "DEV_Test_V02.mttl",
            "Scan Me.PDF",
            "PROD_Tester_V1.mttx.lnk",
            "file.backup.pdf",
            "README",
            ".bashrc",
            "report.",
            "a..b",
            "x.mttl",
            "exact name.mttl",
            "exact name.pdf",
            "DUT-ID_0866.pdf",
        ]
        mismatches: list[tuple[str, str, bool, bool]] = []
        for _ in range(2000):
            n_tokens = rng.randint(1, 6)
            query = " ".join(rng.choice(token_pool) for _ in range(n_tokens))
            name = rng.choice(names)
            got = match_filter(name, query)
            want = ch.reference_match_filter(name, query)
            if got != want:
                mismatches.append((name, query, got, want))
        assert mismatches == [], mismatches[:10]


class TestCompileQueryCaching:
    """compile_query is memoized (lru_cache, 256)."""

    def test_repeated_call_hits_cache(self) -> None:
        first = compile_query("a b")
        info_before = compile_query.cache_info()
        second = compile_query("a b")
        info_after = compile_query.cache_info()

        assert first is second
        assert info_after.hits == info_before.hits + 1

    def test_no_tokens_compiles_to_match_all(self) -> None:
        for query in ("", "   ", '""'):
            matcher = compile_query(query)
            assert matcher("anything.pdf") is True
            assert matcher("PROD") is True

    def test_casefold_term_mismatch_still_delegates(self) -> None:
        """Basic operator semantics preserved through the compiled closure."""
        matcher = compile_query("PROD -Tester")
        assert matcher("PROD_Test.mttl") is True
        assert matcher("PROD_Tester.mttl") is False
        assert matcher("st_pro_test.MTTL") is True
