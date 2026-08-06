"""Tests for profiles.utils.file_utils — scan_directory, _matches_extension, launch_file, open_file_explorer, open_with_default_app, list_directory_paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.utils.file_utils import (
    _matches_extension,
    hash_file,
    launch_file,
    list_directory_paths,
    open_file_explorer,
    open_with_default_app,
    scan_directory,
)


class TestScanDirectory:
    """scan_directory — directory scanning with optional recursion."""

    def test_non_recursive_finds_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.mttl").write_text("", encoding="utf-8")
        (tmp_path / "b.txt").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl")
        assert len(files) == 1
        assert files[0].name == "a.mttl"

    def test_non_recursive_all_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "a.mttl").write_text("", encoding="utf-8")
        (tmp_path / "b.txt").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="")
        assert len(files) == 2

    def test_non_recursive_all_keyword(self, tmp_path: Path) -> None:
        (tmp_path / "a.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="All")
        assert len(files) == 1

    def test_empty_directory(self, tmp_path: Path) -> None:
        files = scan_directory(tmp_path, extension="mttl")
        assert files == []

    def test_nonexistent_directory(self) -> None:
        files = scan_directory(Path("C:/nonexistent_dir_xyz"), extension="mttl")
        assert files == []

    def test_recursive_finds_nested_files(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "root.mttl").write_text("", encoding="utf-8")
        (sub / "nested.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", recursive=True)
        assert len(files) == 2
        names = {f.name for f in files}
        assert names == {"root.mttl", "nested.mttl"}

    def test_recursive_exclude_dirs(self, tmp_path: Path) -> None:
        excluded = tmp_path / ".git"
        excluded.mkdir()
        (excluded / "should_not_appear.mttl").write_text("", encoding="utf-8")
        (tmp_path / "visible.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", recursive=True, exclude_dirs=(".git",))
        names = {f.name for f in files}
        assert "visible.mttl" in names
        assert "should_not_appear.mttl" not in names

    def test_recursive_exclude_dirs_wildcard_prefix(self, tmp_path: Path) -> None:
        """Glob prefix `*tmp` skips `tmp`, `obsoletetmp`, etc., case-insensitively."""
        for name in ("tmp", "obsoletetmp", "Debug", "keepme"):
            (tmp_path / name).mkdir()
            (tmp_path / name / f"{name}.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", recursive=True, exclude_dirs=("*tmp",))
        names = {f.name for f in files}
        assert "tmp.mttl" not in names
        assert "obsoletetmp.mttl" not in names
        assert "Debug.mttl" in names
        assert "keepme.mttl" in names

    def test_recursive_exclude_dirs_wildcard_case_insensitive(self, tmp_path: Path) -> None:
        """Pattern `debug*` matches `Debug`, `debug1`, `DEBuGged`, etc."""
        for name in ("Debug", "debug1", "DEBuGged", "source"):
            (tmp_path / name).mkdir()
            (tmp_path / name / f"{name}.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", recursive=True, exclude_dirs=("debug*",))
        names = {f.name for f in files}
        assert "Debug.mttl" not in names
        assert "debug1.mttl" not in names
        assert "DEBuGged.mttl" not in names
        assert "source.mttl" in names

    def test_recursive_exclude_dirs_mixed_glob_and_literal(self, tmp_path: Path) -> None:
        """Globs and plain names can coexist in the same tuple."""
        for name in (".git", "node_modules", "DebugV1", "src"):
            (tmp_path / name).mkdir()
            (tmp_path / name / f"{name}.mttl").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path,
            extension="mttl",
            recursive=True,
            exclude_dirs=(".git", "node_*", "Debug*"),
        )
        names = {f.name for f in files}
        assert names == {"src.mttl"}

    def test_recursive_empty_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "empty"
        sub.mkdir()
        files = scan_directory(tmp_path, extension="mttl", recursive=True)
        assert files == []

    def test_recursive_multiple_subdirs(self, tmp_path: Path) -> None:
        for name in ("a", "b", "c"):
            d = tmp_path / name
            d.mkdir()
            (d / f"{name}.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", recursive=True)
        assert len(files) == 3

    def test_recursive_extension_filter(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "correct.mttl").write_text("", encoding="utf-8")
        (sub / "wrong.txt").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", recursive=True)
        assert len(files) == 1
        assert files[0].name == "correct.mttl"

    def test_sorts_results(self, tmp_path: Path) -> None:
        (tmp_path / "z.mttl").write_text("", encoding="utf-8")
        (tmp_path / "a.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl")
        assert files[0].name == "a.mttl"
        assert files[1].name == "z.mttl"

    def test_non_recursive_glob(self, tmp_path: Path) -> None:
        """With a non-empty extension and non-recursive, uses glob for speed."""
        (tmp_path / "alpha.mttl").write_text("", encoding="utf-8")
        (tmp_path / "beta.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl")
        assert len(files) == 2

    # ── exclude_files ────────────────────────────────────────────────

    def test_non_recursive_exclude_files(self, tmp_path: Path) -> None:
        """exclude_files filters out matching files in non-recursive scans."""
        (tmp_path / "keep.mttl").write_text("", encoding="utf-8")
        (tmp_path / "backup.mttl").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path, extension="mttl", exclude_files=("*backup*",)
        )
        names = {f.name for f in files}
        assert names == {"keep.mttl"}

    def test_non_recursive_exclude_files_all_keyword(self, tmp_path: Path) -> None:
        """exclude_files works with extension='All'."""
        (tmp_path / "keep.mttl").write_text("", encoding="utf-8")
        (tmp_path / "skip.tmp").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path, extension="All", exclude_files=("*.tmp",)
        )
        names = {f.name for f in files}
        assert names == {"keep.mttl"}

    def test_non_recursive_exclude_files_wildcard_case_insensitive(
        self, tmp_path: Path
    ) -> None:
        """Pattern *BACKUP* matches backup, Backup, etc."""
        (tmp_path / "keep.mttl").write_text("", encoding="utf-8")
        (tmp_path / "Backup.mttl").write_text("", encoding="utf-8")
        (tmp_path / "data_BACKUP.mttl").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path, extension="mttl", exclude_files=("*BACKUP*",)
        )
        names = {f.name for f in files}
        assert names == {"keep.mttl"}

    def test_recursive_exclude_files(self, tmp_path: Path) -> None:
        """exclude_files filters matching files in recursive scans."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "root.mttl").write_text("", encoding="utf-8")
        (sub / "nested.mttl").write_text("", encoding="utf-8")
        (sub / "backup.mttl").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path,
            extension="mttl",
            recursive=True,
            exclude_files=("*backup*",),
        )
        names = {f.name for f in files}
        assert names == {"root.mttl", "nested.mttl"}

    def test_exclude_files_combined_with_exclude_dirs(self, tmp_path: Path) -> None:
        """Both exclude_dirs and exclude_files apply simultaneously."""
        excluded_dir = tmp_path / "skipdir"
        excluded_dir.mkdir()
        (excluded_dir / "in_dir.mttl").write_text("", encoding="utf-8")
        (tmp_path / "keep.mttl").write_text("", encoding="utf-8")
        (tmp_path / "backup.mttl").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path,
            extension="mttl",
            recursive=True,
            exclude_dirs=("skipdir",),
            exclude_files=("*backup*",),
        )
        names = {f.name for f in files}
        assert names == {"keep.mttl"}

    def test_exclude_files_mixed_glob_and_literal(self, tmp_path: Path) -> None:
        """Globs and plain names can coexist in exclude_files."""
        (tmp_path / "keep.mttl").write_text("", encoding="utf-8")
        (tmp_path / "backup.mttl").write_text("", encoding="utf-8")
        (tmp_path / "draft_v2.mttl").write_text("", encoding="utf-8")
        (tmp_path / "exact.mttl").write_text("", encoding="utf-8")
        files = scan_directory(
            tmp_path,
            extension="mttl",
            exclude_files=("*backup*", "exact.mttl", "*draft*"),
        )
        names = {f.name for f in files}
        assert names == {"keep.mttl"}

    def test_exclude_files_empty_tuple_matches_all(self, tmp_path: Path) -> None:
        """An empty exclude_files tuple does not filter anything."""
        (tmp_path / "a.mttl").write_text("", encoding="utf-8")
        (tmp_path / "b.mttl").write_text("", encoding="utf-8")
        files = scan_directory(tmp_path, extension="mttl", exclude_files=())
        assert len(files) == 2


class TestMatchesExtension:
    """_matches_extension — internal extension filter logic."""

    def test_exact_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "mttl") is True

    def test_no_match(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "mttl") is False

    def test_empty_extension_matches_all(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "") is True

    def test_all_extension_matches_all(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "all") is True

    def test_case_insensitive_suffix(self, tmp_path: Path) -> None:
        """Suffix comparison is case-insensitive."""
        f = tmp_path / "test.MTTL"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "mttl") is True

    # ── Compound / double extensions ───────────────────────────────────

    def test_compound_extension_match(self, tmp_path: Path) -> None:
        """Compound ext like .mttx.lnk should match with 'mttx.lnk'."""
        f = tmp_path / "program.mttx.lnk"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "mttx.lnk") is True

    def test_compound_extension_no_match_partial(self, tmp_path: Path) -> None:
        """Compound ext .mttx.lnk should NOT match partial ext 'lnk'."""
        f = tmp_path / "program.mttx.lnk"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "lnk") is False

    def test_compound_extension_single_part_no_match(self, tmp_path: Path) -> None:
        """Single ext 'mttx' should NOT match compound ext .mttx.lnk."""
        f = tmp_path / "program.mttx.lnk"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "mttx") is False

    def test_simple_extension_still_works(self, tmp_path: Path) -> None:
        """Simple single-dot extensions still match correctly."""
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        assert _matches_extension(f, "mttl") is True
        assert _matches_extension(f, "lnk") is False


class TestOpenFileExplorer:
    """open_file_explorer — opens directory in system explorer."""

    @pytest.fixture(autouse=True)
    def _force_windows(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", True)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", False)

    def test_existing_directory(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mock_startfile = mocker.patch("os.startfile")
        result = open_file_explorer(tmp_path)
        assert result is True
        mock_startfile.assert_called_once_with(str(tmp_path))

    def test_nonexistent_directory(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("os.startfile")
        result = open_file_explorer(tmp_path / "nope")
        assert result is False

    def test_oserror_returns_false(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("os.startfile", side_effect=OSError("access denied"))
        result = open_file_explorer(tmp_path)
        assert result is False

    def test_pathlib_path(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mock_startfile = mocker.patch("os.startfile")
        result = open_file_explorer(Path(tmp_path))
        assert result is True
        mock_startfile.assert_called_once()

    def test_macos_uses_open(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        """On macOS, falls back to `open` instead of os.startfile."""
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", True)
        result = open_file_explorer(tmp_path)
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "open"
        assert str(tmp_path) in args

    def test_linux_uses_xdg_open(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        """On Linux, falls back to `xdg-open`."""
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", False)
        result = open_file_explorer(tmp_path)
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "xdg-open"


class TestLaunchFile:
    """launch_file — launches file with OS default association."""

    @pytest.fixture(autouse=True)
    def _force_windows(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", True)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", False)

    def test_existing_file(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mock_startfile = mocker.patch("os.startfile")
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        result = launch_file(f)
        assert result is True
        mock_startfile.assert_called_once_with(str(f))

    def test_nonexistent_file(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("os.startfile")
        result = launch_file(Path("C:/nonexistent_file_xyz.mttl"))
        assert result is False

    def test_oserror_returns_false(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("os.startfile", side_effect=OSError("failed"))
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        result = launch_file(f)
        assert result is False

    def test_is_file_check(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mock_startfile = mocker.patch("os.startfile")
        # Directory is not a file
        result = launch_file(tmp_path)
        assert result is False
        mock_startfile.assert_not_called()

    def test_macos_uses_open(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        """On macOS, falls back to `open` instead of os.startfile."""
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", True)
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        result = launch_file(f)
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "open"
        assert str(f) in args

    def test_linux_uses_xdg_open(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        """On Linux, falls back to `xdg-open`."""
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", False)
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        result = launch_file(f)
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "xdg-open"

    def test_subprocess_failure_returns_false(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        """Subprocess raising any exception must be swallowed into False."""
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mocker.patch("subprocess.run", side_effect=Exception("boom"))
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", True)
        f = tmp_path / "test.mttl"
        f.write_text("", encoding="utf-8")
        result = launch_file(f)
        assert result is False


class TestOpenWithDefaultApp:
    """open_with_default_app — opens any file with OS default handler."""

    @pytest.fixture(autouse=True)
    def _force_windows(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", True)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", False)

    def test_existing_file(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mock_startfile = mocker.patch("os.startfile")
        f = tmp_path / "config.ini"
        f.write_text("", encoding="utf-8")
        result = open_with_default_app(f)
        assert result is True
        mock_startfile.assert_called_once_with(str(f))

    def test_nonexistent_file(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("os.startfile")
        result = open_with_default_app(Path("C:/nope.ini"))
        assert result is False

    def test_macos_uses_open(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", True)
        f = tmp_path / "log.txt"
        f.write_text("", encoding="utf-8")
        result = open_with_default_app(f)
        assert result is True
        args = mock_run.call_args[0][0]
        assert args[0] == "open"
        assert str(f) in args

    def test_linux_uses_xdg_open(self, tmp_path: Path, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch(
            "os.startfile",
            create=True,
            side_effect=AssertionError("should not be called"),
        )
        mock_run = mocker.patch("subprocess.run")
        mocker.patch("profiles.utils.file_utils._IS_WINDOWS", False)
        mocker.patch("profiles.utils.file_utils._IS_MACOS", False)
        f = tmp_path / "log.txt"
        f.write_text("", encoding="utf-8")
        result = open_with_default_app(f)
        assert result is True
        args = mock_run.call_args[0][0]
        assert args[0] == "xdg-open"


class TestListDirectoryPaths:
    """list_directory_paths — filters non-directories from path list."""

    def test_all_existing(self, tmp_path: Path) -> None:
        d1 = tmp_path / "d1"
        d2 = tmp_path / "d2"
        d1.mkdir()
        d2.mkdir()
        result = list_directory_paths([d1, d2])
        assert result == [d1, d2]

    def test_mixed_valid_invalid(self, tmp_path: Path) -> None:
        d1 = tmp_path / "exists"
        d1.mkdir()
        result = list_directory_paths([d1, tmp_path / "nope"])
        assert result == [d1]

    def test_empty_list(self) -> None:
        assert list_directory_paths([]) == []

    def test_nonexistent_all(self, tmp_path: Path) -> None:
        result = list_directory_paths([tmp_path / "a", tmp_path / "b"])
        assert result == []

    def test_string_paths(self, tmp_path: Path) -> None:
        d = tmp_path / "dir"
        d.mkdir()
        result = list_directory_paths([str(d)])
        assert len(result) == 1
        assert isinstance(result[0], Path)


# ── hash_file utility ──────────────────────────────────────────────────────


class TestHashFile:
    """profiles.utils.file_utils.hash_file — streaming file hashing."""

    def test_md5_matches_hashlib(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        import hashlib

        assert hash_file(f, "md5") == hashlib.md5(b"hello world").hexdigest()

    def test_sha256_matches_hashlib(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"hello world")
        import hashlib

        assert hash_file(f, "sha256") == hashlib.sha256(b"hello world").hexdigest()

    def test_default_algorithm_is_sha256(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"x")
        import hashlib

        assert hash_file(f) == hashlib.sha256(b"x").hexdigest()

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        import hashlib

        assert hash_file(f, "md5") == hashlib.md5(b"").hexdigest()

    def test_large_file_streamed(self, tmp_path: Path) -> None:
        # 1 MiB to force multiple 64 KiB read chunks.
        f = tmp_path / "big.bin"
        f.write_bytes(b"a" * (1024 * 1024))
        import hashlib

        expected = hashlib.sha256(b"a" * (1024 * 1024)).hexdigest()
        assert hash_file(f, "sha256") == expected

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_file(tmp_path / "nope.bin", "md5")

    def test_invalid_algorithm_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "data.bin"
        f.write_bytes(b"x")
        with pytest.raises(ValueError):
            hash_file(f, "not-a-real-algo")
