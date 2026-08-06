"""Tests for profiles.core.config.io.yaml_io — round-trip YAML read/write."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.config.io.yaml_io import find_config_file, read_yaml, write_value


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
        with pytest.raises(Exception):
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

    def test_not_found(self, tmp_path: Path) -> None:
        assert find_config_file(start_path=tmp_path) is None
