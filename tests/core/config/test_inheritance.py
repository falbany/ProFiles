"""Tests for profiles.core.config.inheritance — defaults + extends resolution."""

from __future__ import annotations

import pytest

from profiles.core.config.inheritance import resolve_configs
from profiles.core.config.schema import AppConfigYaml, ConfigError, MachineConfig


def _cfg(**kwargs) -> AppConfigYaml:
    return AppConfigYaml(**kwargs)


class TestResolveConfigs:
    def test_defaults_applied(self) -> None:
        cfg = _cfg(
            defaults={"extensions": ["All", ".lnk"], "filters": ["", "ST_PRO"]},
            configs={"base": {"directory": "/x"}},
        )
        resolved = resolve_configs(cfg)
        assert resolved["base"].extensions == ["All", ".lnk"]
        assert resolved["base"].filters == ["", "ST_PRO"]

    def test_local_overrides_scalar(self) -> None:
        cfg = _cfg(
            defaults={"search_dir": "/default"},
            configs={"base": {"directory": "/local"}},
        )
        resolved = resolve_configs(cfg)
        assert resolved["base"].directory == "/local"

    def test_extends_merges_lists(self) -> None:
        cfg = _cfg(
            defaults={"extensions": ["All"]},
            configs={
                "base": {"extensions": [".pdf"]},
                "prod": {"extends": "base", "extensions": [".xlsx"]},
            },
        )
        resolved = resolve_configs(cfg)
        # local first, then inherited, then defaults, deduped
        assert resolved["prod"].extensions == [".xlsx", ".pdf", "All"]

    def test_extends_inherits_scalar(self) -> None:
        cfg = _cfg(
            configs={
                "base": {"directory": "/base"},
                "prod": {"extends": "base"},
            }
        )
        resolved = resolve_configs(cfg)
        assert resolved["prod"].directory == "/base"

    def test_unknown_extends_raises(self) -> None:
        cfg = _cfg(configs={"prod": {"extends": "ghost"}})
        with pytest.raises(ConfigError):
            resolve_configs(cfg)

    def test_cycle_raises(self) -> None:
        cfg = _cfg(configs={"a": {"extends": "b"}, "b": {"extends": "a"}})
        with pytest.raises(ConfigError):
            resolve_configs(cfg)
