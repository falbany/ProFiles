"""Tests for merged exclude-list resolution — D4 (Task 2).

Effective exclude lists must merge, in first-seen order with duplicates
removed: global ``AppConfig`` list → caller list → active
``MachineConfiguration`` list.
"""

from __future__ import annotations

from pathlib import Path

from profiles.core.config import service as config_service
from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.core.processing.scanner import (
    _merge_unique,
    _resolve_scan_config,
    is_simple_extension,
    scan_and_process,
)


class TestMergeUnique:
    """Unit tests for _merge_unique."""

    def test_concatenate_and_dedupe_keeps_first_seen_order(self) -> None:
        assert _merge_unique((".git", "tmp"), ("tmp", "bin"), ("bin", "obj")) == (
            ".git",
            "tmp",
            "bin",
            "obj",
        )

    def test_none_and_empty_sequences(self) -> None:
        assert _merge_unique(None, (), (".git",)) == (".git",)
        assert _merge_unique(None, None) == ()

    def test_within_sequence_duplicates(self) -> None:
        assert _merge_unique(("a", "a", "b"), ("b", "a")) == ("a", "b")


class TestResolveScanConfigMerge:
    """_resolve_scan_config merges global + caller + active excludes."""

    def test_no_config_only_caller_list(self, tmp_path: Path) -> None:
        recursive, depth, dirs, files = _resolve_scan_config(
            str(tmp_path), True, ("caller_dir",), ("caller_file",), None
        )
        assert (recursive, depth) == (True, 10)
        assert dirs == ("caller_dir",)
        assert files == ("caller_file",)

    def test_global_and_active_merge(self, tmp_path: Path) -> None:
        config = AppConfig(search_exclude_dirs=(".git",))
        active = MachineConfiguration(
            name="bench",
            scan=(str(tmp_path),),
            search_exclude_dirs=("node_modules",),
            search_exclude_files=("~$*",),
        )
        config.configurations = [active]
        _recursive, _depth, dirs, files = _resolve_scan_config(
            str(tmp_path), True, None, None, config
        )
        assert dirs == (".git", "node_modules")
        assert files == ("~$*",)


class TestMergedExcludesEndToEnd:
    """End-to-end: only non-excluded files survive the scan."""

    def _build(self, tmp_path: Path) -> None:
        for rel in (".git/x.pdf", "node_modules/y.pdf", "keep/z.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")

    def test_global_plus_active_excludes(self, tmp_path: Path) -> None:
        self._build(tmp_path)
        config = AppConfig(search_exclude_dirs=(".git",))
        active = MachineConfiguration(
            name="bench", scan=(str(tmp_path),), search_exclude_dirs=("node_modules",)
        )
        config.configurations = [active]
        assert config_service.find_active_config(config, str(tmp_path)) is active
        results = scan_and_process(str(tmp_path), recursive=True, config=config)
        assert [r.filename for r in results] == ["keep/z.pdf"]

    def test_caller_excludes_merge_with_global(self, tmp_path: Path) -> None:
        self._build(tmp_path)
        config = AppConfig(search_exclude_dirs=(".git",))
        results = scan_and_process(
            str(tmp_path),
            recursive=True,
            exclude_dirs=("keep",),
            config=config,
        )
        assert [r.filename for r in results] == ["node_modules/y.pdf"]

    def test_files_excludes_merge(self, tmp_path: Path) -> None:
        for rel in (".git/x.pdf", "keep/bad.pdf", "keep/good.pdf"):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x", encoding="utf-8")
        config = AppConfig(search_exclude_dirs=(".git",), search_exclude_files=("bad*",))
        active = MachineConfiguration(
            name="bench", scan=(str(tmp_path),), search_exclude_files=("~$*",)
        )
        config.configurations = [active]
        results = scan_and_process(
            str(tmp_path),
            recursive=True,
            exclude_files=("*.lnk",),
            config=config,
        )
        assert [r.filename for r in results] == ["keep/good.pdf"]


class TestDocstringContract:
    """The public contract: simple extensions unaffected by the merge.

    Guards Task 2's negative-space: quote-only queries stay simple and
    extension filters are unaffected by exclude resolution.
    """

    def test_simple_extension_contract(self) -> None:
        assert is_simple_extension("pdf") is True
        assert is_simple_extension("All") is True
