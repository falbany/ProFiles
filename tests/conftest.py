"""Shared test fixtures for ProFiles."""

from __future__ import annotations

import os

# Mock os.startfile on non-Windows platforms so that mocker.patch("os.startfile") works
if not hasattr(os, "startfile"):
    os.startfile = lambda path: None

from pathlib import Path
from textwrap import dedent

import pytest


@pytest.fixture(scope="function")
def sample_config_path(tmp_path: Path) -> Path:
    """Create a sample .profiles YAML file for baseline testing."""
    config_content = """
version: 1
defaults:
    title: "ProFiles Test"
    extensions: [".txt", ".py"]
    filters: ["PROD", "DEV"]
    search_exclude_dirs: [".git", "build"]
    search_exclude_files: ["*.tmp"]
    row_colors:
        - { pattern: "*", color: "white" }

configs:
    all_hosts:
        match:
            hostname: ["All"]
        scan: ["/mount/default"]
        extensions: [".md"]
        filters: ["DOC"]
"""
    config_file = tmp_path / ".profiles"
    config_file.write_text(dedent(config_content))
    return config_file


@pytest.fixture(scope="function")
def empty_config_path(tmp_path: Path) -> Path:
    """Create an empty .profiles file."""
    config_content = """
version: 1
configs:
    all_hosts:
        match:
            hostname: ["All"]
        scan: ["/mount/default"]
"""
    config_file = tmp_path / ".profiles"
    config_file.write_text(dedent(config_content))
    return config_file


@pytest.fixture(scope="function")
def isolated_user_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the per-user data dir at a temp home (issue #191 hermeticity).

    Every path helper in :mod:`profiles.core.paths` resolves the user
    home through ``Path.home()``; patching it makes ``user_data_dir``,
    ``user_config_path``, ``find_user_config``, the uninformative-directory
    home check and the ``default_search_directory`` fallback all see the
    same fake home, so tests never depend on (or pollute) the developer's
    real ``~/.profiles`` folder.  Returns the fake home itself.
    """
    user_home = tmp_path / "uhome"
    user_home.mkdir()
    monkeypatch.setattr("profiles.core.paths.Path.home", lambda: user_home)
    return user_home
