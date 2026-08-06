"""Shared test fixtures for ProFiles."""

from __future__ import annotations

import os

# Mock os.startfile on non-Windows platforms so that mocker.patch("os.startfile") works
if not hasattr(os, "startfile"):
    os.startfile = lambda path: None

from pathlib import Path

import pytest


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "requires_tkinter: mark test as requiring Tkinter to be available"
    )


@pytest.fixture
def sample_profile_conf(tmp_path: Path) -> Path:
    """Create a minimal .profiles configuration for testing."""
    content = """version: 1
defaults:
  release: "2025.3.0"
  gui_auto_launch: true
  close_after_execute: false
  extension: .mttl
  filter: ""
configs:
  c1:
    pc_ip: All
    pc_hostname: All
    pc_name: All
    directory: M:/test/dir
"""
    path = tmp_path / ".profiles"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def sample_files(tmp_path: Path) -> Path:
    """Create sample test program files for testing."""
    files = [
        "ST_PRO_Mutest_V01-Rel6.2.1.mttl",
        "ST_ENG_Test_V02.mttl",
        "ST_PRO_Production_V03.mttx",
        "readme.txt",
        "config.ini",
    ]
    for f in files:
        (tmp_path / f).write_text("dummy", encoding="utf-8")
    return tmp_path


@pytest.fixture
def config_with_profile(tmp_path: Path) -> Path:
    """Create a tmp_path with both .profiles config and sample files.

    This fixture ensures that tests never trigger the config creation prompt.
    """
    # Create config file
    content = f"""version: 1
defaults:
  release: "2025.3.0"
  gui_auto_launch: false
  close_after_execute: false
  extension: .mttl
  filter: ""
configs:
  c1:
    pc_ip: All
    pc_hostname: All
    pc_name: All
    directory: {str(tmp_path)}
"""
    config_path = tmp_path / ".profiles"
    config_path.write_text(content, encoding="utf-8")

    # Create sample files
    files = [
        "ST_PRO_Mutest_V01-Rel6.2.1.mttl",
        "ST_ENG_Test_V02.mttl",
        "ST_PRO_Production_V03.mttx",
    ]
    for f in files:
        (tmp_path / f).write_text("dummy", encoding="utf-8")

    return tmp_path
