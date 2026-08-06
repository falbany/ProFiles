"""Tests for pattern matcher specificity ranking."""

from profiles.core.environment.matcher import select_most_specific_pattern


def test_exact_match_wins():
    patterns = ["*.mttl", "toto.mttl", ".mttl"]
    filename = "toto.mttl"
    result = select_most_specific_pattern(patterns, filename)
    assert result == "toto.mttl"


def test_star_pattern():
    patterns = [".pdf", "*.pdf", "report_*.pdf"]
    filename = "report_2026.pdf"
    result = select_most_specific_pattern(patterns, filename)
    assert result == "report_*.pdf"


def test_no_match():
    patterns = [".mttl", "*.pdf"]
    filename = "test.txt"
    result = select_most_specific_pattern(patterns, filename)
    assert result is None


def test_question_mark_pattern():
    patterns = [".pdf", "test?.txt"]
    filename = "test1.txt"
    result = select_most_specific_pattern(patterns, filename)
    assert result == "test?.txt"
