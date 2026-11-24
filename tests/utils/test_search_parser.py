"""Tests for profiles.utils.search_parser."""

from __future__ import annotations

import pytest

from profiles.utils.search_parser import match_filter, split_or_groups, tokenize

# ── tokenize ──────────────────────────────────────────────────────────────


class TestTokenize:
    """Unit tests for the tokenize function."""

    def test_single_word(self) -> None:
        assert tokenize("PROD") == ["PROD"]

    def test_multiple_words(self) -> None:
        assert tokenize("PROD Tester V01") == ["PROD", "Tester", "V01"]

    def test_quoted_phrase(self) -> None:
        assert tokenize('"DUT-ID_0866"') == ["DUT-ID_0866"]

    def test_quoted_phrase_with_spaces(self) -> None:
        assert tokenize('"Hello World"') == ["Hello World"]

    def test_mixed_quoted_and_unquoted(self) -> None:
        assert tokenize('PROD "Tester V01"') == ["PROD", "Tester V01"]

    def test_not_operator(self) -> None:
        assert tokenize("-V01") == ["-V01"]

    def test_plus_operator(self) -> None:
        assert tokenize("+PROD") == ["+PROD"]

    def test_or_keyword(self) -> None:
        assert tokenize("PROD OR DEV") == ["PROD", "OR", "DEV"]

    def test_empty_string(self) -> None:
        assert tokenize("") == []

    def test_whitespace_only(self) -> None:
        assert tokenize("   ") == []

    def test_trailing_quote(self) -> None:
        # An unclosed quote — tokenizer keeps the " as-is
        tokens = tokenize('PROD "unclosed')
        assert tokens == ["PROD", '"unclosed']

    def test_multiple_spaces(self) -> None:
        assert tokenize("PROD    Tester") == ["PROD", "Tester"]

    def test_special_characters(self) -> None:
        assert tokenize("a_b-c_d") == ["a_b-c_d"]


# ── split_or_groups ───────────────────────────────────────────────────────


class TestSplitOrGroups:
    """Unit tests for the split_or_groups function."""

    def test_no_or(self) -> None:
        assert split_or_groups(["PROD", "Tester"]) == [["PROD", "Tester"]]

    def test_single_or(self) -> None:
        assert split_or_groups(["PROD", "OR", "DEV"]) == [
            ["PROD"],
            ["DEV"],
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
        assert match_filter("PROD_Tester.mttl", "") is True

    def test_whitespace_query_matches(self) -> None:
        assert match_filter("PROD_Tester.mttl", "   ") is True

    def test_none_query_matches(self) -> None:
        # An empty filter is the same as no filter
        assert match_filter("PROD_Tester.mttl", "") is True

    # ── Simple keyword (backward compatible) ──────────────────────────

    def test_single_keyword_match(self) -> None:
        assert match_filter("PROD_Tester.mttl", "PROD") is True

    def test_single_keyword_no_match(self) -> None:
        assert match_filter("DEV_Test.mttl", "PROD") is False

    def test_case_insensitive(self) -> None:
        assert match_filter("st_prod_Tester.mttl", "PROD") is True

    def test_case_insensitive_reverse(self) -> None:
        assert match_filter("PROD_Tester.mttl", "prod") is True

    def test_partial_match(self) -> None:
        assert match_filter("PROD_Tester.mttl", "Test") is True

    # ── AND (space-separated, implicit) ───────────────────────────────

    def test_and_both_match(self) -> None:
        assert match_filter("PROD_Tester_V01.mttl", "PROD Tester") is True

    def test_and_one_missing(self) -> None:
        assert match_filter("PROD_Tester.mttl", "PROD TOTO") is False

    def test_and_both_missing(self) -> None:
        assert match_filter("DEV_Test.mttl", "PROD Tester") is False

    def test_and_three_terms(self) -> None:
        assert match_filter("PROD_Tester_DUT-ID_V01.mttl", "PROD Tester V01") is True

    def test_and_with_substring(self) -> None:
        assert match_filter("PROD_Production_V03.mttx", "PRO V03") is True

    # ── OR ────────────────────────────────────────────────────────────

    def test_or_first_matches(self) -> None:
        assert match_filter("PROD_Tester.mttl", "PROD OR DEV") is True

    def test_or_second_matches(self) -> None:
        assert match_filter("DEV_Test.mttl", "PROD OR DEV") is True

    def test_or_both_match(self) -> None:
        assert match_filter("PROD_DEV_Tester.mttl", "PROD OR DEV") is True

    def test_or_neither_matches(self) -> None:
        assert match_filter("readme.txt", "PROD OR DEV") is False

    def test_or_three_alternatives(self) -> None:
        assert match_filter("readme.txt", "PROD OR DEV OR readme") is True

    def test_or_none_of_three(self) -> None:
        assert match_filter("readme.txt", "PROD OR DEV OR TOTO") is False

    def test_or_case_insensitive(self) -> None:
        assert match_filter("PROD.mttl", "prod or dev") is True

    # ── Mixed AND + OR ────────────────────────────────────────────────

    def test_and_or_combined_group1_matches(self) -> None:
        # Group 1: PROD + Tester  |  Group 2: DEV
        assert match_filter("PROD_Tester.mttl", "PROD Tester OR DEV") is True

    def test_and_or_combined_group2_matches(self) -> None:
        assert match_filter("DEV_Test.mttl", "PROD Tester OR DEV") is True

    def test_and_or_combined_no_match(self) -> None:
        assert match_filter("readme.txt", "PROD Tester OR DEV") is False

    def test_complex_and_or(self) -> None:
        # Group 1: PROD + DUT-ID  |  Group 2: DEV + V02
        assert match_filter("DEV_Test_V02.mttl", "PROD DUT-ID OR DEV V02") is True
        assert match_filter("PROD_DUT-ID.mttl", "PROD DUT-ID OR DEV V02") is True
        assert match_filter("readme.txt", "PROD DUT-ID OR DEV V02") is False

    # ── NOT (-prefix) ─────────────────────────────────────────────────

    def test_not_excludes(self) -> None:
        assert match_filter("PROD_Tester_V01.mttl", "PROD -V01") is False

    def test_not_allows_others(self) -> None:
        assert match_filter("PROD_Tester.mttl", "PROD -V01") is True

    def test_not_with_or(self) -> None:
        assert match_filter("DEV_Test.mttl", "PROD OR -DEV") is False
        assert match_filter("readme.txt", "PROD OR -DEV") is True

    def test_not_alone(self) -> None:
        assert match_filter("PROD.mttl", "-PROD") is False
        assert match_filter("readme.txt", "-PROD") is True

    def test_not_empty(self) -> None:
        # A bare "-" without a term should be ignored
        assert match_filter("PROD.mttl", "-") is True

    def test_not_case_insensitive(self) -> None:
        assert match_filter("PROD.mttl", "-prod") is False

    # ── Exact phrase (quoted) ─────────────────────────────────────────

    def test_exact_phrase_match(self) -> None:
        assert match_filter("PROD_Tester_V01.mttl", '"PROD_Tester"') is True

    def test_exact_phrase_no_match(self) -> None:
        assert match_filter("PROD_Tester.mttl", '"DEV_Test"') is False

    def test_exact_phrase_with_spaces(self) -> None:
        # Even though filenames don't have spaces, the parser should handle it
        assert match_filter("my file.mttl", '"my file"') is True
        assert match_filter("my_file.mttl", '"my file"') is False

    def test_exact_phrase_with_and(self) -> None:
        assert match_filter("PROD_Tester_V01.mttl", 'PROD "Tester_V01"') is True
        assert match_filter("PROD_Tester_V01.mttl", 'PROD "Bad_Phrase"') is False

    def test_exact_phrase_with_or(self) -> None:
        assert match_filter("PROD.mttl", '"PROD" OR "DEV"') is True
        assert match_filter("DEV.mttl", '"PROD" OR "DEV"') is True
        assert match_filter("readme.txt", '"PROD" OR "DEV"') is False

    # ── Real-world filename scenarios ─────────────────────────────────

    @pytest.fixture
    def sample_filenames(self) -> dict[str, str]:
        return {
            "PROD_Tester_DUTID_0866_V1.0.2-beta": "PROD",
            "DEV_Test_V02.mttl": "DEV",
            "PROD_Production_V03.mttx": "PROD",
            "readme.txt": "other",
            "config.ini": "other",
        }

    def test_scenario_prod_filter(self, sample_filenames: dict[str, str]) -> None:
        """Filter all PROD files."""
        matches = [f for f in sample_filenames if match_filter(f, "PROD")]
        assert "PROD_Tester_DUTID_0866_V1.0.2-beta" in matches
        assert "PROD_Production_V03.mttx" in matches
        assert "DEV_Test_V02.mttl" not in matches

    def test_scenario_prod_tester(self, sample_filenames: dict[str, str]) -> None:
        """Find PROD files related to Tester."""
        matches = [f for f in sample_filenames if match_filter(f, "PROD Tester")]
        assert "PROD_Tester_DUTID_0866_V1.0.2-beta" in matches
        assert "PROD_Production_V03.mttx" not in matches

    def test_scenario_prod_not_0866(self, sample_filenames: dict[str, str]) -> None:
        """PROD files but exclude 0866 version."""
        matches = [f for f in sample_filenames if match_filter(f, "PROD -0866")]
        assert "PROD_Production_V03.mttx" in matches
        assert "PROD_Tester_DUTID_0866_V1.0.2-beta" not in matches

    def test_scenario_prod_or_dev(self, sample_filenames: dict[str, str]) -> None:
        """All production or development files."""
        matches = [f for f in sample_filenames if match_filter(f, "PROD OR DEV")]
        assert len(matches) == 3  # 2 PROD + 1 DEV

    def test_scenario_exact_version(self, sample_filenames: dict[str, str]) -> None:
        """Find a specific exact version."""
        matches = [f for f in sample_filenames if match_filter(f, '"V1.0.2-beta"')]
        assert "PROD_Tester_DUTID_0866_V1.0.2-beta" in matches
        assert "DEV_Test_V02.mttl" not in matches

    def test_stress_many_terms(self) -> None:
        """All terms present should match."""
        fname = "PROD_Tester_DUTID_0866_V1.0.2-beta"
        assert match_filter(fname, "PROD Tester DUTID 0866 V1.0.2 beta") is True

    def test_stress_many_terms_one_missing(self) -> None:
        fname = "PROD_Tester_DUTID_0866_V1.0.2-beta"
        assert match_filter(fname, "PROD Tester DUTID NOPE") is False

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
        assert match_filter("PROD.mttl", "  PROD") is True

    def test_trailing_space(self) -> None:
        assert match_filter("PROD.mttl", "PROD  ") is True


# ── D3: empty and blank tokens are dropped (Task 1) ──────────────────────

from profiles.core.processing.scanner import is_simple_extension  # noqa: E402


class TestEmptyTokenDropping:
    """D3: tokens that are empty or whitespace-only are dropped; quote-only
    filters match everything instead of raising."""

    @pytest.mark.parametrize("query", ['""', '"  "', "   "])
    def test_empty_or_blank_tokens_are_dropped(self, query: str) -> None:
        assert tokenize(query) == []

    def test_empty_phrase_between_terms_is_dropped(self) -> None:
        assert tokenize('a "" b') == ["a", "b"]

    def test_empty_quoted_filter_matches_everything(self) -> None:
        assert match_filter("anything.pdf", '""') is True

    def test_empty_quoted_extension_is_simple(self) -> None:
        assert is_simple_extension('""') is True

    def test_unmatched_quote_is_literal_token(self) -> None:
        assert tokenize('"foo bar') == ['"foo', "bar"]


# ── Attribute operators (Task 2, #227) ────────────────────────────────────

from datetime import datetime  # noqa: E402

from profiles.core.processing.file_metadata import FileAttrs  # noqa: E402
from profiles.utils.search_parser import (  # noqa: E402
    AttrTerm,
    _Comparator,
    _parse_attr_token,
    match_file,
    query_needs_attributes,
)

NOW = 1_700_000_000.0
DAY = 86400


def _local_midnight_ts(year: int, month: int, day: int) -> float:
    """Local midnight timestamp of a calendar day (test-side helper)."""
    return datetime(year, month, day).timestamp()


def _midnight_of_now(now: float) -> float:
    """Local midnight of *now* (mirrors the parser's ``today`` anchor)."""
    return (
        datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )


class TestMatchFileSizeOperators:
    """size operators: strict comparisons, inclusive ranges, floored decimals."""

    def test_size_gt_strict_at_boundary(self) -> None:
        attrs = FileAttrs(10485760, NOW, NOW)
        assert match_file("f.log", "size:>10mb", attrs, now=NOW) is False

    def test_size_gt_above_boundary(self) -> None:
        attrs = FileAttrs(10485761, NOW, NOW)
        assert match_file("f.log", "size:>10mb", attrs, now=NOW) is True

    def test_size_gt_below_threshold(self) -> None:
        attrs = FileAttrs(900 * 1024, NOW, NOW)
        assert match_file("f.log", "size:>10mb", attrs, now=NOW) is False

    def test_size_lt_strict_at_boundary(self) -> None:
        attrs = FileAttrs(500 * 1024, NOW, NOW)
        assert match_file("f.log", "size:<500kb", attrs, now=NOW) is False

    def test_size_lt_below_boundary(self) -> None:
        attrs = FileAttrs(500 * 1024 - 1, NOW, NOW)
        assert match_file("f.log", "size:<500kb", attrs, now=NOW) is True

    def test_size_range_inclusive_lower_bound(self) -> None:
        attrs = FileAttrs(1024, NOW, NOW)
        assert match_file("f.log", "size:1kb..1mb", attrs, now=NOW) is True

    def test_size_range_inclusive_upper_bound(self) -> None:
        attrs = FileAttrs(1048576, NOW, NOW)
        assert match_file("f.log", "size:1kb..1mb", attrs, now=NOW) is True

    def test_size_range_below_lower_bound(self) -> None:
        attrs = FileAttrs(1023, NOW, NOW)
        assert match_file("f.log", "size:1kb..1mb", attrs, now=NOW) is False

    def test_size_range_above_upper_bound(self) -> None:
        attrs = FileAttrs(1048577, NOW, NOW)
        assert match_file("f.log", "size:1kb..1mb", attrs, now=NOW) is False

    def test_size_bare_equality_match(self) -> None:
        attrs = FileAttrs(1048576, NOW, NOW)
        assert match_file("f.log", "size:1048576", attrs, now=NOW) is True

    def test_size_bare_equality_off_by_one(self) -> None:
        attrs = FileAttrs(1048577, NOW, NOW)
        assert match_file("f.log", "size:1048576", attrs, now=NOW) is False

    def test_size_decimal_exact(self) -> None:
        attrs = FileAttrs(1572864, NOW, NOW)
        assert match_file("f.log", "size:1.5mb", attrs, now=NOW) is True

    def test_size_decimal_floored(self) -> None:
        attrs = FileAttrs(1572863, NOW, NOW)
        assert match_file("f.log", "size:1.5mb", attrs, now=NOW) is False

    def test_size_key_and_unit_case_insensitive(self) -> None:
        big = FileAttrs(10485761, NOW, NOW)
        assert match_file("f.log", "SIZE:>10MB", big, now=NOW) is True
        assert match_file("f.log", "size:>10Mb", big, now=NOW) is True

    def test_size_key_and_unit_case_insensitive_no_match(self) -> None:
        small = FileAttrs(900 * 1024, NOW, NOW)
        assert match_file("f.log", "SIZE:>10MB", small, now=NOW) is False


class TestMatchFileSubstringFallback:
    """Malformed operators are not errors: they degrade to substring terms."""

    def test_unparseable_value_without_attrs_is_substring(self) -> None:
        assert match_file("report_size:abc.log", "size:abc", None, now=NOW) is True

    def test_unparseable_value_with_attrs_is_substring_miss(self) -> None:
        attrs = FileAttrs(10, NOW, NOW)
        assert match_file("unrelated.log", "size:abc", attrs, now=NOW) is False

    def test_unparseable_value_with_attrs_is_substring_hit(self) -> None:
        attrs = FileAttrs(10, NOW, NOW)
        assert match_file("size:abc.log", "size:abc", attrs, now=NOW) is True


class TestMatchFileModifiedDurations:
    """Durations compare the file's AGE (``modified:<7d`` means recent)."""

    def test_modified_lt_7d_recent_file(self) -> None:
        attrs = FileAttrs(1, NOW - 3600, NOW)
        assert match_file("f.log", "modified:<7d", attrs, now=NOW) is True

    def test_modified_lt_7d_old_file(self) -> None:
        attrs = FileAttrs(1, NOW - 8 * DAY, NOW)
        assert match_file("f.log", "modified:<7d", attrs, now=NOW) is False

    def test_modified_gt_7d_old_file(self) -> None:
        attrs = FileAttrs(1, NOW - 8 * DAY, NOW)
        assert match_file("f.log", "modified:>7d", attrs, now=NOW) is True

    def test_modified_gt_7d_recent_file(self) -> None:
        attrs = FileAttrs(1, NOW - 3600, NOW)
        assert match_file("f.log", "modified:>7d", attrs, now=NOW) is False

    def test_modified_range_middle_of_window(self) -> None:
        attrs = FileAttrs(1, NOW - 3 * DAY, NOW)
        assert match_file("f.log", "modified:1d..7d", attrs, now=NOW) is True

    def test_modified_range_too_recent(self) -> None:
        attrs = FileAttrs(1, NOW - 3600, NOW)
        assert match_file("f.log", "modified:1d..7d", attrs, now=NOW) is False

    def test_modified_range_too_old(self) -> None:
        attrs = FileAttrs(1, NOW - 8 * DAY, NOW)
        assert match_file("f.log", "modified:1d..7d", attrs, now=NOW) is False


class TestMatchFileDates:
    """Date operators anchor to local midnights of the calendar day."""

    def test_modified_gt_date_same_day(self) -> None:
        mtime = _local_midnight_ts(2026, 11, 1) + 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:>2026-11-01", attrs, now=NOW) is True

    def test_modified_gt_date_prior_day(self) -> None:
        mtime = _local_midnight_ts(2026, 10, 31) + 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:>2026-11-01", attrs, now=NOW) is False

    def test_modified_lt_date_prior_day(self) -> None:
        mtime = _local_midnight_ts(2026, 10, 31) + 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:<2026-11-01", attrs, now=NOW) is True

    def test_modified_lt_date_excludes_same_day(self) -> None:
        mtime = _local_midnight_ts(2026, 11, 1) + 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:<2026-11-01", attrs, now=NOW) is False

    def test_bare_date_matches_whole_local_day(self) -> None:
        mtime = _local_midnight_ts(2026, 11, 1) + 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:2026-11-01", attrs, now=NOW) is True

    def test_bare_date_excludes_next_day(self) -> None:
        mtime = _local_midnight_ts(2026, 11, 1) + 86401
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:2026-11-01", attrs, now=NOW) is False

    def test_created_date_evaluates_birthtime_not_mtime(self) -> None:
        birthtime = _local_midnight_ts(2026, 11, 1) + 3600
        mtime = _local_midnight_ts(2020, 1, 1)  # far older — must not matter
        attrs = FileAttrs(1, mtime, birthtime)
        assert match_file("f.log", "created:>2026-11-01", attrs, now=NOW) is True

    def test_created_date_prior_day(self) -> None:
        birthtime = _local_midnight_ts(2026, 10, 31) + 3600
        mtime = _local_midnight_ts(2020, 1, 1)
        attrs = FileAttrs(1, mtime, birthtime)
        assert match_file("f.log", "created:>2026-11-01", attrs, now=NOW) is False


class TestMatchFileToday:
    """``today`` resolves against the injected *now* anchor."""

    def test_modified_today_after_local_midnight(self) -> None:
        mtime = _midnight_of_now(NOW) + 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:today", attrs, now=NOW) is True

    def test_modified_today_before_local_midnight(self) -> None:
        mtime = _midnight_of_now(NOW) - 3600
        attrs = FileAttrs(1, mtime, mtime)
        assert match_file("f.log", "modified:today", attrs, now=NOW) is False


class TestMatchFileNegationAndMixing:
    """Prefixes, OR groups, and mixing substring terms with operators."""

    def test_negated_size_operator_on_small_file(self) -> None:
        attrs = FileAttrs(500, NOW, NOW)
        assert match_file("f.log", "-size:>10mb", attrs, now=NOW) is True

    def test_negated_size_operator_on_big_file(self) -> None:
        attrs = FileAttrs(10485761, NOW, NOW)
        assert match_file("f.log", "-size:>10mb", attrs, now=NOW) is False

    def test_plus_prefix_applies_operator_normally(self) -> None:
        attrs = FileAttrs(10485761, NOW, NOW)
        assert match_file("f.log", "+size:>10mb", attrs, now=NOW) is True

    def test_or_group_with_size_operator(self) -> None:
        attrs = FileAttrs(500, NOW, NOW)
        assert match_file("small_run.log", "big OR size:<1kb", attrs, now=NOW) is True

    def test_mixed_substring_and_negated_operator_old_file(self) -> None:
        attrs = FileAttrs(1, NOW - 8 * DAY, NOW)
        assert match_file("report_final.log", "report -modified:<1d", attrs, now=NOW) is True

    def test_mixed_substring_and_negated_operator_recent_file(self) -> None:
        attrs = FileAttrs(1, NOW - 3600, NOW)
        assert match_file("report_final.log", "report -modified:<1d", attrs, now=NOW) is False


class TestMatchFileWithoutAttrs:
    """attrs=None: attribute terms fail while substring terms still evaluate."""

    def test_operator_term_is_false_without_attrs(self) -> None:
        assert match_file("anything.log", "size:>10mb", None, now=NOW) is False

    def test_substring_alternative_still_matches_without_attrs(self) -> None:
        assert match_file("report_2026.log", "report OR size:>10mb", None, now=NOW) is True

    def test_and_group_fails_on_operator_term_without_attrs(self) -> None:
        assert match_file("report_2026.log", "report size:>10mb", None, now=NOW) is False

    def test_pure_substring_query_without_attrs(self) -> None:
        assert match_file("report_2026.log", "report", None, now=NOW) is True


class TestMatchFileBasics:
    """Operator-mode edge cases shared with match_filter semantics."""

    def test_empty_query_matches_everything(self) -> None:
        attrs = FileAttrs(1, NOW, NOW)
        assert match_file("any.log", "", attrs, now=NOW) is True

    def test_substring_semantics_unchanged_with_attrs(self) -> None:
        attrs = FileAttrs(1, NOW, NOW)
        assert match_file("PROD_Tester_V01.mttl", "PROD -V01", attrs, now=NOW) is False
        assert match_file("PROD_Tester.mttl", "PROD -V01", attrs, now=NOW) is True
        assert match_file("PROD_Tester.mttl", "PROD", attrs, now=NOW) is True

    def test_non_string_filename_raises(self) -> None:
        with pytest.raises(TypeError):
            match_file(123, "query", None)  # type: ignore[arg-type]

    def test_non_string_query_raises(self) -> None:
        with pytest.raises(TypeError):
            match_file("file.txt", 456, None)  # type: ignore[arg-type]


class TestQueryNeedsAttributes:
    """Precheck telling callers whether attribute data must be collected."""

    @pytest.mark.parametrize("query", ["", "datalog", "size:abc", '"size:>10mb"', "modified:7d"])
    def test_queries_without_operators(self, query: str) -> None:
        assert query_needs_attributes(query) is False

    @pytest.mark.parametrize(
        "query",
        ["size:>10mb", "datalog modified:<7d", "report -size:>1gb", "created:2026-11-01"],
    )
    def test_queries_with_operators(self, query: str) -> None:
        assert query_needs_attributes(query) is True


class TestMatchFilterRegression:
    """match_filter never enters operator mode (substring behavior preserved)."""

    def test_operator_shaped_token_stays_substring(self) -> None:
        assert match_filter("size:>10mb.log", "size:>10mb") is True

    def test_operator_shaped_token_misses_other_names(self) -> None:
        assert match_filter("unrelated.log", "size:>10mb") is False


class TestParseAttrToken:
    """Structural contract of the exported-for-tests parse hook."""

    def test_size_gt(self) -> None:
        term = _parse_attr_token("size:>10mb")
        assert term == AttrTerm("size", (_Comparator("size_bytes", "gt", 10485760),))

    def test_created_maps_to_birthtime(self) -> None:
        term = _parse_attr_token("created:>2026-11-01")
        assert term == AttrTerm(
            "created", (_Comparator("birthtime", "since_day_start", "2026-11-01"),)
        )

    def test_bare_date_is_whole_day_window(self) -> None:
        term = _parse_attr_token("modified:2026-11-01")
        assert term == AttrTerm(
            "modified",
            (
                _Comparator("mtime", "since_day_start", "2026-11-01"),
                _Comparator("mtime", "before_day_end", "2026-11-01"),
            ),
        )

    def test_lt_date_is_strict_before_midnight(self) -> None:
        term = _parse_attr_token("modified:<2026-11-01")
        assert term == AttrTerm("modified", (_Comparator("mtime", "lt", "2026-11-01"),))

    def test_duration_range_uses_age_comparators(self) -> None:
        term = _parse_attr_token("modified:1d..7d")
        assert term == AttrTerm(
            "modified",
            (
                _Comparator("mtime", "age_ge", 86400),
                _Comparator("mtime", "age_le", 604800),
            ),
        )

    def test_size_range_is_inclusive_bounds(self) -> None:
        term = _parse_attr_token("size:1kb..1mb")
        assert term == AttrTerm(
            "size",
            (
                _Comparator("size_bytes", "ge", 1024),
                _Comparator("size_bytes", "le", 1048576),
            ),
        )

    def test_kind_mismatch_is_rejected(self) -> None:
        assert _parse_attr_token("modified:>10mb") is None
        assert _parse_attr_token("size:>2026-11-01") is None

    def test_bare_duration_is_rejected(self) -> None:
        assert _parse_attr_token("modified:7d") is None

    def test_invalid_calendar_date_is_rejected(self) -> None:
        assert _parse_attr_token("modified:2026-13-45") is None

    def test_prefixes_are_caller_responsibility(self) -> None:
        assert _parse_attr_token("-size:>10mb") is None
        assert _parse_attr_token("+size:>10mb") is None

    def test_unknown_key_is_rejected(self) -> None:
        assert _parse_attr_token("owner:>10mb") is None

    def test_missing_separator_is_rejected(self) -> None:
        assert _parse_attr_token("size") is None

    def test_multiple_range_separators_are_rejected(self) -> None:
        assert _parse_attr_token("size:1..2..3") is None
