"""Pydantic YAML schema models for ProFiles configuration files.

Single Responsibility: define the shape of the YAML configuration file and
validate its types. No I/O, no inheritance resolution, no UI dependencies.

The resolved dataclasses in :mod:`profiles.core.config.models` are the
runtime interface consumed by the rest of the app; these schema models are
the on-disk YAML shape only.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ConfigError(Exception):
    """A configuration error with a precise YAML path.

    Attributes:
        path: Dotted YAML path (e.g. ``configs.production.extends``).
        message: Human-readable description.
    """

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path
        self.message = message


class RowColor(BaseModel):
    """A row-coloring rule ``{pattern, color}``."""

    pattern: str
    color: str

    @field_validator("color")
    @classmethod
    def _check_color(cls, value: str) -> str:
        if not _COLOR_RE.match(value):
            raise ValueError(f"invalid color '{value}', expected #RRGGBB")
        return value


class ColumnMapping(BaseModel):
    """A dynamic column definition."""

    name: str | None = None  # User-friendly header display name (falls back to key)
    width: int = 150
    stretch: bool = False
    match: str = ".*"  # Built-in keyword or raw regex
    transform: str | None = None  # Optional replacement with group backreferences
    priority: int = 0
    default: str = ""


class HookEntry(BaseModel):
    """A single launch hook entry (legacy phase-based)."""

    when: Literal["before", "after", "instead", "abort", "confirm"] = "before"
    command: str = ""
    requires_success: bool = True


class WorkflowStepSchema(BaseModel):
    """A single workflow step (step-based model).

    ``command`` holds the shell command template executed by command-type
    actions (``run`` / ``run_after`` / ``replace`` / ``check``);
    ``message`` holds the Markdown-formatted text shown to the user
    (required for ``notify``, optional elsewhere). ``output`` controls
    whether a blocking command step's captured output is displayed
    (``hide`` / ``show`` / ``fail_only``). Both keys are accepted on every
    action. Unknown keys — including the removed ``content`` — are
    rejected with a schema error.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action: Literal["notify", "run", "run_after", "replace", "check"]
    command: str = ""
    message: str = ""
    ask: str | None = None
    wait: bool = True
    on_failure: Literal["stop", "warn", "continue"] = "stop"
    timeout: int | None = None
    if_: str | None = Field(default=None, alias="if")
    output: Literal["hide", "show", "fail_only"] = "hide"


class HooksConfig(BaseModel):
    """The ``hooks`` top-level section."""

    failmode: Literal["warn", "abort", "skip"] = "warn"
    timeout: int = 30
    # YAML ``entries:`` with only comments under it parses as None;
    # coerce to empty dict so the template works out-of-the-box.
    entries: dict[str, list[WorkflowStepSchema]] = Field(default_factory=dict)

    @field_validator("entries", mode="before")
    @classmethod
    def _none_to_dict(cls, value: object) -> dict[str, list[WorkflowStepSchema]]:
        return value or {}

    @model_validator(mode="after")
    def _validate_step_required_fields(self) -> HooksConfig:
        """Enforce per-action required keys, reporting the entry pattern."""
        # pylint: disable-next=no-member  (pylint infers FieldInfo, not the dict)
        for pattern, steps in self.entries.items():
            for pos, step in enumerate(steps):
                if step.action == "notify" and not step.message:
                    raise ValueError(
                        f"hooks entry '{pattern}' step {pos + 1}: "
                        "a 'notify' step requires 'message'"
                    )
                if step.action != "notify" and not step.command:
                    raise ValueError(
                        f"hooks entry '{pattern}' step {pos + 1}: "
                        f"a '{step.action}' step requires 'command'"
                    )
        return self


class Defaults(BaseModel):
    """Global defaults inherited by every configuration."""

    title: str = ""
    gui_auto_launch: bool = True
    close_after_execute: bool = False
    theme: Literal["light", "dark", "auto"] = "auto"
    language: Literal["en", "fr"] = "en"
    search_dir: str = ""
    recursive_search: bool = False
    extensions: list[str] = Field(default_factory=lambda: ["All", ".lnk"])
    filters: list[str] = Field(default_factory=lambda: ["", "PROD", "DEV"])
    row_colors: list[RowColor] = Field(default_factory=list)
    search_exclude_dirs: list[str] = Field(default_factory=lambda: [".git"])
    search_exclude_files: list[str] = Field(default_factory=list)
    verbose: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    scan_metrics: bool = False
    max_search_depth: int = Field(default=10, ge=0)


class MatchCriteriaSchema(BaseModel):
    """Matcher criteria for machine configuration auto-selection."""

    hostname: list[str] = Field(default_factory=list)
    ip: list[str] = Field(default_factory=list)
    path: list[str] = Field(default_factory=list)

    @field_validator("hostname", "ip", "path", mode="before")
    @classmethod
    def _coerce_list(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value]
        return []


class MachineConfig(BaseModel):
    """A named configuration block in YAML configs dict.

    The ``name`` field defaults to ``None``; the reader fills it in from
    the dict key (or the YAML ``name:`` key if present) when building
    :class:`MachineConfiguration`.
    """

    name: str | None = None
    extends: str | None = None
    match: MatchCriteriaSchema = Field(default_factory=MatchCriteriaSchema)
    scan: list[str] = Field(default_factory=list)
    extensions: list[str] | None = None
    filters: list[str] | None = None
    row_colors: list[RowColor] | None = None
    search_exclude_files: list[str] | None = None
    max_search_depth: int | None = Field(default=None, ge=0)
    recursive_search: bool | None = None
    search_exclude_dirs: list[str] | None = None

    @field_validator("scan", mode="before")
    @classmethod
    def _coerce_scan_list(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value]
        return []


class AppConfigYaml(BaseModel):
    """Root of the ``.profiles.yaml`` file."""

    version: int = 1
    defaults: Defaults = Field(default_factory=Defaults)
    columns: dict[str, ColumnMapping] = Field(default_factory=dict)
    hooks: HooksConfig = Field(default_factory=HooksConfig)
    configs: dict[str, MachineConfig] = Field(default_factory=dict)


__all__ = [
    "AppConfigYaml",
    "ColumnMapping",
    "ConfigError",
    "Defaults",
    "HookEntry",
    "HooksConfig",
    "MachineConfig",
    "MatchCriteriaSchema",
    "RowColor",
]
