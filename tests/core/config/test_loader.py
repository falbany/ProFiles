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
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_user_home
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # No .profiles in tree or user dir — defaults bound to the default
        # path (issue #191: the project folder for a terminal launch)
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

    def test_user_config_loaded_when_project_tree_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_user_home
    ) -> None:
        """No project config but ~/.profiles/.profiles exists → it loads (#191)."""
        monkeypatch.chdir(tmp_path)
        user_config = isolated_user_home / ".profiles" / ".profiles"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("defaults:\n  theme: dark\n", encoding="utf-8")

        config = load_config()
        assert config.theme == "dark"
        assert config.config_path == user_config

    def test_uninformative_cwd_skips_tree_search(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_user_home
    ) -> None:
        """A System32-style CWD is never searched for configs (#191)."""
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()
        (system32 / ".profiles").write_text("defaults:\n  theme: light\n", encoding="utf-8")
        monkeypatch.chdir(system32)

        config = load_config()
        # Not the System32 "project" config: defaults bound to the user path
        assert config.config_path == isolated_user_home / ".profiles" / ".profiles"

    def test_default_path_is_user_config_for_launcher_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_user_home
    ) -> None:
        """No config anywhere + System32 CWD → defaults bound to the user path."""
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()
        monkeypatch.chdir(system32)

        config = load_config()
        assert config.config_path == isolated_user_home / ".profiles" / ".profiles"


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

        def failing_write(*args, **kwargs):  # noqa: ANN001
            raise OSError("denied")

        monkeypatch.setattr("profiles.core.actions.write_text_atomic", failing_write)
        assert propose_config_creation() is False

    def test_launcher_cwd_creates_in_user_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, isolated_user_home
    ) -> None:
        """A System32-style CWD creates the config in ~/.profiles (#191)."""
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()
        monkeypatch.chdir(system32)
        monkeypatch.setattr("builtins.input", lambda: "y")

        assert propose_config_creation() is True
        target = isolated_user_home / ".profiles" / ".profiles"
        assert target.exists()
        assert not (system32 / ".profiles").exists()
