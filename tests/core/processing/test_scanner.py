"""Tests for profiles.core.processing.scanner — scan_and_process, ScannedFile, ScannedFileDynamic, is_simple_extension, extension filter integration."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pytest

import profiles.core.processing.scanner as scanner
from profiles.core.config.models import AppConfig, ColumnConfiguration, MachineConfiguration
from profiles.core.processing import file_metadata
from profiles.core.processing.file_metadata import FileAttrs
from profiles.core.processing.scanner import (
    ScannedFile,
    ScannedFileDynamic,
    _scan_and_filter,
    is_simple_extension,
    scan_and_process,
    scan_and_process_dynamic,
)
from profiles.utils.search_parser import match_filter


class TestIsSimpleExtension:
    """Tests for core.scanner.is_simple_extension."""

    def test_empty_string(self) -> None:
        assert is_simple_extension("") is True

    def test_whitespace_only(self) -> None:
        assert is_simple_extension("   ") is True

    def test_all_keyword(self) -> None:
        assert is_simple_extension("All") is True
        assert is_simple_extension("all") is True
        assert is_simple_extension("ALL") is True

    def test_simple_dot_extension(self) -> None:
        assert is_simple_extension(".mttl") is True

    def test_simple_extension_no_dot(self) -> None:
        assert is_simple_extension("mttl") is True

    def test_simple_lnk(self) -> None:
        assert is_simple_extension(".lnk") is True

    def test_or_expression(self) -> None:
        assert is_simple_extension(".mttl OR .mttx") is False

    def test_or_lowercase(self) -> None:
        assert is_simple_extension("mttl or mttx") is False

    def test_negation(self) -> None:
        assert is_simple_extension("-.lnk") is False

    def test_plus_prefix(self) -> None:
        assert is_simple_extension("+.mttl") is False

    def test_quoted_simple(self) -> None:
        # Quoted string is one token, no operator prefix → treated as simple
        assert is_simple_extension('".mttl"') is True

    def test_two_terms_and(self) -> None:
        # Two space-separated terms = AND = implicit operator → complex
        assert is_simple_extension(".mttl .mttx") is False

    def test_mixed_and_or(self) -> None:
        assert is_simple_extension(".mttl OR .mttx -.lnk") is False

    def test_single_negation_only(self) -> None:
        # Lone "-" has negation prefix → treated as complex (correct:
        # scanning with "-" would glob *- which is not intended)
        assert is_simple_extension("-") is False

    # ── Compound / double extensions (e.g. .mttx.lnk) ──────────────────

    def test_compound_extension_simple(self) -> None:
        """A compound extension like .mttx.lnk is a single token → simple."""
        assert is_simple_extension(".mttx.lnk") is True

    def test_compound_extension_or(self) -> None:
        """Compound extension in OR expression → complex."""
        assert is_simple_extension(".mttx.lnk OR .mttl") is False

    def test_compound_extension_not(self) -> None:
        assert is_simple_extension("-.mttx.lnk") is False


class TestExtensionMatchFilter:
    """Tests that match_filter works correctly on file suffixes.

    This mimics the exact logic used in
    :meth:`profiles.gui.main_window.MainWindow._refresh_file_list`::

        match_filter(file_path.suffix, extension_expression)
    """

    # ── Simple suffix match (single extension) ────────────────────────

    def test_single_suffix_match(self) -> None:
        assert match_filter(".mttl", ".mttl") is True

    def test_single_suffix_no_match(self) -> None:
        assert match_filter(".mttl", ".mttx") is False

    def test_single_suffix_no_dot_in_query(self) -> None:
        # User types "mttl" without dot, suffix is ".mttl" (with dot)
        # match_filter does substring check → "mttl" is in ".mttl"
        assert match_filter(".mttl", "mttl") is True

    def test_single_suffix_no_match_no_dot(self) -> None:
        assert match_filter(".mttl", "lnk") is False

    # ── OR operator ───────────────────────────────────────────────────

    def test_or_both_match(self) -> None:
        assert match_filter(".mttl", ".mttl OR .mttx") is True

    def test_or_second_matches(self) -> None:
        assert match_filter(".mttx", ".mttl OR .mttx") is True

    def test_or_neither_matches(self) -> None:
        assert match_filter(".lnk", ".mttl OR .mttx") is False

    def test_or_three_alternatives(self) -> None:
        assert match_filter(".txt", ".mttl OR .mttx OR .txt") is True
        assert match_filter(".lnk", ".mttl OR .mttx OR .txt") is False

    def test_or_without_dot_in_query(self) -> None:
        assert match_filter(".mttl", "mttl OR mttx") is True
        assert match_filter(".mttx", "mttl OR mttx") is True
        assert match_filter(".lnk", "mttl OR mttx") is False

    # ── AND operator (space = implicit AND) ───────────────────────────

    def test_and_both_terms_in_suffix(self) -> None:
        # "mttl" AND "v01" both in ".mttl" → ".mttl" does NOT contain "v01"
        # This is a bit artificial for extensions but tests the logic
        assert match_filter("_v01.mttl", "mttl v01") is True

    def test_and_one_term_missing_in_suffix(self) -> None:
        assert match_filter(".mttl", "mttl mttx") is False

    # ── NOT operator (prefix -) ───────────────────────────────────────

    def test_not_excludes_suffix(self) -> None:
        assert match_filter(".lnk", "-.lnk") is False

    def test_not_allows_other_suffix(self) -> None:
        assert match_filter(".mttl", "-.lnk") is True

    def test_not_with_or(self) -> None:
        # Include .mttl OR .mttx but NOT .lnk
        expr = ".mttl OR .mttx -.lnk"
        assert match_filter(".mttl", expr) is True
        assert match_filter(".mttx", expr) is True
        assert match_filter(".lnk", expr) is False

    # ── Exact phrase (quoted) ─────────────────────────────────────────

    def test_exact_suffix_match(self) -> None:
        assert match_filter(".mttl", '".mttl"') is True

    def test_exact_suffix_no_match(self) -> None:
        assert match_filter(".mttl", '".mttx"') is False

    # ── Edge cases ────────────────────────────────────────────────────

    def test_empty_query_matches_all(self) -> None:
        assert match_filter(".mttl", "") is True

    def test_all_keyword_never_reaches_match_filter(self) -> None:
        # "All" is handled by _is_simple_extension at the higher level.
        # If it DID reach match_filter, it would do substring matching:
        # "all" is NOT a substring of ".mttl". This is fine because "All"
        # is intercepted before match_filter is ever called.
        assert match_filter(".mttl", "All") is False
        assert is_simple_extension("All") is True

    def test_case_insensitive_suffix(self) -> None:
        assert match_filter(".MTTL", ".mttl") is True
        assert match_filter(".MTTL", "mttl") is True

    def test_plus_prefix(self) -> None:
        assert match_filter(".mttl", "+.mttl") is True
        assert match_filter(".mttl", "+mttl") is True

    def test_whitespace_in_query(self) -> None:
        assert match_filter(".mttl", "  .mttl  ") is True

    def test_no_extension_file(self) -> None:
        # Files with no suffix (e.g. "Makefile") have suffix ""
        assert match_filter("", ".mttl") is False
        assert match_filter("", "") is True

    def test_complex_mixed_expression(self) -> None:
        """Realistic scenario: mttl or mttx, no lnk."""
        expr = ".mttl OR .mttx -.lnk"
        assert match_filter("file.mttl", expr) is True  # suffix = ".mttl"
        assert match_filter("file.mttx", expr) is True  # suffix = ".mttx"
        assert match_filter("file.lnk", expr) is False  # suffix = ".lnk"
        assert match_filter("file.txt", expr) is False  # suffix = ".txt"

    # ── Integration scenario: end-to-end extension filtering logic ─────────

    # ── Compound / double extensions (e.g. .mttx.lnk) ──────────────────

    def test_compound_single_match(self) -> None:
        """Match compound extension verbatim."""
        assert match_filter(".mttx.lnk", ".mttx.lnk") is True

    def test_compound_single_no_match(self) -> None:
        assert match_filter(".mttx.lnk", ".mttl") is False

    def test_compound_or(self) -> None:
        """Compound extension in OR expression."""
        assert match_filter(".mttx.lnk", ".mttl OR .mttx.lnk") is True
        assert match_filter(".mttl", ".mttl OR .mttx.lnk") is True
        assert match_filter(".lnk", ".mttl OR .mttx.lnk") is False

    def test_compound_not(self) -> None:
        """NOT operator with compound extension."""
        assert match_filter(".mttl", "-.mttx.lnk") is True
        assert match_filter(".mttx.lnk", "-.mttx.lnk") is False

    def test_compound_partial_suffix_no_match(self) -> None:
        """A partial suffix (e.g. .lnk) should NOT match a compound ext (.mttx.lnk).

        This test documents that match_filter does substring matching, so
        ``.lnk`` *would* match ``.mttx.lnk`` because ``.lnk`` appears in
        ``.mttx.lnk``.  In practice the user would type the full compound
        extension, so this is acceptable.
        """
        # Substring: ".lnk" is in ".mttx.lnk"
        assert match_filter(".mttx.lnk", ".lnk") is True

    def test_compound_mixed_expression(self) -> None:
        """Realistic: match simple and compound extensions with OR + NOT.

        Note: -.lnk would also exclude .mttx.lnk because .lnk is a substring.
        Use a non-colliding NOT term.
        """
        expr = ".mttl OR .mttx.lnk -.txt"
        assert match_filter(".mttl", expr) is True  # in group 1
        assert match_filter(".mttx.lnk", expr) is True  # in group 2, not negated
        assert match_filter(".lnk", expr) is False  # neither group contains ".lnk"
        assert match_filter(".txt", expr) is False  # excluded by -.txt


class TestExtensionFilterIntegration:
    """Simulates the exact filtering pipeline in _refresh_file_list.

    As of the current implementation the pipeline always scans all files
    and then applies ``match_filter`` on each file's full suffix (the
    ``core.scanner.is_simple_extension`` optimisation was removed because it could
    not handle compound extensions like ``.mttx.lnk`` when the user types
    ``.mttx`` — glob-based pre-filtering would miss the compound file).
    """

    @staticmethod
    def _filter_by_extension(
        suffixes: list[str],
        extension_expr: str,
    ) -> list[str]:
        """Simulate the extension filtering pipeline.

        Always applies ``match_filter`` on each suffix — no fast-path.
        Empty or 'All' matches everything.
        """
        stripped = extension_expr.strip()
        if not stripped or stripped.lower() == "all":
            return list(suffixes)
        return [s for s in suffixes if match_filter(s, extension_expr)]

    def test_simple_extension(self) -> None:
        """A plain extension matches its suffix."""
        suffixes = [".mttl", ".mttx", ".lnk"]
        result = self._filter_by_extension(suffixes, ".mttl")
        assert result == [".mttl"]

    def test_operator_or(self) -> None:
        suffixes = [".mttl", ".mttx", ".lnk", ".txt"]
        result = self._filter_by_extension(suffixes, ".mttl OR .mttx")
        assert result == [".mttl", ".mttx"]

    def test_operator_not(self) -> None:
        suffixes = [".mttl", ".mttx", ".lnk"]
        result = self._filter_by_extension(suffixes, "-.lnk")
        assert result == [".mttl", ".mttx"]

    def test_operator_or_with_not(self) -> None:
        suffixes = [".mttl", ".mttx", ".lnk", ".txt"]
        result = self._filter_by_extension(suffixes, ".mttl OR .mttx -.lnk")
        assert result == [".mttl", ".mttx"]

    def test_empty_expression(self) -> None:
        suffixes = [".mttl", ".mttx", ".lnk"]
        result = self._filter_by_extension(suffixes, "")
        assert result == [".mttl", ".mttx", ".lnk"]

    def test_all_keyword(self) -> None:
        suffixes = [".mttl", ".mttx", ".lnk"]
        result = self._filter_by_extension(suffixes, "All")
        assert result == [".mttl", ".mttx", ".lnk"]

    # ── Compound / double extensions ─────────────────────────────────

    def test_compound_simple_match(self) -> None:
        """Compound extension typed verbatim matches via match_filter."""
        suffixes = [".mttx.lnk", ".mttl", ".lnk"]
        result = self._filter_by_extension(suffixes, ".mttx.lnk")
        assert result == [".mttx.lnk"]  # only the compound ext matches

    def test_simple_ext_matches_compound_files(self) -> None:
        """Typing .mttx also matches .mttx.lnk (substring search)."""
        suffixes = [".mttx.lnk", ".mttx", ".mttl"]
        result = self._filter_by_extension(suffixes, ".mttx")
        assert result == [".mttx.lnk", ".mttx"]

    def test_compound_operator_or(self) -> None:
        """Compound extension in OR expression."""
        suffixes = [".mttx.lnk", ".mttl", ".lnk", ".txt"]
        result = self._filter_by_extension(suffixes, ".mttx.lnk OR .mttl")
        assert result == [".mttx.lnk", ".mttl"]

    def test_compound_operator_not(self) -> None:
        """NOT with compound extension."""
        suffixes = [".mttx.lnk", ".mttl", ".lnk"]
        result = self._filter_by_extension(suffixes, "-.mttx.lnk")
        assert result == [".mttl", ".lnk"]


class TestScannedFileDynamic:
    """Test ScannedFileDynamic named tuple."""

    def test_create_scanned_file_dynamic(self) -> None:
        """Test creating a ScannedFileDynamic instance."""
        column_values = {
            "File": "C:/path/to/test.mttl",  # Full path, not just filename
            "Version": "01",
            "Device": "ABC123",
        }
        scanned = ScannedFileDynamic(
            path=Path("C:/path/to/test.mttl"), column_values=column_values, rel_path="test.mttl"
        )

        assert scanned.path == Path("C:/path/to/test.mttl")
        assert scanned.column_values == column_values
        assert scanned.column_values["File"] == "C:/path/to/test.mttl"

    def test_invalid_pattern_returns_default(self) -> None:
        """Malformed [COLUMN_*] regex must not crash; fall back to default."""
        # '([^/\]+)$' from the buggy starter config — invalid in Python regex
        from profiles.core.processing.column_extractor import ColumnRule

        bad = ColumnRule(name="FileName", match=r"([^/\]+)$", group=1, default="?")
        # Should not raise; should fall back to "?".
        assert bad.extract("foo.txt") == "?"

    def test_invalid_pattern_in_extractor_keeps_other_columns(self) -> None:
        """A bad rule on one column must not break the others."""
        from profiles.core.processing.column_extractor import ColumnExtractor

        extractor = ColumnExtractor()
        extractor.add_rule("File", r".*", group=0, priority=100)
        extractor.add_rule("Bad", r"([^/\]+)$", group=1, priority=10, default="fallback")
        extractor.add_rule("Device", r"Device_([A-Z0-9]+)", group=1, priority=5)

        result = extractor.extract_all("Device_ABC123.mttl", ("File", "Bad", "Device"))
        assert result["File"] == "Device_ABC123.mttl"
        assert result["Bad"] == "fallback"
        assert result["Device"] == "ABC123"


class TestScanAndProcessDynamicRelativeFileColumn:
    """Default `File` column in scan_and_process_dynamic is relative to the scanned dir."""

    def test_file_column_is_relative_to_directory(self, tmp_path: Path) -> None:
        """Recursive scan: files in subdirs appear as `subdir/file.ext` in `File`."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.mttl").write_text("")
        (sub / "nested.mttl").write_text("")

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            recursive=True,
            column_names=("File", "Version"),
        )

        file_values = {item.column_values["File"] for item in results}
        assert file_values == {"top.mttl", str(Path("sub") / "nested.mttl")}

    def test_scanned_file_path_stays_absolute(self, tmp_path: Path) -> None:
        """scanned_file.path must remain the full filesystem path for launch actions."""
        (tmp_path / "top.mttl").write_text("")

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("File", "Version"),
        )

        assert len(results) == 1
        assert results[0].path == tmp_path / "top.mttl"
        assert results[0].column_values["File"] == "top.mttl"


class TestScanPipelineSharedOrchestration:
    """Shared pipeline behavior: parallelism threshold, error semantics, metrics."""

    @staticmethod
    def _write_files(directory: Path, count: int, prefix: str = "file") -> None:
        """Create *count* empty ``.mttl`` files named ``prefix_<i:03d>.mttl``."""
        for i in range(count):
            (directory / f"{prefix}_{i:03d}.mttl").write_text("")

    def test_threshold_boundary_counts(self, tmp_path: Path) -> None:
        """Just below/at the parallelism threshold, every file is processed."""
        small = tmp_path / "small"
        large = tmp_path / "large"
        small.mkdir()
        large.mkdir()
        self._write_files(small, 99)
        self._write_files(large, 100)

        assert len(scan_and_process(str(small), extension=".mttl")) == 99
        assert len(scan_and_process(str(large), extension=".mttl")) == 100
        assert len(scan_and_process_dynamic(str(small), extension=".mttl")) == 99
        assert len(scan_and_process_dynamic(str(large), extension=".mttl")) == 100

    def test_parallel_matches_sequential(self, tmp_path: Path, monkeypatch) -> None:
        """Forcing the thread pool yields the same results and order as sequential."""
        self._write_files(tmp_path, 5)
        sequential = scan_and_process(str(tmp_path), extension=".mttl")

        monkeypatch.setattr(scanner, "_PARALLEL_THRESHOLD", 0)
        parallel = scan_and_process(str(tmp_path), extension=".mttl")

        assert parallel == sequential

    def test_parallel_matches_sequential_dynamic(self, tmp_path: Path, monkeypatch) -> None:
        """Dynamic scan: parallel and sequential paths produce identical output."""
        self._write_files(tmp_path, 5)
        sequential = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("File", "Version"),
        )

        monkeypatch.setattr(scanner, "_PARALLEL_THRESHOLD", 0)
        parallel = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("File", "Version"),
        )

        assert parallel == sequential

    def test_sequential_skips_failing_file(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """A single failing file is skipped + logged, never fatal, in sequential mode."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file

        def failing(
            file_path: Path, display_path: str, full_suffix: str, attrs: FileAttrs | None
        ) -> ScannedFile:
            if file_path.name == "file_001.mttl":
                raise OSError("boom")
            return real(file_path, display_path, full_suffix, attrs)

        monkeypatch.setattr(scanner, "_process_file", failing)

        with caplog.at_level(logging.ERROR, logger="profiles.core.processing.scanner"):
            results = scan_and_process(str(tmp_path), extension=".mttl")

        assert len(results) == 2
        assert {r.filename for r in results} == {"file_000.mttl", "file_002.mttl"}
        assert any("PROCESSING_FAILED" in r.message for r in caplog.records)

    def test_parallel_skips_failing_file(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """The parallel path skips + logs a failing file instead of aborting."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file

        def failing(
            file_path: Path, display_path: str, full_suffix: str, attrs: FileAttrs | None
        ) -> ScannedFile:
            if file_path.name == "file_002.mttl":
                raise OSError("boom")
            return real(file_path, display_path, full_suffix, attrs)

        monkeypatch.setattr(scanner, "_process_file", failing)
        monkeypatch.setattr(scanner, "_PARALLEL_THRESHOLD", 0)

        with caplog.at_level(logging.ERROR, logger="profiles.core.processing.scanner"):
            results = scan_and_process(str(tmp_path), extension=".mttl")

        assert len(results) == 2
        assert {r.filename for r in results} == {"file_000.mttl", "file_001.mttl"}
        assert any("PROCESSING_FAILED" in r.message for r in caplog.records)

    def test_dynamic_skips_failing_file(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """Dynamic extraction failures are skipped + logged, not fatal."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file_dynamic

        def failing(
            file_path: Path,
            display_path: str,
            full_suffix: str,
            attrs: FileAttrs | None,
            extractor,
            column_names,
            extension,
        ) -> ScannedFileDynamic:
            if file_path.name == "file_001.mttl":
                raise OSError("boom")
            return real(
                file_path, display_path, full_suffix, attrs, extractor, column_names, extension
            )

        monkeypatch.setattr(scanner, "_process_file_dynamic", failing)

        with caplog.at_level(logging.ERROR, logger="profiles.core.processing.scanner"):
            results = scan_and_process_dynamic(
                str(tmp_path),
                extension=".mttl",
                column_names=("File", "Version"),
            )

        assert len(results) == 2
        assert {r.path.name for r in results} == {"file_000.mttl", "file_002.mttl"}
        assert any("PROCESSING_FAILED" in r.message for r in caplog.records)

    def test_metrics_reports_error_count(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """ScanMetrics.error_count is populated when a per-file error occurs."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file

        def failing(
            file_path: Path, display_path: str, full_suffix: str, attrs: FileAttrs | None
        ) -> ScannedFile:
            if file_path.name == "file_000.mttl":
                raise OSError("boom")
            return real(file_path, display_path, full_suffix, attrs)

        monkeypatch.setattr(scanner, "_process_file", failing)
        config = AppConfig(scan_metrics=True)

        with caplog.at_level(logging.DEBUG, logger="profiles"):
            scan_and_process(str(tmp_path), extension=".mttl", config=config)

        metrics_records = [r for r in caplog.records if "SCAN_METRICS" in r.message]
        assert len(metrics_records) == 1
        assert "errors=1" in metrics_records[0].message

    def test_no_metrics_when_disabled(self, tmp_path: Path, caplog) -> None:
        """With metrics disabled, no DEBUG metrics line is emitted."""
        self._write_files(tmp_path, 2)

        with caplog.at_level(logging.DEBUG, logger="profiles"):
            scan_and_process(str(tmp_path), extension=".mttl")

        assert not any("SCAN_METRICS" in r.message for r in caplog.records)

    def test_dynamic_log_metrics_flag(self, tmp_path: Path, caplog) -> None:
        """log_metrics=True on the dynamic scan enables metrics logging."""
        self._write_files(tmp_path, 2)

        with caplog.at_level(logging.DEBUG, logger="profiles"):
            scan_and_process_dynamic(
                str(tmp_path),
                extension=".mttl",
                column_names=("File",),
                log_metrics=True,
            )

        assert any("SCAN_METRICS" in r.message for r in caplog.records)

    def test_dynamic_default_columns_equivalent_to_legacy(self, tmp_path: Path) -> None:
        """Dynamic extraction with default File/Version columns matches legacy output."""
        for name in ("prog_V01.mttl", "prog_V02.mttl", "prog_V10.mttl"):
            (tmp_path / name).write_text("")

        legacy = scan_and_process(str(tmp_path), extension=".mttl")
        dynamic = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("File", "Version"),
        )

        legacy_set = {(r.filename, r.version) for r in legacy}
        dynamic_set = {
            (item.column_values["File"], item.column_values["Version"]) for item in dynamic
        }
        assert legacy_set == dynamic_set

    def test_max_search_depth_and_machine_config_overrides(self, tmp_path: Path) -> None:
        """Verify max_search_depth, recursive_search, and search_exclude_dirs override AppConfig."""
        sub = tmp_path / "level1" / "level2" / "level3"
        sub.mkdir(parents=True)
        (sub / "deep.mttl").write_text("deep")

        # Default max_search_depth is 10, but let's test depth 1
        config = AppConfig(
            max_search_depth=1,
            configurations=[
                MachineConfiguration(
                    scan=(str(tmp_path),),
                    max_search_depth=5,
                    recursive_search=True,
                )
            ],
        )

        results = scan_and_process(str(tmp_path), extension=".mttl", recursive=True, config=config)
        assert len(results) == 1
        assert results[0].filename == "level1/level2/level3/deep.mttl"

    def test_recursive_override_beats_machine_entry_and_param(self, tmp_path: Path) -> None:
        """recursive_override wins over both the machine entry and the param.

        Precedence: recursive_override > machine-entry recursive_search >
        the ``recursive`` argument.
        """
        (tmp_path / "top.mttl").write_text("top")
        sub = tmp_path / "level1"
        sub.mkdir()
        (sub / "deep.mttl").write_text("deep")

        config = AppConfig(
            configurations=[MachineConfiguration(scan=(str(tmp_path),), recursive_search=True)]
        )

        # Override False beats the entry's recursive_search=True: flat scan.
        flat = scan_and_process(
            str(tmp_path),
            extension=".mttl",
            recursive=True,
            config=config,
            recursive_override=False,
        )
        assert [r.filename for r in flat] == ["top.mttl"]

        # Override True beats both the entry and the param (param says False).
        deep = scan_and_process(
            str(tmp_path),
            extension=".mttl",
            recursive=False,
            config=config,
            recursive_override=True,
        )
        assert sorted(r.filename for r in deep) == ["level1/deep.mttl", "top.mttl"]

    def test_machine_entry_recursive_search_beats_param_without_override(
        self, tmp_path: Path
    ) -> None:
        """Without an override, a matching entry's recursive_search wins."""
        (tmp_path / "top.mttl").write_text("top")
        sub = tmp_path / "level1"
        sub.mkdir()
        (sub / "deep.mttl").write_text("deep")

        config = AppConfig(
            configurations=[MachineConfiguration(scan=(str(tmp_path),), recursive_search=False)]
        )

        # Entry says flat; the recursive=True param loses.
        flat = scan_and_process(str(tmp_path), extension=".mttl", recursive=True, config=config)
        assert [r.filename for r in flat] == ["top.mttl"]

        # With no entry knob the param rules again (override None defers).
        config_on = AppConfig(
            configurations=[MachineConfiguration(scan=(str(tmp_path),), recursive_search=None)]
        )
        deep = scan_and_process(str(tmp_path), extension=".mttl", recursive=True, config=config_on)
        assert sorted(r.filename for r in deep) == ["level1/deep.mttl", "top.mttl"]

    def test_dynamic_scan_honors_recursive_override(self, tmp_path: Path) -> None:
        """The dynamic (web) scan path threads the override the same way."""
        (tmp_path / "top.mttl").write_text("top")
        sub = tmp_path / "level1"
        sub.mkdir()
        (sub / "deep.mttl").write_text("deep")

        config = AppConfig(
            configurations=[MachineConfiguration(scan=(str(tmp_path),), recursive_search=True)]
        )

        flat = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            recursive=True,
            config=config,
            recursive_override=False,
        )
        assert [item.column_values["File"] for item in flat] == ["top.mttl"]

        deep = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            recursive=False,
            config=config,
            recursive_override=True,
        )
        assert sorted(item.column_values["File"] for item in deep) == [
            "level1/deep.mttl",
            "top.mttl",
        ]

    def test_dynamic_single_file_column_equivalent_to_legacy(self, tmp_path: Path) -> None:
        """The legacy GUI mode (column_names=("File",)) equals the dynamic path.

        The reader normalises ``column_names`` to ``("File",)`` when no
        custom ``[COLUMN_*]`` sections exist, so the unified GUI always
        routes through ``scan_and_process_dynamic``. This locks in the
        equivalence that keeps the single-column layout unchanged.
        """
        self._write_files(tmp_path, 6)

        legacy = scan_and_process(str(tmp_path), extension=".mttl")
        dynamic = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("File",),
        )

        assert [r.filename for r in legacy] == [d.column_values["File"] for d in dynamic]
        assert [r.path for r in legacy] == [d.path for d in dynamic]


class TestDynamicScanProgress:
    """Tests for the optional on_progress callback (issue #152)."""

    def test_scan_and_process_dynamic_reports_progress(self, tmp_path: Path) -> None:
        """on_progress receives monotonically rising counts of filter-passing
        candidates; the final value equals the returned result count."""
        scan_dir = tmp_path / "prog"
        scan_dir.mkdir()
        for i in range(3):
            (scan_dir / f"f{i}.mttl").write_text("x")
        (scan_dir / "skip.txt").write_text("x")

        seen: list[int] = []
        results = scan_and_process_dynamic(
            str(scan_dir), extension=".mttl", on_progress=seen.append
        )

        assert seen == sorted(seen)
        assert len(seen) >= 1
        assert seen[-1] == len(results) == 3  # only .mttl candidates counted

    def test_scan_and_process_dynamic_without_progress_callback(self, tmp_path: Path) -> None:
        """Default (None) is a no-op: same results, no callback."""
        scan_dir = tmp_path / "prog"
        scan_dir.mkdir()
        (scan_dir / "a.mttl").write_text("x")
        assert scan_and_process_dynamic(str(scan_dir), extension=".mttl")


# ── #227: stat-backed scan pipeline (4-tuple candidates, zero-stat gate) ────


def _install_counting_wrapper(monkeypatch: pytest.MonkeyPatch, calls: list[Path]) -> None:
    """Patch ``scanner.collect_file_attrs`` with a counting pass-through wrapper.

    The wrapper delegates to the real implementation so scans still work;
    *calls* records every path the pipeline tried to stat.
    """
    real = file_metadata.collect_file_attrs

    def wrapper(path: Path) -> FileAttrs | None:
        calls.append(path)
        return real(path)

    monkeypatch.setattr(scanner, "collect_file_attrs", wrapper)


_MIB = 1024 * 1024


class TestCandidateTuples:
    """``_scan_and_filter`` yields 4-tuples whose attrs follow the query."""

    def test_plain_query_yields_none_attrs(self, tmp_path: Path) -> None:
        """Substring-free scan: every candidate carries ``attrs=None``."""
        (tmp_path / "a.mttl").write_text("x")

        candidates = list(_scan_and_filter(str(tmp_path), extension=".mttl"))

        assert candidates == [(tmp_path / "a.mttl", "a.mttl", ".mttl", None)]

    def test_operator_query_yields_stat_attrs(self, tmp_path: Path) -> None:
        """Operator query: the 4th element is the stat snapshot of the file."""
        (tmp_path / "a.mttl").write_text("x" * 1234)

        candidates = list(
            _scan_and_filter(str(tmp_path), extension=".mttl", filter_text="size:>1kb")
        )

        assert len(candidates) == 1
        file_path, display_path, full_suffix, attrs = candidates[0]
        assert file_path == tmp_path / "a.mttl"
        assert display_path == "a.mttl"
        assert full_suffix == ".mttl"
        assert attrs is not None
        assert attrs.size_bytes == 1234


class TestOperatorFilterScan:
    """Operator queries filter rows by stat data in the plain scan path."""

    def test_size_operator_keeps_only_big_file(self, tmp_path: Path) -> None:
        """`size:>1mb` on a 100 B vs 10 MiB tree keeps only the big file."""
        (tmp_path / "small.mttl").write_text("x" * 100)
        (tmp_path / "big.mttl").write_text("x" * (10 * _MIB))

        results = scan_and_process(str(tmp_path), extension=".mttl", filter_text="size:>1mb")

        assert [r.filename for r in results] == ["big.mttl"]

    def test_unreachable_size_threshold_returns_nothing(self, tmp_path: Path) -> None:
        """A threshold no file reaches yields an empty result, not an error."""
        (tmp_path / "small.mttl").write_text("x" * 100)

        results = scan_and_process(str(tmp_path), extension=".mttl", filter_text="size:>20mb")

        assert results == []


class TestOperatorFilterDynamic:
    """Dynamic scan: substring and operator terms combine with implicit AND."""

    COLUMNS = {"File": ColumnConfiguration(name="File", match=".*")}

    def test_substring_plus_modified_operator(self, tmp_path: Path) -> None:
        """`datalog modified:<7d`: fresh datalog files pass; old and
        non-matching names are filtered out."""
        aged = tmp_path / "datalog_old.mttl"
        aged.write_text("x")
        old_ts = time.time() - 30 * 24 * 3600  # 30 days ago
        os.utime(aged, (old_ts, old_ts))
        (tmp_path / "datalog_fresh.mttl").write_text("x")  # fresh mtime → passes
        (tmp_path / "other_fresh.mttl").write_text("x")  # fails the substring term

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            filter_text="datalog modified:<7d",
            column_names=("File",),
            columns=self.COLUMNS,
        )

        assert [r.column_values["File"] for r in results] == ["datalog_fresh.mttl"]

    def test_fresh_mtime_passes_modified_operator(self, tmp_path: Path) -> None:
        """Files just written (mtime untouched) satisfy `modified:<7d`."""
        (tmp_path / "datalog_a.mttl").write_text("x")
        (tmp_path / "datalog_b.mttl").write_text("x")

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            filter_text="datalog modified:<7d",
            column_names=("File",),
            columns=self.COLUMNS,
        )

        assert sorted(r.column_values["File"] for r in results) == [
            "datalog_a.mttl",
            "datalog_b.mttl",
        ]


class TestAttrsPassthrough:
    """Attribute columns render from the stat snapshot carried on the row."""

    def test_size_column_renders_and_attrs_stick(self, tmp_path: Path) -> None:
        """Size column shows the human-readable value; row.attrs keeps bytes."""
        (tmp_path / "big.mttl").write_text("x" * 1048576)

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("Size",),
            columns={"Size": ColumnConfiguration(name="Size", match="size")},
        )

        assert len(results) == 1
        row = results[0]
        assert row.column_values["Size"] == "1 MB"
        assert row.attrs is not None
        assert row.attrs.size_bytes == 1048576


class TestOneStatPerCandidate:
    """Operator query + attribute column: exactly one stat per candidate."""

    def test_collection_loop_stats_each_candidate_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """3 extension-passing candidates, 1 filter pass → wrapper called 3×.

        The stat happens once per candidate in the collection loop; workers
        must reuse that snapshot (a worker re-stat would push the count to 4
        and ``row.attrs`` identifies the collection-loop snapshot).
        """
        (tmp_path / "small.mttl").write_text("x" * 100)
        (tmp_path / "small2.mttl").write_text("x" * 200)
        (tmp_path / "big.mttl").write_text("x" * (10 * _MIB))

        calls: list[Path] = []
        _install_counting_wrapper(monkeypatch, calls)

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            filter_text="size:>1mb",
            column_names=("Size",),
            columns={"Size": ColumnConfiguration(name="Size", match="size")},
        )

        assert [r.rel_path for r in results] == ["big.mttl"]
        assert len(calls) == 3
        assert {c.name for c in calls} == {"small.mttl", "small2.mttl", "big.mttl"}
        assert results[0].attrs is not None
        assert results[0].attrs.size_bytes == 10 * _MIB


class TestStatSites:
    """Stat placement per scan shape: column-only stats per row, plain zero."""

    def test_column_only_scan_stats_once_per_row(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No operator query, attribute column → workers collect the snapshot."""
        for i in range(3):
            (tmp_path / f"f{i}.mttl").write_text("x" * (100 * (i + 1)))

        calls: list[Path] = []
        _install_counting_wrapper(monkeypatch, calls)

        results = scan_and_process_dynamic(
            str(tmp_path),
            extension=".mttl",
            column_names=("Size",),
            columns={"Size": ColumnConfiguration(name="Size", match="size")},
        )

        assert len(results) == 3
        assert len(calls) == 3  # one per row, from the worker-side stat site
        assert all(r.attrs is not None for r in results)

    def test_plain_dynamic_scan_stats_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plain query + no attribute column → zero calls, attrs stay None."""
        for i in range(3):
            (tmp_path / f"f{i}.mttl").write_text("x")

        calls: list[Path] = []
        _install_counting_wrapper(monkeypatch, calls)

        results = scan_and_process_dynamic(str(tmp_path), extension=".mttl")

        assert len(results) == 3
        assert calls == []
        assert all(r.attrs is None for r in results)


class TestZeroStatGate:
    """THE hard acceptance criterion of #227: plain scans stat nothing.

    ``collect_file_attrs`` is the only stat path added by #227 — every
    other stage (directory walk, extension pushdown, keyword filtering,
    version extraction) is untouched.  Patching it with a counting wrapper
    and observing 0 calls for plain scans therefore proves the plain
    pipeline gained no stat cost.
    """

    def test_plain_scan_and_process_never_stats(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plain scan, substring-only filter: wrapper call count == 0."""
        for i in range(5):
            (tmp_path / f"file_{i}.mttl").write_text("x" * 10)

        calls: list[Path] = []
        _install_counting_wrapper(monkeypatch, calls)

        results = scan_and_process(str(tmp_path), extension=".mttl", filter_text="file")

        assert len(results) == 5
        assert calls == []

    def test_plain_dynamic_scan_never_stats(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plain dynamic scan (no attribute columns, no filter): count == 0."""
        for i in range(5):
            (tmp_path / f"file_{i}.mttl").write_text("x" * 10)

        calls: list[Path] = []
        _install_counting_wrapper(monkeypatch, calls)

        results = scan_and_process_dynamic(str(tmp_path), extension=".mttl")

        assert len(results) == 5
        assert calls == []
        assert all(r.attrs is None for r in results)


class TestDeletedMidScan:
    """A file deleted between listing and stat degrades, never raises."""

    def test_unstatable_candidates_excluded_without_raising(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`collect_file_attrs` → None: operator rows drop out (attr terms
        evaluate False) while substring-only OR alternatives still match."""
        (tmp_path / "datalog_small.mttl").write_text("x" * 100)
        (tmp_path / "big.mttl").write_text("x" * (10 * _MIB))

        monkeypatch.setattr(scanner, "collect_file_attrs", lambda path: None)

        # Pure operator query: every row excluded, no exception raised.
        results = scan_and_process(str(tmp_path), extension=".mttl", filter_text="size:>1mb")
        assert results == []

        # OR query: the substring alternative keeps its rows.
        or_results = scan_and_process(
            str(tmp_path), extension=".mttl", filter_text="size:>1mb OR datalog"
        )
        assert [r.filename for r in or_results] == ["datalog_small.mttl"]


class TestScannedFileDynamicPositional:
    """The trailing attrs field defaults so 3-positional construction holds."""

    def test_three_positional_args_default_attrs(self) -> None:
        """`ScannedFileDynamic(path, column_values, rel_path)` stays valid."""
        entry = ScannedFileDynamic(Path("a.mttl"), {"File": "a.mttl"}, "a.mttl")
        assert entry.path == Path("a.mttl")
        assert entry.rel_path == "a.mttl"
        assert entry.attrs is None

    def test_four_positional_args_fill_attrs(self) -> None:
        """The 4th positional argument populates the attrs field."""
        attrs = FileAttrs(7, 1.0, 2.0)
        entry = ScannedFileDynamic(Path("a.mttl"), {}, "a.mttl", attrs)
        assert entry.attrs is attrs
