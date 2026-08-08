"""Tests for profiles.core.config.service — domain operations over AppConfig."""

from __future__ import annotations

from pathlib import Path

from profiles.core.config import service as config_service
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


class TestDirectoryComboboxValues:
    """config_service.get_directory_combobox_values."""

    def test_returns_directory_entries(self, tmp_path: Path) -> None:
        """Entries include config names and scan paths."""
        from profiles.core.config.service import get_directory_combobox_values

        config = AppConfig(
            configurations=[
                MachineConfiguration(
                    name="prod",
                    match=MatchCriteria(hostname=["prod-host"]),
                    scan=["/prod/path1", "/prod/path2"],
                ),
                MachineConfiguration(
                    name="dev",
                    match=MatchCriteria(hostname=["dev-host"]),
                    scan=["/dev/path"],
                ),
            ],
        )
        entries = get_directory_combobox_values(config)
        labels = [e.label for e in entries]
        assert "prod" in labels
        assert "dev" in labels
        assert "/prod/path1" in labels
        assert "/prod/path2" in labels
        assert "/dev/path" in labels
        # Config entries have multiple paths
        prod_entry = next(e for e in entries if e.label == "prod")
        assert prod_entry.paths == ["/prod/path1", "/prod/path2"]
        assert prod_entry.icon == "📁"
        # Individual path entries
        path_entry = next(e for e in entries if e.label == "/prod/path1")
        assert path_entry.paths == ["/prod/path1"]
        assert path_entry.icon == "📄"

    def test_no_configurations_returns_search_dir(self) -> None:
        """When no configs, falls back to search_dir."""
        from profiles.core.config.service import get_directory_combobox_values

        config = AppConfig(
            configurations=(),
            search_dir="/fallback/dir",
        )
        entries = get_directory_combobox_values(config)
        assert len(entries) == 1
        assert entries[0].label == "/fallback/dir"
        assert entries[0].paths == ["/fallback/dir"]
        assert entries[0].icon == "📄"


class TestFindConfigByName:
    """config_service.find_config_by_name."""

    def test_exact_match(self, tmp_path: Path) -> None:
        from profiles.core.config.service import find_config_by_name

        config = AppConfig(
            configurations=[
                MachineConfiguration(
                    name="Production",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/prod"],
                ),
            ],
        )
        result = find_config_by_name(config, "Production")
        assert result is not None
        assert result.name == "Production"
        assert result.scan == ("/prod",)

    def test_case_insensitive(self, tmp_path: Path) -> None:
        from profiles.core.config.service import find_config_by_name

        config = AppConfig(
            configurations=[
                MachineConfiguration(
                    name="Production",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/prod"],
                ),
            ],
        )
        result = find_config_by_name(config, "production")
        assert result is not None
        assert result.name == "Production"

    def test_no_match_returns_none(self) -> None:
        from profiles.core.config.service import find_config_by_name

        config = AppConfig(
            configurations=[
                MachineConfiguration(
                    name="base",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/base"],
                ),
            ],
        )
        result = find_config_by_name(config, "nonexistent")
        assert result is None

    def test_no_configurations(self) -> None:
        from profiles.core.config.service import find_config_by_name

        config = AppConfig()
        result = find_config_by_name(config, "anything")
        assert result is None


class TestFindActiveConfigByName:
    """config_service.find_active_config with config names."""

    def test_finds_config_by_name(self, tmp_path: Path) -> None:
        """find_active_config resolves a config display name."""
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\n"
            "configs:\n"
            "  prod:\n"
            "    match:\n"
            "      hostname: [prod-host]\n"
            "    scan: [M:/prod_dir]\n"
            "  dev:\n"
            "    match:\n"
            "      hostname: [dev-host]\n"
            "    scan: [M:/dev_dir]\n",
            encoding="utf-8",
        )
        from profiles.core.config.reader import ConfigReader

        reader = ConfigReader(conf)
        config = reader.load()
        result = config_service.find_active_config(config, "prod")
        assert result is not None
        assert result.scan == ("M:/prod_dir",)


class TestAutoSelectDirectoryWithName:
    """config_service.auto_select_directory returns config name."""

    def test_returns_config_name_on_match(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\n"
            "configs:\n"
            "  prod:\n"
            "    match:\n"
            "      hostname: [prod-host]\n"
            "    scan: [M:/prod_dir]\n",
            encoding="utf-8",
        )
        from profiles.core.config.reader import ConfigReader

        reader = ConfigReader(conf)
        config = reader.load()
        result = config_service.auto_select_directory(config, "prod-host")
        assert result == "prod"

    def test_returns_first_config_when_no_hostname_match(self, tmp_path: Path) -> None:
        """Falls back to config name when hostname doesn't match."""
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\n"
            "configs:\n"
            "  prod:\n"
            "    match:\n"
            "      hostname: [non-existent]\n"
            "    scan: [M:/fallback_dir]\n",
            encoding="utf-8",
        )
        from profiles.core.config.reader import ConfigReader

        reader = ConfigReader(conf)
        config = reader.load()
        result = config_service.auto_select_directory(config, "other-host")
        assert result == "prod"


class TestConfigNameFromYaml:
    """Verify the optional `name:` YAML key overrides the dict key."""

    def test_yaml_name_overrides_dict_key(self, tmp_path: Path) -> None:
        config = AppConfig(
            configurations=[
                MachineConfiguration(
                    name="Production",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/prod"],
                ),
            ],
        )
        result = config_service.find_config_by_name(config, "Production")
        assert result is not None
        assert result.name == "Production"

    def test_find_config_by_name_after_yaml_load(self, tmp_path: Path) -> None:
        """End-to-end: load a .profiles file with `name:` and verify lookup."""
        conf = tmp_path / ".profiles"
        conf.write_text(
            "version: 1\n"
            "configs:\n"
            "  prod:\n"
            "    name: Production\n"
            "    match:\n"
            "      hostname: [prod-host]\n"
            "    scan:\n"
            "      - M:/dir1\n"
            "      - M:/dir2\n",
            encoding="utf-8",
        )
        from profiles.core.config.reader import ConfigReader

        reader = ConfigReader(conf)
        config = reader.load()
        assert config.configurations[0].name == "Production"
        result = config_service.find_config_by_name(config, "Production")
        assert result is not None
        assert result.scan == ("M:/dir1", "M:/dir2")


class TestMultiPathScanDisplay:
    """Verify all scan paths are preserved in combobox entries."""

    def test_config_group_preserves_all_scan_paths(self) -> None:
        """Config group entry includes all scan paths and individual paths appear."""
        config = AppConfig(
            search_dir="/shared/path",
            configurations=[
                MachineConfiguration(
                    name="prod",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/shared/path", "/unique/path"],
                ),
            ],
        )
        entries = config_service.get_directory_combobox_values(config)
        # The config group should have BOTH scan paths
        prod_entry = next(e for e in entries if e.label == "prod")
        assert prod_entry.paths == ["/shared/path", "/unique/path"]
        assert prod_entry.icon == "📁"
        # Individual path entries for the non-search_dir path
        assert "/unique/path" in [e.label for e in entries]
        unique_entry = next(e for e in entries if e.label == "/unique/path")
        assert unique_entry.icon == "📄"
        assert unique_entry.paths == ["/unique/path"]

    def test_multiple_configs_all_paths_displayed(self) -> None:
        """Each config group shows its own scan paths, plus individual entries."""
        config = AppConfig(
            configurations=[
                MachineConfiguration(
                    name="prod",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/prod1", "/prod2"],
                ),
                MachineConfiguration(
                    name="dev",
                    match=MatchCriteria(hostname=["*"]),
                    scan=["/dev1", "/dev2"],
                ),
            ],
        )
        entries = config_service.get_directory_combobox_values(config)
        prod_entry = next(e for e in entries if e.label == "prod")
        dev_entry = next(e for e in entries if e.label == "dev")
        assert prod_entry.paths == ["/prod1", "/prod2"]
        assert dev_entry.paths == ["/dev1", "/dev2"]
        # Individual path entries also present
        labels = [e.label for e in entries]
        for p in ("/prod1", "/prod2", "/dev1", "/dev2"):
            assert p in labels
