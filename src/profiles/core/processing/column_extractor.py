"""Column extraction rules for ProFiles.

Provides dynamic column configuration via regex patterns extracted from
filenames. Supports custom columns beyond the default File and Version.

Usage:
    from profiles.core.processing.column_extractor import ColumnExtractor, ColumnRule

    extractor = ColumnExtractor()
    extractor.add_rule("Device", r"Device_(\\w+)")
    extractor.add_rule("Version", r"_V(.+)", priority=10)

    filename = "ST_PRO_Device_ABC123_V01-Rel6.2.1.mttl"
    values = extractor.extract_all(filename)
    # {"File": "ST_PRO_Device_ABC123_V01-Rel6.2.1.mttl", "Device": "ABC123", "Version": "01-Rel6.2.1"}
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import ClassVar

_logger = logging.getLogger("profiles")


BUILTIN_PATTERNS: dict[str, str] = {
    "version": r"[-_]V(\d+(?:\.\d+)*)(?=[^\\/]*\.[a-zA-Z0-9]+$)",
    "date": r"(\d{4}[-_]\d{2}[-_]\d{2}|\d{8})",
    "git_commit": r"_g([a-f0-9]{7})",
    "type": r"(PRO|ENG|DEV|TMP|DEBUG)(?!.*(?:PRO|ENG|DEV|TMP|DEBUG))",
    "filename": r"([^/\\]+)$",
    "extension": r"\.([^./\\]+)$",
}


@dataclass
class ColumnRule:
    """A single column extraction rule.

    Attributes:
        name: Column header name (must match config column_names).
        match: Built-in keyword (e.g. "version") or raw regex pattern.
        transform: Optional replacement pattern with group backreferences
            (e.g. "\\1 (Build \\2)"). If omitted, group 1 is returned when it
            exists, else the whole match (group 0).
        priority: Extraction priority (higher = processed first).
        default: Default value if pattern doesn't match.
        group: Legacy explicit group index (0 = entire match, 1+ = captured
            group). Only consulted when ``transform`` is not set and ``group``
            differs from the default of 1.
    """

    name: str
    match: str
    transform: str | None = None
    priority: int = 0
    default: str = ""
    group: int = 1

    # Class-level cache for compiled patterns shared across all instances.
    # This avoids recompiling the same pattern repeatedly.  Cleared via
    # :meth:`clear_cache` to support test isolation.
    _compiled: ClassVar[dict[str, re.Pattern]] = {}
    _warned: ClassVar[set[str]] = set()  # patterns already logged as invalid
    _BROKEN_SENTINEL: ClassVar[re.Pattern] = re.compile(r"(?!)")  # never-matching placeholder

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the compiled-pattern cache and warning set.

        Useful in test teardown to prevent state leakage between tests
        that use malformed regex patterns.
        """
        cls._compiled.clear()
        cls._warned.clear()

    def _resolve_pattern(self) -> str:
        """Return the built-in pattern for a keyword, else the raw regex."""
        pattern_key = self.match.lower()
        if pattern_key in BUILTIN_PATTERNS:
            return BUILTIN_PATTERNS[pattern_key]
        return self.match

    def compiled(self) -> re.Pattern:
        """Get compiled regex pattern with caching.

        Invalid patterns fall back to a never-matching sentinel after
        logging a warning once.  This keeps the GUI/caller alive on
        malformed ``[COLUMN_*]`` expressions instead of crashing the
        whole scan.
        """
        pattern = self._resolve_pattern()
        if pattern not in ColumnRule._compiled:
            try:
                ColumnRule._compiled[pattern] = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                if pattern not in ColumnRule._warned:
                    _logger.warning(
                        "Invalid regex for column %r (%s): %s -- using default value as fallback",
                        self.name,
                        pattern,
                        exc,
                    )
                    ColumnRule._warned.add(pattern)
                ColumnRule._compiled[pattern] = ColumnRule._BROKEN_SENTINEL
        return ColumnRule._compiled[pattern]

    def extract(self, filename: str) -> str:
        """Extract value from filename using match and transform.

        If ``transform`` is set, uses Python's ``match.expand()`` with group
        backreferences. The ``{group:N}`` syntax is supported as a
        user-friendly alternative to ``\\g<N>`` — it is translated to
        ``\\g<N>`` before calling ``expand()``. Otherwise, if the legacy
        ``group`` index differs from 1, returns that explicit group
        (0 = full match). Otherwise returns group 1 if it exists, else
        the whole match (group 0).

        Args:
            filename: The filename to extract value from.

        Returns:
            Extracted value or default if no match / group is missing.
        """
        match = self.compiled().search(filename)
        if not match:
            return self.default

        try:
            if self.transform:
                # Translate {group:N} syntax to \g<N> for re.Pattern.expand()
                transform = re.sub(
                    r"\{group:(\d+)\}",
                    lambda m: r"\g<" + m.group(1) + ">",
                    self.transform,
                )
                return match.expand(transform)
            if self.group != 1:
                return match.group(0) if self.group == 0 else match.group(self.group)
            return match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
        except (IndexError, AttributeError, re.error):
            return self.default


class ColumnExtractor:
    """Extracts column values from filenames using configurable rules.

    The extractor keeps an **immutable snapshot** of its rules (a tuple
    always sorted by priority).  Mutations rebuild the tuple in a single
    atomic assignment; extraction only ever reads it.  Once built, the
    extractor can therefore be shared safely across worker threads.

    Example:
        extractor = ColumnExtractor()
        extractor.add_rule("File", r"(.+)", group=0, priority=100)
        extractor.add_rule("Version", r"_V([^_]+)", priority=10)
        extractor.add_rule("Device", r"Device_([A-Z0-9]+)", priority=5)

        values = extractor.extract_all("ST_PRO_Device_ABC123_V01.mttl")
        # {"File": "ST_PRO_Device_ABC123_V01.mttl", "Version": "01", "Device": "ABC123"}
    """

    def __init__(self) -> None:
        """Initialize the column extractor with no rules."""
        self._rules: tuple[ColumnRule, ...] = ()

    def add_rule(
        self,
        name: str,
        match: str,
        transform: str | None = None,
        priority: int = 0,
        default: str = "",
        group: int = 1,
    ) -> None:
        """Add a column extraction rule.

        Args:
            name: Column header name.
            match: Built-in keyword or raw regex pattern.
            transform: Optional replacement pattern with group backreferences.
            priority: Extraction priority (higher = first).
            default: Default value if pattern doesn't match.
            group: Legacy explicit group index (0 = full match, 1+ = group).
        """
        rule = ColumnRule(
            name=name,
            match=match,
            transform=transform,
            priority=priority,
            default=default,
            group=group,
        )
        self._rules = tuple(sorted(self._rules + (rule,), key=lambda r: r.priority, reverse=True))

    def remove_rule(self, name: str) -> bool:
        """Remove a rule by name.

        Args:
            name: Column rule name to remove.

        Returns:
            True if rule was found and removed.
        """
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                self._rules = self._rules[:i] + self._rules[i + 1 :]
                return True
        return False

    def get_rules(self) -> list[ColumnRule]:
        """Get all rules sorted by priority (highest first).

        Returns:
            A fresh list copy; mutating it does not affect the extractor.
        """
        return list(self._rules)

    def extract_all(self, filename: str, column_names: tuple[str, ...]) -> dict[str, str]:
        """Extract all column values for a filename.

        Args:
            filename: The filename to extract values from.
            column_names: Ordered list of column names to extract.

        Returns:
            Dictionary mapping column names to extracted values.
        """
        result: dict[str, str] = {}

        # Immutable snapshot: safe to read concurrently even if a
        # mutation reassigns self._rules in another thread.
        rules = self._rules
        rules_by_name: dict[str, ColumnRule] = {rule.name: rule for rule in rules}

        for col_name in column_names:
            if col_name in rules_by_name:
                # Use configured rule
                result[col_name] = rules_by_name[col_name].extract(filename)
            elif col_name == "File":
                # Special case: File column always returns the full filename
                result[col_name] = filename
            else:
                # Unknown column: empty value
                result[col_name] = ""

        return result

    def clear_rules(self) -> None:
        """Remove all extraction rules."""
        self._rules = ()


def load_column_rules_from_config(column_config: str) -> ColumnExtractor:
    """Load column rules from .profiles COLUMN_DEFINITIONS string.

    Format:
        name:pattern:group:priority:default,name2:pattern2:group2:priority2:default2

    Example:
        "File:.*:0:100::Version:_V(.+):1:10::Device:Device_([A-Z0-9]+):1:5::"

    Args:
        column_config: Comma-separated column definitions.

    Returns:
        Configured ColumnExtractor instance.
    """
    extractor = ColumnExtractor()

    if not column_config.strip():
        # Default rules if none specified
        extractor.add_rule("File", r".+", group=0, priority=100)
        extractor.add_rule("Version", r"_V(.+)", group=1, priority=10)
        return extractor

    for definition in column_config.split(","):
        definition = definition.strip()
        if not definition:
            continue

        parts = definition.split(":")
        if len(parts) < 2:
            continue

        name = parts[0].strip()
        pattern = parts[1].strip()

        group = int(parts[2]) if len(parts) > 2 and parts[2].strip() else 1
        priority = int(parts[3]) if len(parts) > 3 and parts[3].strip() else 0
        default = parts[4].strip() if len(parts) > 4 else ""

        extractor.add_rule(name, pattern, group=group, priority=priority, default=default)

    return extractor
