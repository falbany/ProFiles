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


def test_only_release_workflow_triggers_on_version_tags() -> None:
    """Exactly one workflow may trigger on `v*` tags: release.yml (stale duplicates pollute releases)."""
    workflows = (_PYPROJECT.parent / ".github" / "workflows").glob("*.yml")
    tag_triggers = set()
    for wf in workflows:
        text = wf.read_text(encoding="utf-8")
        if "tags:" in text and "'v*'" in text.replace('"v*"', "'v*'"):
            tag_triggers.add(wf.name)
    assert tag_triggers == {"release.yml"}, (
        f"workflows co-triggering on v* tags: {sorted(tag_triggers)}"
    )


def test_briefcase_document_type_uses_singular_table_with_url() -> None:
    """Briefcase 0.4.x binds the *singular* ``document_type`` table param.

    The plural ``document_types`` key is absorbed by **kwargs and then
    overwritten with ``{}`` (AppConfig.__init__ assigns from the singular
    ``document_type`` param only), so no CFBundleDocumentTypes ever reach
    Info.plist and macOS cannot associate ``*.profiles`` files. Each entry
    requires extension/icon/description/url (validate_document_type_config).
    """
    data = _load()
    doc_types = data["tool"]["briefcase"]["app"]["profiles"]["document_type"]
    assert isinstance(doc_types, dict) and "profiles" in doc_types
    entry = doc_types["profiles"]
    assert entry["extension"] == "profiles"
    assert entry["extension"].isalnum()
    assert isinstance(entry["icon"], str) and entry["icon"]
    assert isinstance(entry["description"], str) and entry["description"]
    assert entry["url"].startswith("https://")
    mac = entry.get("macOS", {})
    assert mac.get("CFBundleTypeRole") == "Editor"
    assert mac.get("LSHandlerRank") == "Owner"


def test_briefcase_requires_runtime_complete_and_tk_free() -> None:
    requires = " ".join(_load()["tool"]["briefcase"]["app"]["profiles"]["requires"]).lower()
    for pkg in ("pydantic", "fastapi", "uvicorn", "pywebview", "sse-starlette", "qrcode", "ruamel"):
        assert pkg in requires
    assert "sv-ttk" not in requires
    assert "darkdetect" not in requires
