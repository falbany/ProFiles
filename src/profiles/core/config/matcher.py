import fnmatch
import os
import re
from collections.abc import Sequence

from profiles.core.config.models import AppConfig, MachineConfiguration


def _normalize_path(path: str) -> str:
    """Normalize filesystem path for cross-platform matching."""
    if not path:
        return ""
    expanded = os.path.expanduser(path)
    norm = os.path.normpath(expanded)
    return norm.replace("\\", "/").lower()


def match_pattern(pattern: str, value: str, is_path: bool = False) -> bool:
    """Match value against pattern (glob or regex)."""
    if not pattern or not value:
        return False

    if pattern.startswith("re:"):
        regex = pattern[3:]
        target = _normalize_path(value) if is_path else value
        return bool(re.search(regex, target, re.IGNORECASE))

    if is_path:
        norm_pattern = _normalize_path(pattern)
        norm_value = _normalize_path(value)
        return fnmatch.fnmatch(norm_value, norm_pattern)

    return fnmatch.fnmatch(value.lower(), pattern.lower())


def eval_criteria_list(patterns: Sequence[str], candidate: str, is_path: bool = False) -> bool:
    """Return True if any pattern in patterns matches candidate."""
    return any(match_pattern(pat, candidate, is_path=is_path) for pat in patterns)


def matches_machine_config(
    config: MachineConfiguration,
    hostname: str,
    ip: str,
    path: str,
) -> bool:
    """Evaluate if machine config matches current environment (OR logic)."""
    m = config.match
    if m.hostname and eval_criteria_list(m.hostname, hostname):
        return True
    if m.ip and eval_criteria_list(m.ip, ip):
        return True
    return m.path and eval_criteria_list(m.path, path, is_path=True)


def select_active_configuration(
    config: AppConfig,
    hostname: str,
    ip: str,
    path: str,
) -> MachineConfiguration | None:
    """Select the first matching configuration or default fallback."""
    for machine in config.configurations:
        if matches_machine_config(machine, hostname, ip, path):
            return machine

    return config.configurations[0] if config.configurations else None
