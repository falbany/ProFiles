"""Configuration subsystem — single egress for config-related APIs.

Consolidates the consolidated configuration subsystem:

- ``models``    : pure dataclasses (:class:`AppConfig`, :class:`MachineConfiguration`, …)
- ``service``   : domain operations over :class:`AppConfig` (merge, find, auto-select)
- ``template``  : starter :data:`STARTER_CONFIG_TEMPLATE` for fresh installs
- ``loader``    : top-level :func:`load_config` and :func:`propose_config_creation`
- ``reader``    : :class:`ConfigReader` that parses ``.profiles`` into :class:`AppConfig`
- ``io/``       : low-level YAML serialization primitives (read/write/find)

Callers should import from this top-level package; deeper submodules are
implementation details and may change without notice.
"""

from __future__ import annotations

from profiles.core.config.io.yaml_io import find_config_file
from profiles.core.config.loader import load_config, propose_config_creation
from profiles.core.config.models import (
    AppConfig,
    ColumnConfiguration,
    HookSpec,
    MachineConfiguration,
)
from profiles.core.config.reader import ConfigReader
from profiles.core.config.service import (
    auto_select_directory,
    find_active_config,
    find_configuration_by_hostname,
    get_unique_directories,
    merge_config_overrides,
)
from profiles.core.config.template import STARTER_CONFIG_TEMPLATE

__all__ = [
    # Models
    "AppConfig",
    "ColumnConfiguration",
    "HookSpec",
    "MachineConfiguration",
    # Loader
    "load_config",
    "propose_config_creation",
    # Reader
    "ConfigReader",
    # Domain operations
    "auto_select_directory",
    "find_active_config",
    "find_configuration_by_hostname",
    "get_unique_directories",
    "merge_config_overrides",
    # Template
    "STARTER_CONFIG_TEMPLATE",
    # YAML I/O
    "find_config_file",
]
