"""Configuration data models — pure dataclasses, zero side effects.

Single Responsibility: define the shape of configuration data only.
No I/O, no parsing, no UI dependencies. Safe to import from anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from profiles import __version__ as _pkg_version
from profiles.core.config.io.yaml_io import PRIMARY_CONFIG_NAME


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
        name: Column name (from section header).
        width: Column width in pixels.
        expression: Regex pattern for extraction.
        group: Regex group to extract (0=full match, 1+=captured group).
        priority: Extraction priority (higher = processed first).
        default: Default value if pattern doesn't match.
    """

    name: str = ""
    width: int = 150
    expression: str = ""
    group: int = 1
    priority: int = 0
    default: str = ""


@dataclass
class MachineConfiguration:
    """A single ``[CONFIGURATION_N]`` section from ``.profiles``.

    Attributes:
        pc_ip: IP address of the PC running MuTest.
        pc_hostname: Hostname of the PC.
        pc_name: Friendly name of the PC.
        directory: Directory containing test programs for this config.
        extensions: Per-config extension overrides (empty = use ``[LAUNCHER]`` defaults).
        filters: Per-config filter overrides (empty = use ``[LAUNCHER]`` defaults).
        row_colors: Per-config row-coloring rules as ``(pattern, color)`` tuples.
            Empty = no row coloring. The GUI applies the first rule whose
            pattern is a case-insensitive substring of the filename.
        search_exclude_files: Per-config file exclusion patterns (case-insensitive
            glob/wildcard). Appended to ``[LAUNCHER].search_exclude_files``.
    """

    pc_ip: str = ""
    pc_hostname: str = ""
    pc_name: str = ""
    directory: str = ""
    extensions: tuple[str, ...] = ()
    filters: tuple[str, ...] = ()
    row_colors: tuple[tuple[str, str], ...] = ()
    search_exclude_files: tuple[str, ...] = ()


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
            ``[CONFIGURATION_N].search_exclude_files`` are APPENDED.
        row_colors: Generic row-coloring rules as ``(pattern, color)`` tuples.
            These serve as a base; ``[CONFIGURATION_N]``.row_colors are APPENDED
            to this list, with per-config rules taking priority.
        verbose: Logging verbosity level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        scan_metrics: If True, log performance metrics after each scan operation.
        configurations: List of MachineConfiguration entries.
        config_path: Path to the .profiles file.
        skip_config_prompt: If True, skip config file creation prompt (for testing).
        launch_hooks: Per-extension launch hooks keyed by normalised extension
            (e.g. ``".mttx"``).
        launch_hook_failmode: Behavior when a hook fails (``"warn"``, ...).
        launch_hook_timeout: Hook timeout in seconds.
    """

    release: str = _pkg_version
    title: str = ""
    gui_auto_launch: bool = True
    close_after_execute: bool = False
    search_dir: str = ""
    recursive_search: bool = False
    theme: str = "light"
    language: str = "en"
    column_names: tuple[str, ...] = ()  # Built from [COLUMN_*] sections
    column_widths: tuple[int, ...] = ()  # Built from [COLUMN_*] sections
    columns: dict[str, ColumnConfiguration] = field(default_factory=dict)
    extensions: tuple[str, ...] = ("All", ".lnk")
    filters: tuple[str, ...] = ("", "ST_PRO", "ST_ENG")
    search_exclude_dirs: tuple[str, ...] = (".git",)
    search_exclude_files: tuple[str, ...] = ()
    row_colors: tuple[tuple[str, str], ...] = ()
    verbose: str = "INFO"
    scan_metrics: bool = False
    configurations: list[MachineConfiguration] = field(default_factory=list)
    config_path: Path = field(default_factory=lambda: Path.cwd() / PRIMARY_CONFIG_NAME)
    skip_config_prompt: bool = False
    launch_hooks: dict[str, tuple[HookSpec, ...]] = field(default_factory=dict)
    launch_hook_failmode: str = "warn"
    launch_hook_timeout: int = 30


__all__ = [
    "AppConfig",
    "ColumnConfiguration",
    "HookSpec",
    "MachineConfiguration",
]
