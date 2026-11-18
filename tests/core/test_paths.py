"""Tests for :mod:`profiles.core.paths` — the per-user path policy.

Issue #191: launcher-style launches (Start Menu, ``.desktop``) run with
an uninformative CWD (System32, the home folder) and must propose
``~/.profiles/.profiles`` instead of writing a config into a system
directory.  All user-home-dependent behaviour is exercised through the
``isolated_user_home`` fixture so no test touches the real home.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from profiles.core.paths import (
    USER_DATA_DIRNAME,
    default_config_path,
    default_search_directory,
    find_user_config,
    is_uninformative_directory,
    user_config_path,
    user_data_dir,
)

pytestmark = pytest.mark.usefixtures("isolated_user_home")


class TestUserDataDir:
    def test_user_data_dir_is_under_home(self, isolated_user_home: Path) -> None:
        assert user_data_dir() == isolated_user_home / USER_DATA_DIRNAME
        assert USER_DATA_DIRNAME == ".profiles"

    def test_user_config_path_is_primary_name_in_data_dir(self, isolated_user_home: Path) -> None:
        assert user_config_path() == isolated_user_home / ".profiles" / ".profiles"

    def test_default_log_path_shares_the_data_dir(self, isolated_user_home: Path) -> None:
        """Logs and the per-user config live in the same folder (#191)."""
        from profiles.core.telemetry.diagnostics import default_log_path

        assert default_log_path() == user_data_dir() / "profiles.log"


class TestFindUserConfig:
    def test_returns_none_when_data_dir_is_missing(self) -> None:
        assert find_user_config() is None

    def test_finds_primary_name(self, isolated_user_home: Path) -> None:
        config = user_config_path()
        config.parent.mkdir(parents=True)
        config.write_text("defaults:\n  theme: light\n")
        assert find_user_config() == config

    def test_yaml_fallback_only_without_primary(self, isolated_user_home: Path) -> None:
        data_dir = user_data_dir()
        data_dir.mkdir(parents=True)
        yaml_config = data_dir / ".profiles.yaml"
        yaml_config.write_text("defaults:\n  theme: dark\n")
        assert find_user_config() == yaml_config

    def test_primary_beats_yaml(self, isolated_user_home: Path) -> None:
        data_dir = user_data_dir()
        data_dir.mkdir(parents=True)
        (data_dir / ".profiles").write_text("x")
        yaml_config = data_dir / ".profiles.yaml"
        yaml_config.write_text("x")
        assert find_user_config() == data_dir / ".profiles"

    def test_ignores_directories_named_like_configs(self, isolated_user_home: Path) -> None:
        """A directory must never be mistaken for a config file."""
        data_dir = user_data_dir()
        (data_dir / ".profiles").mkdir(parents=True)
        assert find_user_config() is None

    def test_ignores_nested_configs(self, isolated_user_home: Path) -> None:
        """Depth 0 only: no wildcard walk of the data dir."""
        nested = user_data_dir() / "sub" / ".profiles"
        nested.parent.mkdir(parents=True)
        nested.write_text("x")
        assert find_user_config() is None


class TestIsUninformativeDirectory:
    def test_none_is_uninformative(self) -> None:
        assert is_uninformative_directory(None) is True

    def test_filesystem_root_is_uninformative(self) -> None:
        root = Path(tmp_root())
        assert is_uninformative_directory(root) is True

    def test_home_itself_is_uninformative(self, isolated_user_home: Path) -> None:
        assert is_uninformative_directory(isolated_user_home) is True

    def test_directory_inside_home_is_informative(self, isolated_user_home: Path) -> None:
        project = isolated_user_home / "project"
        project.mkdir()
        assert is_uninformative_directory(project) is False

    def test_python_prefix_is_uninformative(self, isolated_user_home: Path) -> None:
        inside_runtime = Path(sys.prefix) / "lib"
        assert is_uninformative_directory(inside_runtime) is True

    def test_executable_directory_is_uninformative(self, isolated_user_home: Path) -> None:
        exe_dir = Path(sys.executable).resolve().parent
        assert is_uninformative_directory(exe_dir) is True

    def test_system_root_env_is_uninformative(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fake %SystemRoot% (via env, portable on every platform)."""
        monkeypatch.setenv("SystemRoot", str(isolated_user_home / "Windows"))
        system32 = isolated_user_home / "Windows" / "System32"
        system32.mkdir(parents=True)
        assert is_uninformative_directory(system32) is True

    def test_windir_env_is_uninformative(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("windir", str(isolated_user_home / "WinDir"))
        inside = isolated_user_home / "WinDir" / "SysWOW64"
        inside.mkdir(parents=True)
        assert is_uninformative_directory(inside) is True

    def test_program_files_env_is_uninformative(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ProgramFiles", str(isolated_user_home / "Program Files"))
        inside = isolated_user_home / "Program Files" / "ProFiles"
        inside.mkdir(parents=True)
        assert is_uninformative_directory(inside) is True

    def test_program_files_x86_env_is_uninformative(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ProgramFiles(x86)", str(isolated_user_home / "PF86"))
        inside = isolated_user_home / "PF86" / "ProFiles"
        inside.mkdir(parents=True)
        assert is_uninformative_directory(inside) is True

    def test_temp_dir_is_informative(self, tmp_path: Path) -> None:
        assert is_uninformative_directory(tmp_path) is False


def tmp_root() -> str:
    """Return a filesystem root for the current platform."""
    return "/" if sys.platform != "win32" else "C:\\"


class TestDefaultConfigPath:
    def test_uninformative_start_proposes_user_config(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        system32 = isolated_user_home / "Windows" / "System32"
        system32.mkdir(parents=True)
        monkeypatch.setenv("SystemRoot", str(isolated_user_home / "Windows"))
        assert default_config_path(system32) == user_config_path()

    def test_none_start_uses_cwd_policy(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """None start resolves the CWD; an uninformative one → per-user path."""
        system32 = isolated_user_home / "Windows" / "System32"
        system32.mkdir(parents=True)
        monkeypatch.setenv("SystemRoot", str(isolated_user_home / "Windows"))
        monkeypatch.chdir(system32)
        assert default_config_path(None) == user_config_path()

    def test_informative_start_proposes_in_place(self, tmp_path: Path) -> None:
        assert default_config_path(tmp_path) == tmp_path / ".profiles"

    def test_directory_collision_falls_back_to_user_config(
        self, isolated_user_home: Path, tmp_path: Path
    ) -> None:
        """start/.profiles already being a DIRECTORY must never be proposed."""
        (tmp_path / ".profiles").mkdir()
        assert default_config_path(tmp_path) == user_config_path()

    def test_existing_file_does_not_trigger_collision_fallback(
        self, isolated_user_home: Path, tmp_path: Path
    ) -> None:
        """An existing .profiles FILE stays the candidate (idempotent)."""
        (tmp_path / ".profiles").write_text("x")
        assert default_config_path(tmp_path) == tmp_path / ".profiles"


class TestDefaultSearchDirectory:
    def test_uninformative_start_returns_home(
        self, isolated_user_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        system32 = isolated_user_home / "Windows" / "System32"
        system32.mkdir(parents=True)
        monkeypatch.setenv("SystemRoot", str(isolated_user_home / "Windows"))
        assert default_search_directory(system32) == isolated_user_home

    def test_informative_start_returns_itself(self, tmp_path: Path) -> None:
        assert default_search_directory(tmp_path) == tmp_path

    def test_none_start_resolves_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        assert default_search_directory() == tmp_path

    def test_home_cwd_resolves_to_home(self, isolated_user_home: Path) -> None:
        """CWD == home is uninformative: the scan target becomes home."""
        assert default_search_directory(isolated_user_home) == isolated_user_home
