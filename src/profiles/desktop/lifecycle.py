"""Port allocation and background Uvicorn lifecycle management."""

from __future__ import annotations

import socket
import threading
from pathlib import Path

import uvicorn

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState


def find_available_port(start_port: int = 8088, max_attempts: int = 50) -> int:
    """Find an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # Fallback to OS assigned ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class BackgroundServer:
    """Spawns and manages a local Uvicorn instance in a background thread."""

    def __init__(self, config: AppConfig, host: str = "127.0.0.1", port: int = 8088) -> None:
        self.config = config
        self.host = host
        self.port = port if port != 0 else find_available_port(8088)
        self.state = ServerState(
            config=config,
            active_directory=Path(config.search_dir) if config.search_dir else None,
        )
        self._app = create_app(self.state)
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the background server thread."""
        uv_config = uvicorn.Config(
            app=self._app,
            host=self.host,
            port=self.port,
            log_level="warning",
            loop="asyncio",
        )
        self._server = uvicorn.Server(uv_config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the Uvicorn server to stop and join thread."""
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
