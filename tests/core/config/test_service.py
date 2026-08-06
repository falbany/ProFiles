"""Tests for profiles.core.config.service — domain operations over AppConfig."""

from __future__ import annotations

from pathlib import Path

from profiles.config import (
    AppConfig,
    ConfigReader,
    MachineConfiguration,
)


class TestFindConfigurationByHostname:
    """ConfigReader.find_configuration_by_hostname."""

    def test_exact_match(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\n"
            "configs:\n"
            "  c1:\n"
            "    pc_hostname: PC-01\n"
            "    directory: M:/dir1\n"
            "  c2:\n"
            "    pc_hostname: PC-02\n"
            "    directory: M:/dir2\n",
            encoding="utf-8",
        )
        reader = ConfigReader(conf)
        result = reader.find_configuration_by_hostname("PC-02")
        assert result is not None
        assert result.directory == "M:/dir2"

    def test_case_insensitive(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\nconfigs:\n  c1:\n    pc_hostname: My-Host\n    directory: M:/dir\n",
            encoding="utf-8",
        )
        reader = ConfigReader(conf)
        result = reader.find_configuration_by_hostname("my-host")
        assert result is not None
        assert result.directory == "M:/dir"

    def test_no_match_returns_first(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\nconfigs:\n  c1:\n    pc_hostname: PC-01\n    directory: M:/dir1\n",
            encoding="utf-8",
        )
        reader = ConfigReader(conf)
        result = reader.find_configuration_by_hostname("NONEXISTENT")
        assert result is not None
        assert result.pc_hostname == "PC-01"

    def test_no_configurations(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("version: 1\ndefaults:\n  release: '1.0'\n", encoding="utf-8")
        reader = ConfigReader(conf)
        result = reader.find_configuration_by_hostname("ANYTHING")
        assert result is None

    def test_with_explicit_config(self, tmp_path: Path) -> None:
        """Pass an AppConfig directly instead of loading fresh."""
        config = AppConfig(
            configurations=[
                MachineConfiguration(pc_hostname="PC-X", directory="M:/x"),
            ],
        )
        reader = ConfigReader(tmp_path / "dummy")
        result = reader.find_configuration_by_hostname("PC-X", config=config)
        assert result is not None
        assert result.directory == "M:/x"
