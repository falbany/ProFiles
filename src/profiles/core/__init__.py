"""ProFiles core domain logic — shared by GUI, CLI, and TUI.

Single point of egress for the core domain. The internal layout is
organised into SOLID-aligned sub-packages:

- :mod:`profiles.core.config`        — configuration subsystem (models, service, loader, reader, io)
- :mod:`profiles.core.environment`   — OS environment & process spawn (system, execution)
- :mod:`profiles.core.processing`    — file scanning, classification, column extraction
- :mod:`profiles.core.telemetry`     — logging & diagnostics

The names re-exported below are the public surface of ``profiles.core``.
"""

from __future__ import annotations

from profiles.core.actions import (
    ActionResult,
    ActionStatus,
    clear_file,
    launch_selected_file,
    open_config_file,
    open_log_file,
    write_starter_config,
)
from profiles.core.config import (
    STARTER_CONFIG_TEMPLATE,
    AppConfig,
    ColumnConfiguration,
    ConfigReader,
    HookSpec,
    MachineConfiguration,
    auto_select_directory,
    find_active_config,
    find_configuration_by_hostname,
    get_unique_directories,
    load_config,
    merge_config_overrides,
    propose_config_creation,
)
from profiles.core.environment import (
    HookOutcome,
    SystemInfo,
    apply_source_to_logger,
    collect_system_info,
    parse_hook_entries,
    run_hooks_for_file,
)
from profiles.core.processing import (
    ScannedFile,
    ScannedFileDynamic,
    directory_exists,
    ensure_trailing_separator,
    extract_version,
    get_file_info,
    is_simple_extension,
    scan_and_process,
)

__all__ = [
    # Models
    "AppConfig",
    "ColumnConfiguration",
    "MachineConfiguration",
    "HookSpec",
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
    # Launch hooks
    "HookOutcome",
    "parse_hook_entries",
    "run_hooks_for_file",
    # File service
    "directory_exists",
    "ensure_trailing_separator",
    "extract_version",
    "get_file_info",
    # Scanner
    "ScannedFile",
    "ScannedFileDynamic",
    "is_simple_extension",
    "scan_and_process",
    # Template
    "STARTER_CONFIG_TEMPLATE",
    # System
    "SystemInfo",
    "collect_system_info",
    "apply_source_to_logger",
    # Actions
    "ActionResult",
    "ActionStatus",
    "clear_file",
    "launch_selected_file",
    "open_config_file",
    "open_log_file",
    "write_starter_config",
]
