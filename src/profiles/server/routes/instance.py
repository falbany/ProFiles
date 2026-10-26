"""Instance identity, config handoff, and UI notification endpoints.

The handoff protocol (issue #4): a second ProFiles launch that cannot
bind the default port identifies the port owner with a secret-token
handshake and forwards the clicked ``.profiles`` file. The token comes
from the per-port instance manifest in the user temp dir, so a foreign
process serving on the port — which knows neither the manifest nor the
token — is rejected with 403 and the new launch falls back to a free
port. The applied config is surfaced in the running UI through the
``/api/notifications`` polling channel.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

import profiles
from profiles.desktop.instance import HANDOFF_TOKEN_HEADER
from profiles.server.routes.config import LoadConfigRequest, _apply_config_from_disk
from profiles.server.state import ServerState

router = APIRouter(tags=["instance"])


def _require_handoff_token(state: ServerState, request: Request) -> None:
    """Reject requests that do not carry this instance's shared secret.

    A missing or mismatched token is a hard 403: the caller is either a
    foreign process on the port or a launch without the manifest — both
    must never be able to swap the running configuration.
    """
    provided = request.headers.get(HANDOFF_TOKEN_HEADER, "")
    expected = state.instance_token
    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid ProFiles handoff token")


@router.get("/api/instance/identity")
async def instance_identity(request: Request) -> dict:
    """Identity handshake for a new launch probing a busy port.

    Answers only to requests carrying the manifest's secret token, so a
    200 response is proof the port owner is a ProFiles instance.
    """
    state: ServerState = request.app.state.server_state
    _require_handoff_token(state, request)
    return {"app": "ProFiles", "version": profiles.__version__, "pid": os.getpid()}


@router.post("/api/instance/handoff")
async def instance_handoff(payload: LoadConfigRequest, request: Request) -> dict:
    """Apply a config forwarded by a second launch and notify the UI.

    Applies the forwarded file exactly like the in-app load endpoint,
    then buffers a notification so the running web UI shows a toast and
    re-applies the (server-side) new configuration on its next poll.
    """
    state: ServerState = request.app.state.server_state
    _require_handoff_token(state, request)
    config_path = Path(payload.config_path).expanduser().resolve()
    response = _apply_config_from_disk(state, config_path)
    state.record_external_event(
        kind="config_handoff",
        message=f"Configuration '{config_path.name}' applied by a new ProFiles launch",
        config_applied=True,
    )
    return response


@router.get("/api/notifications")
async def notifications(request: Request, after: int = 0) -> dict:
    """Return UI events recorded after *after* (frontend polling channel)."""
    state: ServerState = request.app.state.server_state
    return {"events": state.external_events_after(after)}
