"""Verify that the new ColumnConfiguration fields are exported and accessible.

These tests guard the public API surface so that downstream consumers
(GUI, CLI, TUI) can rely on the re-exported names.
"""

from __future__ import annotations

from profiles.config import ColumnConfiguration as ConfigColumnConfiguration
from profiles.core import ColumnConfiguration as CoreColumnConfiguration
from profiles.core.config import ColumnConfiguration as SubpkgColumnConfiguration


class TestColumnConfigurationExports:
    """ColumnConfiguration must be importable from all public paths."""

    def test_importable_from_profiles_config(self) -> None:
        """profiles.config re-exports ColumnConfiguration."""
        assert ConfigColumnConfiguration is not None

    def test_importable_from_profiles_core(self) -> None:
        """profiles.core re-exports ColumnConfiguration."""
        assert CoreColumnConfiguration is not None

    def test_importable_from_profiles_core_config(self) -> None:
        """profiles.core.config re-exports ColumnConfiguration."""
        assert SubpkgColumnConfiguration is not None

    def test_all_three_are_same_class(self) -> None:
        """All three import paths resolve to the same class object."""
        assert ConfigColumnConfiguration is CoreColumnConfiguration
        assert CoreColumnConfiguration is SubpkgColumnConfiguration


class TestColumnConfigurationFields:
    """ColumnConfiguration must expose the new match/transform/stretch fields."""

    def test_default_values(self) -> None:
        """New fields have sensible defaults for backward compatibility."""
        col = ConfigColumnConfiguration()
        assert col.name == ""
        assert col.width == 150
        assert col.stretch is False
        assert col.match == ".*"
        assert col.transform is None
        assert col.priority == 0
        assert col.default == ""

    def test_all_fields_constructible(self) -> None:
        """All new fields can be set via the constructor."""
        col = ConfigColumnConfiguration(
            name="Version",
            width=200,
            stretch=True,
            match="version",
            transform=r"v{group:1}",
            priority=10,
            default="unknown",
        )
        assert col.name == "Version"
        assert col.width == 200
        assert col.stretch is True
        assert col.match == "version"
        assert col.transform == r"v{group:1}"
        assert col.priority == 10
        assert col.default == "unknown"


class TestAppConfigColumnFields:
    """AppConfig must expose column_stretches and column_headers tuples."""

    def test_app_config_has_new_fields(self) -> None:
        """AppConfig carries column_stretches and column_headers."""
        from profiles.core.config.models import AppConfig

        cfg = AppConfig()
        assert hasattr(cfg, "column_stretches")
        assert hasattr(cfg, "column_headers")
        assert cfg.column_stretches == ()
        assert cfg.column_headers == ()

    def test_app_config_still_has_legacy_fields(self) -> None:
        """AppConfig retains column_names and column_widths for backward compat."""
        from profiles.core.config.models import AppConfig

        cfg = AppConfig()
        assert hasattr(cfg, "column_names")
        assert hasattr(cfg, "column_widths")
        assert cfg.column_names == ()
        assert cfg.column_widths == ()
