"""Tests for :mod:`profiles.app` launch configuration resolution."""

from __future__ import annotations

from profiles.app import ProFileApp


class TestResolveStartupConfig:
    """Tests for _resolve_startup_config() helper."""

    def test_explicit_config_flag_wins(self, tmp_path, monkeypatch) -> None:
        """An explicit --config path is returned unchanged."""
        explicit = tmp_path / "custom.profiles"
        explicit.write_text("x")

        app = ProFileApp(config_path=explicit)
        resolved, missing = app._resolve_startup_config(explicit)

        assert resolved == explicit
        assert missing is False

    def test_no_args_in_dir_with_config_finds_it(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        """When no args, finds .profiles in CWD."""
        config = tmp_path / ".profiles"
        config.write_text("x")

        monkeypatch.chdir(tmp_path)
        app = ProFileApp()
        resolved, missing = app._resolve_startup_config(None)

        assert resolved == config
        assert missing is False

    def test_no_args_no_config_returns_none(self, monkeypatch, tmp_path) -> None:
        """When no config found anywhere, returns None."""
        monkeypatch.chdir(tmp_path)
        app = ProFileApp()
        resolved, missing = app._resolve_startup_config(None)

        assert resolved is None
        assert missing is False

    def test_missing_explicit_config_is_reported(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        """Missing explicit config is reported as missing."""
        missing = tmp_path / "nonexistent.profiles"

        app = ProFileApp(config_path=missing)
        resolved, missing_flag = app._resolve_startup_config(missing)

        assert resolved == missing
        assert missing_flag is True
