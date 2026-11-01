"""Configuration data models — pure dataclasses, zero side effects.

Single Responsibility: define the shape of configuration data only.
No I/O, no parsing, no UI dependencies. Safe to import from anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from profiles import __version__ as _pkg_version
from profiles.core.config.conditions import evaluate_hook_condition
from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME
from profiles.core.config.schema import MatchCriteriaSchema
from profiles.utils.file_utils import DEFAULT_MAX_SEARCH_DEPTH

WorkflowOutputMode = Literal["hide", "show", "fail_only"]


@dataclass(frozen=True)
class WorkflowStep:
    """A single step in a launch workflow.

    Attributes:
        action: The type of action — one of ``"notify"``, ``"run"``,
            ``"run_after"``, ``"replace"``, ``"check"``.
        command: Shell command template (token-substituted at runtime).
            Required for command-type actions (``run``, ``run_after``,
            ``replace``, ``check``); ignored on ``notify``.
        message: Markdown-formatted message shown to the user. Required
            for ``notify``; optional on command-type actions (shown as a
            notice, or above the ``ask`` question when combined).
        ask: Optional confirmation message. If present, user must confirm
            before the action executes.
        wait: Whether to block execution until this step completes.
            Default: True.
        on_failure: Behavior when step fails — one of ``"stop"``, ``"warn"``,
            ``"continue"``. Default: "stop".
        timeout: Optional per-step timeout in seconds. Overrides the
            global ``failmode`` timeout when set. Default: None (uses global).
        if_: Optional conditional. If present, the step is skipped when the
            condition evaluates to false. Grammar: ``env:VAR`` (set),
            ``env:VAR=value`` (equals), ``env:VAR!=value`` (set and differs),
            ``file:PATH`` (path exists), and ``!COND`` (negation of any
            form). Tokens are substituted before evaluation. Default: None.
        phase: Execution phase — ``"pre"`` (default) runs before the OS
            launch decision; ``"post"`` runs only after a successful OS
            launch. ``replace`` steps cannot be ``post`` (a replace step
            *is* the launch).
        output: Command output display mode for blocking command steps —
            one of ``"hide"`` (capture and discard), ``"show"`` (show the
            captured output as a non-blocking notice), or ``"fail_only"``
            (show it only when the step fails). Ignored on non-blocking
            steps (``run_after``, ``run`` with ``wait=False``). Default:
            "hide".

    Raises:
        ValueError: If a ``notify`` step has no ``message``, or a
            command-type action (``run``/``run_after``/``replace``/``check``)
            has no ``command``.
    """

    action: Literal["notify", "run", "run_after", "replace", "check"]
    command: str = ""
    message: str = ""
    ask: str | None = None
    wait: bool = True
    on_failure: Literal["stop", "warn", "continue"] = "stop"
    timeout: int | None = None
    if_: str | None = None
    output: Literal["hide", "show", "fail_only"] = "hide"
    phase: Literal["pre", "post"] = "pre"

    def __post_init__(self) -> None:
        """Validate per-action required fields (mirrors config-load validation)."""
        if self.action == "notify":
            if not self.message:
                raise ValueError("A 'notify' workflow step requires a 'message'.")
        elif not self.command:
            raise ValueError(f"A '{self.action}' workflow step requires a 'command'.")
        if self.action == "replace" and self.phase == "post":
            raise ValueError(
                "A 'replace' step cannot use 'phase: post': replace *is* the launch, "
                "so it can only run before the OS launch."
            )

    def evaluate_condition(self) -> bool:
        """Evaluate the ``if_`` conditional. Always True when ``if_`` is unset.

        Delegates to :func:`profiles.core.config.conditions.evaluate_hook_condition`
        (see the grammar there). Note: this raw evaluation does not perform
        token substitution — the workflow engine substitutes tokens into the
        condition string before evaluation.
        """
        return evaluate_hook_condition(self.if_)


@dataclass(frozen=True)
class HookSpec:
    """A launch hook: a command template run around file launches.

    Attributes:
        when: When the hook runs — one of ``"before"``, ``"after"``,
            ``"instead"``, ``"abort"``, ``"confirm"``. Unknown values
            coerce to ``"before"``.
        template: Command template string (empty = no-op).
        requires_success: If True, sequential hooks before this one must
            succeed (return code 0), otherwise the pipeline aborts.
            Default: True.
    """

    when: str = "before"
    template: str = ""
    requires_success: bool = True

    def __post_init__(self) -> None:
        """Coerce ``when`` to ``"before"`` when it is not a known value."""
        if self.when not in {"before", "after", "instead", "abort", "confirm"}:
            object.__setattr__(self, "when", "before")


@dataclass
class ColumnConfiguration:
    """A single ``[COLUMN_<Name>]`` section from ``.profiles``.

    Attributes:
        name: User-friendly header display name (optional; falls back to the
            config key in the GUI).
        width: Column width in pixels (used when stretch=False).
        stretch: Whether the Treeview column should stretch to fill space.
        match: Built-in keyword (e.g. "version", "date") or raw regex pattern.
        transform: Optional replacement pattern with group backreferences
            (e.g. "\\1 (Build \\2)"). If omitted, group 1 is returned when it
            exists, else the whole match (group 0).
        priority: Extraction priority (higher = processed first).
        default: Default value if pattern doesn't match.
    """

    name: str = ""
    width: int = 150
    stretch: bool = False
    match: str = ".*"
    transform: str | None = None
    priority: int = 0
    default: str = ""


@dataclass(frozen=True)
class MatchCriteria:
    """Auto-selection match criteria for a machine configuration.

    The logic is OR-based: any pattern match in any field is sufficient.
    - ``hostname``: Glob patterns for the machine's hostname.
    - ``ip``: Glob patterns for the machine's IP address.
    - ``path``: Glob patterns for paths that must exist on the filesystem.
    """

    hostname: tuple[str, ...] = ()
    ip: tuple[str, ...] = ()
    path: tuple[str, ...] = ()


@dataclass
class MachineConfiguration:
    """A single machine configuration entry from ``configs`` in ``.profiles``.

    Attributes:
        match: Auto-selection criteria based on hostname, IP, or path existence.
        scan: Directories to scan for test programs.
        extensions: Per-config extension overrides (empty = use ``defaults``).
        filters: Per-config filter overrides (empty = use ``defaults``).
        row_colors: Per-config row-coloring rules as ``(pattern, color)`` tuples.
            Empty = no row coloring. The GUI applies the first rule whose
            pattern is a case-insensitive substring of the filename.
        search_exclude_files: Per-config file exclusion patterns (case-insensitive
            glob/wildcard). Appended to ``defaults.search_exclude_files``.
        max_search_depth: Maximum depth for recursive directory scanning.
        recursive_search: Whether to scan subdirectories recursively.
        search_exclude_dirs: Per-config directory exclusion patterns
            (case-insensitive glob/wildcard). Order-merged with the global
            ``AppConfig.search_exclude_dirs`` (first-seen order, duplicates
            removed).
    """

    match: MatchCriteria = field(default_factory=MatchCriteria)
    scan: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    filters: tuple[str, ...] = ()
    row_colors: tuple[tuple[str, str], ...] = ()
    search_exclude_files: tuple[str, ...] = ()
    max_search_depth: int | None = None
    recursive_search: bool | None = None
    search_exclude_dirs: tuple[str, ...] = ()
    name: str | None = None

    def __post_init__(self) -> None:
        """Coerce list inputs to tuples for consistent immutability."""
        if isinstance(self.match, MatchCriteriaSchema):
            self.match = MatchCriteria(
                hostname=tuple(self.match.hostname),
                ip=tuple(self.match.ip),
                path=tuple(self.match.path),
            )
        for field_name in (
            "scan",
            "extensions",
            "filters",
            "row_colors",
            "search_exclude_files",
            "search_exclude_dirs",
        ):
            value = getattr(self, field_name)
            if isinstance(value, list):
                setattr(self, field_name, tuple(value))


@dataclass
class AppConfig:
    """Complete application configuration derived from ``.profiles``.

    Attributes:
        release: Version string from pyproject.toml (via ``profiles.__version__``).
        title: Optional custom title appended to the window title.
        gui_auto_launch: Whether the GUI auto-launches on start.
        close_after_execute: Whether to close after launching a program.
        search_dir: Default search directory for test programs.
        recursive_search: Whether to search subdirectories recursively.
        column_names: Column header names for file listings.
        column_widths: Column widths corresponding to column_names.
        extensions: Available file extension filter options.
        filters: Available keyword filter options.
        search_exclude_files: Filename glob patterns (case-insensitive)
            for files to skip during scanning. Per-config
            ``search_exclude_files`` are APPENDED.
        search_exclude_dirs: Directory-name glob patterns (case-insensitive)
            for directories to skip during scanning. Order-merges with the
            global list: global → caller → per-config (first-seen order,
            duplicates removed). Default excludes ``.git``; since the merge,
            ``.git`` is now ALWAYS excluded in pipeline scans unless removed
            from the global list.
            ``search_exclude_dirs`` are APPENDED to the global list
            (first-seen order, duplicates removed).
        row_colors: Generic row-coloring rules as ``(pattern, color)`` tuples.
            These serve as a base; per-config ``row_colors`` are APPENDED
            to this list, with per-config rules taking priority.
        verbose: Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        scan_metrics: If True, log performance metrics after each scan operation.
        max_search_depth: Global maximum depth for recursive search.
        configurations: List of MachineConfiguration entries.
        config_path: Path to the .profiles file.
        skip_config_prompt: If True, skip config file creation prompt (for testing).
        launch_hooks: Per-extension launch workflow steps keyed by
            normalised extension (e.g. ``".mttx"``). Each step is a
            :class:`WorkflowStep` (action, command/message, optional ask
            guard).
        launch_hook_failmode: Behavior when a hook fails (``"warn"``, ...).
        launch_hook_timeout: Hook timeout in seconds.
    """

    release: str = _pkg_version
    title: str = ""
    gui_auto_launch: bool = True
    close_after_execute: bool = False
    search_dir: str = ""
    recursive_search: bool = False
    theme: str = "auto"
    language: str = "en"
    column_names: tuple[str, ...] = ()  # Built from [COLUMN_*] sections
    column_widths: tuple[int, ...] = ()  # Built from [COLUMN_*] sections
    column_stretches: tuple[bool, ...] = ()  # Built from [COLUMN_*] sections
    column_headers: tuple[str, ...] = ()  # Display names from ColumnConfiguration.name
    columns: dict[str, ColumnConfiguration] = field(default_factory=dict)
    extensions: tuple[str, ...] = ("All", ".lnk")
    filters: tuple[str, ...] = ("", "PROD", "DEV")
    search_exclude_dirs: tuple[str, ...] = (".git",)
    search_exclude_files: tuple[str, ...] = ()
    row_colors: tuple[tuple[str, str], ...] = ()
    verbose: str = "INFO"
    scan_metrics: bool = False
    max_search_depth: int = DEFAULT_MAX_SEARCH_DEPTH
    configurations: list[MachineConfiguration] = field(default_factory=list)
    config_path: Path = field(default_factory=lambda: Path.cwd() / PRIMARY_CONFIG_NAME)
    skip_config_prompt: bool = False
    launch_hooks: dict[str, tuple[WorkflowStep, ...]] = field(default_factory=dict)
    launch_hook_failmode: str = "warn"
    launch_hook_timeout: int = 30


__all__ = [
    "AppConfig",
    "ColumnConfiguration",
    "DEFAULT_MAX_SEARCH_DEPTH",
    "HookSpec",
    "MachineConfiguration",
]
