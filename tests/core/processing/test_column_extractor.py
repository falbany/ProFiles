"""Tests for profiles.core.processing.column_extractor — ColumnRule, ColumnExtractor.

Covers the regex/rules engine, the attribute keywords (size, size_bytes,
modified, created) backed by a ``FileAttrs`` snapshot, and the ``path``
keyword (parent directory of the display path).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from profiles.core.processing.column_extractor import (
    ATTRIBUTE_KEYWORDS,
    DEFAULT_ATTR_DATETIME_FORMAT,
    ColumnExtractor,
    ColumnRule,
    format_human_size,
)
from profiles.core.processing.file_metadata import FileAttrs


class TestColumnRule:
    """Test ColumnRule extraction logic."""

    def test_extract_with_capture_group(self) -> None:
        """Test extraction using capture group 1."""
        rule = ColumnRule(name="Device", match=r"Device_([A-Z0-9]+)", group=1)
        result = rule.extract("Device_ABC123_V01.mttl")
        assert result == "ABC123"

    def test_extract_with_full_match(self) -> None:
        """Test extraction using full match (group 0)."""
        rule = ColumnRule(name="File", match=r".+", group=0)
        result = rule.extract("test.mttl")
        assert result == "test.mttl"

    def test_extract_no_match_returns_default(self) -> None:
        """Test that no match returns default value."""
        rule = ColumnRule(name="Device", match=r"Device_([A-Z0-9]+)", group=1, default="Unknown")
        result = rule.extract("nodeviceatall.mttl")
        assert result == "Unknown"

    def test_extract_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        rule = ColumnRule(name="Version", match=r"_V(.+)", group=1)
        result = rule.extract("test_V01.mttl")
        assert result == "01.mttl"  # Extension not stripped at this level

    def test_extract_group_index_error_returns_default(self) -> None:
        """A group index beyond the match returns the default."""
        rule = ColumnRule(name="Device", match=r"Device_([A-Z0-9]+)", group=4, default="X")
        assert rule.extract("Device_ABC123.mttl") == "X"

    def test_compiled_cache_reuse(self) -> None:
        """Compiling the same pattern twice reuses the cache."""
        ColumnRule.clear_cache()
        rule1 = ColumnRule(name="A", match=r"A_(.+)")
        rule2 = ColumnRule(name="B", match=r"A_(.+)")
        assert rule1.compiled() is rule2.compiled()

    def test_invalid_pattern_logs_once_and_uses_sentinel(self) -> None:
        """A malformed regex falls back to a never-matching sentinel."""
        ColumnRule.clear_cache()
        rule = ColumnRule(name="Bad", match=r"(unclosed")
        compiled = rule.compiled()
        assert compiled is ColumnRule._BROKEN_SENTINEL
        # Cached for repeat calls without a re-warning.
        assert rule.compiled() is ColumnRule._BROKEN_SENTINEL

    def test_default_value_used_when_empty_group_misses(self) -> None:
        """When the whole match bounds are fine but group indexing fails."""
        ColumnRule.clear_cache()
        rule = ColumnRule(name="Device", match=r"([A-Z]+)", group=2, default="D")
        assert rule.extract("ABC123") == "D"


class TestColumnExtractor:
    """Test ColumnExtractor orchestration."""

    def test_extract_all_columns(self) -> None:
        """Test extracting multiple columns from a filename."""
        extractor = ColumnExtractor()
        extractor.add_rule("File", r".*", group=0, priority=100)
        extractor.add_rule("Version", r"_V(.+)", group=1, priority=10)
        extractor.add_rule("Device", r"Device_([A-Z0-9]+)", group=1, priority=5)

        result = extractor.extract_all(
            "PROD_Device_ABC123_V1.0.2-beta.mttl",
            ("File", "Version", "Device"),
        )

        assert result["File"] == "PROD_Device_ABC123_V1.0.2-beta.mttl"
        assert result["Version"] == "1.0.2-beta.mttl"
        assert result["Device"] == "ABC123"

    def test_priority_order(self) -> None:
        """Test that rules are processed by priority."""
        extractor = ColumnExtractor()
        extractor.add_rule("Low", r".*", group=0, priority=1)
        extractor.add_rule("High", r".*", group=0, priority=100)

        rules = extractor.get_rules()
        assert rules[0].name == "High"
        assert rules[1].name == "Low"

    def test_remove_rule(self) -> None:
        """Test removing a rule by name."""
        extractor = ColumnExtractor()
        extractor.add_rule("Device", r"Device_([A-Z0-9]+)", group=1)
        extractor.add_rule("Version", r"_V(.+)", group=1)

        assert extractor.remove_rule("Device") is True
        assert extractor.remove_rule("NonExistent") is False

        rules = extractor.get_rules()
        assert len(rules) == 1
        assert rules[0].name == "Version"

    def test_unknown_column_returns_empty(self) -> None:
        """An unknown column name yields an empty string."""
        extractor = ColumnExtractor()
        extractor.add_rule("Version", r"_V(.+)", group=1)
        result = extractor.extract_all("file.mttl", ("Version", "Missing"))
        assert result["Version"] == ""
        assert result["Missing"] == ""

    def test_clear_rules(self) -> None:
        """clear_rules empties the rule list."""
        extractor = ColumnExtractor()
        extractor.add_rule("Version", r"_V(.+)", group=1)
        extractor.clear_rules()
        assert extractor.get_rules() == []


class TestLoadColumnRulesFromConfig:
    """load_column_rules_from_config() parsing."""

    def test_empty_config_adds_defaults(self) -> None:
        """An empty/blank config yields File + Version default rules."""
        from profiles.core.processing.column_extractor import load_column_rules_from_config

        extractor = load_column_rules_from_config("")
        names = [r.name for r in extractor.get_rules()]
        assert names == ["File", "Version"]

    def test_full_definition_parsed(self) -> None:
        """Comma-separated definitions become rules with all attributes."""
        from profiles.core.processing.column_extractor import load_column_rules_from_config

        extractor = load_column_rules_from_config(
            "File:.*:0:100::,Version:_V(.+):1:10::,Device:Device_([A-Z0-9]+):1:5:Unknown"
        )
        rules = {r.name: r for r in extractor.get_rules()}
        assert rules["File"].group == 0
        assert rules["File"].priority == 100
        assert rules["Version"].match == r"_V(.+)"
        assert rules["Device"].default == "Unknown"

    def test_malformed_entries_skipped(self) -> None:
        """Entries with fewer than 2 parts are skipped."""
        from profiles.core.processing.column_extractor import load_column_rules_from_config

        extractor = load_column_rules_from_config("bad,Version:_V(.+):1:10:")
        names = [r.name for r in extractor.get_rules()]
        assert names == ["Version"]

    def test_partial_fields_default(self) -> None:
        """Missing group/priority/default use sane defaults."""
        from profiles.core.processing.column_extractor import load_column_rules_from_config

        extractor = load_column_rules_from_config("Device:Device_([A-Z0-9]+)")
        rules = extractor.get_rules()
        assert len(rules) == 1
        assert rules[0].group == 1
        assert rules[0].priority == 0
        assert rules[0].default == ""


class TestColumnExtractorImmutability:
    """ColumnExtractor keeps an immutable snapshot; safe to share across threads."""

    def test_get_rules_returns_fresh_copy(self) -> None:
        """Mutating the returned list must not affect the extractor."""
        extractor = ColumnExtractor()
        extractor.add_rule("File", r".*", group=0, priority=100)

        snapshot = extractor.get_rules()
        snapshot.append(ColumnRule(name="HACK", match=r".*"))

        assert [r.name for r in extractor.get_rules()] == ["File"]

    def test_rules_sorted_at_add_time(self) -> None:
        """Rules are returned sorted by priority without any recomputation."""
        extractor = ColumnExtractor()
        extractor.add_rule("Low", r".*", priority=1)
        extractor.add_rule("High", r".*", priority=100)
        extractor.add_rule("Mid", r".*", priority=50)

        first = extractor.get_rules()
        second = extractor.get_rules()
        assert [r.name for r in first] == ["High", "Mid", "Low"]
        assert [r.name for r in second] == ["High", "Mid", "Low"]

    def test_concurrent_extract_all_matches_sequential(self) -> None:
        """A shared extractor used from a thread pool yields identical results."""
        import concurrent.futures

        extractor = ColumnExtractor()
        extractor.add_rule("File", r".*", group=0, priority=100)
        extractor.add_rule("Version", r"_V(.+)", group=1, priority=10)
        extractor.add_rule("Device", r"Device_([A-Z0-9]+)", group=1, priority=5)

        filenames = [
            f"PROD_{name}_V{version}.mttl"
            for name in ("ABC", "DEF", "GHI")
            for version in ("01", "02", "03", "04")
        ]
        column_names = ("File", "Version", "Device")

        sequential = [extractor.extract_all(fn, column_names) for fn in filenames]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            parallel = list(pool.map(lambda fn: extractor.extract_all(fn, column_names), filenames))

        assert parallel == sequential


class TestAttributeKeywords:
    """Attribute keyword rules (size / size_bytes / modified / created)."""

    def test_attribute_keywords_exact_set(self) -> None:
        """The keyword set is exactly the four documented attribute keys."""
        assert {"size", "size_bytes", "modified", "created"} == ATTRIBUTE_KEYWORDS

    def test_size_human_format(self) -> None:
        """`size` formats the byte count in human-readable units."""
        rule = ColumnRule(name="Size", match="size")
        attrs = FileAttrs(1572864, 1795545600.0, 1790000000.0)
        assert rule.extract_attr(attrs) == "1.5 MB"

    def test_size_bytes_raw_count(self) -> None:
        """`size_bytes` returns the raw integer byte count as a string."""
        rule = ColumnRule(name="SizeBytes", match="size_bytes")
        attrs = FileAttrs(1572864, 1795545600.0, 1790000000.0)
        assert rule.extract_attr(attrs) == "1572864"

    def test_size_boundaries(self) -> None:
        """`size` boundary pins: 0, 512, 1023 and the 1 MB rounding."""
        rule = ColumnRule(name="Size", match="size")
        for size_bytes, expected in (
            (0, "0 B"),
            (512, "512 B"),
            (1023, "1023 B"),
            (1048576, "1 MB"),
        ):
            attrs = FileAttrs(size_bytes, 0.0, 0.0)
            assert rule.extract_attr(attrs) == expected

    def test_modified_default_format(self) -> None:
        """`modified` uses the default datetime format in local time."""
        rule = ColumnRule(name="Modified", match="modified")
        attrs = FileAttrs(1572864, 1795545600.0, 1790000000.0)
        expected = datetime.fromtimestamp(1795545600.0).strftime(DEFAULT_ATTR_DATETIME_FORMAT)
        assert rule.extract_attr(attrs) == expected

    def test_modified_custom_transform_format(self) -> None:
        """`modified` honors transform as a strftime pattern."""
        rule = ColumnRule(name="Modified", match="modified", transform="%d/%m/%Y")
        attrs = FileAttrs(1572864, 1795545600.0, 1790000000.0)
        assert rule.extract_attr(attrs) == datetime.fromtimestamp(1795545600.0).strftime("%d/%m/%Y")

    def test_created_uses_birthtime(self) -> None:
        """`created` formats birthtime, not mtime."""
        rule = ColumnRule(name="Created", match="created")
        attrs = FileAttrs(1572864, 1795545600.0, 1790000000.0)
        expected = datetime.fromtimestamp(1790000000.0).strftime(DEFAULT_ATTR_DATETIME_FORMAT)
        assert rule.extract_attr(attrs) == expected

    def test_none_attrs_returns_default_for_all_keywords(self) -> None:
        """attrs=None yields the rule default for every attribute keyword."""
        for keyword in ATTRIBUTE_KEYWORDS:
            rule = ColumnRule(name=keyword.title(), match=keyword, default="N/A")
            assert rule.extract_attr(None) == "N/A"

    def test_is_attribute_case_insensitive(self) -> None:
        """is_attribute is True for keyword matches regardless of case."""
        assert ColumnRule(name="Size", match="SIZE").is_attribute is True
        assert ColumnRule(name="Modified", match="Modified").is_attribute is True

    def test_is_attribute_false_for_regex(self) -> None:
        """is_attribute is False for raw regex matches."""
        assert ColumnRule(name="File", match=r".*").is_attribute is False
        assert ColumnRule(name="Device", match=r"Device_([A-Z0-9]+)").is_attribute is False

    def test_format_human_size_pins(self) -> None:
        """format_human_size boundary pins (binary units, 1 KB = 1024 B)."""
        assert format_human_size(0) == "0 B"
        assert format_human_size(512) == "512 B"
        assert format_human_size(1023) == "1023 B"
        assert format_human_size(1048576) == "1 MB"
        assert format_human_size(1572864) == "1.5 MB"


class TestPathKeyword:
    """`path` keyword rule: parent directory of the display path (no stat)."""

    def test_path_returns_parent_directory(self) -> None:
        """A nested display path yields its containing directory."""
        extractor = ColumnExtractor()
        extractor.add_rule("Path", "path", default=".")
        result = extractor.extract_all("sub/dir/dump.log", ("Path",))
        assert result["Path"] == str(Path("sub/dir/dump.log").parent)

    def test_path_bare_filename_returns_dot(self) -> None:
        """A bare filename has no directory component: '.' is returned."""
        extractor = ColumnExtractor()
        extractor.add_rule("Path", "path", default=".")
        result = extractor.extract_all("dump.log", ("Path",))
        assert result["Path"] == "."

    def test_path_transform_ignored(self) -> None:
        """transform has no effect on the `path` keyword."""
        extractor = ColumnExtractor()
        extractor.add_rule("Path", "path", transform="IGNORED", default=".")
        result = extractor.extract_all("sub/dir/dump.log", ("Path",))
        assert result["Path"] == str(Path("sub/dir/dump.log").parent)

    def test_path_is_not_an_attribute(self) -> None:
        """`path` rules never count as attribute rules (no stat cost)."""
        assert ColumnRule(name="Path", match="path").is_attribute is False


class TestHasAttributeRules:
    """ColumnExtractor.has_attribute_rules() gating for worker-side stat."""

    def test_true_when_attribute_column_requested(self) -> None:
        """An attribute rule whose name is requested returns True."""
        extractor = ColumnExtractor()
        extractor.add_rule("Size", "size")
        assert extractor.has_attribute_rules(("Size",)) is True

    def test_false_for_regex_only(self) -> None:
        """A pure regex rule set never triggers a stat."""
        extractor = ColumnExtractor()
        extractor.add_rule("File", r".*", group=0, priority=100)
        assert extractor.has_attribute_rules(("File",)) is False

    def test_false_for_path_rule(self) -> None:
        """`path` rules are string-derived and must not count."""
        extractor = ColumnExtractor()
        extractor.add_rule("Path", "path")
        assert extractor.has_attribute_rules(("Path",)) is False

    def test_false_when_attribute_column_not_requested(self) -> None:
        """An attribute rule outside the requested columns does not count."""
        extractor = ColumnExtractor()
        extractor.add_rule("Size", "size")
        assert extractor.has_attribute_rules(("File",)) is False

    def test_false_with_no_rules(self) -> None:
        """An empty extractor has no attribute rules."""
        assert ColumnExtractor().has_attribute_rules(("Size",)) is False


class TestExtractAllWithAttrs:
    """extract_all() integration with the optional attrs snapshot."""

    def test_extract_all_fills_attribute_columns(self) -> None:
        """File / Size / Modified columns fill from filename and attrs."""
        extractor = ColumnExtractor()
        extractor.add_rule("File", r".*", group=0, priority=100)
        extractor.add_rule("Size", "size", priority=20)
        extractor.add_rule("Modified", "modified", priority=10)
        attrs = FileAttrs(1572864, 1795545600.0, 1790000000.0)

        result = extractor.extract_all("dump.log", ("File", "Size", "Modified"), attrs)

        assert result["File"] == "dump.log"
        assert result["Size"] == "1.5 MB"
        assert result["Modified"] == datetime.fromtimestamp(1795545600.0).strftime(
            DEFAULT_ATTR_DATETIME_FORMAT
        )

    def test_extract_all_without_attrs_uses_defaults(self) -> None:
        """Omitting attrs (2-arg call) keeps attribute defaults — callers unaffected."""
        extractor = ColumnExtractor()
        extractor.add_rule("Size", "size", default="?")
        result = extractor.extract_all("dump.log", ("Size",))
        assert result["Size"] == "?"
