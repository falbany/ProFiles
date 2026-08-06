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

from pydantic import BaseModel, Field, field_validator

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

    width: int = 150
    expression: str = ""
    group: int = 1
    priority: int = 0
    default: str = ""


class HookEntry(BaseModel):
    """A single launch hook entry."""

    when: Literal["before", "after", "instead", "abort", "confirm"] = "before"
    command: str = ""
    requires_success: bool = True


class HooksConfig(BaseModel):
    """The ``hooks`` top-level section."""

    failmode: Literal["warn", "abort", "skip"] = "warn"
    timeout: int = 30
    # YAML ``entries:`` with only comments under it parses as None;
    # coerce to empty dict so the template works out-of-the-box.
    entries: dict[str, list[HookEntry]] = Field(default_factory=dict)

    @field_validator("entries", mode="before")
    @classmethod
    def _none_to_dict(cls, value: object) -> dict[str, list[HookEntry]]:
        return value or {}


class Defaults(BaseModel):
    """Global defaults inherited by every configuration."""

    title: str = ""
    gui_auto_launch: bool = True
    close_after_execute: bool = False
    theme: Literal["light", "dark"] = "light"
    language: Literal["en", "fr"] = "en"
    search_dir: str = ""
    recursive_search: bool = False
    extensions: list[str] = Field(default_factory=lambda: ["All", ".lnk"])
    filters: list[str] = Field(default_factory=lambda: ["", "ST_PRO", "ST_ENG"])
    row_colors: list[RowColor] = Field(default_factory=list)
    search_exclude_dirs: list[str] = Field(default_factory=lambda: [".git"])
    search_exclude_files: list[str] = Field(default_factory=list)
    verbose: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    scan_metrics: bool = False


class MachineConfig(BaseModel):
    """A named configuration block. The name is the dict key in ``configs``."""

    extends: str | None = None
    pc_hostname: str = ""
    pc_ip: str = ""
    pc_name: str = ""
    directory: str = ""
    extensions: list[str] | None = None
    filters: list[str] | None = None
    row_colors: list[RowColor] | None = None
    search_exclude_files: list[str] | None = None


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
    "RowColor",
]
