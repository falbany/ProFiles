"""Tests for per-directory scan failure scope — Task 3.

Directory-level failures keep ``events.scan_failed`` (WARNING) while
per-entry skips surface via ``events.scan_skipped`` (DEBUG); a failure on
one root must not abort the other roots.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import profiles.core.processing.scanner as scanner
from profiles.core.processing.scanner import is_simple_extension, scan_and_process


class TestScanFailureScope:
    """One failing root does not abort the remaining roots."""

    def test_second_root_failure_keeps_first_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        root_a = tmp_path / "a"
        root_b = tmp_path / "b"
        for rel in ("a/f1.pdf", "b/f2.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

        real_scan_directory = scanner.scan_directory

        def flaky_scan_directory(directory: object, *args: object, **kwargs: object) -> list[Path]:
            if str(directory) == str(root_b):
                raise RuntimeError("boom: unreadable root")
            return real_scan_directory(directory, *args, **kwargs)

        monkeypatch.setattr(scanner, "scan_directory", flaky_scan_directory)

        with caplog.at_level(logging.DEBUG):
            results = scan_and_process([str(root_a), str(root_b)], recursive=True)

        assert [r.filename for r in results] == ["f1.pdf"]
        assert any("SCAN_FAILED" in rec.message for rec in caplog.records)

    def test_resolve_error_skips_single_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Per-file resolve failure skips that file (DEBUG) — multi-root scan.

        Path resolution only runs when dedupe is active (several roots);
        a single-root scan can never duplicate a file, so it never
        resolves (Task 6). Two identical roots keep dedupe on here.
        """
        root = tmp_path / "scan"
        root.mkdir()
        (root / "good.pdf").write_text("x", encoding="utf-8")
        (root / "bad.pdf").write_text("x", encoding="utf-8")
        bad = root / "bad.pdf"

        original_resolve = Path.resolve

        def flaky_resolve(self: Path, *args: object, **kwargs: object) -> Path:  # type: ignore[no-untyped-def]
            if str(self) == str(bad):
                raise OSError("resolved link out of scope")
            return original_resolve(self)

        monkeypatch.setattr(Path, "resolve", flaky_resolve)

        with caplog.at_level(logging.DEBUG):
            results = scan_and_process([str(root), str(root)])

        assert [r.filename for r in results] == ["good.pdf"]
        assert any("SCAN_SKIPPED" in rec.message for rec in caplog.records)


class TestSimpleExtensionGuard:
    """Guard the module surface touched by Task 3 (unchanged behavior)."""

    def test_is_simple_extension(self) -> None:
        assert is_simple_extension("pdf") is True
