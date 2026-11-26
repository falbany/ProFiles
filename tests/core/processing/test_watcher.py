"""Tests for profiles.core.processing.watcher — snapshot_dir_mtimes."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.processing.watcher import snapshot_dir_mtimes


class TestSnapshotDirMtimes:
    """Tests for core.watcher.snapshot_dir_mtimes."""

    def test_snapshot_includes_root_and_subdirectories(self, tmp_path: Path) -> None:
        """The snapshot keys cover the root and every first-level subdirectory."""
        sub = tmp_path / "sub"
        sub.mkdir()

        snapshot = snapshot_dir_mtimes(tmp_path)

        assert set(snapshot) == {str(tmp_path), str(sub)}
        assert all(mtime > 0 for mtime in snapshot.values())

    def test_snapshot_excluded_dirs_pruned(self, tmp_path: Path) -> None:
        """An excluded directory (and its whole subtree) never enters the snapshot."""
        excluded_child = tmp_path / "node_modules" / "x"
        excluded_child.mkdir(parents=True)
        keep = tmp_path / "keep"
        keep.mkdir()

        snapshot = snapshot_dir_mtimes(tmp_path, exclude_dirs=("node_modules",))

        assert str(tmp_path / "node_modules") not in snapshot
        assert str(excluded_child) not in snapshot
        assert str(keep) in snapshot

    def test_snapshot_case_insensitive_exclusion(self, tmp_path: Path) -> None:
        """Pattern matching is case-insensitive, like the scan walk's excludes."""
        excluded = tmp_path / "node_modules"
        excluded.mkdir()
        (excluded / "f.txt").write_text("x")

        snapshot = snapshot_dir_mtimes(tmp_path, exclude_dirs=("Node_Modules",))

        assert str(excluded) not in snapshot

    def test_snapshot_max_depth_zero_root_only(self, tmp_path: Path) -> None:
        """max_depth=0 descends nowhere: the snapshot holds the root alone."""
        (tmp_path / "sub").mkdir()

        snapshot = snapshot_dir_mtimes(tmp_path, max_depth=0)

        assert set(snapshot) == {str(tmp_path)}

    def test_snapshot_max_depth_limits_descent(self, tmp_path: Path) -> None:
        """max_depth=1 keeps root + first-level dirs; deeper dirs are absent."""
        first = tmp_path / "a"
        second = first / "b"
        second.mkdir(parents=True)

        snapshot = snapshot_dir_mtimes(tmp_path, max_depth=1)

        assert set(snapshot) == {str(tmp_path), str(first)}
        assert str(second) not in snapshot

    def test_snapshot_missing_root_raises(self, tmp_path: Path) -> None:
        """A nonexistent root raises OSError (never a silent empty snapshot)."""
        with pytest.raises(OSError):
            snapshot_dir_mtimes(tmp_path / "nope")
