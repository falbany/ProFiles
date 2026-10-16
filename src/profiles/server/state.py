"""Shared runtime state for ProFiles FastAPI server."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
