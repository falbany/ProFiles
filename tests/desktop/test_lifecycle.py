"""Test desktop port discovery and background server lifecycle."""

from __future__ import annotations

import time

import httpx

from profiles.core.config.models import AppConfig
from profiles.desktop.lifecycle import BackgroundServer, find_available_port


def test_find_available_port() -> None:
    port = find_available_port(start_port=8088)
    assert 1024 <= port <= 65535


def test_background_server_lifecycle() -> None:
    config = AppConfig(title="Test Server")
    server = BackgroundServer(config=config, port=0)  # Ephemeral port
    try:
        server.start()
        time.sleep(0.5)
        assert server.is_running
        assert server.port > 0

        # Verify reachable
        resp = httpx.get(f"http://127.0.0.1:{server.port}/api/health", timeout=2.0)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    finally:
        server.stop()
        time.sleep(0.5)
        assert not server.is_running
