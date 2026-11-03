"""Port allocation and background Uvicorn lifecycle management."""

from __future__ import annotations

import contextlib
import os
import secrets
import socket
import threading
import time

import uvicorn

from profiles.core.config.models import AppConfig
from profiles.desktop.instance import (
    InstanceManifest,
    prune_stale_manifests,
    remove_manifest,
    write_manifest,
)
from profiles.server.app import create_app
from profiles.server.state import ServerState

_STARTUP_TIMEOUT_S = 10.0
_GRACEFUL_STOP_TIMEOUT_S = 3.0
_FORCE_STOP_TIMEOUT_S = 2.0


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

    def __init__(self, config: AppConfig, host: str = "127.0.0.1", port: int = 8088) -> None:
        self.config = config
        self.host = host
        self.port = port if port != 0 else find_available_port(8088)
        # Secret shared with the instance manifest: a second launch uses
        # it to confirm this process owns the port before a config handoff.
        self._instance_token = secrets.token_urlsafe(24)
        self._manifest_published = False

        from profiles.core.config import service as config_service
        from profiles.utils.network import get_hostname

        # Shared with the server's config load/drop endpoints so a runtime
        # load resolves the same directory a launch with this file would.
        active_dir = config_service.choose_active_directory(config, get_hostname())

        self.state = ServerState(
            config=config,
            active_directory=active_dir,
            instance_token=self._instance_token,
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

        ``SO_REUSEADDR`` is required for :meth:`rebind`: uvicorn closes the
        accepted keep-alive connections server-side during shutdown, and each
        of those leaves a TIME_WAIT socket pinned to the old address for
        ~15-30 s on macOS. Without the option the new bind fails with
        ``EADDRINUSE`` even though no listener holds the port anymore
        (loopback→LAN rebind was therefore effectively impossible).

        The double-bind hazard this option adds is contained elsewhere:
        :func:`find_available_port` probes *without* it so port discovery
        still refuses occupied ports, and a second launch is arbitrated by
        the instance manifest/port-handoff mechanism (issue #4), never by
        sharing the listener. ``SO_REUSEPORT`` stays off — that is the
        option that would let two servers silently share the port. Binding
        here still surfaces address conflicts synchronously instead of
        inside the worker thread.
        """
        if self._sock is not None:
            self._sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # IPv4 only: all call sites bind ``0.0.0.0`` or ``127.0.0.1``
        # (no IPv6-literal or hostname hosts).
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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

        # Route code reaches the running server through the app instance
        # (structural BindableServer protocol in server/state.py).
        self._app.state.background_server = self

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
                self._publish_instance_manifest()
                return
            time.sleep(0.05)

        self.stop()
        msg = f"ProFiles server did not start within {timeout}s on {self.host}:{self.port}"
        raise ServerStartError(msg)

    def _publish_instance_manifest(self) -> None:
        """Advertise this instance in the temp dir for config handoff.

        Published only once the server is confirmed serving, so a
        manifest never points at a port nobody listens on.
        """
        from profiles import __version__

        prune_stale_manifests()
        write_manifest(
            InstanceManifest(
                pid=os.getpid(),
                port=self.port,
                host=self.host,
                version=__version__,
                token=self._instance_token,
            )
        )
        self._manifest_published = True

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

        Safe to call before :meth:`start` or more than once. A client
        wedged in a long-lived request can outlast the graceful shutdown
        window; in that case the server is force-exited (abruptly closing
        outstanding requests) so the port is actually released for a
        subsequent :meth:`start` — e.g. the rebind path.
        """
        if self._manifest_published:
            self._manifest_published = False
            remove_manifest(self.port)
        if self._server is not None and not self._server.should_exit:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=_GRACEFUL_STOP_TIMEOUT_S)
        if self._thread and self._thread.is_alive() and self._server is not None:
            self._server.force_exit = True
            self._thread.join(timeout=_FORCE_STOP_TIMEOUT_S)
        self._reset()

    def rebind(self, host: str) -> None:
        """Restart the server bound to a new address, in place.

        Used by the ``POST /api/system/bind`` route so the web UI can turn
        LAN exposure on and off while a client is connected. When the new
        bind fails, this server is brought back up on the *previous* host
        and the original :class:`ServerStartError` is re-raised — the app
        must never be left unreachable.

        Args:
            host: New bind address (e.g. ``"0.0.0.0"`` or ``"127.0.0.1"``).

        Raises:
            ServerStartError: The new bind could not be established. The
                previous bind is still serving when this is raised.
        """
        if host == self.host and self.is_running:
            return
        previous_host = self.host
        self.stop()
        self.host = host
        try:
            self.start()
        except ServerStartError:
            self.host = previous_host
            with contextlib.suppress(ServerStartError):
                self.start()
            raise
