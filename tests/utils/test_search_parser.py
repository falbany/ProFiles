"""Tests for profiles.utils.search_parser."""

from __future__ import annotations

import pytest

from profiles.utils.search_parser import match_filter, split_or_groups, tokenize

# ── tokenize ──────────────────────────────────────────────────────────────


class TestTokenize:
    """Unit tests for the tokenize function."""

    def test_single_word(self) -> None:
        assert tokenize("ST_PRO") == ["ST_PRO"]

    def test_multiple_words(self) -> None:
        assert tokenize("ST_PRO Mutest V01") == ["ST_PRO", "Mutest", "V01"]

    def test_quoted_phrase(self) -> None:
        assert tokenize('"IM611B_0866"') == ["IM611B_0866"]

    def test_quoted_phrase_with_spaces(self) -> None:
        assert tokenize('"Hello World"') == ["Hello World"]

    def test_mixed_quoted_and_unquoted(self) -> None:
        assert tokenize('ST_PRO "Mutest V01"') == ["ST_PRO", "Mutest V01"]

    def test_not_operator(self) -> None:
        assert tokenize("-V01") == ["-V01"]

    def test_plus_operator(self) -> None:
        assert tokenize("+ST_PRO") == ["+ST_PRO"]

    def test_or_keyword(self) -> None:
        assert tokenize("ST_PRO OR ST_ENG") == ["ST_PRO", "OR", "ST_ENG"]

    def test_empty_string(self) -> None:
        assert tokenize("") == []

    def test_whitespace_only(self) -> None:
        assert tokenize("   ") == []

    def test_trailing_quote(self) -> None:
        # An unclosed quote — tokenizer keeps the " as-is
        tokens = tokenize('ST_PRO "unclosed')
        assert tokens == ["ST_PRO", '"unclosed']

    def test_multiple_spaces(self) -> None:
        assert tokenize("ST_PRO    Mutest") == ["ST_PRO", "Mutest"]

    def test_special_characters(self) -> None:
        assert tokenize("a_b-c_d") == ["a_b-c_d"]


# ── split_or_groups ───────────────────────────────────────────────────────


class TestSplitOrGroups:
    """Unit tests for the split_or_groups function."""

    def test_no_or(self) -> None:
        assert split_or_groups(["ST_PRO", "Mutest"]) == [["ST_PRO", "Mutest"]]

    def test_single_or(self) -> None:
        assert split_or_groups(["ST_PRO", "OR", "ST_ENG"]) == [
            ["ST_PRO"],
            ["ST_ENG"],
        ]

    def test_multiple_or(self) -> None:
        assert split_or_groups(["A", "OR", "B", "OR", "C"]) == [
            ["A"],
            ["B"],
            ["C"],
        ]

    def test_mixed_and_or(self) -> None:
        assert split_or_groups(["A", "B", "OR", "C", "D"]) == [
            ["A", "B"],
            ["C", "D"],
        ]

    def test_or_lowercase(self) -> None:
        assert split_or_groups(["a", "or", "b"]) == [["a"], ["b"]]

    def test_trailing_or(self) -> None:
        assert split_or_groups(["A", "OR"]) == [["A"], []]

    def test_leading_or(self) -> None:
        assert split_or_groups(["OR", "A"]) == [[], ["A"]]

    def test_empty_tokens(self) -> None:
        assert split_or_groups([]) == [[]]


# ── match_filter ──────────────────────────────────────────────────────────


class TestMatchFilter:
    """Functional tests for match_filter — the main public API."""

    # ── Empty / edge cases ────────────────────────────────────────────

    def test_empty_query_matches(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "") is True

    def test_whitespace_query_matches(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "   ") is True

    def test_none_query_matches(self) -> None:
        # An empty filter is the same as no filter
        assert match_filter("ST_PRO_Mutest.mttl", "") is True

    # ── Simple keyword (backward compatible) ──────────────────────────

    def test_single_keyword_match(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "ST_PRO") is True

    def test_single_keyword_no_match(self) -> None:
        assert match_filter("ST_ENG_Test.mttl", "ST_PRO") is False

    def test_case_insensitive(self) -> None:
        assert match_filter("st_pro_mutest.mttl", "ST_PRO") is True

    def test_case_insensitive_reverse(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "st_pro") is True

    def test_partial_match(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "Mute") is True

    # ── AND (space-separated, implicit) ───────────────────────────────

    def test_and_both_match(self) -> None:
        assert match_filter("ST_PRO_Mutest_V01.mttl", "ST_PRO Mutest") is True

    def test_and_one_missing(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "ST_PRO TOTO") is False

    def test_and_both_missing(self) -> None:
        assert match_filter("ST_ENG_Test.mttl", "ST_PRO Mutest") is False

    def test_and_three_terms(self) -> None:
        assert match_filter("ST_PRO_Mutest_IM611B_V01.mttl", "ST_PRO Mutest V01") is True

    def test_and_with_substring(self) -> None:
        assert match_filter("ST_PRO_Production_V03.mttx", "PRO V03") is True

    # ── OR ────────────────────────────────────────────────────────────

    def test_or_first_matches(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "ST_PRO OR ST_ENG") is True

    def test_or_second_matches(self) -> None:
        assert match_filter("ST_ENG_Test.mttl", "ST_PRO OR ST_ENG") is True

    def test_or_both_match(self) -> None:
        assert match_filter("ST_PRO_ST_ENG_Mutest.mttl", "ST_PRO OR ST_ENG") is True

    def test_or_neither_matches(self) -> None:
        assert match_filter("readme.txt", "ST_PRO OR ST_ENG") is False

    def test_or_three_alternatives(self) -> None:
        assert match_filter("readme.txt", "ST_PRO OR ST_ENG OR readme") is True

    def test_or_none_of_three(self) -> None:
        assert match_filter("readme.txt", "ST_PRO OR ST_ENG OR TOTO") is False

    def test_or_case_insensitive(self) -> None:
        assert match_filter("ST_PRO.mttl", "st_pro or st_eng") is True

    # ── Mixed AND + OR ────────────────────────────────────────────────

    def test_and_or_combined_group1_matches(self) -> None:
        # Group 1: ST_PRO + Mutest  |  Group 2: ST_ENG
        assert match_filter("ST_PRO_Mutest.mttl", "ST_PRO Mutest OR ST_ENG") is True

    def test_and_or_combined_group2_matches(self) -> None:
        assert match_filter("ST_ENG_Test.mttl", "ST_PRO Mutest OR ST_ENG") is True

    def test_and_or_combined_no_match(self) -> None:
        assert match_filter("readme.txt", "ST_PRO Mutest OR ST_ENG") is False

    def test_complex_and_or(self) -> None:
        # Group 1: ST_PRO + IM611B  |  Group 2: ST_ENG + V02
        assert match_filter("ST_ENG_Test_V02.mttl", "ST_PRO IM611B OR ST_ENG V02") is True
        assert match_filter("ST_PRO_IM611B.mttl", "ST_PRO IM611B OR ST_ENG V02") is True
        assert match_filter("readme.txt", "ST_PRO IM611B OR ST_ENG V02") is False

    # ── NOT (-prefix) ─────────────────────────────────────────────────

    def test_not_excludes(self) -> None:
        assert match_filter("ST_PRO_Mutest_V01.mttl", "ST_PRO -V01") is False

    def test_not_allows_others(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", "ST_PRO -V01") is True

    def test_not_with_or(self) -> None:
        assert match_filter("ST_ENG_Test.mttl", "ST_PRO OR -ST_ENG") is False
        assert match_filter("readme.txt", "ST_PRO OR -ST_ENG") is True

    def test_not_alone(self) -> None:
        assert match_filter("ST_PRO.mttl", "-ST_PRO") is False
        assert match_filter("readme.txt", "-ST_PRO") is True

    def test_not_empty(self) -> None:
        # A bare "-" without a term should be ignored
        assert match_filter("ST_PRO.mttl", "-") is True

    def test_not_case_insensitive(self) -> None:
        assert match_filter("ST_PRO.mttl", "-st_pro") is False

    # ── Exact phrase (quoted) ─────────────────────────────────────────

    def test_exact_phrase_match(self) -> None:
        assert match_filter("ST_PRO_Mutest_V01.mttl", '"ST_PRO_Mutest"') is True

    def test_exact_phrase_no_match(self) -> None:
        assert match_filter("ST_PRO_Mutest.mttl", '"ST_ENG_Test"') is False

    def test_exact_phrase_with_spaces(self) -> None:
        # Even though filenames don't have spaces, the parser should handle it
        assert match_filter("my file.mttl", '"my file"') is True
        assert match_filter("my_file.mttl", '"my file"') is False

    def test_exact_phrase_with_and(self) -> None:
        assert match_filter("ST_PRO_Mutest_V01.mttl", 'ST_PRO "Mutest_V01"') is True
        assert match_filter("ST_PRO_Mutest_V01.mttl", 'ST_PRO "Bad_Phrase"') is False

    def test_exact_phrase_with_or(self) -> None:
        assert match_filter("ST_PRO.mttl", '"ST_PRO" OR "ST_ENG"') is True
        assert match_filter("ST_ENG.mttl", '"ST_PRO" OR "ST_ENG"') is True
        assert match_filter("readme.txt", '"ST_PRO" OR "ST_ENG"') is False

    # ── Real-world filename scenarios ─────────────────────────────────

    @pytest.fixture
    def sample_filenames(self) -> dict[str, str]:
        return {
            "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl": "PROD",
            "ST_ENG_Test_V02.mttl": "DEV",
            "ST_PRO_Production_V03.mttx": "PROD",
            "readme.txt": "other",
            "config.ini": "other",
        }

    def test_scenario_stpro_filter(self, sample_filenames: dict[str, str]) -> None:
        """Filter all PROD files."""
        matches = [f for f in sample_filenames if match_filter(f, "ST_PRO")]
        assert "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl" in matches
        assert "ST_PRO_Production_V03.mttx" in matches
        assert "ST_ENG_Test_V02.mttl" not in matches

    def test_scenario_stpro_mutest(self, sample_filenames: dict[str, str]) -> None:
        """Find ST_PRO files related to Mutest."""
        matches = [f for f in sample_filenames if match_filter(f, "ST_PRO Mutest")]
        assert "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl" in matches
        assert "ST_PRO_Production_V03.mttx" not in matches

    def test_scenario_stpro_not_0866(self, sample_filenames: dict[str, str]) -> None:
        """ST_PRO files but exclude 0866 version."""
        matches = [f for f in sample_filenames if match_filter(f, "ST_PRO -0866")]
        assert "ST_PRO_Production_V03.mttx" in matches
        assert "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl" not in matches

    def test_scenario_prod_or_dev(self, sample_filenames: dict[str, str]) -> None:
        """All production or development files."""
        matches = [f for f in sample_filenames if match_filter(f, "ST_PRO OR ST_ENG")]
        assert len(matches) == 3  # 2 PROD + 1 DEV

    def test_scenario_exact_version(self, sample_filenames: dict[str, str]) -> None:
        """Find a specific exact version."""
        matches = [f for f in sample_filenames if match_filter(f, '"V01-Rel6.2.1"')]
        assert "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl" in matches
        assert "ST_ENG_Test_V02.mttl" not in matches

    def test_stress_many_terms(self) -> None:
        """All terms present should match."""
        fname = "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl"
        assert match_filter(fname, "ST_PRO Mutest IM611B 0866 V01 Rel6.2.1") is True

    def test_stress_many_terms_one_missing(self) -> None:
        fname = "ST_PRO_Mutest_IM611B_0866_V01-Rel6.2.1.mttl"
        assert match_filter(fname, "ST_PRO Mutest IM611B NOPE") is False

    # ── Type validation ───────────────────────────────────────────────

    def test_non_string_filename_raises(self) -> None:
        with pytest.raises(TypeError):
            match_filter(123, "query")  # type: ignore[arg-type]

    def test_non_string_query_raises(self) -> None:
        with pytest.raises(TypeError):
            match_filter("file.txt", 456)  # type: ignore[arg-type]

    # ── Regression: single-char tokens ────────────────────────────────

    def test_single_char_term(self) -> None:
        assert match_filter("A_file.mttl", "A") is True
        assert match_filter("B_file.mttl", "A") is False

    def test_not_with_single_char(self) -> None:
        assert match_filter("AB.mttl", "A -B") is False
        assert match_filter("A.mttl", "A -B") is True

    # ── Regression: OR with AND groups of varying sizes ───────────────

    def test_or_with_single_and_double_groups(self) -> None:
        assert match_filter("A_B.mttl", "A OR B C") is True  # group2: B + C → both needed
        assert match_filter("A_C.mttl", "A OR B C") is True  # group1: A → matches
        assert match_filter("B.mttl", "A OR B C") is False  # need C too

    # ── Regression: leading/trailing spaces ───────────────────────────

    def test_leading_space(self) -> None:
        assert match_filter("ST_PRO.mttl", "  ST_PRO") is True

    def test_trailing_space(self) -> None:
        assert match_filter("ST_PRO.mttl", "ST_PRO  ") is True
