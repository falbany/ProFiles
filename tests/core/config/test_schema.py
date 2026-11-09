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
    MatchCriteriaSchema,
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
        assert d.filters == ["", "PROD", "DEV"]
        assert d.theme == "auto"
        assert d.verbose == "INFO"

    def test_unknown_key_raises(self) -> None:
        # extra="forbid": a typo or a key that only exists in old docs
        # (e.g. `columns:` under defaults) must fail loudly, not be ignored.
        with pytest.raises(ValidationError) as exc_info:
            Defaults(columns="File, Version")
        assert "columns" in str(exc_info.value)


class TestAppConfigYaml:
    def test_empty(self) -> None:
        cfg = AppConfigYaml()
        assert cfg.version == 1
        assert cfg.configs == {}

    def test_config_name_is_dict_key(self) -> None:
        cfg = AppConfigYaml(
            configs={"prod": MachineConfig(match=MatchCriteriaSchema(hostname=["PC1"]))}
        )
        assert "prod" in cfg.configs
        assert cfg.configs["prod"].match.hostname == ["PC1"]


class TestMatchCriteriaSchema:
    def test_valid_glob_and_regex(self) -> None:
        schema = MatchCriteriaSchema(
            hostname=["WORKSTATION-*", "re:^station-\\d+$"],
            ip=["192.168.1.*"],
            path=["re:^/data/.*"],
        )
        assert len(schema.hostname) == 2
        assert schema.ip == ["192.168.1.*"]
        assert schema.path == ["re:^/data/.*"]

    def test_invalid_regex_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError) as exc:
            MatchCriteriaSchema(hostname=["re:([unclosed"])
        assert "invalid regex pattern" in str(exc.value)
        assert "re:([unclosed" in str(exc.value)

    def test_invalid_regex_in_ip_and_path_raises(self) -> None:
        with pytest.raises(ValidationError) as exc_ip:
            MatchCriteriaSchema(ip=["re:*bad"])
        assert "invalid regex pattern" in str(exc_ip.value)

        with pytest.raises(ValidationError) as exc_path:
            MatchCriteriaSchema(path=["re:[unclosed"])
        assert "invalid regex pattern" in str(exc_path.value)
