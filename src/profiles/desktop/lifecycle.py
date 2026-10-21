"""Port allocation and background Uvicorn lifecycle management."""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from pathlib import Path

import uvicorn

from profiles.core.config.models import AppConfig
from profiles.server.app import create_app
from profiles.server.state import ServerState

_STARTUP_TIMEOUT_S = 10.0


class ServerStartError(RuntimeError):
    """Raised when the background uvicorn server fails to start.

    Callers must not open a window against a dead server; the error message
    names the host and port so the collision can be diagnosed.
    """


def find_available_port(start_port: int = 8088, max_attempts: int = 50) -> int:
    """Find an available TCP port starting from start_port.

    A port counts as free only when it can be bound *and* listened on, so a
    port held by another process is skipped rather than reported available.

    The probe deliberately does NOT set ``SO_REUSEADDR``: on macOS/BSD that
    option allows a second bind against an active listener, which would
    make the probe report occupied ports as free.
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                sock.listen(1)
                return port
            except OSError:
                continue
    # Fallback to OS assigned ephemeral port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return sock.getsockname()[1]


class BackgroundServer:
    """Spawns and manages a local Uvicorn instance in a background thread."""

    def __init__(self, config: AppConfig, host: str = "0.0.0.0", port: int = 8088) -> None:
        self.config = config
        self.host = host
        self.port = port if port != 0 else find_available_port(8088)

        active_dir = None
        if config.search_dir and Path(config.search_dir).exists():
            active_dir = Path(config.search_dir)
        else:
            from profiles.core.config import service as config_service
            from profiles.utils.network import get_hostname

            selected = config_service.auto_select_directory(config, get_hostname())
            if selected and Path(selected).exists():
                active_dir = Path(selected)
            else:
                for m in config.configurations:
                    for s in m.scan:
                        if Path(s).exists():
                            active_dir = Path(s)
                            break
                    if active_dir:
                        break

        self.state = ServerState(
            config=config,
            active_directory=active_dir,
        )
        self._app = create_app(self.state)
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._startup_error: BaseException | None = None
        self._sock: socket.socket | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _bind_listener(self) -> socket.socket:
        """Create, bind, and pre-listen the server socket.

        Deliberately without ``SO_REUSEADDR`` (and without ``SO_REUSEPORT``):
        on macOS/BSD those options permit a second bind against an active
        listener, which would let two server instances silently share a
        port. Binding here also surfaces address conflicts synchronously
        instead of inside the worker thread.
        """
        if self._sock is not None:
            self._sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Not SO_REUSEADDR — see docstring. IPv4 only: all call sites bind
        # ``0.0.0.0`` or ``127.0.0.1`` (no IPv6-literal or hostname hosts).
        sock.bind((self.host, self.port))
        sock.listen(1)
        self._sock = sock
        return sock

    def start(self, timeout: float = _STARTUP_TIMEOUT_S) -> None:
        """Start the background server thread and wait until it is serving.

        Args:
            timeout: Seconds to wait for uvicorn to reach the serving state.

        Raises:
            ServerStartError: If the server fails to bind or start, so callers
                never present a UI backed by a dead server.
        """
        if self.is_running:
            return

        try:
            self._bind_listener()
        except OSError as exc:
            msg = f"ProFiles server failed to start on {self.host}:{self.port}: {exc}"
            raise ServerStartError(msg) from exc

        uv_config = uvicorn.Config(
            app=self._app,
            host=self.host,
            port=self.port,
            log_level="warning",
            loop="asyncio",
        )
        self._server = uvicorn.Server(uv_config)
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._startup_error is not None:
                error = self._startup_error
                self.stop()
                msg = f"ProFiles server failed to start on {self.host}:{self.port}: {error}"
                raise ServerStartError(msg)
            if self.is_running and self._server is not None and self._server.started:
                return
            time.sleep(0.05)

        self.stop()
        msg = f"ProFiles server did not start within {timeout}s on {self.host}:{self.port}"
        raise ServerStartError(msg)

    def _run_server(self) -> None:
        """Run uvicorn on the pre-bound socket, recording startup failures.

        The socket is pre-bound by :meth:`start` so that address conflicts
        surface synchronously; ``run(sockets=[...])`` skips uvicorn's own
        bind (and its ``SO_REUSEADDR``-permitting default).
        """
        assert self._server is not None and self._sock is not None
        sock = self._sock
        try:
            self._server.run(sockets=[sock])
        except SystemExit as exc:  # uvicorn calls sys.exit on runtime failure
            self._startup_error = exc
        except OSError as exc:
            self._startup_error = exc
        finally:
            # asyncio never closes caller-provided sockets on shutdown.
            with contextlib.suppress(OSError):
                sock.close()
            self._sock = None

    def _reset(self) -> None:
        """Clear thread/server references after a failed or completed run."""
        self._server = None
        self._thread = None
        self._startup_error = None

    def stop(self) -> None:
        """Signal the Uvicorn server to stop and join the thread.

        Safe to call before :meth:`start` or more than once.
        """
        if self._server is not None:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._reset()
