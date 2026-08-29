"""Tests for profiles.core.config.models — AppConfig, MachineConfiguration, HookSpec dataclasses."""

from __future__ import annotations

from pathlib import Path

from profiles.config import (
    AppConfig,
    MachineConfiguration,
)
from profiles.core.config.models import HookSpec, MatchCriteria


class TestAppConfig:
    """Default and custom AppConfig construction."""

    def test_default_values(self) -> None:
        config = AppConfig()
        assert config.release == "2026.8.0"
        assert config.title == ""
        assert config.gui_auto_launch is True
        assert config.close_after_execute is False
        assert config.search_dir == ""
        assert config.recursive_search is False
        assert config.column_names == ()  # Empty by default, built from [COLUMN_*] sections
        assert config.column_widths == ()  # Empty by default
        assert config.extensions == ("All", ".lnk")
        assert config.filters == ("", "ST_PRO", "ST_ENG")
        assert config.search_exclude_dirs == (".git",)
        assert config.search_exclude_files == ()
        assert config.theme == "light"
        assert config.verbose == "INFO"
        assert config.configurations == []
        assert config.config_path == Path.cwd() / ".profiles"

    def test_custom_values(self) -> None:
        config = AppConfig(
            release="2025.4.0",
            gui_auto_launch=False,
            close_after_execute=True,
            search_dir="M:/tests",
            recursive_search=True,
            column_names=("A", "B"),
            column_headers=("A", "B"),
            column_widths=(100, 200),
            column_stretches=(True, False),
            extensions=(".abc",),
            filters=("prod",),
            search_exclude_dirs=(".git", "__pycache__"),
            search_exclude_files=("*backup*", "~$*"),
            configurations=[
                MachineConfiguration(
                    match=MatchCriteria(hostname=("PC1",)),
                    scan=("M:/dir",),
                )
            ],
            config_path=Path("custom/.profiles"),
        )
        assert config.release == "2025.4.0"
        assert config.gui_auto_launch is False
        assert config.close_after_execute is True
        assert config.search_dir == "M:/tests"
        assert config.search_exclude_files == ("*backup*", "~$*")
        assert config.configurations[0].match.hostname == ("PC1",)


class TestMachineConfiguration:
    """Default MachineConfiguration dataclass."""

    def test_default_values(self) -> None:
        mc = MachineConfiguration()
        assert mc.match.hostname == ()
        assert mc.match.ip == ()
        assert mc.match.path == ()
        assert mc.scan == ()
        assert mc.extensions == ()
        assert mc.filters == ()
        assert mc.row_colors == ()
        assert mc.search_exclude_files == ()


class TestHookSpec:
    """HookSpec when-coercion and defaults."""

    def test_invalid_when_coerces_to_before(self) -> None:
        """An unknown when value is coerced to 'before'."""
        hook = HookSpec(when="garbage", template="x")
        assert hook.when == "before"

    def test_valid_when_passes_through(self) -> None:
        """A known when value is preserved."""
        hook = HookSpec(when="after", template="x")
        assert hook.when == "after"

    def test_confirm_when_passes_through(self) -> None:
        """The 'confirm' phase is a known value and is preserved."""
        hook = HookSpec(when="confirm", template="Are you sure?")
        assert hook.when == "confirm"
        assert hook.template == "Are you sure?"

    def test_template_empty_default(self) -> None:
        """template defaults to an empty string."""
        assert HookSpec().template == ""

    def test_requires_success_default_true(self) -> None:
        """requires_success defaults to True."""
        assert HookSpec().requires_success is True

    def test_requires_success_can_be_disabled(self) -> None:
        """requires_success can be set to False for optional sequential hooks."""
        hook = HookSpec(
            when="before",
            template="optional-check.sh",
            requires_success=False,
        )
        assert hook.requires_success is False
