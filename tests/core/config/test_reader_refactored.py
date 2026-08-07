"""Tests for the refactored config reader column handling."""

from profiles.core.config.models import AppConfig, ColumnConfiguration
from profiles.core.config.reader import ConfigReader


def test_build_column_configs_with_stretch_and_headers():
    """_build_column_configs builds stretch + header tuples."""
    config = AppConfig(
        search_dir="C:\\test",
        columns={
            "File": ColumnConfiguration(
                name="File", width=600, stretch=True, match=".*", priority=100
            ),
            "Version": ColumnConfiguration(
                name="Version Number",
                width=120,
                stretch=False,
                match="version",
                transform="Ver. \\1",
                priority=20,
            ),
        },
    )

    ConfigReader._build_column_configs(config)

    assert config.column_names == ("File", "Version")
    assert config.column_widths == (600, 120)
    assert config.column_stretches == (True, False)
    assert config.column_headers == ("File", "Version Number")


def test_build_column_configs_defaults_when_empty():
    """Empty columns yield a single File column."""
    config = AppConfig(search_dir="C:\\test")
    ConfigReader._build_column_configs(config)
    assert config.column_names == ("File",)
    assert config.column_widths == (600,)
    assert config.column_stretches == (False,)
    assert config.column_headers == ("File",)


def test_build_column_configs_header_falls_back_to_key():
    """A column with no name uses the dict key as the header."""
    config = AppConfig(
        search_dir="C:\\test",
        columns={
            "Version": ColumnConfiguration(width=120, match="version", priority=20),
        },
    )

    ConfigReader._build_column_configs(config)

    assert config.column_headers == ("File", "Version")
    assert config.column_stretches == (False, False)
