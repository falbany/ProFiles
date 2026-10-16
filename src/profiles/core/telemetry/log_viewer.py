"""Parse ``profiles.log`` entries into structured records.

Lives in ``core`` because log inspection is a cross-cutting domain
concern shared by every front-end (GUI, CLI, TUI) and has zero
dependency on Tkinter.

The on-disk grammar produced by :mod:`profiles.core.telemetry.diagnostics`
is::

    YYYY-MM-DD HH:MM:SS - LEVEL - SOURCE: EVENT key="value" key=value

Lines that do not match the expected shape are preserved verbatim as
``message`` records with an ``UNKNOWN`` level so operators never lose
visibility into a torn or partially-written line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

_LOG_VIEWER_LOGGER = getLogger(__name__)

# Anchored to the full line: timestamp, level, source, message body.
_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r"\s+-\s+"
    r"(?P<level>[A-Z]+)"
    r"\s+-\s+"
    r"(?P<source>.+?)"
    r"(?::\s+|\s+: )"
    r"(?P<message>.*)$"
)

# Leading UPPER_SNAKE_CASE token of a message body, when present.
_EVENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]+$")

# Levels ordered from least to most severe, for the viewer's filter control.
LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Fallback level used for lines the grammar cannot classify.
UNKNOWN_LEVEL = "UNKNOWN"

# Bytes read from the end of a log file; roughly 1 MB tail window.
_TAIL_WINDOW_BYTES = 1 * 1024 * 1024


@dataclass(frozen=True)
class LogEntry:
    """A single parsed log line.

    Attributes:
        timestamp: ``YYYY-MM-DD HH:MM:SS`` string, or the raw line when unparsed.
        level: Log level name (``INFO``), or ``UNKNOWN`` for unparsed lines.
        source: Machine/source identifier emitted by the logger, if any.
        message: Event name plus any structured ``key=value`` payload.
        raw: The original, untouched line.
    """

    timestamp: str
    level: str
    source: str
    message: str
    raw: str

    @property
    def event(self) -> str:
        """Leading UPPER_SNAKE_CASE event name of the message, if present."""
        first = self.message.split(" ", 1)[0] if self.message else ""
        return first if _EVENT_NAME.match(first) else ""

    @property
    def is_error(self) -> bool:
        """Whether the entry is at WARNING severity or above."""
        return self.level in {"WARNING", "ERROR", "CRITICAL"}


def parse_log_line(line: str) -> LogEntry:
    """Parse one raw log line into a :class:`LogEntry`.

    Args:
        line: A single line, with or without its trailing newline.

    Returns:
        A structured entry. Unrecognised lines are returned as
        ``UNKNOWN`` entries that retain their ``raw`` text.
    """
    raw = line.rstrip("\r\n")

    match = _LINE_PATTERN.match(raw)
    if match is None:
        return LogEntry(
            timestamp="",
            level=UNKNOWN_LEVEL,
            source="",
            message=raw,
            raw=raw,
        )

    message = match.group("message")
    return LogEntry(
        timestamp=match.group("timestamp"),
        level=match.group("level").upper(),
        source=match.group("source").strip(),
        message=message.strip(),
        raw=raw,
    )


def read_log_entries(
    path: Path | str,
    limit: int = 500,
    level: str | None = None,
    search: str = "",
) -> list[LogEntry]:
    """Read the tail of a log file as structured entries.

    Only the tail is read into memory so that a multi-megabyte log file
    never slows down the viewer.

    Args:
        path: Path to the log file.
        limit: Maximum number of entries to return (newest last).
        level: Optional level name filter (e.g. ``"ERROR"``). Levels at
            or above the given severity are kept; ``"DEBUG"`` keeps all.
        search: Optional case-insensitive substring matched against the
            whole raw line.
    Returns:
        Parsed entries in file order (oldest first). Empty when the file
        does not exist or is empty.
    """
    log_path = Path(path).expanduser()
    if not log_path.exists():
        return []

    try:
        # Read only the tail window so a multi-megabyte log never loads whole.
        size = log_path.stat().st_size
        with log_path.open("rb") as handle:
            if size > _TAIL_WINDOW_BYTES:
                handle.seek(size - _TAIL_WINDOW_BYTES)
                # Drop the partial line the seek most likely landed inside.
                discarded = handle.readline()
                _LOG_VIEWER_LOGGER.debug(
                    "log_viewer tail read size=%d discarded_partial_bytes=%d", size, len(discarded)
                )
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []

    entries = [parse_log_line(line) for line in lines if line.strip()]

    if level:
        entries = [e for e in entries if _keeps_level(e.level, level)]

    needle = search.strip().lower()
    if needle:
        entries = [e for e in entries if needle in e.raw.lower()]

    if limit and len(entries) > limit:
        entries = entries[-limit:]
    return entries


def log_file_size(path: Path | str) -> int:
    """Return the log file size in bytes, or ``0`` when it does not exist."""
    log_path = Path(path).expanduser()
    try:
        return log_path.stat().st_size
    except OSError:
        return 0


def _severity(level: str) -> int:
    """Map a level name onto a comparable rank where higher is worse.

    Returns ``-1`` for levels outside :data:`LOG_LEVELS` (unparsed lines).
    """
    try:
        return LOG_LEVELS.index(level.upper())
    except ValueError:
        return -1


def _keeps_level(entry_level: str, minimum: str) -> bool:
    """Whether an entry at or above ``minimum`` severity should be kept.

    Unparsed (``UNKNOWN``) lines are always kept, at any threshold, so a
    torn line is never silently filtered out of the viewer.
    """
    if entry_level.upper() == UNKNOWN_LEVEL:
        return True
    return _severity(entry_level) >= _severity(minimum)
