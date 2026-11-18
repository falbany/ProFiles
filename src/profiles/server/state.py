"""Shared runtime state for ProFiles FastAPI server."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from profiles.core.config.io.yaml_io import find_config_file
from profiles.core.config.models import AppConfig
from profiles.core.paths import default_config_path
from profiles.core.telemetry import events

_MAX_EXTERNAL_EVENTS = 50

# Server-side telemetry logger (the "profiles" logger writes profiles.log);
# same module-level lookup as server/app.py.
_LOGGER = logging.getLogger("profiles")


class BindableServer(Protocol):
    """The subset of ``BackgroundServer`` the route layer touches.

    Declared here so ``server/routes`` can type the registered server
    without importing ``profiles.desktop`` (desktop imports server; the
    reverse would be a layering cycle).
    """

    @property
    def is_running(self) -> bool: ...

    @property
    def host(self) -> str: ...

    def rebind(self, host: str) -> None: ...


@dataclass
class ServerState:
    """Holds active application configuration and cached scan results."""

    config: AppConfig
    active_directory: Path | None = None
    config_path: Path | None = None
    # True while the active config is an in-memory trial from a
    # dropped/loaded content payload (no disk anchor).
    session_trial: bool = False
    # Raw YAML text behind ``session_trial`` trials (issue #97): the ONLY
    # record of what was applied, since parsing discards the payload.
    # GET /content echoes it so a reopened editor shows the live trial
    # configuration. Cleared by every disk-anchoring path — it belongs to
    # no real file, so anchoring invalidates it.
    trial_content: str | None = None
    # Shared secret verifying handoff requests from a second ProFiles
    # launch (issue #4); None disables the identity/handoff endpoints.
    instance_token: str | None = None
    cached_results: list[Any] = field(default_factory=list)
    scan_in_progress: bool = False
    scan_generation: int = 0
    # UI events recorded by external actors (config handoff), drained by
    # the frontend's /api/notifications poll.
    _external_events: list[dict[str, Any]] = field(default_factory=list)
    _external_event_seq: int = 0

    def active_config_path(self) -> Path:
        """Return the configuration file this server considers active.

        Resolution order mirrors launch-time resolution: any explicit
        ``config_path`` recorded after loading, then the path carried by
        the loaded :class:`AppConfig`, then a core search of the CWD
        subtree, and finally :func:`default_config_path` (the per-user
        ``~/.profiles/.profiles`` for launcher-style launches, the
        project folder otherwise; issue #191). An existing **directory**
        is never returned as the config file — the ``CWD == home``
        collision with the ``~/.profiles`` log directory falls through to
        :func:`default_config_path` instead.
        """
        config_path = self.config_path or getattr(self.config, "config_path", None)
        if config_path is None:
            config_path = find_config_file() or default_config_path()
        resolved = Path(config_path)
        try:
            if resolved.is_dir():
                return default_config_path()
        except OSError:
            pass
        return resolved

    def record_external_event(
        self, kind: str, message: str, *, config_applied: bool = False
    ) -> int:
        """Buffer a UI notification for the polling channel; return its id.

        The buffer is capped so a long-lived server cannot grow it
        without bound even when no client is polling.

        Every event is also mirrored to the logger as a DEBUG TOAST
        record (issue #194): the single choke point covers all current
        and future producers (odoc applier, instance handoff route).
        """
        self._external_event_seq += 1
        self._external_events.append(
            {
                "id": self._external_event_seq,
                "kind": kind,
                "message": message,
                "config_applied": config_applied,
            }
        )
        if len(self._external_events) > _MAX_EXTERNAL_EVENTS:
            excess = len(self._external_events) - _MAX_EXTERNAL_EVENTS
            del self._external_events[:excess]
        events.toast(
            _LOGGER,
            source="server",
            kind=kind,
            message=message,
            applied=config_applied,
        )
        return self._external_event_seq

    def external_events_after(self, after_id: int) -> list[dict[str, Any]]:
        """Return buffered events with an id greater than *after_id*."""
        return [event for event in self._external_events if event["id"] > after_id]
