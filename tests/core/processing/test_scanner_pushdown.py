"""Scanner pushdown tests — Task 7: name filtering happens inside the scan.

``scan_directory`` accepts a ``name_filter`` applied to every file's
``entry.name`` after the file check and before the Path is built. The
scanner builds the predicate from the extension expression
(``match_filter(suffix_of_name(name), extension)``) and removes its own
post-scan check.
"""

from __future__ import annotations

from pathlib import Path

from profiles.core.processing.scanner import scan_and_process
from profiles.utils.file_utils import scan_directory


class TestNameFilterPushdown:
    """The name_filter callback sees every file name exactly once."""

    def test_filter_called_once_per_file(self, tmp_path: Path) -> None:
        for rel in ("a.pdf", "one/b.pdf", "one/two/c.pdf", "skip.txt"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

        seen: list[str] = []

        def record(name: str) -> bool:
            seen.append(name)
            return True

        files = scan_directory(str(tmp_path), "", recursive=True, name_filter=record)

        returned = sorted(Path(f).name for f in files)
        assert returned == ["a.pdf", "b.pdf", "c.pdf", "skip.txt"]
        assert sorted(seen) == returned
        assert seen.count("a.pdf") == 1

    def test_filter_false_drops_file(self, tmp_path: Path) -> None:
        for rel in ("keep.pdf", "drop.pdf"):
            p = tmp_path / rel
            p.write_text("x", encoding="utf-8")

        files = scan_directory(str(tmp_path), "", name_filter=lambda n: n != "drop.pdf")

        assert sorted(Path(f).name for f in files) == ["keep.pdf"]

    def test_no_filter_is_passthrough(self, tmp_path: Path) -> None:
        for rel in ("keep.pdf", "drop.pdf"):
            p = tmp_path / rel
            p.write_text("x", encoding="utf-8")

        unfiltered = scan_directory(str(tmp_path), "")
        filtered = scan_directory(str(tmp_path), "", name_filter=lambda _n: True)

        assert [p.name for p in filtered] == [p.name for p in unfiltered]


class TestScannerBuildsPredicate:
    """The scanner pushes the extension filter down; output is unchanged."""

    def test_extension_scan_matches_unfiltered_pipeline(self, tmp_path: Path) -> None:
        for rel in ("doc.pdf", "doc_upper.PDF", "other.mttl", "only.pdf.bak"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

        expect_all = scan_and_process(str(tmp_path), recursive=True)
        expect_pdf = [
            r
            for r in scan_and_process(str(tmp_path), recursive=True)
            if "pdf" in "".join(r.path.suffixes).lower()
        ]

        pdf_results = scan_and_process(str(tmp_path), extension="pdf", recursive=True)

        assert [r.path for r in pdf_results] == [r.path for r in expect_pdf]
        # D1: substring matching — `pdf` matches `only.pdf.bak`
        assert "only.pdf.bak" in {Path(r.path).name for r in pdf_results}
        assert len(expect_all) == 4
