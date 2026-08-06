"""Tests for profiles.core.config.schema — Pydantic YAML schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from profiles.core.config.schema import (
    AppConfigYaml,
    ConfigError,
    Defaults,
    HookEntry,
    MachineConfig,
    RowColor,
)


class TestConfigError:
    def test_fields(self) -> None:
        err = ConfigError("configs.production.extends", "unknown config 'ghost'")
        assert err.path == "configs.production.extends"
        assert "unknown config 'ghost'" in str(err)


class TestRowColor:
    def test_valid_color(self) -> None:
        rc = RowColor(pattern="TMP", color="#BAC015")
        assert rc.color == "#BAC015"

    def test_invalid_color_raises(self) -> None:
        with pytest.raises(ValidationError):
            RowColor(pattern="TMP", color="BAC015")  # missing '#'
        with pytest.raises(ValidationError):
            RowColor(pattern="TMP", color="#12345")  # wrong length


class TestHookEntry:
    def test_default_when_is_before(self) -> None:
        assert HookEntry(command="x").when == "before"

    def test_invalid_when_raises(self) -> None:
        with pytest.raises(ValidationError):
            HookEntry(when="sideways", command="x")


class TestDefaults:
    def test_defaults(self) -> None:
        d = Defaults()
        assert d.extensions == ["All", ".lnk"]
        assert d.filters == ["", "ST_PRO", "ST_ENG"]
        assert d.theme == "light"
        assert d.verbose == "INFO"


class TestAppConfigYaml:
    def test_empty(self) -> None:
        cfg = AppConfigYaml()
        assert cfg.version == 1
        assert cfg.configs == {}

    def test_config_name_is_dict_key(self) -> None:
        cfg = AppConfigYaml(configs={"prod": MachineConfig(pc_hostname="PC1")})
        assert "prod" in cfg.configs
        assert cfg.configs["prod"].pc_hostname == "PC1"
