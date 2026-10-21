"""Unit tests for the shared entry classifier — Task 10.

``_classify`` returns ``("dir", path)`` to descend, ``("file", path)``
for a matching file, or ``None`` to skip — one implementation replacing
the three duplicated entry checks.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from profiles.utils.file_utils import _classify


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "sub").mkdir()
    (tmp_path / "match.pdf").write_text("x", encoding="utf-8")
    (tmp_path / "nope.txt").write_text("x", encoding="utf-8")
    (tmp_path / "skipme").mkdir()
    (tmp_path / "bad.pdf").write_text("x", encoding="utf-8")
    (tmp_path / "link.pdf").symlink_to(tmp_path / "match.pdf")
    return tmp_path


def _entry(root: Path, name: str) -> os.DirEntry[str]:
    with os.scandir(root) as entries:
        for e in entries:
            if e.name == name:
                return e
    raise KeyError(name)


class TestClassify:
    """One classifier, one contract."""

    def test_matching_file(self, tree: Path) -> None:
        tag, path = _classify(_entry(tree, "match.pdf"), "pdf", (), (), None, None)
        assert tag == "file"
        assert path == tree / "match.pdf"

    def test_non_matching_file(self, tree: Path) -> None:
        assert _classify(_entry(tree, "nope.txt"), "pdf", (), (), None, None) is None

    def test_directory(self, tree: Path) -> None:
        tag, path = _classify(_entry(tree, "sub"), "pdf", (), (), None, None)
        assert tag == "dir"
        assert path == tree / "sub"

    def test_excluded_directory(self, tree: Path) -> None:
        assert _classify(_entry(tree, "skipme"), "pdf", ("skipme",), (), None, None) is None

    def test_excluded_file(self, tree: Path) -> None:
        assert _classify(_entry(tree, "bad.pdf"), "pdf", (), ("bad*",), None, None) is None

    def test_symlink_to_file_return_none(self, tree: Path) -> None:
        # follow_symlinks=False: symlinks are never files or dirs here
        assert _classify(_entry(tree, "link.pdf"), "pdf", (), (), None, None) is None

    def test_name_filter_false_skips(self, tree: Path) -> None:
        assert _classify(_entry(tree, "match.pdf"), "pdf", (), (), lambda _n: False, None) is None

    def test_name_filter_true_keeps(self, tree: Path) -> None:
        tag, _path = _classify(_entry(tree, "match.pdf"), "pdf", (), (), lambda _n: True, None)
        assert tag == "file"

    def test_report_skip_through_on_skip(self, tree: Path) -> None:
        class Boom:
            @property
            def name(self) -> str:
                return "boom.pdf"

            def is_file(self, follow_symlinks: bool = True) -> bool:  # noqa: ARG002
                raise PermissionError("locked")

            def is_dir(self, follow_symlinks: bool = True) -> bool:  # noqa: ARG002
                raise PermissionError("locked")

            @property
            def path(self) -> str:
                return str(tree / "boom.pdf")

        skips: list[tuple[str, str]] = []
        result = _classify(Boom(), "pdf", (), (), None, lambda p, e: skips.append((p, e)))
        assert result is None
        assert skips and "locked" in skips[0][1]
