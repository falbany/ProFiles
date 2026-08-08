"""Test robust error handling and cross-platform compatibility."""

import logging
from pathlib import Path

import pytest

from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader


def test_config_load_with_invalid_yaml(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Verify that invalid YAML (escape chars) falls back to defaults and logs error.

    Given: A .profiles file with invalid YAML (bad escape sequences)
    When: ConfigReader.load() is called
    Then: Returns default config, logs error, doesn't crash
    """
    # Create invalid YAML with escape character error (like Windows paths in double quotes)
    config_file = tmp_path / ".profiles"
    config_file.write_text(
        "defaults:\n"
        '  search_dir: "C:\\Invalid\\Escape\\Path"\n'  # \I, \E, \P are invalid escapes
        "  title: Test\n",
        encoding="utf-8",
    )

    # Capture logs from the reader module
    caplog.set_level(logging.ERROR, logger="profiles.core.config.reader")

    # Should not raise, should return defaults
    reader = ConfigReader(config_file)
    config = reader.load()

    # Verify fallback to defaults
    assert isinstance(config, AppConfig)
    assert config.config_path == config_file

    # Verify error was logged
    assert any("Failed to parse configuration file" in rec.message for rec in caplog.records)
    assert any("Falling back to defaults" in rec.message for rec in caplog.records)


def test_config_load_with_validation_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify that validation errors fall back to defaults and log error.

    Given: A .profiles file with valid YAML but invalid schema
    When: ConfigReader.load() is called
    Then: Returns default config, logs error, doesn't crash
    """
    # Create valid YAML but invalid schema (wrong type for theme)
    config_file = tmp_path / ".profiles"
    config_file.write_text(
        "defaults:\n"
        "  search_dir: /valid/path\n"
        "  title: Test\n"
        "  gui_auto_launch: false\n"
        "  close_after_execute: false\n"
        "  theme: invalid_theme_value\n"  # Must be 'light' or 'dark'
        "  language: en\n"
        "  recursive_search: false\n"
        "  extensions: []\n"
        "  filters: []\n"
        "  search_exclude_dirs: []\n"
        "  search_exclude_files: []\n"
        "  row_colors: []\n"
        "  verbose: INFO\n"
        "  scan_metrics: false\n",
        encoding="utf-8",
    )

    # Capture logs from the reader module
    caplog.set_level(logging.ERROR, logger="profiles.core.config.reader")

    reader = ConfigReader(config_file)
    config = reader.load()

    assert isinstance(config, AppConfig)
    # Check that validation error was logged
    assert any("failed" in rec.message.lower() for rec in caplog.records)


def test_config_load_missing_file_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify missing config file logs warning and uses defaults.

    Given: Non-existent config file path
    When: ConfigReader.load() is called
    Then: Returns defaults, logs warning
    """
    config_file = tmp_path / "nonexistent" / ".profiles"

    # Capture logs from the reader module
    caplog.set_level(logging.DEBUG, logger="profiles.core.config.reader")

    reader = ConfigReader(config_file)
    config = reader.load()

    assert isinstance(config, AppConfig)
    # Check that debug message about not found was logged
    assert any("not found" in rec.message.lower() for rec in caplog.records)


def test_config_load_success_logs_info(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Verify successful config load logs info message.

    Given: Valid .profiles file
    When: ConfigReader.load() is called
    Then: Returns loaded config, logs success
    """
    # Create valid minimal config with correct schema values
    config_file = tmp_path / ".profiles"
    config_file.write_text(
        "defaults:\n"
        "  search_dir: /valid/path\n"
        "  title: Test Config\n"
        "  gui_auto_launch: false\n"
        "  close_after_execute: false\n"
        "  theme: light\n"  # Valid value
        "  language: en\n"
        "  recursive_search: false\n"
        "  extensions: [.txt]\n"
        "  filters: []\n"
        "  search_exclude_dirs: []\n"
        "  search_exclude_files: []\n"
        "  row_colors: []\n"
        "  verbose: INFO\n"  # Valid value
        "  scan_metrics: false\n"
        "columns: {}\n"
        "hooks:\n"
        "  failmode: warn\n"
        "  timeout: 30\n"
        "  entries: {}\n"
        "configs:\n"
        "  base:\n"
        "    match:\n"
        "      hostname: [Generic]\n"
        "    scan: [/valid/path]\n"
        "    row_colors: []\n",
        encoding="utf-8",
    )

    # Capture logs from the reader module
    caplog.set_level(logging.INFO, logger="profiles.core.config.reader")

    reader = ConfigReader(config_file)
    config = reader.load()

    assert isinstance(config, AppConfig)
    # Check that success was logged
    assert any("successfully" in rec.message for rec in caplog.records)


def test_cross_platform_path_handling() -> None:
    """Verify template works on Windows, macOS, and Linux.

    The template uses single quotes for paths, which is cross-platform safe.
    """
    from profiles.core.config.template import STARTER_CONFIG_TEMPLATE

    # Template should use single quotes (safe for all platforms)
    assert "search_dir: '{cwd}'" in STARTER_CONFIG_TEMPLATE
    assert "directory: '{cwd}'" in STARTER_CONFIG_TEMPLATE

    # Double quotes would be unsafe on Windows
    assert 'search_dir: "{cwd}"' not in STARTER_CONFIG_TEMPLATE
    assert 'directory: "{cwd}"' not in STARTER_CONFIG_TEMPLATE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
