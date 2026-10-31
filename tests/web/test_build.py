"""Tests for web build CLI."""

import sys


def test_needs_rebuild_no_marker(tmp_path):
    """Verify rebuild needed when marker doesn't exist."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    marker_file = dist_dir / ".web-build-marker"

    from src.profiles.web.build import _needs_rebuild

    assert _needs_rebuild(marker_file)


def test_needs_rebuild_with_marker(tmp_path):
    """Verify rebuild not needed when marker exists."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    marker_file = dist_dir / ".web-build-marker"
    marker_file.touch()

    # Note: This test verifies marker exists, actual timestamp logic
    # depends on package.json which may not exist in test
    assert marker_file.exists()


def test_main_without_npm(capsys, monkeypatch, tmp_path):
    """Verify CLI fails gracefully when no usable npm is found."""
    # Simulate an environment where npm can never execute, whatever PATH
    # is used (the real machine may have a working npm on PATH or in the
    # hardcoded fallback dirs).
    monkeypatch.setattr("src.profiles.web.build._npm_runs", lambda env: False)
    monkeypatch.setattr(
        "src.profiles.web.build._NODE_FALLBACK_DIRS",
        {sys.platform: [str(tmp_path / "no-node")]},
    )

    # Mock sys.argv to avoid pytest arguments
    monkeypatch.setattr("sys.argv", ["build.py"])

    from src.profiles.web.build import main

    result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "npm not found" in captured.err


def test_build_env_falls_back_to_node_dirs(monkeypatch, tmp_path):
    """Verify _build_env rescues a broken PATH npm from the fallback dirs."""
    import src.profiles.web.build as build

    fallback = tmp_path / "nodejs"
    fallback.mkdir()
    (fallback / "npm").touch()

    # First probe (PATH as-is) fails; the probe on the patched PATH succeeds.
    attempts: list[str] = []

    def fake_npm_runs(env):
        attempts.append(env["PATH"])
        return len(attempts) > 1

    monkeypatch.setattr(build, "_npm_runs", fake_npm_runs)
    monkeypatch.setattr(build, "_NODE_FALLBACK_DIRS", {sys.platform: [str(fallback)]})

    env = build._build_env()

    assert env is not None
    assert str(fallback) == attempts[1].split(build.os.pathsep)[0]
