"""Tests for profiles.core.config.validator — semantic validation."""

from __future__ import annotations

import pytest

from profiles.core.config.schema import ConfigError
from profiles.core.config.validator import validate


class TestValidate:
    def test_valid_passes(self) -> None:
        raw = {
            "version": 1,
            "configs": {
                "base": {"directory": "/x"},
                "prod": {"extends": "base"},
            },
        }
        validate(raw)  # should not raise

    def test_unknown_extends(self) -> None:
        raw = {"configs": {"prod": {"extends": "ghost"}}}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.prod.extends"
        assert "ghost" in exc.value.message

    def test_cycle(self) -> None:
        raw = {
            "configs": {
                "a": {"extends": "b"},
                "b": {"extends": "a"},
            }
        }
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.b.extends"
        assert "cycle" in exc.value.message.lower()

    def test_unknown_top_level_key(self) -> None:
        raw = {"bogus": 1}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "bogus"
