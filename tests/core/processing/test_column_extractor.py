"""Tests for profiles.core.processing.column_extractor — ColumnRule, ColumnExtractor."""

from __future__ import annotations

from profiles.core.processing.column_extractor import ColumnExtractor, ColumnRule


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
            "ST_PRO_Device_ABC123_V01-Rel6.2.1.mttl",
            ("File", "Version", "Device"),
        )

        assert result["File"] == "ST_PRO_Device_ABC123_V01-Rel6.2.1.mttl"
        assert result["Version"] == "01-Rel6.2.1.mttl"
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
            f"ST_PRO_{name}_V{version}.mttl"
            for name in ("ABC", "DEF", "GHI")
            for version in ("01", "02", "03", "04")
        ]
        column_names = ("File", "Version", "Device")

        sequential = [extractor.extract_all(fn, column_names) for fn in filenames]

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            parallel = list(pool.map(lambda fn: extractor.extract_all(fn, column_names), filenames))

        assert parallel == sequential
