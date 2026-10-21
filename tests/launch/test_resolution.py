"""Tests for :mod:`profiles.launch.resolution` — config path selection.

These tests verify the pure decision logic that chooses which configuration
file ProFiles should use at startup.  No files are read or written here;
that is tested in :mod:`test_creation`.
"""

from __future__ import annotations

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

    def test_no_match_returns_none(self, tmp_path) -> None:
        """When nothing is found, resolve_config_path returns None."""
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
