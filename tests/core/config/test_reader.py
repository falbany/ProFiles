"""Tests for profiles.core.config.reader — ConfigReader YAML loading."""

from __future__ import annotations

from pathlib import Path

from profiles.core.config.reader import ConfigReader


def _write_yaml(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestConfigReader:
    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = ConfigReader(tmp_path / ".profiles").load()
        assert config.extensions == ("All", ".lnk")
        assert config.config_path == tmp_path / ".profiles"

    def test_loads_defaults(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles",
            "defaults:\n  theme: dark\n  recursive_search: true\n",
        )
        config = ConfigReader(conf).load()
        assert config.theme == "dark"
        assert config.recursive_search is True

    def test_loads_columns(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles",
            "columns:\n  Version:\n    name: Version Number\n    width: 80\n"
            "    stretch: false\n    match: '[-_]V(\\d+)'\n    priority: 10\n",
        )
        config = ConfigReader(conf).load()
        assert "Version" in config.columns
        assert config.columns["Version"].width == 80
        assert config.columns["Version"].match == r"[-_]V(\d+)"
        assert config.columns["Version"].stretch is False
        assert config.columns["Version"].name == "Version Number"
        assert config.column_names == ("File", "Version")
        assert config.column_stretches == (False, False)
        assert config.column_headers == ("File", "Version Number")

    def test_loads_configs_with_inheritance(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles",
            "defaults:\n  extensions: [All, .lnk]\n"
            "configs:\n"
            "  base:\n    directory: /base\n"
            "  prod:\n    extends: base\n    pc_hostname: PC1\n",
        )
        config = ConfigReader(conf).load()
        assert len(config.configurations) == 2
        prod = next(c for c in config.configurations if c.pc_hostname == "PC1")
        assert prod.directory == "/base"
        # extensions resolved = defaults merged (no local/inherited extensions)
        assert prod.extensions == ("All", ".lnk")

    def test_loads_hooks(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles",
            "hooks:\n  failmode: abort\n  timeout: 10\n"
            "  entries:\n    '.mttl':\n      - action: run\n        content: 'x {{path}}'\n",
        )
        config = ConfigReader(conf).load()
        assert config.launch_hook_failmode == "abort"
        assert config.launch_hook_timeout == 10
        assert ".mttl" in config.launch_hooks
        assert config.launch_hooks[".mttl"][0].content == "x {{path}}"
