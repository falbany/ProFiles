"""Tests for profiles.core.processing.file_metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.processing.file_metadata import get_file_metadata


class TestGetFileMetadata:
    """Tests for get_file_metadata()."""

    def test_returns_expected_keys(self, tmp_path: Path) -> None:
        """The dict has name, path, size_bytes, modified and created."""
        target = tmp_path / "doc.txt"
        target.write_text("hello")
        meta = get_file_metadata(target)
        assert meta["name"] == "doc.txt"
        assert meta["path"] == str(target)
        assert meta["size_bytes"] == 5
        assert isinstance(meta["modified"], str) and meta["modified"]
        assert isinstance(meta["created"], str) and meta["created"]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """A non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_file_metadata(tmp_path / "nope.txt")

    def test_size_matches_file_contents(self, tmp_path: Path) -> None:
        """size_bytes is the exact byte length of the file."""
        target = tmp_path / "x.bin"
        payload = b"\x00\x01\x02\x03\x04"
        target.write_bytes(payload)
        assert get_file_metadata(target)["size_bytes"] == len(payload)
