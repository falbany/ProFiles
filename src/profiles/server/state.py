"""Shared runtime state for ProFiles FastAPI server."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME, find_config_file
from profiles.core.config.models import AppConfig

_MAX_EXTERNAL_EVENTS = 50


@dataclass
class ServerState:
    """Holds active application configuration and cached scan results."""

    config: AppConfig
    active_directory: Path | None = None
    config_path: Path | None = None
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
        subtree, and finally the canonical primary name in the CWD.
        """
        config_path = self.config_path or getattr(self.config, "config_path", None)
        if config_path is None:
            config_path = find_config_file() or Path.cwd() / PRIMARY_CONFIG_NAME
        return Path(config_path)

    def record_external_event(
        self, kind: str, message: str, *, config_applied: bool = False
    ) -> int:
        """Buffer a UI notification for the polling channel; return its id.

        The buffer is capped so a long-lived server cannot grow it
        without bound even when no client is polling.
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
        return self._external_event_seq

    def external_events_after(self, after_id: int) -> list[dict[str, Any]]:
        """Return buffered events with an id greater than *after_id*."""
        return [event for event in self._external_events if event["id"] > after_id]
