"""Shared test fixtures for ProFiles."""

from __future__ import annotations

import os

# Mock os.startfile on non-Windows platforms so that mocker.patch("os.startfile") works
if not hasattr(os, "startfile"):
    os.startfile = lambda path: None

from pathlib import Path
from textwrap import dedent

import pytest


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "requires_tkinter: mark test as requiring Tkinter to be available"
    )


@pytest.fixture(scope="function")
def sample_config_path(tmp_path: Path) -> Path:
    """Create a sample .profiles YAML file for baseline testing."""
    config_content = """
version: 1
defaults:
    title: "ProFiles Test"
    extensions: [".txt", ".py"]
    filters: ["ST_PRO", "ST_ENG"]
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
