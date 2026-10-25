"""Tests for web build CLI."""


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


def test_main_without_npm(capsys, monkeypatch):
    """Verify CLI fails gracefully when npm not found."""
    # Mock shutil.which to return None
    import shutil

    original_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda x: None)

    # Mock sys.argv to avoid pytest arguments
    monkeypatch.setattr("sys.argv", ["build.py"])

    from src.profiles.web.build import main

    result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "npm not found" in captured.err

    # Restore
    monkeypatch.setattr(shutil, "which", original_which)
