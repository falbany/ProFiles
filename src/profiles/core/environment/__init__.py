"""Environment subsystem — OS environment, hostname/IP, and process spawn.

Decouples the domain from raw OS calls:

- ``system``    : :func:`collect_system_info` (hostname / username / IP)
- ``execution`` : launch-hook process spawn orchestration (:class:`HookOutcome`)
"""

from __future__ import annotations

from profiles.core.environment.execution import (
    HookOutcome,
    parse_hook_entries,
    run_blocking_hook,
    run_hooks_for_file,
    spawn_background_hook,
)
from profiles.core.environment.system import (
    SystemInfo,
    apply_source_to_logger,
    collect_system_info,
)

__all__ = [
    # System info
    "SystemInfo",
    "collect_system_info",
    "apply_source_to_logger",
    # Execution (launch hooks)
    "HookOutcome",
    "parse_hook_entries",
    "run_hooks_for_file",
    "run_blocking_hook",
    "spawn_background_hook",
]
