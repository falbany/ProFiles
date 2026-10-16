"""Tests for ProFiles.pyw launch behavior."""

from __future__ import annotations

import sys
from unittest.mock import patch


class TestChooseWorkingDir:
    """Tests for _choose_working_dir() helper in ProFiles.pyw."""

    def test_shortcut_uses_invoking_folder(self, tmp_path, monkeypatch) -> None:
        """When launch context provides a working directory, it is used."""
        # Simulate launch context with working_directory set
        invoking_folder = tmp_path / "invoking_folder"
        invoking_folder.mkdir()

        from profiles.launch import LaunchContext

        ctx = LaunchContext(
            document_paths=(),
            working_directory=invoking_folder,
            explicit_config=None,
            source="launcher",
        )

        with patch("profiles.launch.detect_launch_context", return_value=ctx):
            # Import after patching
            import importlib

            import ProFiles

            importlib.reload(ProFiles)

            result = ProFiles._choose_working_dir(tmp_path)

        assert result == invoking_folder

    def test_shortcut_falls_back_to_script_folder(self, tmp_path, monkeypatch) -> None:
        """When launch context has no working directory, script folder is used."""
        from profiles.launch import LaunchContext

        ctx = LaunchContext(
            document_paths=(),
            working_directory=None,
            explicit_config=None,
            source="cwd",
        )

        with patch("profiles.launch.detect_launch_context", return_value=ctx):
            import importlib

            import ProFiles

            importlib.reload(ProFiles)

            result = ProFiles._choose_working_dir(tmp_path)

        assert result == tmp_path

    def test_add_src_to_path_still_targets_the_script_repo(self, tmp_path) -> None:
        """_add_src_to_path still uses the script's repo root, not invoking folder."""
        # Create src/ directory in the script's repo
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        import importlib

        import ProFiles

        importlib.reload(ProFiles)

        # The function should add tmp_path/src to sys.path
        with patch.object(ProFiles, "_project_root", return_value=tmp_path):
            ProFiles._add_src_to_path(tmp_path)

        # Verify src/ is in sys.path
        assert any("src" in p and str(tmp_path) in p for p in sys.path)
