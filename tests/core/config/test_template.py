"""Tests for profiles.core.config.template — YAML starter template."""

from __future__ import annotations

from profiles.core.config.template import STARTER_CONFIG_TEMPLATE


class TestStarterTemplate:
    def test_is_yaml(self) -> None:
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        assert "version: 1" in body
        assert "defaults:" in body
        assert "configs:" in body

    def test_has_cwd_placeholder(self) -> None:
        assert "{cwd}" in STARTER_CONFIG_TEMPLATE

    def test_formats_cwd(self) -> None:
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/my/dir")
        assert "/my/dir" in body
