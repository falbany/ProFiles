"""On-disk instance manifest shared by concurrent ProFiles processes.

Each running web server records a small JSON manifest in the user temp
dir (one file per port) holding its PID, port, version and a secret
handoff token. A second launch that finds the default port busy reads
the manifest to identify the owner and, when the owner confirms the
secret over HTTP, forwards the clicked ``.profiles`` file to it instead
of failing to bind (issue #4). Manifests of dead processes are pruned
on read and on startup, so a stale file can never misidentify an owner.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

MANIFEST_PREFIX = "profiles-instance-"
MANIFEST_SUFFIX = ".json"
HANDOFF_TOKEN_HEADER = "X-ProFiles-Token"

# Windows access rights for the non-killing liveness check (OpenProcess).
_WINDOWS_PROCESS_QUERY_LIMITED = 0x1000
_WINDOWS_STILL_ACTIVE = 0x103


@dataclass(frozen=True)
class InstanceManifest:
    """Identity of one running ProFiles web server (one file per port)."""

    pid: int
    port: int
    host: str
    version: str
    token: str


def manifest_path(port: int) -> Path:
    """Return the manifest file path for the server listening on *port*."""
    return Path(tempfile.gettempdir()) / f"{MANIFEST_PREFIX}{port}{MANIFEST_SUFFIX}"


def write_manifest(manifest: InstanceManifest) -> Path:
    """Persist *manifest* atomically and return its path.

    The atomic replace means a reader never observes a half-written
    file, even when two launches race around the same port.
    """
    path = manifest_path(manifest.port)
    payload = json.dumps(asdict(manifest), indent=2)
    handle_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    return path


def read_manifest(port: int) -> InstanceManifest | None:
    """Return the live manifest for *port*, or None after cleaning stale ones.

    A manifest is stale when it is unreadable/corrupt or its PID is no
    longer alive; stale files are removed so a dead instance can never
    be mistaken for the port owner.
    """
    path = manifest_path(port)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        manifest = InstanceManifest(
            pid=int(data["pid"]),
            port=int(data["port"]),
            host=str(data["host"]),
            version=str(data["version"]),
            token=str(data["token"]),
        )
    except (OSError, TypeError, ValueError, KeyError):
        _discard(path)
        return None
    if not pid_alive(manifest.pid):
        _discard(path)
        return None
    return manifest


def remove_manifest(port: int) -> None:
    """Delete the manifest for *port* (clean shutdown); missing file is fine."""
    _discard(manifest_path(port))


def prune_stale_manifests() -> None:
    """Remove manifests whose process is gone (startup hygiene).

    Called before a new manifest is published so temp-dir clutter from
    killed instances never accumulates.
    """
    for path in Path(tempfile.gettempdir()).glob(f"{MANIFEST_PREFIX}*{MANIFEST_SUFFIX}"):
        alive = False
        with contextlib.suppress(OSError, TypeError, ValueError, KeyError):
            data = json.loads(path.read_text(encoding="utf-8"))
            alive = pid_alive(int(data["pid"]))
        if not alive:
            _discard(path)


def pid_alive(pid: int) -> bool:
    """Return True when *pid* is a live process (cross-platform, no deps).

    Deliberately avoids ``os.kill(pid, 0)`` on Windows: for unknown
    signals that call maps to ``TerminateProcess`` and would kill the
    very instance being checked.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_pid_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OverflowError:
        # Beyond the C int range: no real OS pid can be this large.
        return False
    except PermissionError:
        # Exists but owned by another user — alive for our purposes.
        return True
    except OSError:
        return True
    return True


def _windows_pid_alive(pid: int) -> bool:
    """Windows liveness via OpenProcess (query-limited, no termination)."""
    import ctypes
    import ctypes.wintypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(_WINDOWS_PROCESS_QUERY_LIMITED, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            # Queried but exit code unreadable — assume alive (conservative).
            return True
        return exit_code.value == _WINDOWS_STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _discard(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()
