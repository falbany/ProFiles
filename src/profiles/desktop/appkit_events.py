"""macOS open-document (odoc) capture for double-clicked ``.profiles`` files.

macOS LaunchServices delivers a double-clicked document to a bundled
app exclusively as an ``odoc`` AppleEvent — never as an ``argv`` entry —
so plain launch resolution never sees the clicked file (issue #188).
This module restores the missing signal in two complementary ways:

* :func:`capture_open_documents` — called once at startup, before launch
  resolution, it temporarily installs an NSApplication delegate (and an
  ``NSAppleEventManager`` handler) and pumps the event loop for a
  bounded time so a pending ``odoc`` can arrive. The result is merged
  into the launch context by :func:`profiles.launch.context.with_documents`.
* :func:`install_running_doc_handler` — called by the desktop launcher
  before the GUI event loop starts, it adds ``application:openFiles:``
  to pywebview's AppDelegate so a double-click landing on the *running*
  window applies the config in-process instead of macOS raising the
  "cannot open files in the 'ProFiles launch-handoff document' format"
  dialog (NSApp answers the event through its AppDelegate).

Both entry points are no-ops off macOS and degrade to no-ops when
PyObjC is unavailable, so the module is importable everywhere.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import urllib.parse
from collections.abc import Callable, Sequence
from pathlib import Path

logger = logging.getLogger("profiles.desktop.appkit_events")

#: How long the startup capture may pump the event loop waiting for a
#: pending ``odoc``. Chosen so a GUI-style launch cannot be delayed by
#: more than a beat (same philosophy as the Finder CWD probe).
_DEFAULT_CAPTURE_TIMEOUT_S = 1.5
#: Extra drain window after the first document arrives, so a rapid
#: multi-file double-click (sibling ``odoc`` events milliseconds apart)
#: is captured whole.
_SETTLE_S = 0.25
#: Single run-loop slice while pumping.
_PUMP_SLICE_S = 0.05


def _fourcc(code: str) -> int:
    """Return *code* as the uint32 FourCharCode the AE APIs expect."""
    return int.from_bytes(code.encode("ascii"), "big")


_KEY_DIRECT_OBJECT = _fourcc("----")  # keyDirectObject
_EVENT_CLASS_CORE = _fourcc("aevt")  # kCoreEventClass
_EVENT_ID_OPEN_DOCS = _fourcc("odoc")  # kAEOpenDocuments
_TYPE_FILE_URL = _fourcc("furl")  # typeFileURL
_TYPE_TEXT_CODES = (_fourcc("utxt"), _fourcc("TEXT"))  # typeUnicodeText, typeChar


def capture_open_documents(timeout_s: float = _DEFAULT_CAPTURE_TIMEOUT_S) -> tuple[Path, ...]:
    """Collect documents macOS delivered for this launch (issue #188).

    Runs only on macOS, and only for GUI-style launches (uninformative
    CWD — the signature of a LaunchServices launch): a terminal launch
    keeps its argv/CWD signals and must not pay the pump delay. Every
    failure degrades to an empty tuple, so startup is never blocked or
    broken by this probe.

    Args:
        timeout_s: Maximum seconds to pump the event loop for a pending
            ``odoc`` event. Early exit once a document arrived (plus a
            short settle drain for multi-file double-clicks).

    Returns:
        Resolved, deduplicated document paths (empty when nothing was
        delivered or the platform does not use AppleEvents).
    """
    if sys.platform != "darwin":
        return ()
    from profiles.launch.context import cwd_is_uninformative

    try:
        cwd = Path.cwd()
    except OSError:
        return ()
    if not cwd_is_uninformative(cwd):
        return ()

    received: list[str] = []
    # The delegate is the dispatch point NSApplication itself consults
    # for ``odoc`` (the same route the running-window handler uses, and
    # the one proven to receive events in a full GUI loop). It must be
    # installed BEFORE the launch is declared, so it is the delegate in
    # place when LaunchServices releases the queued event.
    uninstall = _install_odoc_sink(received)
    if uninstall is None:
        return ()
    _finish_app_launch()
    logger.info("odoc capture armed for %.1fs (pid=%d)", timeout_s, os.getpid())
    deadline = time.monotonic() + timeout_s
    try:
        _pump_runloop(deadline, received)
    except Exception:  # noqa: BLE001 — degrade to "no documents", never block startup
        logger.warning("odoc capture pump failed", exc_info=True)
        return ()
    finally:
        uninstall()
    documents = tuple(dict.fromkeys(Path(p).expanduser().resolve() for p in received))
    logger.info(
        "odoc capture done: %d document(s)%s",
        len(documents),
        f": {[str(d) for d in documents]}" if documents else "",
    )
    return documents


def _install_odoc_sink(sink: list[str]) -> Callable[[], None] | None:
    """Arm a delegate + AE-manager collector appending into *sink*.

    Two redundant routes, because NSApplication may consult either when
    an ``odoc`` arrives:

    * an ``NSApplicationDelegate`` implementing ``application:openFiles:``
      — the route a full GUI loop provably uses (issue #188 facet B);
    * an ``NSAppleEventManager`` handler for ``aevt``/``odoc``.

    Returns the uninstaller (also yields the delegate slot back so the
    GUI toolkit can install its own), or None off macOS / without PyObjC
    / when registration fails — a capture probe must never crash the
    launch.
    """
    try:
        from AppKit import NSAppleEventManager, NSApplication
        from Foundation import NSObject

        manager = NSAppleEventManager.sharedAppleEventManager()

        class _OdocCollector(NSObject):
            def application_openFiles_(  # noqa: N802 — Cocoa delegate selector
                self, _application: object, filenames: Sequence[object]
            ) -> None:
                try:
                    sink.extend(str(name) for name in filenames)
                except Exception:  # noqa: BLE001
                    logger.warning("Failed to collect odoc documents", exc_info=True)

            def handleOpenDocuments_withReplyEvent_(self, event: object, _reply: object) -> None:  # noqa: N802 — Cocoa AE-manager selector
                try:
                    sink.extend(documents_from_odoc_event(event))
                except Exception:  # noqa: BLE001 — a malformed event must not crash startup
                    logger.warning("Failed to extract odoc documents", exc_info=True)

        collector = _OdocCollector.alloc().init()
        NSApplication.sharedApplication().setDelegate_(collector)
        manager.setEventHandler_andSelector_forEventClass_andEventID_(
            collector,
            "handleOpenDocuments:withReplyEvent:",
            _EVENT_CLASS_CORE,
            _EVENT_ID_OPEN_DOCS,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Could not register the odoc capture handler", exc_info=True)
        return None

    def uninstall() -> None:
        # Yield the delegate slot back (the GUI toolkit installs its own)
        # and drop the AE-manager handler. Both best effort: the capture
        # is transient and a failed teardown must not break startup.
        try:
            from AppKit import NSApplication

            app = NSApplication.sharedApplication()
            if app.delegate() is collector:
                app.setDelegate_(None)
        except Exception:  # noqa: BLE001
            logger.debug("odoc delegate teardown failed", exc_info=True)
        try:
            manager.removeEventHandlerForEventClass_andEventID_(
                _EVENT_CLASS_CORE,
                _EVENT_ID_OPEN_DOCS,
            )
        except Exception:  # noqa: BLE001
            logger.debug("odoc handler removal failed", exc_info=True)

    return uninstall


def _finish_app_launch() -> None:
    """Declare the (yet to run) GUI application as launched.

    Releases LaunchServices' queued ``odoc`` for dispatch. Best effort:
    without PyObjC there is nothing to declare and the capture degrades
    to an empty result through the uninstaller check that follows.
    """
    try:
        from AppKit import NSApplication

        app = NSApplication.sharedApplication()
        if not app.isRunning():
            app.finishLaunching()
    except Exception:  # noqa: BLE001
        logger.debug("NSApplication launch declaration unavailable", exc_info=True)


def install_running_doc_handler(on_documents: Callable[[Sequence[str]], None]) -> bool:
    """Route double-click documents arriving while the GUI runs.

    Adds ``application:openFiles:`` to pywebview's AppDelegate class —
    the object ``NSApplication`` hands ``odoc`` to once the GUI event
    loop runs. Must be called before ``webview.start()``. Off macOS, or
    when pywebview's Cocoa backend is unavailable, this is a no-op.

    Args:
        on_documents: Callback invoked with the delivered document paths.

    Returns:
        True when the handler was installed.
    """
    if sys.platform != "darwin":
        return False
    try:
        import objc
        from webview.platforms import cocoa

        def open_files_callback(_self: object, _app: object, filenames: Sequence[object]) -> None:
            try:
                on_documents([str(name) for name in filenames])
            except Exception:  # noqa: BLE001 — a GUI callback must never crash the app
                logger.exception("Applying double-clicked documents failed")

        # Best-effort, like the media-capture permission hook: a failing
        # install only means macOS keeps showing its "cannot open" dialog.
        objc.classAddMethod(
            cocoa.BrowserView.AppDelegate,
            b"application:openFiles:",
            objc.selector(
                open_files_callback,
                selector=b"application:openFiles:",
                signature=b"v@:@@",  # void (self, SEL, NSApplication*, NSArray*)
            ),
        )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Could not install the running-doc handler", exc_info=True)
        return False


def documents_from_odoc_event(event: object) -> list[str]:
    """Extract file paths from an ``odoc`` AppleEvent.

    The direct object is an AE list whose items are file URLs on modern
    macOS (``typeFileURL``), with plain-text or legacy descriptors as
    older variants. Legacy items are coerced to file URLs once; anything
    unparseable is skipped rather than raising — a malformed event must
    never break the launch or the running GUI.

    Args:
        event: An ``NSAppleEventDescriptor`` for the ``odoc`` event.

    Returns:
        POSIX path strings, in the order macOS supplied them.
    """
    direct = event.paramDescriptorForKeyword_(_KEY_DIRECT_OBJECT)  # type: ignore[attr-defined]
    if direct is None:
        return []
    paths: list[str] = []
    for index in range(1, direct.numberOfItems() + 1):
        item = direct.descriptorAtIndex_(index)
        path = _path_from_descriptor(item)
        if path:
            paths.append(path)
    return paths


def _path_from_descriptor(item: object) -> str | None:
    """Return the POSIX path carried by one AE list item, or None."""
    try:
        descriptor_type = item.descriptorType()  # type: ignore[attr-defined]
        if descriptor_type == _TYPE_FILE_URL:
            return _path_from_url_bytes(bytes(item.data()))  # type: ignore[attr-defined]
        if descriptor_type in _TYPE_TEXT_CODES:
            return item.stringValue() or None  # type: ignore[attr-defined]
        coerced = item.coerceToDescriptorType_(_TYPE_FILE_URL)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — hostile descriptors must degrade, not raise
        return None
    if coerced is None:
        return None
    try:
        return _path_from_url_bytes(bytes(coerced.data()))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return None


def _path_from_url_bytes(raw: bytes) -> str | None:
    """Decode a ``typeFileURL`` payload (percent-encoded file:// URL)."""
    if not raw:
        return None
    url = raw.decode("utf-8", errors="replace")
    prefix = "file://"
    if url.startswith(prefix):
        url = url[len(prefix) :]
    return urllib.parse.unquote(url) or None


def _pump_runloop(deadline: float, received: Sequence[str]) -> None:
    """Drain the application event queue in short slices until *deadline*.

    LaunchServices delivers ``odoc`` through NSApplication's event
    queue: raw run-loop servicing alone does not drain it — the events
    are only dispatched when ``nextEventMatchingMask`` pulls them off
    the queue and ``sendEvent:`` routes them (which is how a full GUI
    loop would). Slicing keeps the bounded timeout responsive (early
    exit once a document arrived, plus a short settle drain for
    multi-file double-clicks).
    """
    try:
        from AppKit import (
            NSAnyEventMask,
            NSApplication,
            NSDate,
            NSDefaultRunLoopMode,
        )
    except ImportError:
        return
    app = NSApplication.sharedApplication()
    end_time = NSDate.dateWithTimeIntervalSinceNow_(_PUMP_SLICE_S)
    while time.monotonic() < deadline and not received:
        event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            NSAnyEventMask,
            end_time,
            NSDefaultRunLoopMode,
            True,
        )
        if event is not None:
            app.sendEvent_(event)
        end_time = NSDate.dateWithTimeIntervalSinceNow_(_PUMP_SLICE_S)
    if received:
        settle_deadline = time.monotonic() + _SETTLE_S
        while time.monotonic() < settle_deadline:
            event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                NSAnyEventMask,
                NSDate.dateWithTimeIntervalSinceNow_(_PUMP_SLICE_S),
                NSDefaultRunLoopMode,
                True,
            )
            if event is not None:
                app.sendEvent_(event)


__all__ = [
    "capture_open_documents",
    "documents_from_odoc_event",
    "install_running_doc_handler",
]
