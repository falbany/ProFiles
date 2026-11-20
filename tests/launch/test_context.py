"""Tests for profiles.launch.context — launch-signal detection.

Source of truth for how ProFiles learns *where it was started from* on
each platform.  If macOS ever changes how a double-click is delivered,
these tests are the first place the change should show up.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from profiles.launch.context import (
    CONFIG_SUFFIX,
    FALLBACK_CONFIG_SUFFIX,
    FALLBACK_CONFIG_SUFFIXES,
    LaunchContext,
    _documents_from_argv,
    cwd_is_uninformative,
    detect_launch_context,
    with_documents,
)


class TestDocumentsFromArgv:
    def test_parses_profiles_documents(self) -> None:
        paths = _documents_from_argv(["prog", "/a/my.profiles", "/b/proj.profiles"])
        # Use resolve() so Windows paths include drive letter
        assert paths == (Path("/a/my.profiles").resolve(), Path("/b/proj.profiles").resolve())

    def test_accepts_legacy_yaml_suffix(self) -> None:
        paths = _documents_from_argv(["prog", "/a/config.profiles.yaml"])
        assert paths == (Path("/a/config.profiles.yaml").resolve(),)

    def test_accepts_yml_suffix(self) -> None:
        paths = _documents_from_argv(["prog", "/a/config.profiles.yml"])
        assert paths == (Path("/a/config.profiles.yml").resolve(),)

    def test_ignores_non_config_argv(self) -> None:
        assert _documents_from_argv(["prog", "file.mttl", "other.txt"]) == ()

    def test_ignores_flag_like_argv(self) -> None:
        assert _documents_from_argv(["prog", "--server-only", "--config"]) == ()

    def test_ignores_none_entries_without_raising(self) -> None:
        # Hostile input must never crash startup.
        assert _documents_from_argv(["prog", "", "   ", "."]) == ()

    def test_relative_document_is_resolved_absolute(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        paths = _documents_from_argv(["prog", "my.profiles"])
        # /tmp is a symlink to /private/tmp on macOS, so resolve() follows it
        # and the comparison must too.
        expected = (tmp_path / "my.profiles").resolve()
        assert paths == (expected,)
        assert paths[0].is_absolute()

    def test_matches_the_declared_suffixes(self) -> None:
        assert CONFIG_SUFFIX == ".profiles"
        assert FALLBACK_CONFIG_SUFFIX == ".profiles.yaml"
        assert FALLBACK_CONFIG_SUFFIXES == (".profiles.yaml", ".profiles.yml")


class TestDetectLaunchContext:
    def test_returns_launch_context(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        ctx = detect_launch_context(["prog"])
        assert isinstance(ctx, LaunchContext)

    def test_documents_reach_the_context(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        doc = tmp_path / "x.profiles"
        ctx = detect_launch_context(["prog", str(doc)])
        assert doc.resolve() in ctx.document_paths

    def test_working_directory_defaults_to_cwd(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        ctx = detect_launch_context(["prog"])
        assert ctx.working_directory == tmp_path

    def test_explicit_config_is_none_by_default(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        assert detect_launch_context(["prog"]).explicit_config is None

    def test_source_is_a_documented_value(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        monkeypatch.chdir("/")
        assert detect_launch_context(["prog"]).source in {
            "document",
            "launcher",
            "cwd",
            "explicit",
        }

    def test_source_is_document_when_one_is_supplied(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        doc = tmp_path / "x.profiles"
        ctx = detect_launch_context(["prog", str(doc)])
        assert ctx.source == "document"

    def test_source_is_cwd_without_document_or_probe(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        assert detect_launch_context(["prog"]).source == "cwd"

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only source label")
    def test_source_is_launcher_when_cwd_is_uninformative(self, monkeypatch) -> None:
        """A GUI-style launch (CWD == "/") attributes the folder to the launcher."""
        monkeypatch.chdir("/")
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: Path("/Users/someone/ProjectFolder"),
        )
        ctx = detect_launch_context(["prog"])
        assert ctx.source == "launcher"
        assert ctx.working_directory == Path("/Users/someone/ProjectFolder")

    def test_real_cwd_beats_probe(self, monkeypatch, tmp_path) -> None:
        """A terminal launch must never have its CWD hijacked by the probe."""
        monkeypatch.chdir(tmp_path)
        unrelated = Path("/the/front/finder/window")
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: unrelated,
        )
        ctx = detect_launch_context(["prog"])
        assert ctx.source == "cwd"
        assert ctx.working_directory == tmp_path
        assert ctx.working_directory != unrelated

    def test_detects_argv_from_sys_when_not_supplied(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        doc = tmp_path / "from-argv.profiles"
        monkeypatch.setattr(sys, "argv", ["prog", str(doc)])
        assert doc.resolve() in detect_launch_context().document_paths


class TestFinderProbe:
    def test_failure_is_silent(self, monkeypatch) -> None:
        """A failed probe must degrade, never raise."""

        def _boom(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=2.0)

        monkeypatch.setattr(subprocess, "run", _boom)
        assert _call_probe() is None

    def test_os_error_is_silent(self, monkeypatch) -> None:
        def _boom(*_a, **_k):
            raise FileNotFoundError("osascript missing")

        monkeypatch.setattr(subprocess, "run", _boom)
        assert _call_probe() is None

    def test_empty_output_is_none(self, monkeypatch) -> None:
        monkeypatch.setattr(
            subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 0, "", "")
        )
        assert _call_probe() is None

    def test_installed_probe_is_inert_off_macos(self) -> None:
        """Off macOS the probe must not spawn anything."""
        if sys.platform == "darwin":
            pytest.skip("probe shells out to Finder on macOS")

        def _no_subprocess(*_a, **_k):
            raise AssertionError("the probe must not spawn a subprocess off macOS")

        original = subprocess.run
        subprocess.run = _no_subprocess  # type: ignore[assignment]
        try:
            assert _call_probe() is None
        finally:
            subprocess.run = original  # type: ignore[assignment]


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only probe")
class TestFinderProbeMacOS:
    def test_probe_parses_finder_output(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: subprocess.CompletedProcess([], 0, f"{tmp_path}\n", ""),
        )
        assert _call_probe() == tmp_path

    def test_probe_ignores_non_directory_result(self, monkeypatch, tmp_path) -> None:
        missing = tmp_path / "gone"
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: subprocess.CompletedProcess([], 0, f"{missing}\n", ""),
        )
        assert _call_probe() is None


def _call_probe() -> Path | None:
    from profiles.launch.context import _finder_working_directory

    return _finder_working_directory()


class TestWithDocuments:
    """Merging odoc-captured documents into the launch context (#188)."""

    def test_empty_documents_returns_context_unchanged(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        ctx = detect_launch_context(["prog"])
        assert with_documents(ctx, []) is ctx

    def test_merges_captured_documents_and_marks_source(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: None,
        )
        doc = tmp_path / "clicked.profiles"
        ctx = with_documents(detect_launch_context(["prog"]), [str(doc)])
        assert ctx.document_paths == (doc.resolve(),)
        assert ctx.source == "document"

    def test_argv_documents_win_over_captured_duplicates(self, tmp_path) -> None:
        ctx = LaunchContext(
            document_paths=(Path("/a/argv.profiles"),),
            working_directory=None,
            explicit_config=None,
            source="document",
        )
        merged = with_documents(ctx, ["/a/argv.profiles", "/b/odoc.profiles"])
        assert merged.document_paths == (
            Path("/a/argv.profiles").resolve(),
            Path("/b/odoc.profiles").resolve(),
        )

    def test_relative_documents_resolve_against_cwd(self, monkeypatch, tmp_path) -> None:
        monkeypatch.chdir(tmp_path)
        ctx = LaunchContext(
            document_paths=(),
            working_directory=None,
            explicit_config=None,
            source="cwd",
        )
        merged = with_documents(ctx, ["clicked.profiles"])
        assert merged.document_paths == ((tmp_path / "clicked.profiles").resolve(),)
        assert merged.source == "document"


class TestCwdIsUninformative:
    """The GUI-launch CWD heuristic shared by the probe and odoc capture.

    Delegates to profiles.core.paths.is_uninformative_directory (issue
    #191), so System32-style and home-folder CWDs are uninformative on
    every platform — verified here with monkeypatched env vars / homes
    for portability.
    """

    def test_root_is_uninformative(self) -> None:
        assert cwd_is_uninformative(Path("/")) is True

    def test_none_is_uninformative(self) -> None:
        assert cwd_is_uninformative(None) is True

    def test_runtime_prefix_is_uninformative(self) -> None:
        assert cwd_is_uninformative(Path(sys.prefix) / "sub") is True

    def test_real_working_directory_is_informative(self, tmp_path) -> None:
        assert cwd_is_uninformative(tmp_path) is False

    def test_system32_is_uninformative(self, isolated_user_home, monkeypatch) -> None:
        """Start-Menu CWD (%SystemRoot%\\System32) must be discarded (#191)."""
        monkeypatch.setenv("SystemRoot", str(isolated_user_home / "Windows"))
        system32 = isolated_user_home / "Windows" / "System32"
        system32.mkdir(parents=True)
        assert cwd_is_uninformative(system32) is True

    def test_home_folder_is_uninformative(self, isolated_user_home) -> None:
        """A launcher CWD == home says nothing about a project (#191)."""
        assert cwd_is_uninformative(isolated_user_home) is True


class TestProbeResultFiltering:
    """The Finder probe result must pass the same policy as a CWD (#191).

    The probe mirrors the front Finder window — often the folder the user
    launched FROM (a mounted DMG volume, /Applications), not their
    project.  A probe result that is itself uninformative is discarded
    and the launch falls back to the plain CWD.
    """

    def test_probe_result_on_mount_point_is_discarded(self, monkeypatch, tmp_path) -> None:
        """A probe returning a mounted DMG volume falls back to the CWD."""
        import profiles.core.paths as paths_module

        dmg = tmp_path / "ProFiles 0.12.0b1"
        dmg.mkdir()
        monkeypatch.setattr("profiles.launch.context._finder_working_directory", lambda: dmg)
        real_device_id = paths_module._device_id

        def fake_device_id(path):
            try:
                if path.resolve() == dmg.resolve():
                    return 424242  # separate "volume"
            except OSError:
                return None
            return real_device_id(path)

        monkeypatch.setattr(paths_module, "_device_id", fake_device_id)
        monkeypatch.chdir("/")  # GUI-style launch: uninformative CWD

        ctx = detect_launch_context(["prog"])

        assert ctx.source == "cwd"
        assert ctx.working_directory == Path("/")

    def test_probe_result_in_project_folder_is_kept(self, monkeypatch, tmp_path) -> None:
        """A probe returning a real project folder is still trusted."""
        monkeypatch.setattr(
            "profiles.launch.context._finder_working_directory",
            lambda: tmp_path / "project",
        )
        (tmp_path / "project").mkdir()
        monkeypatch.chdir("/")

        ctx = detect_launch_context(["prog"])

        assert ctx.source == "launcher"
        assert ctx.working_directory == tmp_path / "project"
