"""Instance manifest: write/read/prune lifecycle and PID liveness."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from profiles.desktop.instance import (
    InstanceManifest,
    manifest_path,
    pid_alive,
    prune_stale_manifests,
    read_manifest,
    remove_manifest,
    write_manifest,
)


@pytest.fixture
def temp_tempdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the manifest temp dir so tests never touch the real one."""
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    return tmp_path


def _manifest(port: int = 8088, pid: int | None = None) -> InstanceManifest:
    return InstanceManifest(
        pid=pid if pid is not None else os.getpid(),
        port=port,
        host="127.0.0.1",
        version="0.9.0",
        token="secret-token",
    )


class TestManifestRoundtrip:
    """write_manifest / read_manifest / remove_manifest."""

    def test_write_then_read_returns_equal_manifest(self, temp_tempdir: Path) -> None:
        manifest = _manifest(port=9101)
        path = write_manifest(manifest)

        assert path == manifest_path(9101)
        assert path.exists()
        assert read_manifest(9101) == manifest

    def test_read_missing_manifest_returns_none(self, temp_tempdir: Path) -> None:
        assert read_manifest(9102) is None

    def test_remove_manifest_deletes_file(self, temp_tempdir: Path) -> None:
        write_manifest(_manifest(port=9103))
        remove_manifest(9103)
        assert not manifest_path(9103).exists()

    def test_remove_missing_manifest_is_safe(self, temp_tempdir: Path) -> None:
        remove_manifest(9104)  # must not raise

    def test_write_is_atomic_leaves_no_tmp_files(self, temp_tempdir: Path) -> None:
        write_manifest(_manifest(port=9105))
        leftovers = list(temp_tempdir.glob("*.tmp"))
        assert leftovers == []


class TestStaleManifestHandling:
    """Stale manifests are ignored AND cleaned so they never misidentify."""

    def test_corrupt_manifest_returns_none_and_is_removed(self, temp_tempdir: Path) -> None:
        path = manifest_path(9106)
        path.write_text("{not json", encoding="utf-8")

        assert read_manifest(9106) is None
        assert not path.exists()

    def test_manifest_with_missing_fields_returns_none(self, temp_tempdir: Path) -> None:
        path = manifest_path(9107)
        path.write_text(json.dumps({"pid": 1}), encoding="utf-8")

        assert read_manifest(9107) is None
        assert not path.exists()

    def test_dead_pid_manifest_returns_none_and_is_removed(
        self, temp_tempdir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("profiles.desktop.instance.pid_alive", lambda pid: False)
        path = manifest_path(9108)
        write_manifest(_manifest(port=9108))

        assert read_manifest(9108) is None
        assert not path.exists()

    def test_live_pid_manifest_is_kept(self, temp_tempdir: Path) -> None:
        manifest = _manifest(port=9109, pid=os.getpid())
        write_manifest(manifest)
        assert read_manifest(9109) == manifest


class TestPidAlive:
    """Cross-platform PID liveness (must never kill the checked process)."""

    def test_own_pid_is_alive(self) -> None:
        assert pid_alive(os.getpid()) is True

    def test_nonpositive_pid_is_dead(self) -> None:
        assert pid_alive(0) is False
        assert pid_alive(-1) is False

    def test_implausible_pid_is_dead(self) -> None:
        # Above any plausible OS pid_max (Linux ~4M, macOS ~100k, Windows ~4M).
        assert pid_alive(2**40) is False


class TestPruneStaleManifests:
    """Startup hygiene: dead-PID manifests go, live ones stay."""

    def test_prunes_dead_and_corrupt_keeps_live(self, temp_tempdir: Path) -> None:
        live = manifest_path(9110)
        write_manifest(_manifest(port=9110, pid=os.getpid()))
        dead = manifest_path(9111)
        write_manifest(_manifest(port=9111, pid=2**40))
        corrupt = manifest_path(9112)
        corrupt.write_text("garbage", encoding="utf-8")

        prune_stale_manifests()

        assert live.exists()
        assert not dead.exists()
        assert not corrupt.exists()
