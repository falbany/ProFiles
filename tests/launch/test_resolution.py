"""Tests for :mod:`profiles.launch.resolution` — config path selection.

These tests verify the pure decision logic that chooses which configuration
file ProFiles should use at startup.  No files are read or written here;
that is tested in :mod:`test_creation`.

Since issue #191 the resolution also consults the per-user default
(``~/.profiles/.profiles``) as the final fallback and skips the CWD tree
search for uninformative directories — the user home is isolated through
the ``isolated_user_home`` fixture wherever that fallback is in play.
"""

from __future__ import annotations

import pytest

from profiles.launch.context import LaunchContext
from profiles.launch.resolution import resolve_config_path


class TestResolveConfigPath:
    def test_explicit_config_wins_everything(self, tmp_path) -> None:
        """An explicit --config path always wins, even with documents present."""
        doc = tmp_path / "doc.profiles"
        doc.write_text("x")
        explicit = tmp_path / "explicit.profiles"

        ctx = LaunchContext(
            document_paths=(doc,),
            working_directory=tmp_path,
            explicit_config=explicit,
            source="explicit",
        )
        assert resolve_config_path(ctx) == explicit

    def test_document_wins_over_search(self, tmp_path) -> None:
        """A document path beats a config found by tree search."""
        doc = tmp_path / "my.profiles"
        doc.write_text("x")

        # Create a deeper config that would be found by search
        deep = tmp_path / "a" / "b" / ".profiles"
        deep.parent.mkdir(parents=True)
        deep.write_text("y")

        ctx = LaunchContext(
            document_paths=(doc,),
            working_directory=tmp_path,
            explicit_config=None,
            source="document",
        )
        result = resolve_config_path(ctx)
        assert result == doc

    def test_first_document_used_when_several(self, tmp_path) -> None:
        """When multiple documents are supplied, the first one is used."""
        doc1 = tmp_path / "first.profiles"
        doc2 = tmp_path / "second.profiles"
        doc1.write_text("x")
        doc2.write_text("y")

        ctx = LaunchContext(
            document_paths=(doc1, doc2),
            working_directory=tmp_path,
            explicit_config=None,
            source="document",
        )
        assert resolve_config_path(ctx) == doc1

    def test_tree_search_from_working_directory(self, tmp_path) -> None:
        """Config is found by searching down from working_directory."""
        # Create .profiles at depth 3
        deep = tmp_path / "a" / "b" / "c" / ".profiles"
        deep.parent.mkdir(parents=True)
        deep.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        result = resolve_config_path(ctx)
        assert result == deep

    def test_no_match_returns_none(self, tmp_path, isolated_user_home) -> None:
        """When nothing is found anywhere, resolve_config_path returns None."""
        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) is None

    def test_missing_working_directory_uses_cwd(self, tmp_path, monkeypatch) -> None:
        """When working_directory is None, the CWD is used as fallback."""
        monkeypatch.chdir(tmp_path)
        config = tmp_path / ".profiles"
        config.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=None,
            explicit_config=None,
            source="cwd",
        )
        result = resolve_config_path(ctx)
        assert result == config

    def test_explicit_config_does_not_need_to_exist(self, tmp_path) -> None:
        """An explicit path is returned verbatim, no existence check."""
        explicit = tmp_path / "nonexistent.profiles"

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=explicit,
            source="explicit",
        )
        result = resolve_config_path(ctx)
        assert result == explicit
        assert not result.exists()

    def test_legacy_yaml_suffix_is_found_by_search(self, tmp_path) -> None:
        """The legacy .profiles.yaml suffix is also searched."""
        config = tmp_path / ".profiles.yaml"
        config.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        result = resolve_config_path(ctx)
        assert result == config

    def test_yml_suffix_is_found_by_search(self, tmp_path) -> None:
        """The .profiles.yml suffix is also searched."""
        config = tmp_path / ".profiles.yml"
        config.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        result = resolve_config_path(ctx)
        assert result == config

    def test_search_tier_priority(self, tmp_path) -> None:
        """Primary beats .yaml across the whole tree; .yaml beats .yml."""
        (tmp_path / ".profiles.yml").write_text("x")
        yaml_conf = tmp_path / "sub" / ".profiles.yaml"
        yaml_conf.parent.mkdir()
        yaml_conf.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) == yaml_conf


class TestPerUserConfigFallback:
    """The per-user default (~/.profiles/.profiles) as final fallback (#191)."""

    def test_empty_tree_falls_back_to_user_config(self, tmp_path, isolated_user_home) -> None:
        """Matrix row 6: no project config, user config exists → it wins."""
        user_config = isolated_user_home / ".profiles" / ".profiles"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("defaults:\n  theme: dark\n")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) == user_config

    def test_project_config_beats_user_config(self, tmp_path, isolated_user_home) -> None:
        """A project config in the CWD tree still wins over the user one."""
        user_config = isolated_user_home / ".profiles" / ".profiles"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("x")

        project_config = tmp_path / ".profiles"
        project_config.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) == project_config

    def test_uninformative_cwd_skips_tree_search(
        self, tmp_path, isolated_user_home, monkeypatch
    ) -> None:
        """A System32-style CWD is never walked for configs (#191)."""
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()
        # A config inside the "system" tree must NOT be discovered.
        (system32 / ".profiles").write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=system32,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) is None

    def test_uninformative_cwd_with_user_config_falls_back(
        self, tmp_path, isolated_user_home, monkeypatch
    ) -> None:
        """Matrix row 4: launcher start, user config exists → loaded."""
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()

        user_config = isolated_user_home / ".profiles" / ".profiles"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=system32,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) == user_config

    def test_yaml_user_config_is_found(self, tmp_path, isolated_user_home) -> None:
        """The legacy .profiles.yaml name also works as the user default."""
        user_config = isolated_user_home / ".profiles" / ".profiles.yaml"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("x")

        ctx = LaunchContext(
            document_paths=(),
            working_directory=tmp_path,
            explicit_config=None,
            source="cwd",
        )
        assert resolve_config_path(ctx) == user_config

    @pytest.mark.parametrize("winner", ["explicit", "document"])
    def test_explicit_and_document_still_win(self, tmp_path, isolated_user_home, winner) -> None:
        """Explicit flags and opened documents outrank the user default."""
        user_config = isolated_user_home / ".profiles" / ".profiles"
        user_config.parent.mkdir(parents=True)
        user_config.write_text("x")

        winning = tmp_path / "winner.profiles"
        winning.write_text("x")

        ctx = LaunchContext(
            document_paths=(winning,) if winner == "document" else (),
            working_directory=tmp_path,
            explicit_config=winning if winner == "explicit" else None,
            source=winner,
        )
        assert resolve_config_path(ctx) == winning
