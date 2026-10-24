"""Packaging rules: Tk-only deps are dev-only; Briefcase requires are runtime-complete.

Related spec: docs/superpowers/specs/2026-10-23-native-installer-design.md §5.1, §5.3.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _load() -> dict:
    with _PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_tk_deps_absent_from_runtime_dependencies() -> None:
    deps = " ".join(_load()["project"]["dependencies"]).lower()
    assert "sv-ttk" not in deps
    assert "darkdetect" not in deps


def test_tk_deps_present_in_both_dev_lists() -> None:
    data = _load()
    extras_dev = " ".join(data["project"]["optional-dependencies"]["dev"]).lower()
    groups_dev = " ".join(data["dependency-groups"]["dev"]).lower()
    for where in (extras_dev, groups_dev):
        assert "sv-ttk" in where
        assert "darkdetect" in where


def test_dev_dependency_lists_stay_in_sync() -> None:
    """Spec §5.1: [project.optional-dependencies].dev and [dependency-groups].dev must match."""
    data = _load()
    extras_dev = set(data["project"]["optional-dependencies"]["dev"])
    groups_dev = set(data["dependency-groups"]["dev"])
    assert extras_dev == groups_dev


def test_briefcase_available_as_dev_dependency() -> None:
    """CI runs `uv run briefcase` without a global install: briefcase must be in dev deps."""
    data = _load()
    extras_dev = " ".join(data["project"]["optional-dependencies"]["dev"]).lower()
    groups_dev = " ".join(data["dependency-groups"]["dev"]).lower()
    for where in (extras_dev, groups_dev):
        assert "briefcase" in where


def test_briefcase_requires_runtime_complete_and_tk_free() -> None:
    requires = " ".join(_load()["tool"]["briefcase"]["app"]["profiles"]["requires"]).lower()
    for pkg in ("pydantic", "fastapi", "uvicorn", "pywebview", "sse-starlette", "qrcode", "ruamel"):
        assert pkg in requires
    assert "sv-ttk" not in requires
    assert "darkdetect" not in requires
