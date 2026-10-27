"""Diagnose camera (getUserMedia) availability inside the pywebview shell.

Serves a one-page site on 127.0.0.1 that (1) requests the camera with the same
constraints as the ProFiles scanner modal, (2) reports every stage back to the
server, then opens a pywebview window with the production launcher's WKWebView
permission hook installed. Reports are printed when the window closes.

Why this exists: WKWebView only exposes ``navigator.mediaDevices`` when the
host process's bundle declares ``NSCameraUsageDescription`` — a bare
``python`` process never has one, so camera scanning silently can't work in
source runs. Run the probe from a packaged app (or a stub .app whose Mach-O
embeds Python) to verify the packaged configuration.

Usage: python scripts/dev/probe_webview_camera.py [seconds]
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "src")

# Apply the exact same hook as the production launcher BEFORE importing webview
from profiles.desktop.launcher import _configure_webview_permissions  # noqa: E402

_configure_webview_permissions()

import webview  # noqa: E402

REPORTS: list[dict] = []

PAGE = """<!doctype html>
<html><body><video playsInline muted style="width:320px"></video><pre id="out">probing…</pre>
<script>
const out = document.getElementById('out');
const report = (r) => fetch('/report', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(r)});
(async () => {
  const log = (m) => { out.textContent += m + "\\n"; };
  try {
    log('isSecureContext: ' + window.isSecureContext);
    log('has mediaDevices: ' + !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
    log('has BarcodeDetector: ' + ('BarcodeDetector' in window));
    await report({stage: 'env', secure: window.isSecureContext,
                  hasMediaDevices: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
                  hasBarcodeDetector: 'BarcodeDetector' in window});
    if (!navigator.mediaDevices?.getUserMedia) return;
    const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment', width: {ideal: 1280}}});
    const video = document.querySelector('video');
    video.srcObject = stream;
    await video.play();
    const tracks = stream.getVideoTracks().map(t => t.label);
    log('camera tracks: ' + JSON.stringify(tracks));
    await report({stage: 'getUserMedia', ok: true, tracks});
    // Let the camera visibly run for a moment, then stop.
    await new Promise(r => setTimeout(r, 3000));
    stream.getTracks().forEach(t => t.stop());
    await report({stage: 'done'});
    log('DONE');
  } catch (e) {
    log('ERROR: ' + e.name + ': ' + e.message);
    await report({stage: 'error', name: e.name, message: e.message});
  }
})();
</script></body></html>"""


class ProbeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        REPORTS.append(json.loads(self.rfile.read(length) or b"{}"))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


def main() -> int:
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    server = HTTPServer(("127.0.0.1", 8999), ProbeHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def watchdog() -> None:
        import time

        time.sleep(seconds)
        for w in list(webview.windows):
            w.destroy()

    threading.Thread(target=watchdog, daemon=True).start()

    try:
        webview.create_window(
            title="camera probe",
            url="http://127.0.0.1:8999/",
            width=520,
            height=480,
        )
        webview.start()
    finally:
        server.shutdown()
        print("\n===== PROBE REPORTS =====")
        print(json.dumps(REPORTS, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
