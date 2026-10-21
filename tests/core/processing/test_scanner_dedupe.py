"""Characterization + regression tests for dedupe gating — Task 6.

Pins: single roots never deduplicate; overlapping roots (``A`` and
``A/sub``) yield each file exactly once with the union count. These pass
on the current code (they are written BEFORE the `dedupe` change to
protect it).
"""

from __future__ import annotations

from pathlib import Path

from profiles.core.processing.scanner import _scan_and_filter, scan_and_process


class TestSingleRootNoDedupe:
    """A single root yields each nested file exactly once."""

    def test_nested_folders_each_file_once(self, tmp_path: Path) -> None:
        for rel in ("a.pdf", "one/b.pdf", "one/two/c.pdf", "one/two/d.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

        files = list(_scan_and_filter(str(tmp_path), recursive=True))

        rels = sorted(f.relative_to(tmp_path).as_posix() for f, _d, _s in files)
        assert rels == ["a.pdf", "one/b.pdf", "one/two/c.pdf", "one/two/d.pdf"]

    def test_nested_folders_each_file_once_scan_and_process(self, tmp_path: Path) -> None:
        for rel in ("a.pdf", "one/b.pdf", "one/two/c.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

        results = scan_and_process(str(tmp_path), recursive=True)
        assert [r.filename for r in results] == ["a.pdf", "one/b.pdf", "one/two/c.pdf"]


class TestOverlappingRootsDedupe:
    """``A`` and ``A/sub`` yield each file exactly once (union count)."""

    def test_overlapping_roots_yield_each_file_once(self, tmp_path: Path) -> None:
        root_a = tmp_path / "a"
        root_a.mkdir(parents=True)
        (root_a / "shared.pdf").write_text("x", encoding="utf-8")
        (root_a / "a_only.pdf").write_text("x", encoding="utf-8")
        (root_a / "sub").mkdir()
        (root_a / "sub" / "sub_only.pdf").write_text("x", encoding="utf-8")

        scan_a = scan_and_process(str(root_a), recursive=True)
        scan_sub = scan_and_process(str(root_a / "sub"), recursive=True)
        combined = scan_and_process([str(root_a), str(root_a / "sub")], recursive=True)

        rel = lambda r: Path(r.path).relative_to(tmp_path).as_posix()  # noqa: E731
        names_a = {rel(r) for r in scan_a}
        names_sub = {rel(r) for r in scan_sub}
        names_combined = [rel(r) for r in combined]

        # Each file appears exactly once; count equals the union of the two scans
        assert len(set(names_combined)) == len(names_combined)
        assert set(names_combined) == names_a | names_sub
        assert len(names_combined) == len(names_a | names_sub)
