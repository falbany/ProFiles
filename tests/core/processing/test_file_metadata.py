"""Tests for profiles.core.processing.file_metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.processing.file_metadata import collect_file_attrs, get_file_metadata


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


class TestCollectFileAttrs:
    """Tests for collect_file_attrs()."""

    def test_returns_size_mtime_birthtime(self, tmp_path: Path) -> None:
        """The snapshot carries size, mtime and a birthtime (ctime fallback)."""
        f = tmp_path / "a.log"
        f.write_text("x" * 1234)
        attrs = collect_file_attrs(f)
        assert attrs is not None
        assert attrs.size_bytes == 1234
        assert attrs.mtime == pytest.approx(f.stat().st_mtime)
        assert attrs.birthtime == pytest.approx(f.stat().st_ctime)  # Linux fallback path

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """A non-existent path yields None instead of raising."""
        assert collect_file_attrs(tmp_path / "gone.log") is None

    def test_birthtime_prefers_st_birthtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """st_birthtime wins over the st_ctime fallback when the OS provides it."""
        f = tmp_path / "a.log"
        f.write_text("x")
        st = f.stat()

        # Simulate an OS with st_birthtime: build a stat_result-like shim
        class _Shim:
            st_size = st.st_size
            st_mtime = st.st_mtime + 5.0
            st_ctime = st.st_ctime
            st_birthtime = st.st_mtime + 5.0

        monkeypatch.setattr("profiles.core.processing.file_metadata._stat_path", lambda p: _Shim())
        attrs = collect_file_attrs(f)
        assert attrs is not None and attrs.birthtime == pytest.approx(st.st_mtime + 5.0)
