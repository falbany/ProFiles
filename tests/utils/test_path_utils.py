"""Tests for profiles.utils.path_utils."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from profiles.utils.path_utils import normalize_user_path


def test_mapped_drive_letter_is_preserved_verbatim() -> None:
    """A Windows mapped-drive path must NOT be canonicalized to its UNC target.

    Path.resolve() on Windows rewrites ``M:/projects`` to
    ``\\\\server\\share\\projects``; the whole point of normalize_user_path
    is to keep the configured drive-letter form. Separators are compared
    slash-insensitively because os.path.normpath only backslash-normalizes
    on Windows.
    """
    result = str(normalize_user_path("M:/projects"))
    assert result.replace("\\", "/") == "M:/projects"
    assert "UNC" not in result


def test_unc_path_is_left_untouched() -> None:
    """An already-UNC path passes through without further rewriting."""
    raw = "\\\\server\\share\\projects"
    assert str(normalize_user_path(raw)) == raw


def test_expanduser_is_applied() -> None:
    result = normalize_user_path("~/programs")
    assert not str(result).startswith("~")
    assert result == Path.home() / "programs"


def test_redundant_separators_and_dotdot_are_collapsed(tmp_path: Path) -> None:
    target_file = tmp_path / "file.txt"
    target_file.write_text("x", encoding="utf-8")
    messy = os.path.join(str(tmp_path), "sub", "..", "file.txt")
    assert normalize_user_path(messy) == target_file


def test_symlink_is_not_resolved(tmp_path: Path) -> None:
    """Symlinks stay intact — the regression test for the resolve() policy.

    resolve() collapses the link to its target; normalize_user_path must
    return the link path itself. Asserting the two differ proves resolve()
    was not called under the hood (true on every platform).
    """
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "app.mttl").write_text("launchable", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(real_dir, target_is_directory=True)

    result = normalize_user_path(link / "app.mttl")

    assert result == link / "app.mttl"
    assert result != (link / "app.mttl").resolve()


def test_relative_path_is_not_made_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only expanduser + normpath run: no implicit cwd anchoring."""
    monkeypatch.chdir(tmp_path)
    assert normalize_user_path("sub/dir") == Path("sub/dir")


def test_path_object_input_is_accepted(tmp_path: Path) -> None:
    assert normalize_user_path(tmp_path) == tmp_path
