"""Tests for the refactored ColumnRule match/transform engine."""

from profiles.core.processing.column_extractor import BUILTIN_PATTERNS, ColumnRule


def test_builtin_version_macro():
    """Built-in 'version' macro extracts a version number."""
    rule = ColumnRule(name="Version", match="version", priority=20, default="")
    assert rule.extract("MyApp_V1.2.3.exe") == "1.2.3"


def test_builtin_keyword_case_insensitive():
    """Built-in keyword lookup is case-insensitive."""
    rule = ColumnRule(name="Version", match="VERSION", priority=20, default="")
    assert rule.extract("MyApp_V1.2.3.exe") == "1.2.3"


def test_custom_regex_with_group_transform():
    """Custom regex + transform combines multiple groups."""
    rule = ColumnRule(
        name="ProjectBuild",
        match=r"Project_([A-Z0-9]+)_Build_(\d+)",
        transform=r"\1 (Build \2)",
        priority=15,
        default="",
    )
    assert rule.extract("Release_Project_ABC_Build_42.exe") == "ABC (Build 42)"


def test_transform_default_to_group1():
    """No transform defaults to group 1 when it exists."""
    rule = ColumnRule(name="Version", match=r"V(\d+\.\d+\.\d+)", priority=0, default="")
    assert rule.extract("App_V1.2.3.exe") == "1.2.3"


def test_transform_default_to_group0_no_groups():
    """No transform and no groups returns the whole match."""
    rule = ColumnRule(name="File", match=r".*", priority=100, default="")
    assert rule.extract("myfile.txt") == "myfile.txt"


def test_invalid_pattern_returns_default():
    """A malformed regex falls back to the default value."""
    ColumnRule.clear_cache()
    rule = ColumnRule(name="Test", match=r"[invalid(regex", priority=0, default="N/A")
    assert rule.extract("anyfile.txt") == "N/A"


def test_legacy_group_field_still_works():
    """Legacy explicit group index (0 = full match, >1 = that group) is preserved."""
    rule0 = ColumnRule(name="File", match=r".+", group=0)
    assert rule0.extract("test.mttl") == "test.mttl"
    rule2 = ColumnRule(name="Device", match=r"([A-Z]+)", group=2, default="D")
    assert rule2.extract("ABC123") == "D"


def test_transform_index_error_returns_default():
    """Transform referencing a missing group returns default."""
    rule = ColumnRule(name="X", match=r"(\d+)", transform=r"\2", default="E")
    assert rule.extract("abc123") == "E"


def test_builtin_patterns_dict_exported():
    """BUILTIN_PATTERNS contains the documented keywords."""
    for key in ("version", "date", "git_commit", "type", "filename", "extension"):
        assert key in BUILTIN_PATTERNS
