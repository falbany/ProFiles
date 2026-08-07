"""``ConfigReader`` — parses a ``.profiles`` file into an :class:`AppConfig`.

Composes the YAML I/O, validator, inheritance resolver, and schema models
to produce the resolved :class:`AppConfig` consumed by the rest of the app.
"""

from __future__ import annotations

import logging
from pathlib import Path

from profiles.core.config.inheritance import resolve_configs
from profiles.core.config.io.yaml_io import find_config_file as _find_config_file
from profiles.core.config.io.yaml_io import read_yaml
from profiles.core.config.models import (
    AppConfig,
    ColumnConfiguration,
    MachineConfiguration,
    WorkflowStep,
)
from profiles.core.config.schema import AppConfigYaml
from profiles.core.config.service import (
    find_configuration_by_hostname as _find_configuration_by_hostname,
)
from profiles.core.config.validator import validate

_DEFAULT_FILE_COLUMN_WIDTH = 600
_DEFAULT_COLUMN_WIDTH = 150


class ConfigReader:
    """Reads and parses the ``.profiles`` configuration file.

    Usage::

        reader = ConfigReader("conf/.profiles")
        config = reader.load()
    """

    def __init__(self, config_path: Path | str) -> None:
        self._config_path = Path(config_path)

    @property
    def config_path(self) -> Path:
        """Path to the configuration file."""
        return self._config_path

    @staticmethod
    def find_config_file(start_path: Path | None = None, max_depth: int = 5) -> Path | None:
        """Locate ``.profiles`` (or ``.profiles.yaml`` fallback) in the CWD subtree."""
        return _find_config_file(start_path, max_depth)

    def find_configuration_by_hostname(
        self,
        hostname: str,
        config: AppConfig | None = None,
    ) -> MachineConfiguration | None:
        """Find the machine configuration matching *hostname*."""
        if config is None:
            config = self.load()
        return _find_configuration_by_hostname(config, hostname)

    def load(self) -> AppConfig:
        """Load and parse the configuration file.

        Returns an :class:`AppConfig` with default values when the file
        does not exist or contains errors. Logs warnings for any issues.
        """
        logger = logging.getLogger(__name__)
        config = AppConfig(config_path=self._config_path)

        # No config file exists — use defaults
        if not self._config_path.exists():
            logger.debug(
                f"Configuration file not found: {self._config_path}. "
                f"Using defaults from current working directory: {Path.cwd()}"
            )
            self._build_column_configs(config)
            return config

        try:
            raw = read_yaml(self._config_path)
        except FileNotFoundError:
            logger.warning(
                f"Configuration file not found: {self._config_path}. "
                f"Falling back to defaults from {Path.cwd()}"
            )
            self._build_column_configs(config)
            return config
        except Exception as e:
            # Catch ALL YAML parsing errors (escape chars, syntax errors, etc.)
            logger.error(
                f"Failed to parse configuration file: {self._config_path}\n"
                f"Error: {type(e).__name__}: {e}\n"
                f"Falling back to defaults from {Path.cwd()}"
            )
            self._build_column_configs(config)
            return config

        try:
            validate(raw)
            schema = AppConfigYaml.model_validate(raw)
            self._apply_defaults(config, schema)
            self._apply_columns(config, schema)
            self._apply_hooks(config, schema)
            config.configurations = self._build_configurations(schema)
            logger.info(f"Configuration loaded successfully: {self._config_path}")
        except Exception as e:
            # Catch validation/schema errors
            logger.error(
                f"Configuration validation failed: {self._config_path}\n"
                f"Error: {type(e).__name__}: {e}\n"
                f"Falling back to defaults from {Path.cwd()}"
            )
            self._build_column_configs(config)
            return config

        return config

    def _apply_defaults(self, config: AppConfig, schema: AppConfigYaml) -> None:
        """Populate *config* from ``schema.defaults``."""
        d = schema.defaults
        config.title = d.title
        config.gui_auto_launch = d.gui_auto_launch
        config.close_after_execute = d.close_after_execute
        config.theme = d.theme
        config.language = d.language
        config.search_dir = d.search_dir
        config.recursive_search = d.recursive_search
        config.extensions = tuple(d.extensions)
        config.filters = tuple(d.filters)
        config.search_exclude_dirs = tuple(d.search_exclude_dirs)
        config.search_exclude_files = tuple(d.search_exclude_files)
        config.row_colors = tuple((rc.pattern, rc.color) for rc in d.row_colors)
        config.verbose = d.verbose
        config.scan_metrics = d.scan_metrics

    def _apply_columns(self, config: AppConfig, schema: AppConfigYaml) -> None:
        """Populate *config* from ``schema.columns``."""
        for name, col in schema.columns.items():
            config.columns[name] = ColumnConfiguration(
                name=col.name or name,
                width=col.width,
                stretch=col.stretch,
                match=col.match,
                transform=col.transform,
                priority=col.priority,
                default=col.default,
            )
        self._build_column_configs(config)

    def _apply_hooks(self, config: AppConfig, schema: AppConfigYaml) -> None:
        """Populate *config* from ``schema.hooks``."""
        config.launch_hook_failmode = schema.hooks.failmode
        config.launch_hook_timeout = schema.hooks.timeout
        for pattern, entries in schema.hooks.entries.items():
            config.launch_hooks[pattern] = tuple(
                WorkflowStep(
                    action=entry.action,
                    content=entry.content,
                    ask=entry.ask,
                    wait=entry.wait,
                    on_failure=entry.on_failure,
                )
                for entry in entries
            )

    def _build_configurations(self, schema: AppConfigYaml) -> list[MachineConfiguration]:
        """Resolve inheritance and build the resolved machine list."""
        resolved = resolve_configs(schema)
        return [
            MachineConfiguration(
                pc_ip=m.pc_ip,
                pc_hostname=m.pc_hostname,
                pc_name=m.pc_name,
                directory=m.directory,
                extensions=tuple(m.extensions),
                filters=tuple(m.filters),
                row_colors=tuple((rc.pattern, rc.color) for rc in m.row_colors),
                search_exclude_files=tuple(m.search_exclude_files),
            )
            for m in resolved.values()
        ]

    @staticmethod
    def _build_column_configs(config: AppConfig) -> None:
        """Materialise ``column_names`` / ``column_widths`` from ``config.columns``.

        Also builds ``column_stretches`` (Treeview stretch behavior) and
        ``column_headers`` (friendly display names from ``name``, falling back
        to the column key).
        """
        if config.columns:
            has_file_column = "File" in config.columns
            column_list = ["File"]
            if has_file_column:
                column_list.extend(name for name in config.columns if name != "File")
            else:
                column_list.extend(config.columns.keys())

            config.column_names = tuple(column_list)
            config.column_widths = tuple(
                config.columns[name].width
                if name in config.columns
                else (_DEFAULT_FILE_COLUMN_WIDTH if name == "File" else _DEFAULT_COLUMN_WIDTH)
                for name in column_list
            )
            config.column_stretches = tuple(
                config.columns[name].stretch if name in config.columns else False
                for name in column_list
            )
            config.column_headers = tuple(
                config.columns[name].name or name if name in config.columns else name
                for name in column_list
            )
        else:
            config.column_names = ("File",)
            config.column_widths = (_DEFAULT_FILE_COLUMN_WIDTH,)
            config.column_stretches = (False,)
            config.column_headers = ("File",)


__all__ = ["ConfigReader"]
