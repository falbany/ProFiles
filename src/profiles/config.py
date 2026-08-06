"""Convenience re-exports for ``profiles.config``.

Provides a short import path for the most common configuration types
and operations so callers can write::

    from profiles.config import AppConfig, load_config

instead of the fully-qualified sub-package path.
"""

from __future__ import annotations

from profiles.core.config.loader import load_config, propose_config_creation
from profiles.core.config.models import (
    AppConfig,
    ColumnConfiguration,
    MachineConfiguration,
)
from profiles.core.config.reader import ConfigReader
from profiles.core.config.service import find_configuration_by_hostname

__all__ = [
    "AppConfig",
    "ColumnConfiguration",
    "MachineConfiguration",
    "ConfigReader",
    "load_config",
    "propose_config_creation",
    "find_configuration_by_hostname",
]
