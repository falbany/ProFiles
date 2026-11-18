"""Tests for :mod:`profiles.launch.creation` — config file creation.

These tests verify that the creation logic correctly offers and writes
starter configuration files without clobbering existing ones.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from profiles.launch.creation import CreationResult, propose_creation


class TestProposeCreation:
    def test_starter_written_where_asked(self, tmp_path) -> None:
        """A new starter config is written when the target has none."""
        result = propose_creation(tmp_path)

        assert result.status == "CREATED"
        assert result.path == tmp_path / ".profiles"
        assert result.path.exists()
        assert result.path.read_text() != ""

    def test_no_clobber(self, tmp_path) -> None:
        """Pre-existing content is preserved; returns a skipped outcome."""
        config = tmp_path / ".profiles"
        original = "# existing content\n"
        config.write_text(original)

        result = propose_creation(tmp_path)

        assert result.status == "SKIPPED"
        assert result.path == config
        assert config.read_text() == original

    def test_template_is_the_project_starter(self, tmp_path) -> None:
        """The written file uses the project's STARTER_CONFIG_TEMPLATE."""

        result = propose_creation(tmp_path)

        assert result.status == "CREATED"
        content = result.path.read_text()
        # The template includes a header comment (use partial match for encoding safety)
        assert "# ProFiles" in content
        assert "Starter Configuration" in content

    def test_parent_directory_is_created(self, tmp_path) -> None:
        """The parent directory is created if it does not exist."""
        nested = tmp_path / "a" / "b" / "c"

        result = propose_creation(nested)

        assert result.status == "CREATED"
        assert result.path.parent.exists()
        assert result.path.exists()

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Cannot simulate unwritable directory on Windows"
    )
    def test_failed_write_returns_failed_status(self, tmp_path, monkeypatch) -> None:
        """When the write fails, the result status is FAILED."""
        # Make the directory read-only to force a write failure
        tmp_path.chmod(0o555)

        try:
            result = propose_creation(tmp_path)
            assert result.status == "FAILED"
            assert "Could not write" in result.message or "Could not create" in result.message
        finally:
            # Restore permissions so cleanup can happen
            tmp_path.chmod(0o755)

    def test_creation_result_is_immutable(self) -> None:
        """CreationResult is a frozen dataclass."""
        result = CreationResult(
            status="CREATED",
            path=Path("/tmp/test.profiles"),
            message="Created",
        )

        # Should raise AttributeError if we try to modify
        with pytest.raises(AttributeError):
            result.status = "SKIPPED"  # type: ignore


class TestStarterSearchDir:
    """The starter's search_dir template placeholder (issue #191)."""

    @staticmethod
    def _starter_search_dir(config_path: Path) -> str:
        """Extract the search_dir value from a written starter file."""
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("search_dir:"):
                return stripped.split(":", 1)[1].strip().strip("'\"")
        raise AssertionError("starter has no search_dir line")

    def test_project_target_scans_itself(self, tmp_path, monkeypatch) -> None:
        """A project-directory creation scans the project folder."""
        monkeypatch.chdir(tmp_path)
        result = propose_creation(tmp_path)

        assert result.status == "CREATED"
        assert self._starter_search_dir(result.path) == str(tmp_path)

    def test_explicit_search_dir_is_used(self, tmp_path) -> None:
        """An explicit search_dir lands in the template verbatim."""
        scan_dir = tmp_path / "programs"
        scan_dir.mkdir()
        result = propose_creation(tmp_path, search_dir=scan_dir)

        assert result.status == "CREATED"
        assert self._starter_search_dir(result.path) == str(scan_dir)

    def test_user_data_dir_target_scans_home(
        self, tmp_path, isolated_user_home, monkeypatch
    ) -> None:
        """Creating in ~/.profiles scans the home, not the data dir (#191).

        The data folder only holds logs and configs, so scanning it is
        useless; with an uninformative CWD (Start-Menu style) the scan
        target falls back to the home folder itself.
        """
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        system32 = tmp_path / "System32"
        system32.mkdir()
        monkeypatch.chdir(system32)

        data_dir = isolated_user_home / ".profiles"
        result = propose_creation(data_dir)

        assert result.status == "CREATED"
        assert self._starter_search_dir(result.path) == str(isolated_user_home)
