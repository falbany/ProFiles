"""Tests for profiles.core.config.loader — load_config entry point + default column behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.config import (
    load_config,
)
from profiles.core.config.loader import propose_config_creation


class TestLoadConfig:
    """load_config() module-level convenience function."""

    def test_with_explicit_path(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles"
        conf.write_text("defaults:\n  theme: dark\n", encoding="utf-8")
        config = load_config(conf)
        assert config.theme == "dark"

    def test_with_none_searches_tree(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        conf = tmp_path / ".profiles"
        conf.write_text("defaults:\n  theme: light\n", encoding="utf-8")
        config = load_config()
        assert config.theme == "light"

    def test_not_found_uses_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # No .profiles in tree — falls back to default ".profiles" in CWD
        config = load_config()
        assert config.config_path == Path.cwd() / ".profiles"

    def test_fallback_to_profiles_yaml_when_profiles_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When .profiles is missing but .profiles.yaml exists, use .profiles.yaml."""
        monkeypatch.chdir(tmp_path)
        fallback = tmp_path / ".profiles.yaml"
        fallback.write_text("defaults:\n  theme: dark\n", encoding="utf-8")
        config = load_config()
        assert config.theme == "dark"
        assert config.config_path == fallback


class TestDefaultColumnsWithoutConfig:
    """Tests verifying default columns are set when no config file exists."""

    def test_missing_config_file_has_default_file_column(self, tmp_path: Path) -> None:
        """When .profiles doesn't exist, column_names should default to ('File',)."""
        non_existent_path = tmp_path / "nonexistent" / ".profiles"

        config = load_config(non_existent_path)

        # Verify default column configuration is present
        assert config.column_names == ("File",)
        assert config.column_widths == (600,)
        assert len(config.column_names) == 1
        assert config.column_names[0] == "File"

    def test_empty_config_file_has_default_file_column(self, tmp_path: Path) -> None:
        """When .profiles is empty, column_names should default to ('File',)."""
        empty_config = tmp_path / ".profiles"
        empty_config.write_text("")

        config = load_config(empty_config)

        # Verify default column configuration is present
        assert config.column_names == ("File",)
        assert config.column_widths == (600,)

    def test_config_with_defaults_but_no_columns(self, tmp_path: Path) -> None:
        """When .profiles has defaults but no columns, should still have File column."""
        config_file = tmp_path / ".profiles"
        config_file.write_text("defaults:\n  theme: light\n")

        config = load_config(config_file)

        # Verify default column configuration is present
        assert config.column_names == ("File",)
        assert config.column_widths == (600,)


class TestProposeConfigCreation:
    """propose_config_creation() — interactive bootstrap prompt."""

    def test_user_accepts_creates_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A 'y' response writes a starter .profiles and returns True."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", lambda: "y")
        assert propose_config_creation() is True
        assert (tmp_path / ".profiles").exists()

    def test_user_declines_returns_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A 'n' response returns False without writing a file."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", lambda: "n")
        assert propose_config_creation() is False
        assert not (tmp_path / ".profiles").exists()

    def test_eof_error_returns_false(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """An EOFError (e.g. piped stdin) returns False gracefully."""
        monkeypatch.chdir(tmp_path)

        def raise_eof(*_args, **_kwargs):  # noqa: ANN002, ANN003
            raise EOFError()

        monkeypatch.setattr("builtins.input", raise_eof)
        assert propose_config_creation() is False

    def test_existing_file_skips_creation(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """If .profiles already exists, creation is skipped even with 'y'."""
        existing = tmp_path / ".profiles"
        existing.write_text("existing", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", lambda: "y")
        assert propose_config_creation() is False
        assert existing.read_text(encoding="utf-8") == "existing"

    def test_write_error_returns_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An OSError during write returns False without raising."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("builtins.input", lambda: "y")

        real_write = Path.write_text

        def failing_write(self, *args, **kwargs):  # noqa: ANN001
            raise OSError("denied")

        monkeypatch.setattr(Path, "write_text", failing_write)
        try:
            assert propose_config_creation() is False
        finally:
            monkeypatch.setattr(Path, "write_text", real_write)
