"""Public surface for :mod:`profiles.launch`.

Consolidates launch-time configuration handling:

- ``context``    : :class:`LaunchContext` and OS signal detection
- ``resolution`` : pure selection of which config file to use
- ``creation``   : offering and writing a starter ``.profiles``

Callers should import from this package; the submodules are
implementation detail.
"""

from __future__ import annotations

from profiles.launch.context import (
    CONFIG_SUFFIX,
    FALLBACK_CONFIG_SUFFIX,
    LaunchContext,
    detect_launch_context,
    with_explicit_config,
)
from profiles.launch.creation import CreationResult, propose_creation
from profiles.launch.resolution import resolve_config_path

__all__ = [
    "CONFIG_SUFFIX",
    "FALLBACK_CONFIG_SUFFIX",
    "CreationResult",
    "LaunchContext",
    "detect_launch_context",
    "propose_creation",
    "resolve_config_path",
    "with_explicit_config",
]
