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
