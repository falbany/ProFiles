"""Test desktop port discovery and background server lifecycle."""

from __future__ import annotations

import socket
import time
from pathlib import Path

import httpx
import pytest

from profiles.core.config.models import AppConfig, MachineConfiguration
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


def test_background_server_does_not_use_cwd_when_configured_scan_is_unavailable(
    tmp_path: Path,
) -> None:
    scan_dir = tmp_path / "unmounted"
    config = AppConfig(
        configurations=[
            MachineConfiguration(
                name="network",
                scan=(str(scan_dir),),
                extensions=("exe",),
                filters=("installer",),
            )
        ]
    )

    server = BackgroundServer(config=config, port=0)

    assert server.state.active_directory is None
    try:
        server.start()
        response = httpx.get(f"http://127.0.0.1:{server.port}/api/config", timeout=2.0)
        assert response.status_code == 200
        data = response.json()
        assert data["active_directory"] == str(scan_dir)
        assert data["extensions"][0] == "exe"
        assert data["filters"][0] == "installer"
    finally:
        server.stop()


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


def test_rebind_changes_host_and_reverses(tmp_path: Path) -> None:
    """rebind switches the live bind host; app-state registration exposes it."""
    port = find_available_port(start_port=8000)
    server = BackgroundServer(config=AppConfig(title="rebind"), host="127.0.0.1", port=port)
    server.start()
    try:
        server.rebind("0.0.0.0")
        assert server.host == "0.0.0.0"
        response = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2.0)
        assert response.status_code == 200
        # The registration the route layer relies on:
        assert server._app.state.background_server is server
        server.rebind("127.0.0.1")
        response = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2.0)
        assert response.status_code == 200
    finally:
        server.stop()


_original_socket_bind = socket.socket.bind


def _bind_rejects_wildcard(sock: socket.socket, addr: tuple[str, int]) -> None:
    """Bind normally except for 0.0.0.0, which is forced to fail (firewall sim)."""
    if addr[0] == "0.0.0.0":
        raise OSError("simulated bind failure for the wildcard address")
    _original_socket_bind(sock, addr)


def test_rebind_failure_reverts_to_previous_host(mocker, tmp_path: Path) -> None:
    """A denied wildcard bind leaves the server serving the original address."""
    mocker.patch.object(socket.socket, "bind", _bind_rejects_wildcard)
    port = find_available_port(start_port=8000)
    server = BackgroundServer(config=AppConfig(title="revert"), host="127.0.0.1", port=port)
    server.start()
    try:
        with pytest.raises(ServerStartError):
            server.rebind("0.0.0.0")
        assert server.host == "127.0.0.1"
        assert server.is_running
        response = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2.0)
        assert response.status_code == 200
    finally:
        server.stop()
