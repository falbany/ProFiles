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
    detect_launch_context,
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
