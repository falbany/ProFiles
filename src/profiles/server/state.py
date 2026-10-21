"""Shared runtime state for ProFiles FastAPI server."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME, find_config_file
from profiles.core.config.models import AppConfig


@dataclass
class ServerState:
    """Holds active application configuration and cached scan results."""

    config: AppConfig
    active_directory: Path | None = None
    config_path: Path | None = None
    cached_results: list[Any] = field(default_factory=list)
    scan_in_progress: bool = False
    scan_generation: int = 0

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
