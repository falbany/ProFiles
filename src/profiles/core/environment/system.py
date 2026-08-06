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
