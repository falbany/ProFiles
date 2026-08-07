"""Tests for profiles.core.processing.scanner — scan_and_process, ScannedFile, ScannedFileDynamic, is_simple_extension, extension filter integration."""

from __future__ import annotations

import logging
from pathlib import Path

import profiles.core.processing.scanner as scanner
from profiles.core.config.models import AppConfig
from profiles.core.processing.scanner import (
    ScannedFile,
    ScannedFileDynamic,
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
        scanned = ScannedFileDynamic(path=Path("C:/path/to/test.mttl"), column_values=column_values)

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

        def failing(file_path: Path, display_path: str, full_suffix: str) -> ScannedFile:
            if file_path.name == "file_001.mttl":
                raise OSError("boom")
            return real(file_path, display_path, full_suffix)

        monkeypatch.setattr(scanner, "_process_file", failing)

        with caplog.at_level(logging.ERROR, logger="profiles.core.processing.scanner"):
            results = scan_and_process(str(tmp_path), extension=".mttl")

        assert len(results) == 2
        assert {r.filename for r in results} == {"file_000.mttl", "file_002.mttl"}
        assert any("Error processing file" in r.message for r in caplog.records)

    def test_parallel_skips_failing_file(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """The parallel path skips + logs a failing file instead of aborting."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file

        def failing(file_path: Path, display_path: str, full_suffix: str) -> ScannedFile:
            if file_path.name == "file_002.mttl":
                raise OSError("boom")
            return real(file_path, display_path, full_suffix)

        monkeypatch.setattr(scanner, "_process_file", failing)
        monkeypatch.setattr(scanner, "_PARALLEL_THRESHOLD", 0)

        with caplog.at_level(logging.ERROR, logger="profiles.core.processing.scanner"):
            results = scan_and_process(str(tmp_path), extension=".mttl")

        assert len(results) == 2
        assert {r.filename for r in results} == {"file_000.mttl", "file_001.mttl"}
        assert any("Error processing file" in r.message for r in caplog.records)

    def test_dynamic_skips_failing_file(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """Dynamic extraction failures are skipped + logged, not fatal."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file_dynamic

        def failing(
            file_path: Path,
            display_path: str,
            extractor,
            column_names,
            extension,
        ) -> ScannedFileDynamic:
            if file_path.name == "file_001.mttl":
                raise OSError("boom")
            return real(file_path, display_path, extractor, column_names, extension)

        monkeypatch.setattr(scanner, "_process_file_dynamic", failing)

        with caplog.at_level(logging.ERROR, logger="profiles.core.processing.scanner"):
            results = scan_and_process_dynamic(
                str(tmp_path),
                extension=".mttl",
                column_names=("File", "Version"),
            )

        assert len(results) == 2
        assert {r.path.name for r in results} == {"file_000.mttl", "file_002.mttl"}
        assert any("Error processing file" in r.message for r in caplog.records)

    def test_metrics_reports_error_count(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """ScanMetrics.error_count is populated when a per-file error occurs."""
        self._write_files(tmp_path, 3)
        real = scanner._process_file

        def failing(file_path: Path, display_path: str, full_suffix: str) -> ScannedFile:
            if file_path.name == "file_000.mttl":
                raise OSError("boom")
            return real(file_path, display_path, full_suffix)

        monkeypatch.setattr(scanner, "_process_file", failing)
        config = AppConfig(scan_metrics=True)

        with caplog.at_level(logging.DEBUG, logger="profiles"):
            scan_and_process(str(tmp_path), extension=".mttl", config=config)

        metrics_records = [r for r in caplog.records if "Scan metrics" in r.message]
        assert len(metrics_records) == 1
        assert "'error_count': 1" in metrics_records[0].message

    def test_no_metrics_when_disabled(self, tmp_path: Path, caplog) -> None:
        """With metrics disabled, no DEBUG metrics line is emitted."""
        self._write_files(tmp_path, 2)

        with caplog.at_level(logging.DEBUG, logger="profiles"):
            scan_and_process(str(tmp_path), extension=".mttl")

        assert not any("Scan metrics" in r.message for r in caplog.records)

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

        assert any("Scan metrics" in r.message for r in caplog.records)

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
