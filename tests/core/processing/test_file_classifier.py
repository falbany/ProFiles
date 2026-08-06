"""Tests for profiles.core.processing.file_classifier — get_file_info, get_file_info_dynamic, extract_version, directory_exists, ensure_trailing_separator."""

from __future__ import annotations

import os
from pathlib import Path

from profiles.core.processing.file_classifier import (
    directory_exists,
    ensure_trailing_separator,
    extract_version,
    get_file_info,
    get_file_info_dynamic,
)


class TestEnsureTrailingSeparator:
    """ensure_trailing_separator adds/keeps trailing os.sep."""

    def test_adds_separator(self) -> None:
        result = ensure_trailing_separator("C:/path")
        assert result.endswith(os.sep)

    def test_preserves_existing_separator(self) -> None:
        result = ensure_trailing_separator(f"C:/path{os.sep}")
        assert result.endswith(os.sep)
        assert result == f"C:/path{os.sep}"

    def test_pathlib_path(self) -> None:
        result = ensure_trailing_separator(Path("C:/path"))
        assert result.endswith(os.sep)

    def test_empty_string(self) -> None:
        result = ensure_trailing_separator("")
        assert result == os.sep


class TestDirectoryExists:
    """directory_exists checks for existing directories."""

    def test_existing_directory(self, tmp_path: Path) -> None:
        assert directory_exists(tmp_path) is True

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        assert directory_exists(tmp_path / "nope") is False

    def test_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello", encoding="utf-8")
        assert directory_exists(f) is False

    def test_pathlib_path(self, tmp_path: Path) -> None:
        assert directory_exists(tmp_path) is True


class TestExtractVersion:
    """extract_version — extract _V<version> from filenames."""

    def test_with_version(self) -> None:
        assert extract_version("ST_PRO_Mutest_V01-Rel6.2.1.mttl") == "01-Rel6.2.1.mttl"

    def test_no_version(self) -> None:
        assert extract_version("ST_PRO_Mutest.mttl") == ""

    def test_with_extension_strip(self) -> None:
        result = extract_version("ST_PRO_Mutest_V01-Rel6.2.1.mttl", extension=".mttl")
        assert result == "01-Rel6.2.1"

    def test_case_insensitive_v(self) -> None:
        assert extract_version("file_v1.0.txt") == "1.0.txt"

    def test_empty_filename(self) -> None:
        assert extract_version("") == ""

    def test_extension_lowercase_normalized(self) -> None:
        result = extract_version("file_V1.0.MTTL", extension=".mttl")
        assert result == "1.0"

    def test_extension_with_dot_handling(self) -> None:
        result = extract_version("file_V1.0.txt", extension="txt")
        assert result == "1.0"

    def test_version_at_start(self) -> None:
        """_V at the very start."""
        assert extract_version("_V1.0_file.mttl") == "1.0_file.mttl"

    def test_no_underscore_before_v(self) -> None:
        """Only _V triggers version extraction."""
        assert extract_version("file_Version1.mttl") == "ersion1.mttl"  # matches _V(.+)


class TestGetFileInfo:
    """get_file_info — returns (filename, version)."""

    def test_prod_file_with_version(self, tmp_path: Path) -> None:
        f = tmp_path / "ST_PRO_Test_V1.0.mttl"
        f.write_text("", encoding="utf-8")
        filename, version = get_file_info(f, extension=".mttl")
        assert filename == "ST_PRO_Test_V1.0.mttl"
        assert version == "1.0"

    def test_dev_file_no_version(self, tmp_path: Path) -> None:
        f = tmp_path / "ST_ENG_Test.mttl"
        f.write_text("", encoding="utf-8")
        filename, version = get_file_info(f)
        assert version == ""

    def test_string_path(self) -> None:
        result = get_file_info("/some/path/PRO_file_V2.txt", extension=".txt")
        assert result[0] == "PRO_file_V2.txt"
        assert result[1] == "2"


class TestGetFileInfoDynamic:
    """Test dynamic file info extraction."""

    def test_extract_version_and_device(self) -> None:
        """Test extracting version and device from filename."""
        from profiles.config import ColumnConfiguration

        columns = {
            "Version": ColumnConfiguration(
                name="Version", width=150, expression=r"_V(.+)", group=1, priority=10
            ),
            "Device": ColumnConfiguration(
                name="Device", width=120, expression=r"Device_([A-Z0-9]+)", group=1, priority=5
            ),
        }

        result = get_file_info_dynamic(
            "test_Device_ABC123_V01-Rel6.2.1.mttl",
            "mttl",
            ("File", "Version", "Device"),
            columns,
        )

        assert result["File"] == "test_Device_ABC123_V01-Rel6.2.1.mttl"
        assert result["Version"] == "01-Rel6.2.1"  # Extension stripped
        assert result["Device"] == "ABC123"

    def test_extract_with_default_value(self) -> None:
        """Test extraction with default value when pattern doesn't match."""
        from profiles.config import ColumnConfiguration

        columns = {
            "Version": ColumnConfiguration(
                name="Version", width=150, expression=r"_V(.+)", group=1, priority=10
            ),
            "Device": ColumnConfiguration(
                name="Device",
                width=120,
                expression=r"Device_([A-Z0-9]+)",
                group=1,
                priority=5,
                default="Unknown",
            ),
        }

        result = get_file_info_dynamic(
            "nodeviceatall_V01.mttl",
            "mttl",
            ("File", "Version", "Device"),
            columns,
        )

        assert result["Device"] == "Unknown"

    def test_legacy_mode_no_definitions(self) -> None:
        """Test legacy mode when column_definitions is empty."""
        result = get_file_info_dynamic(
            "test_V01.mttl",
            "mttl",
            ("File", "Version"),
            "",
        )

        assert result["File"] == "test_V01.mttl"
        assert result["Version"] == "01"

    def test_extension_stripping_from_version(self) -> None:
        """Test that extension is stripped from version."""
        from profiles.config import ColumnConfiguration

        columns = {
            "Version": ColumnConfiguration(
                name="Version", width=150, expression=r"_V(.+)", group=1, priority=10
            ),
        }

        result = get_file_info_dynamic(
            "test_V01-Rel6.2.1.mttl",
            "mttl",
            ("File", "Version"),
            columns,
        )

        assert result["Version"] == "01-Rel6.2.1"  # .mttl stripped

    def test_column_without_expression_skipped(self) -> None:
        """A column config without an expression is not added as a rule."""
        from profiles.config import ColumnConfiguration

        columns = {
            "Version": ColumnConfiguration(name="Version", width=150, expression=""),
        }

        result = get_file_info_dynamic(
            "test_V01.mttl",
            "mttl",
            ("File", "Version"),
            columns,
        )

        # No rule → Version falls back to legacy _V(.+) behavior? No: with
        # columns truthy, no default rule is added, so Version is empty.
        assert result["File"] == "test_V01.mttl"
        assert result["Version"] == ""

    def test_custom_file_rule_wins_over_path(self) -> None:
        """A user-defined File column rule replaces the full path."""
        from profiles.config import ColumnConfiguration

        columns = {
            "File": ColumnConfiguration(
                name="File", width=200, expression=r"ST_([A-Z]+)_", group=1, priority=100
            ),
        }

        result = get_file_info_dynamic(
            "ST_PRO_Test_V01.mttl",
            "mttl",
            ("File",),
            columns,
        )

        assert result["File"] == "PRO"

    def test_non_dict_columns_ignored(self) -> None:
        """A truthy non-dict columns value yields no rules."""
        result = get_file_info_dynamic(
            "ST_PRO_Test_V01.mttl",
            "mttl",
            ("File", "Version"),
            "not-a-dict",  # type: ignore[arg-type]
        )
        assert result["File"] == "ST_PRO_Test_V01.mttl"
        assert result["Version"] == ""

    def test_version_without_extension_kept(self) -> None:
        """When no extension is given, the version keeps its suffix."""
        from profiles.config import ColumnConfiguration

        columns = {
            "Version": ColumnConfiguration(
                name="Version", width=150, expression=r"_V(.+)", group=1, priority=10
            ),
        }

        result = get_file_info_dynamic(
            "test_V01-Rel6.2.1.mttl",
            "",
            ("File", "Version"),
            columns,
        )

        assert result["Version"] == "01-Rel6.2.1.mttl"
