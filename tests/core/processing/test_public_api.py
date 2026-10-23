"""Public API tests — Task 11.

Public names, read-only ``filename`` alias, the shared depth default,
and required ``rel_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.config.models import DEFAULT_MAX_SEARCH_DEPTH
from profiles.core.processing import file_classifier
from profiles.core.processing.file_classifier import (
    build_column_extractor,
    strip_extension_from_version,
)
from profiles.core.processing.scanner import ScannedFile, ScannedFileDynamic


class TestScannedFileApi:
    """rel_path is the field; filename stays as a read-only alias."""

    def test_filename_alias_equals_rel_path(self) -> None:
        entry = ScannedFile("some/display/path.mttl", "1.0", Path("some/display/path.mttl"))
        assert entry.rel_path == "some/display/path.mttl"
        assert entry.filename == entry.rel_path

    def test_filename_alias_read_only(self) -> None:
        entry = ScannedFile("a.mttl", "", Path("a.mttl"))
        with pytest.raises(AttributeError):
            entry.filename = "other.mttl"  # type: ignore[misc]


class TestScannedFileDynamicApi:
    """rel_path is a required positional/keyword argument."""

    def test_rel_path_required(self) -> None:
        with pytest.raises(TypeError):
            ScannedFileDynamic(Path("a.mttl"), {})  # type: ignore[call-arg]

    def test_full_construction(self) -> None:
        entry = ScannedFileDynamic(Path("a.mttl"), {"File": "a.mttl"}, "a.mttl")
        assert entry.rel_path == "a.mttl"


class TestDepthDefault:
    """One shared depth constant: DEFAULT_MAX_SEARCH_DEPTH."""

    def test_value_is_ten(self) -> None:
        assert DEFAULT_MAX_SEARCH_DEPTH == 10


class TestPublicClassifierNames:
    """file_classifier exposes public names; private aliases remain."""

    def test_build_column_extractor_public(self) -> None:
        assert file_classifier.build_column_extractor is build_column_extractor
        assert file_classifier._build_column_extractor is build_column_extractor

    def test_strip_extension_from_version_public(self) -> None:
        assert file_classifier.strip_extension_from_version is strip_extension_from_version
        assert file_classifier._strip_extension_from_version is strip_extension_from_version

    def test_strip_extension_from_version_behavior(self) -> None:
        assert strip_extension_from_version("1.0.2-beta.mttl", "mttl") == "1.0.2-beta"
        assert strip_extension_from_version("1.0.2-beta", "mttl") == "1.0.2-beta"
