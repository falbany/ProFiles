"""Tests for :mod:`profiles.app` launch configuration resolution."""

from __future__ import annotations

import pytest

from profiles.app import ProFileApp


class TestResolveStartupConfig:
    """Tests for _resolve_startup_config() helper."""

    def test_explicit_config_flag_wins(self, tmp_path, monkeypatch) -> None:
        """An explicit --config path is returned unchanged."""
        explicit = tmp_path / "custom.profiles"
        explicit.write_text("x")

        app = ProFileApp(config_path=explicit)
        resolved, missing, _default = app._resolve_startup_config(explicit)

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
        resolved, missing, _default = app._resolve_startup_config(None)

        assert resolved == config
        assert missing is False

    def test_no_args_no_config_returns_none(
        self, monkeypatch, tmp_path, isolated_user_home
    ) -> None:
        """When no config found anywhere, returns None."""
        monkeypatch.chdir(tmp_path)
        app = ProFileApp()
        resolved, missing, _default = app._resolve_startup_config(None)

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
        resolved, missing_flag, _default = app._resolve_startup_config(missing)

        assert resolved == missing
        assert missing_flag is True


class TestLaunchSourceRecording:
    """The context source is remembered for the handoff gate (issue #188)."""

    def test_folder_search_launch_records_cwd_source(
        self, monkeypatch, tmp_path, isolated_user_home
    ) -> None:
        """A launch with no explicit/doc signal is folder-search driven."""
        monkeypatch.chdir(tmp_path)
        app = ProFileApp()
        resolved, _missing, _default = app._resolve_startup_config(None)

        assert resolved is None  # no literal config name in the folder
        assert app._launch_source == "cwd"

    def test_explicit_flag_records_explicit_source(self, monkeypatch, tmp_path) -> None:
        explicit = tmp_path / "custom.profiles"
        explicit.write_text("x")

        app = ProFileApp()
        app._resolve_startup_config(explicit)

        assert app._launch_source == "explicit"

    def test_headless_launch_skips_odoc_capture(self, monkeypatch, tmp_path, mocker) -> None:
        """Headless runs never pump the macOS event loop."""
        capture = mocker.patch("profiles.desktop.appkit_events.capture_open_documents")
        config = tmp_path / ".profiles"
        config.write_text("x")
        monkeypatch.chdir(tmp_path)

        app = ProFileApp(headless=True)
        app._resolve_startup_config(None)

        capture.assert_not_called()

    def test_odoc_document_drives_resolution(self, monkeypatch, tmp_path, mocker) -> None:
        """A captured double-clicked document beats the folder search."""
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        monkeypatch.chdir("/")  # GUI-style launch: uninformative CWD
        clicked = tmp_path / "clicked.profiles"
        clicked.write_text("x")
        mocker.patch(
            "profiles.desktop.appkit_events.capture_open_documents",
            return_value=(clicked,),
        )

        app = ProFileApp()
        resolved, missing, _default = app._resolve_startup_config(None)

        assert resolved == clicked
        assert missing is False
        assert app._launch_source == "document"


class TestStartMenuLaunch:
    """Simulated launcher-style launches with an uninformative CWD (#191).

    A Start-Menu shortcut with an empty "Start in" runs with
    ``CWD = %SystemRoot%\\System32``. The simulated repro monkeypatches
    the CWD to a fake System32 and ``Path.home()`` to a temp folder, so
    the whole startup resolution is exercised hermetically on any OS.
    """

    @pytest.fixture
    def fake_system32_home(self, tmp_path, monkeypatch):
        """Fake %SystemRoot%\\System32 CWD + fake home; yields (cwd, home).

        The macOS Finder probe is stubbed out: an uninformative CWD is
        exactly the condition that triggers it, and the dev machine's
        real front Finder window must never leak into the result.
        """
        system_root = tmp_path / "Windows"
        system32 = system_root / "System32"
        system32.mkdir(parents=True)
        user_home = tmp_path / "uhome"
        user_home.mkdir()
        monkeypatch.setenv("SystemRoot", str(system_root))
        monkeypatch.chdir(system32)
        monkeypatch.setattr("profiles.core.paths.Path.home", lambda: user_home)
        monkeypatch.setattr("profiles.launch.context._finder_working_directory", lambda: None)
        return system32, user_home

    def test_resolution_proposes_user_config_path(self, fake_system32_home, monkeypatch) -> None:
        """System32 CWD + empty home → launch default is ~/.profiles/.profiles."""
        _system32, user_home = fake_system32_home
        app = ProFileApp()
        resolved, missing, launch_default = app._resolve_startup_config(None)

        assert resolved is None  # System32 tree is never searched
        assert missing is False
        assert launch_default == user_home / ".profiles" / ".profiles"

    def test_load_configuration_binds_user_config_path(self, fake_system32_home, mocker) -> None:
        """AppConfig.config_path carries the per-user path for the UI."""
        _system32, user_home = fake_system32_home
        app = ProFileApp()
        config = app._load_configuration(mocker.Mock())

        assert config.config_path == user_home / ".profiles" / ".profiles"
        assert app._config_path == config.config_path

    def test_existing_user_config_is_loaded_on_relaunch(self, fake_system32_home) -> None:
        """Matrix row 4: second Start-Menu launch loads the user config."""
        _system32, user_home = fake_system32_home
        user_config = user_home / ".profiles" / ".profiles"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("defaults:\n  theme: dark\n", encoding="utf-8")

        app = ProFileApp()
        resolved, missing, _default = app._resolve_startup_config(None)

        assert resolved == user_config
        assert missing is False
