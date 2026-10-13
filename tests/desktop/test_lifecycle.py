"""Test desktop port discovery and background server lifecycle."""

from __future__ import annotations

import socket
import time

import httpx
import pytest

from profiles.core.config.models import AppConfig
from profiles.desktop.lifecycle import (
    BackgroundServer,
    ServerStartError,
    find_available_port,
)


def test_find_available_port() -> None:
    port = find_available_port(start_port=8088)
    assert 1024 <= port <= 65535


def test_find_available_port_skips_occupied_listener() -> None:
    """A port already held by another listener must never be returned."""
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    occupied = blocker.getsockname()[1]
    try:
        assert find_available_port(start_port=occupied, max_attempts=1) != occupied
    finally:
        blocker.close()


def test_start_raises_when_port_is_taken() -> None:
    """A bind failure must surface instead of leaving a silently dead server."""
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    taken_port = blocker.getsockname()[1]
    try:
        server = BackgroundServer(config=AppConfig(title="taken"), port=taken_port)
        with pytest.raises(ServerStartError) as excinfo:
            server.start()
        assert str(taken_port) in str(excinfo.value)
        assert not server.is_running
    finally:
        blocker.close()


def test_stop_is_safe_before_start() -> None:
    server = BackgroundServer(config=AppConfig(title="never started"), port=0)
    server.stop()  # must not raise
    assert not server.is_running


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
