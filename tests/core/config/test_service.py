"""Tests for profiles.core.config.service — domain operations over AppConfig."""

from __future__ import annotations

from pathlib import Path

from profiles.core.config.models import AppConfig, MachineConfiguration, MatchCriteria
from profiles.core.config.reader import ConfigReader
from profiles.core.config.service import (
    find_configuration_by_hostname,
)


class TestFindConfigurationByHostname:
    """ConfigReader.find_configuration_by_hostname."""

    def test_exact_match(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\n"
            "configs:\n"
            "  c1:\n"
            "    match:\n"
            "      hostname: [PC-01]\n"
            "    scan: [M:/dir1]\n"
            "  c2:\n"
            "    match:\n"
            "      hostname: [PC-02]\n"
            "    scan: [M:/dir2]\n",
            encoding="utf-8",
        )
        reader = ConfigReader(conf)
        config = reader.load()
        result = find_configuration_by_hostname(config, "PC-02")
        assert result is not None
        assert result.scan == ("M:/dir2",)

    def test_case_insensitive(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\nconfigs:\n  c1:\n    match:\n      hostname: [My-Host]\n    scan: [M:/dir]\n",
            encoding="utf-8",
        )
        reader = ConfigReader(conf)
        config = reader.load()
        result = find_configuration_by_hostname(config, "my-host")
        assert result is not None
        assert result.scan == ("M:/dir",)

    def test_no_match_returns_first(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\nconfigs:\n  c1:\n    match:\n      hostname: [PC-01]\n    scan: [M:/dir1]\n",
            encoding="utf-8",
        )
        reader = ConfigReader(conf)
        config = reader.load()
        result = find_configuration_by_hostname(config, "NONEXISTENT")
        assert result is not None
        assert result.match.hostname == ("PC-01",)

    def test_no_configurations(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("version: 1\ndefaults:\n  release: '1.0'\n", encoding="utf-8")
        reader = ConfigReader(conf)
        config = reader.load()
        result = find_configuration_by_hostname(config, "ANYTHING")
        assert result is None

    def test_with_explicit_config(self, tmp_path: Path) -> None:
        """Pass an AppConfig directly instead of loading fresh."""
        config = AppConfig(
            configurations=[
                MachineConfiguration(match=MatchCriteria(hostname=["PC-X"]), scan=["M:/x"]),
            ],
        )
        result = find_configuration_by_hostname(config, "PC-X")
        assert result is not None
        assert result.scan == ("M:/x",)
