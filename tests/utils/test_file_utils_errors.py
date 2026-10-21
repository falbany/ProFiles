"""Tests for scan-error surfacing in file_utils — on_skip contract (Task 3).

``scan_directory`` / ``_scan_subtree`` accept an ``on_skip`` callback that
receives ``(path, error_text)`` for every entry or directory that cannot
be read. Default ``None`` keeps the historical silent behavior.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from profiles.utils.file_utils import _scan_subtree, scan_directory


class TestPermissionSkipReporting:
    """Unreadable subtrees are skipped (other folders still scanned) and reported."""

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
    def test_locked_directory_recursive_scan_directory(self, tmp_path: Path) -> None:
        for rel in ("locked/a.pdf", "open/b.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
        (tmp_path / "locked").chmod(0o000)
        try:
            skips: list[tuple[str, str]] = []
            files = scan_directory(
                str(tmp_path), "", recursive=True, on_skip=lambda p, e: skips.append((p, e))
            )
        finally:
            (tmp_path / "locked").chmod(0o755)

        names = [f.name for f in files]
        assert "b.pdf" in names
        assert "a.pdf" not in names
        assert skips, "on_skip must receive the unreadable directory"
        locked_paths = [p for p, _e in skips]
        assert any("locked" in Path(p).name for p in locked_paths)
        assert all(isinstance(e, str) and e for _p, e in skips)

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
    def test_locked_directory_scan_subtree(self, tmp_path: Path) -> None:
        for rel in ("locked/a.pdf", "open/b.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
        (tmp_path / "locked").chmod(0o000)
        try:
            skips: list[tuple[str, str]] = []
            files = _scan_subtree(tmp_path, "", on_skip=lambda p, e: skips.append((p, e)))
        finally:
            (tmp_path / "locked").chmod(0o755)

        assert any(f.name == "b.pdf" for f in files)
        assert skips

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX chmod semantics")
    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")
    def test_no_callback_keeps_silent_behavior(self, tmp_path: Path) -> None:
        """Default on_skip=None: locked dirs are still silently skipped."""
        for rel in ("locked/a.pdf", "open/b.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
        (tmp_path / "locked").chmod(0o000)
        try:
            files = scan_directory(str(tmp_path), "", recursive=True)
        finally:
            (tmp_path / "locked").chmod(0o755)
        assert [f.name for f in files] == ["b.pdf"]
