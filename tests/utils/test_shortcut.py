"""Tests for profiles.utils.shortcut — desktop path detection + shortcut creation."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.utils import shortcut


class TestGetDesktopPath:
    """get_desktop_path() platform resolution."""

    def test_windows_uses_registry_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """On Windows the API-resolved desktop path wins when it exists."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Windows")
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        monkeypatch.setattr(
            shortcut,
            "_get_windows_desktop",
            lambda: desktop,
        )
        assert shortcut.get_desktop_path() == desktop

    def test_windows_falls_back_to_home_desktop(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Windows falls back to ~/Desktop when the API returns None."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Windows")
        monkeypatch.setattr(shortcut, "_get_windows_desktop", lambda: None)
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut.get_desktop_path() == home / "Desktop"

    def test_macos_existing_desktop(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """macOS uses ~/Desktop when it exists."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Darwin")
        home = tmp_path / "home"
        desktop = home / "Desktop"
        desktop.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut.get_desktop_path() == desktop

    def test_macos_fallback_to_documents(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """macOS falls back to ~/Documents/Desktop when ~/Desktop is absent."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Darwin")
        home = tmp_path / "home"
        fallback = home / "Documents" / "Desktop"
        fallback.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut.get_desktop_path() == fallback

    def test_linux_xdg_desktop_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Linux honours XDG_DESKTOP_DIR when it exists."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Linux")
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.setenv("XDG_DESKTOP_DIR", "Desktop")
        (home / "Desktop").mkdir()
        assert shortcut.get_desktop_path() == home / "Desktop"

    def test_linux_common_locations(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Linux probes common desktop folder names."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Linux")
        monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
        home = tmp_path / "home"
        (home / "Bureau").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut.get_desktop_path() == home / "Bureau"

    def test_linux_falls_back_to_home_desktop(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Linux defaults to ~/Desktop when nothing else matches."""
        monkeypatch.setattr(shortcut.platform, "system", lambda: "Linux")
        monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut.get_desktop_path() == home / "Desktop"


class TestGetWindowsDesktop:
    """_get_windows_desktop() internals."""

    def test_api_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A successful SHGetFolderPathW call returns the resolved path."""
        desktop = tmp_path / "Desktop"
        desktop.mkdir()

        class FakeWintypes:
            MAX_PATH = 260

        class FakeBuf:
            value = str(desktop)

        class FakeShell32:
            def SHGetFolderPathW(self, *args):  # noqa: N802
                return 0

        import types
        import sys

        fake_ctypes = types.SimpleNamespace(
            wintypes=FakeWintypes,
            create_unicode_buffer=lambda size: FakeBuf(),
            windll=types.SimpleNamespace(shell32=FakeShell32()),
        )
        monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
        assert shortcut._get_windows_desktop() == desktop

    def test_api_failure_uses_userprofile(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When the API fails, USERPROFILE/Desktop is used if it exists."""
        home = tmp_path / "home"
        (home / "Desktop").mkdir(parents=True)
        monkeypatch.setenv("USERPROFILE", str(home))

        class FakeWintypes:
            MAX_PATH = 260

        class FakeBuf:
            value = ""

        class FakeShell32:
            def SHGetFolderPathW(self, *args):  # noqa: N802
                return 1  # failure

        import types
        import sys

        fake_ctypes = types.SimpleNamespace(
            wintypes=FakeWintypes,
            create_unicode_buffer=lambda size: FakeBuf(),
            windll=types.SimpleNamespace(shell32=FakeShell32()),
        )
        monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
        assert shortcut._get_windows_desktop() == home / "Desktop"

    def test_all_fail_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """No API path and no USERPROFILE yields None."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("USERPROFILE", str(home))  # but Desktop doesn't exist
        monkeypatch.delenv("USERPROFILE", raising=False)

        class FakeWintypes:
            MAX_PATH = 260

        class FakeShell32:
            def SHGetFolderPathW(self, *args):  # noqa: N802
                return 1

        import types
        import sys

        fake_ctypes = types.SimpleNamespace(
            wintypes=FakeWintypes,
            create_unicode_buffer=lambda size: "",
            windll=types.SimpleNamespace(shell32=FakeShell32()),
        )
        monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
        assert shortcut._get_windows_desktop() is None


class TestGetLinuxDesktop:
    """_get_linux_desktop() internals."""

    def test_xdg_path_with_home_expansion(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """XDG_DESKTOP_DIR is joined onto the home directory."""
        home = tmp_path / "home"
        (home / "Desktop").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        monkeypatch.setenv("XDG_DESKTOP_DIR", "Desktop")
        assert shortcut._get_linux_desktop() == home / "Desktop"

    def test_common_candidates(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Common desktop folder names are probed when XDG is unset."""
        monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
        home = tmp_path / "home"
        (home / "desktop").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut._get_linux_desktop() == home / "desktop"

    def test_none_found_returns_none(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """No desktop candidate yields None."""
        monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        assert shortcut._get_linux_desktop() is None


class TestCreateShortcut:
    """create_shortcut() copy behavior."""

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        """A non-existent source file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            shortcut.create_shortcut(tmp_path / "ghost.pyw")

    def test_missing_desktop_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A non-existent desktop directory raises RuntimeError."""
        source = tmp_path / "ProFiles.pyw"
        source.write_text("", encoding="utf-8")
        with pytest.raises(RuntimeError):
            shortcut.create_shortcut(source, desktop=tmp_path / "missing")

    def test_copies_pyw_to_desktop(self, tmp_path: Path) -> None:
        """The .pyw file is copied to the desktop with the given name."""
        source = tmp_path / "ProFiles.pyw"
        source.write_text("print('hi')", encoding="utf-8")
        desktop = tmp_path / "Desktop"
        desktop.mkdir()

        dest = shortcut.create_shortcut(source, desktop=desktop, shortcut_name="ProFiles")
        assert dest == desktop / "ProFiles.pyw"
        assert dest.exists()
        assert dest.read_text(encoding="utf-8") == "print('hi')"

    def test_auto_detect_desktop(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """With desktop=None the platform auto-detection is used."""
        source = tmp_path / "ProFiles.pyw"
        source.write_text("x", encoding="utf-8")
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        monkeypatch.setattr(shortcut, "get_desktop_path", lambda: desktop)

        dest = shortcut.create_shortcut(source)
        assert dest == desktop / "ProFiles.pyw"
