"""Desktop window launcher using pywebview."""

from __future__ import annotations

import logging
import sys

import webview

from profiles.core.config.models import AppConfig
from profiles.desktop.lifecycle import BackgroundServer

logger = logging.getLogger("profiles.desktop.launcher")

# Selector and type encoding for WKUIDelegate's media-capture policy hook.
# The decisionHandler block is ``void (^)(WKPermissionDecision)`` — WKPermissionDecision
# is an NSInteger enum, hence ``v@?q`` for the block itself. PyObjC derives the
# block's call signature from this quoted sub-encoding; without it, calling the
# handler raises "cannot call block without a signature" and aborts the app.
_MEDIA_CAPTURE_SELECTOR = (
    b"webView:requestMediaCapturePermissionForOrigin:initiatedByFrame:type:decisionHandler:"
)
_MEDIA_CAPTURE_TYPESTR = b'v@:@@@Q@?"v@?q"'


def _configure_webview_permissions() -> None:
    """Grant camera and media capture permissions in embedded desktop webviews."""
    if sys.platform != "darwin":
        return

    try:
        import objc
        import WebKit
        from webview.platforms import cocoa

        def request_media_permission(  # pylint: disable=unused-argument
            self: object,
            webview_inst: object,
            origin: object,
            frame: object,
            capture_type: object,
            decision_handler: object,
        ) -> None:
            decision_handler(WebKit.WKPermissionDecisionGrant)  # type: ignore[attr-defined]

        delegate_cls = cocoa.BrowserView.BrowserDelegate
        objc.classAddMethod(
            delegate_cls,
            _MEDIA_CAPTURE_SELECTOR,
            objc.selector(
                request_media_permission,
                selector=_MEDIA_CAPTURE_SELECTOR,
                signature=_MEDIA_CAPTURE_TYPESTR,
            ),
        )
        logger.debug("WKWebView media-capture auto-grant installed")
    except Exception:
        # Auto-grant is best-effort: without it WKWebView shows its own
        # permission prompt, so failing to install it is not fatal.
        logger.warning("Could not install WKWebView media-capture auto-grant", exc_info=True)


def launch_desktop_window(
    config: AppConfig,
    port: int = 8088,
    host: str = "127.0.0.1",
    debug: bool = False,
) -> None:
    """Start local server and open native PyWebView window.

    The background server is stopped whenever the window closes, including
    when startup fails, so no orphaned process is left listening.
    """
    _configure_webview_permissions()
    server = BackgroundServer(config=config, host=host, port=port)

    window_title = f"ProFiles - {config.title}" if config.title else "ProFiles"
    url = f"http://{host}:{server.port}"

    try:
        server.start()
        webview.create_window(
            title=window_title,
            url=url,
            width=1000,
            height=700,
            min_size=(800, 500),
        )
        webview.start(debug=debug)
    finally:
        server.stop()
