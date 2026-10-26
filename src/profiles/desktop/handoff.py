"""Identify a busy port's owner and forward configs to a running instance.

Implements the identify-and-handoff fallback for double-clicked
``.profiles`` files (issue #4): when the default port is taken, the new
launch reads the per-port instance manifest, probes the port with a
secret-token handshake, and — when a ProFiles instance confirms both —
forwards the config over HTTP and exits 0. Anything else (foreign
process, dead manifest, failed handshake) reports a non-handoff outcome
so the caller falls back to a free port. No code path ever kills the
port owner.
"""

from __future__ import annotations

import contextlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from profiles.desktop.instance import HANDOFF_TOKEN_HEADER, read_manifest

_PROFILES_APP_ID = "ProFiles"
_DEFAULT_TIMEOUT_S = 3.0

HandoffStatus = Literal["handed_off", "owner_not_profiles", "handoff_failed"]


@dataclass(frozen=True)
class HandoffResult:
    """Outcome of an identify-and-handoff attempt against a busy port.

    - ``handed_off``: the running ProFiles instance applied the config;
      the new launch should exit 0.
    - ``owner_not_profiles``: the port owner could not be confirmed as
      ProFiles (no manifest, dead PID, rejected handshake) — fall back
      to a free port.
    - ``handoff_failed``: a ProFiles owner was confirmed but the config
      forward was rejected or failed — fall back to a free port too.
    """

    status: HandoffStatus
    detail: str = ""


def probe_instance_identity(
    port: int, token: str, timeout: float = _DEFAULT_TIMEOUT_S
) -> dict | None:
    """Return the identity payload when a ProFiles instance owns *port*.

    Sends the shared secret from the instance manifest; the running
    server answers only when the token matches, so a foreign process
    serving on the port — or an impostor answering fake JSON — can
    never be confirmed. Any error, mismatch, or unexpected payload
    returns None.
    """
    url = f"http://127.0.0.1:{port}/api/instance/identity"
    request = urllib.request.Request(url, headers={HANDOFF_TOKEN_HEADER: token})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("app") != _PROFILES_APP_ID:
        return None
    return payload


def forward_config_to_running_instance(
    port: int,
    config_path: str | Path,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> HandoffResult:
    """Apply *config_path* to a ProFiles instance already listening on *port*.

    The decision is deliberately conservative: the manifest (with a live
    PID), the token-verified identity handshake, and the manifest PID
    must all agree before the config is forwarded. Never raises and
    never signals the port owner — the caller decides the fallback.

    Args:
        port: TCP port found busy at bind time.
        config_path: Path of the ``.profiles`` file to forward.
        timeout: Seconds for each HTTP step of the handshake.

    Returns:
        A :class:`HandoffResult` describing the outcome (never raises).
    """
    manifest = read_manifest(port)
    if manifest is None:
        return HandoffResult("owner_not_profiles", f"no live instance manifest for port {port}")

    identity = probe_instance_identity(port, manifest.token, timeout=timeout)
    if identity is None:
        return HandoffResult("owner_not_profiles", f"identity handshake rejected on port {port}")
    if identity.get("pid") != manifest.pid:
        return HandoffResult("owner_not_profiles", "identity PID does not match the manifest")

    body = json.dumps({"config_path": str(Path(config_path).expanduser().resolve())}).encode(
        "utf-8"
    )
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/instance/handoff",
        data=body,
        headers={
            HANDOFF_TOKEN_HEADER: manifest.token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return HandoffResult("handed_off")
    except urllib.error.HTTPError as exc:
        # Server rejected the config (invalid/missing file, bad request).
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        return HandoffResult("handoff_failed", f"running instance rejected the config: {detail}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HandoffResult("handoff_failed", f"handoff request failed: {exc}")
