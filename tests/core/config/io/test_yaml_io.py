"""Tests for profiles.core.config.io.yaml_io — round-trip YAML read/write."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.config.io.yaml_io import (
    _is_unsafe_search_root,
    find_config_file,
    read_yaml,
    write_value,
)


class TestReadYaml:
    def test_reads_mapping(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("version: 1\ndefaults:\n  theme: dark\n", encoding="utf-8")
        data = read_yaml(conf)
        assert data["version"] == 1
        assert data["defaults"]["theme"] == "dark"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_yaml(tmp_path / "nope.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("defaults: [unclosed\n", encoding="utf-8")
        with pytest.raises((ValueError, Exception)):
            read_yaml(conf)


class TestWriteValue:
    def test_updates_nested_key_preserves_comment(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "# header comment\ndefaults:\n  theme: light  # the theme\n",
            encoding="utf-8",
        )
        write_value(conf, "defaults.theme", "dark")
        content = conf.read_text(encoding="utf-8")
        assert "theme: dark" in content
        assert "# header comment" in content
        assert "# the theme" in content

    def test_updates_boolean(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("defaults:\n  recursive_search: false\n", encoding="utf-8")
        write_value(conf, "defaults.recursive_search", True)
        content = conf.read_text(encoding="utf-8")
        assert "recursive_search: true" in content

    def test_missing_file_creates(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        write_value(conf, "defaults.theme", "dark")
        content = conf.read_text(encoding="utf-8")
        assert "theme: dark" in content


class TestFindConfigFile:
    def test_found_in_start_dir(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == conf

    def test_found_in_subdir(self, tmp_path: Path) -> None:
        conf = tmp_path / "deep" / "nested" / ".profiles"
        conf.parent.mkdir(parents=True)
        conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == conf

    def test_yaml_fallback_found(self, tmp_path: Path) -> None:
        """The .profiles.yaml fallback is found when no primary exists."""
        conf = tmp_path / ".profiles.yaml"
        conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == conf

    def test_yml_fallback_found(self, tmp_path: Path) -> None:
        """The .profiles.yml fallback is found when no other config exists."""
        conf = tmp_path / ".profiles.yml"
        conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == conf

    def test_primary_beats_yaml_fallback(self, tmp_path: Path) -> None:
        """A .profiles anywhere in the tree beats a .profiles.yaml at the root."""
        (tmp_path / ".profiles.yaml").write_text("version: 1\n", encoding="utf-8")
        deep = tmp_path / "sub" / ".profiles"
        deep.parent.mkdir()
        deep.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == deep

    def test_yaml_beats_yml_fallback(self, tmp_path: Path) -> None:
        """When both fallbacks exist, .profiles.yaml wins over .profiles.yml."""
        (tmp_path / ".profiles.yml").write_text("version: 1\n", encoding="utf-8")
        yaml_conf = tmp_path / "sub" / ".profiles.yaml"
        yaml_conf.parent.mkdir()
        yaml_conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == yaml_conf

    def test_closest_to_root_wins_within_a_tier(self, tmp_path: Path) -> None:
        """Within one tier, the shallowest match wins."""
        (tmp_path / "deep" / "deeper" / ".profiles").parent.mkdir(parents=True)
        deep = tmp_path / "deep" / "deeper" / ".profiles"
        deep.write_text("version: 1\n", encoding="utf-8")
        shallow = tmp_path / "sub" / ".profiles"
        shallow.parent.mkdir()
        shallow.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == shallow

    def test_not_found(self, tmp_path: Path) -> None:
        assert find_config_file(start_path=tmp_path) is None


class TestFilesystemRootGuard:
    """find_config_file must never walk the filesystem root as a search root.

    Briefcase bundles launch with ``CWD=/``; a depth-N subtree scan from
    there walks the entire disk (observed as a multi-minute stall in the
    bundled app before any window opens).
    """

    def test_root_predicate_flags_filesystem_roots(self) -> None:
        assert _is_unsafe_search_root(Path("/")) is True
        assert _is_unsafe_search_root(Path.home()) is False
        assert _is_unsafe_search_root(Path("/Users")) is False

    def test_find_config_file_never_scans_filesystem_root(self) -> None:
        """A root start path yields no config immediately — no disk walk."""
        assert find_config_file(start_path=Path("/")) is None
