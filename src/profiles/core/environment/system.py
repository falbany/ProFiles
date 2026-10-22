"""System information collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from profiles.core.telemetry.diagnostics import SourceFilter
from profiles.utils.network import get_hostname, get_local_ip, get_username


@dataclass(frozen=True)
class SystemInfo:
    """System identity collected at startup."""

    hostname: str
    username: str
    ip: str


def collect_system_info() -> SystemInfo:
    """Collect hostname, username, and local IP from the OS."""
    return SystemInfo(
        hostname=get_hostname(),
        username=get_username(),
        ip=get_local_ip(),
    )


def format_user_host(username: str, hostname: str) -> str:
    """Format a log source identifier as ``user@host``.

    Falls back to whichever part is available when the other is empty,
    and to an empty string when both are.

    Args:
        username: OS login name (e.g. ``"f.albany"``).
        hostname: Machine name (e.g. ``"ST-465"``).

    Returns:
        The combined identifier, e.g. ``"f.albany@ST-465"``.
    """
    if username and hostname:
        return f"{username}@{hostname}"
    return username or hostname


def apply_source_to_logger(logger: logging.Logger, source: str) -> None:
    """Update the ``SourceFilter.source`` on every handler of *logger*.

    Lets a logger that was created with a placeholder source (e.g.
    ``"ProFiles"``) be re-tagged with the real hostname after it has
    been collected.
    """
    for handler in logger.handlers:
        for log_filter in handler.filters:
            if isinstance(log_filter, SourceFilter):
                log_filter.source = source
