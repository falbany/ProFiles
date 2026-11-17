"""Tests for :mod:`profiles.desktop.appkit_events` — macOS odoc capture.

Issue #188: macOS delivers double-clicked documents as ``odoc``
AppleEvents (never argv), so nothing saw the clicked file. The unit
tests here fake the AppKit plumbing so they run on every platform; the
macOS-only class drives the real ``NSAppleEventDescriptor`` extraction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from profiles.desktop import appkit_events


@pytest.fixture
def uninformative_cwd(monkeypatch) -> None:
    """Make the capture gate treat every CWD as GUI-style (no real probe)."""
    monkeypatch.setattr(
        "profiles.launch.context.cwd_is_uninformative",
        lambda _cwd: True,
    )


class TestCaptureOpenDocuments:
    """capture_open_documents gates, plumbing, and degradation."""

    def test_off_macos_is_noop(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        install = MagicMock()
        monkeypatch.setattr(appkit_events, "_install_odoc_sink", install)

        assert appkit_events.capture_open_documents(timeout_s=0.05) == ()
        install.assert_not_called()

    def test_informative_cwd_skips_capture(self, monkeypatch, tmp_path) -> None:
        """A terminal launch keeps its argv/CWD signals and pays no pump."""
        monkeypatch.chdir(tmp_path)
        install = MagicMock()
        monkeypatch.setattr(appkit_events, "_install_odoc_sink", install)

        assert appkit_events.capture_open_documents(timeout_s=0.05) == ()
        install.assert_not_called()

    def test_unreadable_cwd_degrades_to_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "profiles.launch.context.cwd_is_uninformative",
            lambda _cwd: True,
        )
        monkeypatch.setattr(Path, "cwd", MagicMock(side_effect=OSError("gone")))
        install = MagicMock()
        monkeypatch.setattr(appkit_events, "_install_odoc_sink", install)

        assert appkit_events.capture_open_documents(timeout_s=0.05) == ()
        install.assert_not_called()

    def test_returns_captured_documents_and_uninstalls(
        self, monkeypatch, uninformative_cwd, tmp_path
    ) -> None:
        # The orchestration under test is platform-agnostic; the darwin
        # gate is mocked like every other AppKit touchpoint so this runs
        # on every CI platform.
        monkeypatch.setattr(sys, "platform", "darwin")
        delivered: list[str] = []
        uninstalled = []

        def fake_install(sink: list[str]) -> None:
            delivered.append(sink)
            return lambda: uninstalled.append(True)

        def fake_pump(_deadline: float, received: list[str]) -> None:
            received.append(str(tmp_path / "b.profiles"))
            received.append(str(tmp_path / "b.profiles"))  # duplicate burst

        finish = MagicMock()
        monkeypatch.setattr(appkit_events, "_finish_app_launch", finish)
        monkeypatch.setattr(appkit_events, "_install_odoc_sink", fake_install)
        monkeypatch.setattr(appkit_events, "_pump_runloop", fake_pump)

        result = appkit_events.capture_open_documents(timeout_s=1.0)

        assert result == ((tmp_path / "b.profiles").resolve(),)
        assert uninstalled == [True]
        assert len(delivered) == 1
        # The delegate must be in place BEFORE the launch is declared.
        finish.assert_called_once()

    def test_install_failure_degrades_to_empty(self, monkeypatch, uninformative_cwd) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(appkit_events, "_install_odoc_sink", lambda _sink: None)
        pump = MagicMock()
        finish = MagicMock()
        monkeypatch.setattr(appkit_events, "_finish_app_launch", finish)
        monkeypatch.setattr(appkit_events, "_pump_runloop", pump)

        assert appkit_events.capture_open_documents(timeout_s=1.0) == ()
        pump.assert_not_called()
        finish.assert_not_called()  # nothing was armed, so nothing to launch

    def test_uninstall_survives_pump_crash(self, monkeypatch, uninformative_cwd) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        uninstalled = []
        monkeypatch.setattr(
            appkit_events,
            "_install_odoc_sink",
            lambda _sink: lambda: uninstalled.append(True),
        )
        monkeypatch.setattr(appkit_events, "_finish_app_launch", MagicMock())
        monkeypatch.setattr(
            appkit_events, "_pump_runloop", MagicMock(side_effect=RuntimeError("boom"))
        )

        assert appkit_events.capture_open_documents(timeout_s=1.0) == ()
        assert uninstalled == [True]


@pytest.mark.skipif(sys.platform != "darwin", reason="real AppleEvent descriptors")
class TestDocumentsFromOdocEvent:
    """Extraction against real NSAppleEventDescriptor payloads."""

    @staticmethod
    def _odoc_event(items: list[object]) -> object:
        from Foundation import NSAppleEventDescriptor

        event = NSAppleEventDescriptor.appleEventWithEventClass_eventID_targetDescriptor_returnID_transactionID_(
            appkit_events._EVENT_CLASS_CORE,
            appkit_events._EVENT_ID_OPEN_DOCS,
            NSAppleEventDescriptor.nullDescriptor(),
            -1,
            0,
        )
        lst = NSAppleEventDescriptor.listDescriptor()
        for index, item in enumerate(items, start=1):
            lst.insertDescriptor_atIndex_(item, index)
        event.setParamDescriptor_forKeyword_(lst, appkit_events._KEY_DIRECT_OBJECT)
        return event

    def test_extracts_multiple_file_urls_with_percent_escapes(self, tmp_path: Path) -> None:
        from Foundation import NSURL, NSAppleEventDescriptor

        event = self._odoc_event(
            [
                NSAppleEventDescriptor.descriptorWithFileURL_(
                    NSURL.fileURLWithPath_(str(tmp_path / "b.profiles"))
                ),
                NSAppleEventDescriptor.descriptorWithFileURL_(
                    NSURL.fileURLWithPath_(str(tmp_path / "my dir" / "a.profiles"))
                ),
            ]
        )
        assert appkit_events.documents_from_odoc_event(event) == [
            str(tmp_path / "b.profiles"),
            str(tmp_path / "my dir" / "a.profiles"),
        ]

    def test_extracts_unicode_text_items(self) -> None:
        from Foundation import NSAppleEventDescriptor

        event = self._odoc_event(
            [NSAppleEventDescriptor.descriptorWithString_("/tmp/legacy.profiles")]
        )
        assert appkit_events.documents_from_odoc_event(event) == ["/tmp/legacy.profiles"]

    def test_empty_list_yields_no_paths(self) -> None:

        event = self._odoc_event([])
        assert appkit_events.documents_from_odoc_event(event) == []

    def test_missing_direct_object_yields_no_paths(self) -> None:
        from Foundation import NSAppleEventDescriptor

        event = NSAppleEventDescriptor.appleEventWithEventClass_eventID_targetDescriptor_returnID_transactionID_(
            appkit_events._EVENT_CLASS_CORE,
            appkit_events._EVENT_ID_OPEN_DOCS,
            NSAppleEventDescriptor.nullDescriptor(),
            -1,
            0,
        )
        assert appkit_events.documents_from_odoc_event(event) == []


class TestInstallRunningDocHandler:
    """Running-window handler: selector installation and callback plumbing."""

    def test_off_macos_is_noop(self, monkeypatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        assert appkit_events.install_running_doc_handler(lambda _paths: None) is False

    @pytest.mark.skipif(sys.platform != "darwin", reason="needs pyobjc")
    def test_adds_open_files_selector_to_webview_delegate(self, monkeypatch, tmp_path) -> None:
        """The handler lands on pywebview's AppDelegate and forwards paths."""
        from Foundation import NSObject
        from webview.platforms import cocoa

        received: list[list[str]] = []

        # Unique ObjC class names: pyobjc registers classes globally, so a
        # repeated name across tests would collide.
        class SelectorDelegate(NSObject):
            pass

        monkeypatch.setattr(cocoa.BrowserView, "AppDelegate", SelectorDelegate)
        installed = appkit_events.install_running_doc_handler(
            lambda paths: received.append(list(paths))
        )

        assert installed is True
        dummy = SelectorDelegate.alloc().init()
        # PyObjC derives the Python name from the selector; self is implicit.
        dummy.application_openFiles_(None, [str(tmp_path / "a.profiles")])
        assert received == [[str(tmp_path / "a.profiles")]]

    @pytest.mark.skipif(sys.platform != "darwin", reason="needs pyobjc")
    def test_callback_exception_does_not_escape(self, monkeypatch) -> None:
        from Foundation import NSObject
        from webview.platforms import cocoa

        class SwallowDelegate(NSObject):
            pass

        monkeypatch.setattr(cocoa.BrowserView, "AppDelegate", SwallowDelegate)

        def _boom(_paths: list[str]) -> None:
            raise RuntimeError("boom")

        appkit_events.install_running_doc_handler(_boom)
        dummy = SwallowDelegate.alloc().init()
        # Must not raise into the Cocoa event loop.
        dummy.application_openFiles_(None, ["/tmp/x.profiles"])
