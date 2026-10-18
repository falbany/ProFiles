"""Desktop window launcher using pywebview."""

from __future__ import annotations

import sys

import webview

from profiles.core.config.models import AppConfig
from profiles.desktop.lifecycle import BackgroundServer


def _configure_webview_permissions() -> None:
    """Grant camera and media capture permissions in embedded desktop webviews."""
    # macOS WKWebView permission delegation via PyObjC
    if sys.platform == "darwin":
        try:
            import WebKit
            import webview.platforms.cocoa as cocoa

            def request_media_permission(
                self: object,
                webview_inst: object,
                origin: object,
                frame: object,
                capture_type: object,
                decision_handler: object,
            ) -> None:
                decision_handler(WebKit.WKPermissionDecisionGrant)  # type: ignore[attr-defined]

            cocoa.BrowserView.BrowserDelegate.webView_requestMediaCapturePermissionForOrigin_initiatedByFrame_type_decisionHandler_ = request_media_permission
        except Exception:
            pass


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
