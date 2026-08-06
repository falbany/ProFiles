# YAML Configuration Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate ProFiles configuration from INI (`.profiles`, `configparser`) to YAML (`.profiles.yaml`) with Pydantic models, inheritance, validation, and round-trip writing.

**Architecture:** Replace the INI config subsystem (`reader.py`, `io/ini_primitives.py`, `io/writer.py`) with a YAML pipeline: `yaml_io.py` (ruamel round-trip) → `validator.py` (semantic errors with precise paths) → `inheritance.py` (defaults + `extends` resolution) → Pydantic `schema.py` models → resolved `AppConfig` dataclass (unchanged interface for consumers). The resolved `AppConfig`/`MachineConfiguration`/`ColumnConfiguration`/`HookSpec` dataclasses are preserved so `scanner.py`, `execution.py`, `service.py`, and the GUI keep working.

**Tech Stack:** Python 3.11+, `ruamel.yaml>=0.18.0` (round-trip), `pydantic>=2.0.0` (models/validation), pytest, ruff, pylint.

## Global Constraints

- **File name:** `.profiles.yaml` (replaces `.profiles` everywhere).
- **No back-compat, no converter:** INI files are not read; `ini_primitives.py` and `writer.py` are deleted.
- **Booleans:** YAML `true`/`false` only (French `Vrai`/`Faux` removed).
- **Resolved interface preserved:** `AppConfig`, `MachineConfiguration`, `ColumnConfiguration`, `HookSpec` dataclasses keep their current field names so `scanner.py`, `execution.py`, `service.py`, and `gui/main_window.py` compile unchanged.
- **Dependencies:** add `ruamel.yaml>=0.18.0` and `pydantic>=2.0.0` to `[project].dependencies`.
- **Python floor:** `>=3.11`.
- **Quality gates:** `ruff format .`, `ruff check .`, `pylint src/profiles --fail-under=8.0`, `pytest --cov=src/profiles --cov-fail-under=85`.
- **Schema:** `version: 1`; top-level keys `defaults`, `columns`, `hooks`, `configs`. Config name = dict key in `configs:`; `extends` references another key in the same dict.

---

### Task 1: Add dependencies + create Pydantic schema models

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Create: `src/profiles/core/config/schema.py`
- Modify: `src/profiles/core/config/models.py` (default `config_path` → `.profiles.yaml`)
- Test: `tests/core/config/test_schema.py`

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces: `ConfigError(path, message)` exception; Pydantic models `RowColor`, `ColumnConfig`, `HookEntry`, `HooksConfig`, `Defaults`, `MachineConfig`, `AppConfigYaml`. Later tasks import these.

- [ ] **Step 1: Add dependencies to `pyproject.toml`**

```toml
dependencies = [
    "sv-ttk>=2.5.0",
    "darkdetect>=0.8.0",
    "ruamel.yaml>=0.18.0",
    "pydantic>=2.0.0",
]
```

- [ ] **Step 2: Write the failing test**

Create `tests/core/config/test_schema.py`:

```python
"""Tests for profiles.core.config.schema — Pydantic YAML schema models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from profiles.core.config.schema import (
    AppConfigYaml,
    ConfigError,
    Defaults,
    HookEntry,
    MachineConfig,
    RowColor,
)


class TestConfigError:
    def test_fields(self) -> None:
        err = ConfigError("configs.production.extends", "unknown config 'ghost'")
        assert err.path == "configs.production.extends"
        assert "unknown config 'ghost'" in str(err)


class TestRowColor:
    def test_valid_color(self) -> None:
        rc = RowColor(pattern="TMP", color="#BAC015")
        assert rc.color == "#BAC015"

    def test_invalid_color_raises(self) -> None:
        with pytest.raises(ValidationError):
            RowColor(pattern="TMP", color="BAC015")  # missing '#'
        with pytest.raises(ValidationError):
            RowColor(pattern="TMP", color="#12345")  # wrong length


class TestHookEntry:
    def test_default_when_is_before(self) -> None:
        assert HookEntry(command="x").when == "before"

    def test_invalid_when_raises(self) -> None:
        with pytest.raises(ValidationError):
            HookEntry(when="sideways", command="x")


class TestDefaults:
    def test_defaults(self) -> None:
        d = Defaults()
        assert d.extensions == ["All", ".lnk"]
        assert d.filters == ["", "ST_PRO", "ST_ENG"]
        assert d.theme == "light"
        assert d.verbose == "INFO"


class TestAppConfigYaml:
    def test_empty(self) -> None:
        cfg = AppConfigYaml()
        assert cfg.version == 1
        assert cfg.configs == {}

    def test_config_name_is_dict_key(self) -> None:
        cfg = AppConfigYaml(configs={"prod": MachineConfig(pc_hostname="PC1")})
        assert "prod" in cfg.configs
        assert cfg.configs["prod"].pc_hostname == "PC1"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/core/config/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'profiles.core.config.schema'`

- [ ] **Step 4: Create `schema.py`**

```python
"""Pydantic YAML schema models for ``.profiles.yaml``.

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
    entries: dict[str, list[HookEntry]] = Field(default_factory=dict)


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
```

- [ ] **Step 5: Update `models.py` default `config_path`**

In `src/profiles/core/config/models.py`, change the `AppConfig.config_path` default:

```python
    config_path: Path = field(default_factory=lambda: Path.cwd() / ".profiles.yaml")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/core/config/test_schema.py -v`
Expected: PASS (all tests)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/profiles/core/config/schema.py src/profiles/core/config/models.py tests/core/config/test_schema.py
git commit -m "feat(config): add Pydantic YAML schema models"
```

---

### Task 2: Create `yaml_io.py` (round-trip read/write)

**Files:**
- Create: `src/profiles/core/config/io/yaml_io.py`
- Test: `tests/core/config/io/test_yaml_io.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `read_yaml(path) -> dict`, `write_value(path, dotted_key, value) -> None`, `find_config_file(start_path, max_depth) -> Path | None`. Task 5 (`reader.py`) and Task 9 (GUI) consume these.

- [ ] **Step 1: Write the failing test**

Create `tests/core/config/io/test_yaml_io.py`:

```python
"""Tests for profiles.core.config.io.yaml_io — round-trip YAML read/write."""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.core.config.io.yaml_io import find_config_file, read_yaml, write_value


class TestReadYaml:
    def test_reads_mapping(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles.yaml"
        conf.write_text("version: 1\ndefaults:\n  theme: dark\n", encoding="utf-8")
        data = read_yaml(conf)
        assert data["version"] == 1
        assert data["defaults"]["theme"] == "dark"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_yaml(tmp_path / "nope.yaml")

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles.yaml"
        conf.write_text("defaults: [unclosed\n", encoding="utf-8")
        with pytest.raises(Exception):
            read_yaml(conf)


class TestWriteValue:
    def test_updates_nested_key_preserves_comment(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles.yaml"
        conf.write_text(
            "# header comment\ndefaults:\n  theme: light  # the theme\n",
            encoding="utf-8",
        )
        write_value(conf, "defaults.theme", "dark")
        content = conf.read_text(encoding="utf-8")
        assert "theme: dark" in content
        assert "# header comment" in content
        assert "# the theme" in content

    def test_updates_boolean(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles.yaml"
        conf.write_text("defaults:\n  recursive_search: false\n", encoding="utf-8")
        write_value(conf, "defaults.recursive_search", True)
        content = conf.read_text(encoding="utf-8")
        assert "recursive_search: true" in content

    def test_missing_file_creates(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles.yaml"
        write_value(conf, "defaults.theme", "dark")
        content = conf.read_text(encoding="utf-8")
        assert "theme: dark" in content


class TestFindConfigFile:
    def test_found_in_start_dir(self, tmp_path: Path) -> None:
        conf = tmp_path / ".profiles.yaml"
        conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == conf

    def test_found_in_subdir(self, tmp_path: Path) -> None:
        conf = tmp_path / "deep" / "nested" / ".profiles.yaml"
        conf.parent.mkdir(parents=True)
        conf.write_text("version: 1\n", encoding="utf-8")
        assert find_config_file(start_path=tmp_path) == conf

    def test_not_found(self, tmp_path: Path) -> None:
        assert find_config_file(start_path=tmp_path) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/config/io/test_yaml_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'profiles.core.config.io.yaml_io'`

- [ ] **Step 3: Create `src/profiles/core/config/io/yaml_io.py`**

```python
"""Round-trip YAML I/O for ``.profiles.yaml``.

Single Responsibility: read and write the YAML file while preserving
comments, ordering, and formatting (via ``ruamel.yaml``). No domain
knowledge, no models.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True


def read_yaml(path: Path | str) -> dict:
    """Read a YAML file into a plain dict (or raise).

    Args:
        path: Path to the ``.profiles.yaml`` file.

    Returns:
        The parsed YAML mapping.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ruamel.yaml.YAMLError: If the file is not valid YAML.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    with p.open("r", encoding="utf-8") as fh:
        return _yaml.load(fh) or {}


def write_value(path: Path | str, dotted_key: str, value: object) -> None:
    """Set a nested key in the YAML file, preserving comments/formatting.

    Args:
        path: Path to the ``.profiles.yaml`` file.
        dotted_key: Dotted path, e.g. ``"defaults.theme"``.
        value: Value to write (bool, str, int, list, ...).
    """
    p = Path(path)
    if p.exists():
        with p.open("r", encoding="utf-8") as fh:
            data = _yaml.load(fh) or {}
    else:
        data = {}

    parts = dotted_key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value

    with p.open("w", encoding="utf-8") as fh:
        _yaml.dump(data, fh)


def find_config_file(
    start_path: Path | None = None,
    max_depth: int = 5,
) -> Path | None:
    """Search the CWD subtree for a ``.profiles.yaml`` file.

    Args:
        start_path: Starting directory (default: current working directory).
        max_depth: Maximum depth of subdirectories to search (default: 5).

    Returns:
        The path to the first ``.profiles.yaml`` found, or ``None``.
    """
    if start_path is None:
        start_path = Path.cwd()

    start = start_path.resolve()
    if not start.is_dir():
        return None

    for candidate in start.rglob(".profiles.yaml"):
        try:
            relative = candidate.relative_to(start)
            depth = len(relative.parts) - 1
            if depth <= max_depth and candidate.is_file():
                return candidate
        except ValueError:
            continue
    return None


__all__ = ["find_config_file", "read_yaml", "write_value"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/config/io/test_yaml_io.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/io/yaml_io.py tests/core/config/io/test_yaml_io.py
git commit -m "feat(config): add round-trip YAML I/O"
```

---

### Task 3: Create `validator.py` (semantic validation)

**Files:**
- Create: `src/profiles/core/config/validator.py`
- Test: `tests/core/config/test_validator.py`

**Interfaces:**
- Consumes: `ConfigError` from `schema.py`.
- Produces: `validate(raw: dict) -> None` — raises `ConfigError` on semantic problems (unknown `extends`, inheritance cycles, unknown top-level keys). Task 5 (`reader.py`) calls it.

- [ ] **Step 1: Write the failing test**

Create `tests/core/config/test_validator.py`:

```python
"""Tests for profiles.core.config.validator — semantic validation."""

from __future__ import annotations

import pytest

from profiles.core.config.schema import ConfigError
from profiles.core.config.validator import validate


class TestValidate:
    def test_valid_passes(self) -> None:
        raw = {
            "version": 1,
            "configs": {
                "base": {"directory": "/x"},
                "prod": {"extends": "base"},
            },
        }
        validate(raw)  # should not raise

    def test_unknown_extends(self) -> None:
        raw = {"configs": {"prod": {"extends": "ghost"}}}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.prod.extends"
        assert "ghost" in exc.value.message

    def test_cycle(self) -> None:
        raw = {
            "configs": {
                "a": {"extends": "b"},
                "b": {"extends": "a"},
            }
        }
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "configs.b.extends"
        assert "cycle" in exc.value.message.lower()

    def test_unknown_top_level_key(self) -> None:
        raw = {"bogus": 1}
        with pytest.raises(ConfigError) as exc:
            validate(raw)
        assert exc.value.path == "bogus"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/config/test_validator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'profiles.core.config.validator'`

- [ ] **Step 3: Create `src/profiles/core/config/validator.py`**

```python
"""Semantic validation of the raw ``.profiles.yaml`` tree.

Single Responsibility: check the raw YAML dict for problems that Pydantic
type validation cannot catch — unknown top-level keys, ``extends``
references to missing configs, and inheritance cycles. Raises
:class:`ConfigError` with a precise dotted path.
"""

from __future__ import annotations

from profiles.core.config.schema import ConfigError

_KNOWN_TOP_LEVEL = {"version", "defaults", "columns", "hooks", "configs"}


def validate(raw: dict) -> None:
    """Validate the raw YAML mapping semantically.

    Args:
        raw: The parsed YAML dict (from :func:`yaml_io.read_yaml`).

    Raises:
        ConfigError: On unknown top-level keys, unknown ``extends``
            references, or inheritance cycles.
    """
    for key in raw:
        if key not in _KNOWN_TOP_LEVEL:
            raise ConfigError(key, f"unknown top-level key '{key}'")

    configs = raw.get("configs") or {}
    if not isinstance(configs, dict):
        return

    for name, cfg in configs.items():
        if not isinstance(cfg, dict):
            continue
        extends = cfg.get("extends")
        if extends is None:
            continue
        if extends not in configs:
            raise ConfigError(
                f"configs.{name}.extends",
                f"unknown config '{extends}'",
            )

    # Cycle detection via DFS
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, stack: tuple[str, ...]) -> None:
        if name in visiting:
            cycle = " -> ".join((*stack, name))
            raise ConfigError(f"configs.{name}.extends", f"inheritance cycle: {cycle}")
        if name in visited:
            return
        visiting.add(name)
        extends = configs[name].get("extends")
        if extends is not None:
            visit(extends, (*stack, name))
        visiting.discard(name)
        visited.add(name)

    for name in configs:
        visit(name, (name,))


__all__ = ["validate"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/config/test_validator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/validator.py tests/core/config/test_validator.py
git commit -m "feat(config): add semantic YAML validator"
```

---

### Task 4: Create `inheritance.py` (defaults + extends resolution)

**Files:**
- Create: `src/profiles/core/config/inheritance.py`
- Test: `tests/core/config/test_inheritance.py`

**Interfaces:**
- Consumes: `AppConfigYaml`, `Defaults`, `MachineConfig`, `RowColor`, `ConfigError` from `schema.py`.
- Produces: `resolve_configs(cfg: AppConfigYaml) -> dict[str, MachineConfig]` — fully-resolved configs (all lists merged with defaults; `None` never present). Task 5 (`reader.py`) consumes it.

- [ ] **Step 1: Write the failing test**

Create `tests/core/config/test_inheritance.py`:

```python
"""Tests for profiles.core.config.inheritance — defaults + extends resolution."""

from __future__ import annotations

import pytest

from profiles.core.config.inheritance import resolve_configs
from profiles.core.config.schema import AppConfigYaml, ConfigError, MachineConfig


def _cfg(**kwargs) -> AppConfigYaml:
    return AppConfigYaml(**kwargs)


class TestResolveConfigs:
    def test_defaults_applied(self) -> None:
        cfg = _cfg(
            defaults={"extensions": ["All", ".lnk"], "filters": ["", "ST_PRO"]},
            configs={"base": {"directory": "/x"}},
        )
        resolved = resolve_configs(cfg)
        assert resolved["base"].extensions == ["All", ".lnk"]
        assert resolved["base"].filters == ["", "ST_PRO"]

    def test_local_overrides_scalar(self) -> None:
        cfg = _cfg(
            defaults={"search_dir": "/default"},
            configs={"base": {"directory": "/local"}},
        )
        resolved = resolve_configs(cfg)
        assert resolved["base"].directory == "/local"

    def test_extends_merges_lists(self) -> None:
        cfg = _cfg(
            defaults={"extensions": ["All"]},
            configs={
                "base": {"extensions": [".pdf"]},
                "prod": {"extends": "base", "extensions": [".xlsx"]},
            },
        )
        resolved = resolve_configs(cfg)
        # local first, then inherited, then defaults, deduped
        assert resolved["prod"].extensions == [".xlsx", ".pdf", "All"]

    def test_extends_inherits_scalar(self) -> None:
        cfg = _cfg(
            configs={
                "base": {"directory": "/base"},
                "prod": {"extends": "base"},
            }
        )
        resolved = resolve_configs(cfg)
        assert resolved["prod"].directory == "/base"

    def test_unknown_extends_raises(self) -> None:
        cfg = _cfg(configs={"prod": {"extends": "ghost"}})
        with pytest.raises(ConfigError):
            resolve_configs(cfg)

    def test_cycle_raises(self) -> None:
        cfg = _cfg(configs={"a": {"extends": "b"}, "b": {"extends": "a"}})
        with pytest.raises(ConfigError):
            resolve_configs(cfg)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/config/test_inheritance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'profiles.core.config.inheritance'`

- [ ] **Step 3: Create `src/profiles/core/config/inheritance.py`**

```python
"""Resolve ``defaults`` + ``extends`` inheritance for configurations.

Single Responsibility: pure functions that turn the raw schema
(:class:`AppConfigYaml`) into fully-resolved :class:`MachineConfig`
objects where every list is merged with defaults and no field is ``None``.
"""

from __future__ import annotations

from profiles.core.config.schema import (
    AppConfigYaml,
    ConfigError,
    Defaults,
    MachineConfig,
    RowColor,
)


def _merge_str(base: list[str], local: list[str] | None) -> list[str]:
    """Merge *local* (first) with *base*, deduped, order-preserving."""
    if local is None:
        return list(base)
    merged = list(local)
    for item in base:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_row(base: list[RowColor], local: list[RowColor] | None) -> list[RowColor]:
    if local is None:
        return list(base)
    merged = list(local)
    for rc in base:
        if rc not in merged:
            merged.append(rc)
    return merged


def _resolve_machine(
    name: str,
    configs: dict[str, MachineConfig],
    defaults: Defaults,
    stack: tuple[str, ...],
) -> MachineConfig:
    cfg = configs[name]

    if cfg.extends is not None:
        if cfg.extends not in configs:
            raise ConfigError(f"configs.{name}.extends", f"unknown config '{cfg.extends}'")
        if cfg.extends in stack:
            cycle = " -> ".join((*stack, cfg.extends))
            raise ConfigError(f"configs.{name}.extends", f"inheritance cycle: {cycle}")
        base = _resolve_machine(cfg.extends, configs, defaults, (*stack, name))
    else:
        base = None

    def pick(field: str):
        local = getattr(cfg, field)
        inherited = getattr(base, field) if base is not None else None
        if field in ("extensions", "filters", "search_exclude_files"):
            return _merge_str(inherited or [], local)
        if field == "row_colors":
            return _merge_row(inherited or [], local)
        return local if local is not None else inherited

    return MachineConfig(
        extends=cfg.extends,
        pc_hostname=pick("pc_hostname") or "",
        pc_ip=pick("pc_ip") or "",
        pc_name=pick("pc_name") or "",
        directory=pick("directory") or "",
        extensions=_merge_str(defaults.extensions, pick("extensions")),
        filters=_merge_str(defaults.filters, pick("filters")),
        row_colors=_merge_row(defaults.row_colors, pick("row_colors")),
        search_exclude_files=_merge_str(
            defaults.search_exclude_files, pick("search_exclude_files")
        ),
    )


def resolve_configs(cfg: AppConfigYaml) -> dict[str, MachineConfig]:
    """Resolve every named config against defaults and the extends chain.

    Returns:
        A dict mapping config name to a fully-resolved :class:`MachineConfig`
        (all lists merged with defaults, no ``None`` fields).

    Raises:
        ConfigError: On unknown ``extends`` or inheritance cycles.
    """
    resolved: dict[str, MachineConfig] = {}
    for name in cfg.configs:
        resolved[name] = _resolve_machine(name, cfg.configs, cfg.defaults, (name,))
    return resolved


__all__ = ["resolve_configs"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/config/test_inheritance.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/inheritance.py tests/core/config/test_inheritance.py
git commit -m "feat(config): add defaults + extends inheritance resolution"
```

---

### Task 5: Rewrite `reader.py` (ConfigReader → YAML pipeline)

**Files:**
- Rewrite: `src/profiles/core/config/reader.py`
- Test: `tests/core/config/test_reader.py`

**Interfaces:**
- Consumes: `read_yaml` from `yaml_io.py`; `validate` from `validator.py`; `resolve_configs` from `inheritance.py`; `AppConfigYaml` from `schema.py`; resolved dataclasses from `models.py`.
- Produces: `ConfigReader` with the same public API as today — `load() -> AppConfig`, `config_path` property, static `find_config_file`, `find_configuration_by_hostname`. Task 6/7/8/9 consume it.

- [ ] **Step 1: Write the failing test**

Rewrite `tests/core/config/test_reader.py`:

```python
"""Tests for profiles.core.config.reader — ConfigReader YAML loading."""

from __future__ import annotations

from pathlib import Path

from profiles.core.config.reader import ConfigReader


def _write_yaml(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestConfigReader:
    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        config = ConfigReader(tmp_path / ".profiles.yaml").load()
        assert config.extensions == ("All", ".lnk")
        assert config.config_path == tmp_path / ".profiles.yaml"

    def test_loads_defaults(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles.yaml",
            "defaults:\n  theme: dark\n  recursive_search: true\n",
        )
        config = ConfigReader(conf).load()
        assert config.theme == "dark"
        assert config.recursive_search is True

    def test_loads_columns(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles.yaml",
            "columns:\n  Version:\n    width: 80\n    expression: '[-_]V(\\\\d+)'\n"
            "    group: 1\n    priority: 10\n",
        )
        config = ConfigReader(conf).load()
        assert "Version" in config.columns
        assert config.columns["Version"].width == 80
        assert config.column_names == ("File", "Version")

    def test_loads_configs_with_inheritance(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles.yaml",
            "defaults:\n  extensions: [All, .lnk]\n"
            "configs:\n"
            "  base:\n    directory: /base\n"
            "  prod:\n    extends: base\n    pc_hostname: PC1\n",
        )
        config = ConfigReader(conf).load()
        assert len(config.configurations) == 2
        prod = next(c for c in config.configurations if c.pc_hostname == "PC1")
        assert prod.directory == "/base"
        # extensions resolved = defaults merged (no local/inherited extensions)
        assert prod.extensions == ("All", ".lnk")

    def test_loads_hooks(self, tmp_path: Path) -> None:
        conf = _write_yaml(
            tmp_path / ".profiles.yaml",
            "hooks:\n  failmode: abort\n  timeout: 10\n"
            "  entries:\n    '.mttl':\n      - when: before\n        command: 'x {{path}}'\n",
        )
        config = ConfigReader(conf).load()
        assert config.launch_hook_failmode == "abort"
        assert config.launch_hook_timeout == 10
        assert ".mttl" in config.launch_hooks
        assert config.launch_hooks[".mttl"][0].template == "x {{path}}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/config/test_reader.py -v`
Expected: FAIL (old INI-based reader cannot parse YAML)

- [ ] **Step 3: Rewrite `src/profiles/core/config/reader.py`**

```python
"""``ConfigReader`` — parses a ``.profiles.yaml`` file into an :class:`AppConfig`.

Composes the YAML I/O, validator, inheritance resolver, and schema models
to produce the resolved :class:`AppConfig` consumed by the rest of the app.
"""

from __future__ import annotations

from pathlib import Path

from profiles.core.config.inheritance import resolve_configs
from profiles.core.config.io.yaml_io import find_config_file as _find_config_file
from profiles.core.config.io.yaml_io import read_yaml
from profiles.core.config.models import (
    AppConfig,
    ColumnConfiguration,
    HookSpec,
    MachineConfiguration,
)
from profiles.core.config.schema import AppConfigYaml
from profiles.core.config.service import (
    find_configuration_by_hostname as _find_configuration_by_hostname,
)
from profiles.core.config.validator import validate

_DEFAULT_FILE_COLUMN_WIDTH = 600
_DEFAULT_COLUMN_WIDTH = 150


class ConfigReader:
    """Reads and parses the ``.profiles.yaml`` configuration file.

    Usage::

        reader = ConfigReader("conf/.profiles.yaml")
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
        """Locate ``.profiles.yaml`` in the CWD subtree."""
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
        does not exist.
        """
        config = AppConfig(config_path=self._config_path)

        if not self._config_path.exists():
            self._build_column_configs(config)
            return config

        try:
            raw = read_yaml(self._config_path)
        except FileNotFoundError:
            self._build_column_configs(config)
            return config

        validate(raw)
        schema = AppConfigYaml.model_validate(raw)
        self._apply_defaults(config, schema)
        self._apply_columns(config, schema)
        self._apply_hooks(config, schema)
        config.configurations = self._build_configurations(schema)
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
                name=name,
                width=col.width,
                expression=col.expression,
                group=col.group,
                priority=col.priority,
                default=col.default,
            )
        self._build_column_configs(config)

    def _apply_hooks(self, config: AppConfig, schema: AppConfigYaml) -> None:
        """Populate *config* from ``schema.hooks``."""
        config.launch_hook_failmode = schema.hooks.failmode
        config.launch_hook_timeout = schema.hooks.timeout
        for ext, entries in schema.hooks.entries.items():
            config.launch_hooks[ext] = tuple(
                HookSpec(
                    when=entry.when,
                    template=entry.command,
                    requires_success=entry.requires_success,
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
        """Materialise ``column_names`` / ``column_widths`` from ``config.columns``."""
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
        else:
            config.column_names = ("File",)
            config.column_widths = (_DEFAULT_FILE_COLUMN_WIDTH,)


__all__ = ["ConfigReader"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/config/test_reader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/reader.py tests/core/config/test_reader.py
git commit -m "feat(config): rewrite ConfigReader for YAML pipeline"
```

---

### Task 6: Rewrite `template.py` (YAML starter template)

**Files:**
- Rewrite: `src/profiles/core/config/template.py`
- Test: `tests/core/config/test_template.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `STARTER_CONFIG_TEMPLATE` — a YAML string with `{cwd}` placeholder. Consumed by `app.py`, `gui/main_window.py`, `actions.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/core/config/test_template.py`:

```python
"""Tests for profiles.core.config.template — YAML starter template."""

from __future__ import annotations

from profiles.core.config.template import STARTER_CONFIG_TEMPLATE


class TestStarterTemplate:
    def test_is_yaml(self) -> None:
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/tmp")
        assert "version: 1" in body
        assert "defaults:" in body
        assert "configs:" in body

    def test_has_cwd_placeholder(self) -> None:
        assert "{cwd}" in STARTER_CONFIG_TEMPLATE

    def test_formats_cwd(self) -> None:
        body = STARTER_CONFIG_TEMPLATE.format(cwd="/my/dir")
        assert "/my/dir" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/core/config/test_template.py -v`
Expected: FAIL (template is still INI)

- [ ] **Step 3: Rewrite `src/profiles/core/config/template.py`**

```python
"""Starter configuration template for ``.profiles.yaml`` files.

This module provides the canonical YAML template for ProFiles
configuration files. It is used by ``write_starter_config()`` and
``init_default_config()`` to generate fresh ``.profiles.yaml`` files.
"""

# Template for a freshly-generated starter .profiles.yaml. `{cwd}` is
# replaced with the current working directory at write time.
STARTER_CONFIG_TEMPLATE = """# ProFiles — Starter Configuration
# ============================================================================
# This file was generated by ProFiles on first launch. Every key matches
# the default value produced when no .profiles.yaml is present, so the GUI
# behaves identically with or without this file.
#
# ProFiles searches for ".profiles.yaml" starting at the current working
# directory (CWD) and walking its subdirectories. The first hit wins.
#
# Booleans use YAML true/false. Lists are YAML arrays.
# ============================================================================

version: 1

# ============================================================================
# DEFAULTS — global values inherited by every configuration below.
# ============================================================================
defaults:
  title: ""
  gui_auto_launch: true
  close_after_execute: false
  theme: light            # "light" or "dark"
  language: en            # "en" or "fr"
  search_dir: "{cwd}"
  recursive_search: false
  extensions: [All, .lnk]
  filters: ["", ST_PRO, ST_ENG]
  row_colors:
    - pattern: TMP
      color: "#BAC015"
    - pattern: DEV
      color: "#C01565"
  search_exclude_dirs: [.git, .*, __pycache__, bin, obj, tmp, Obsolete, Debug]
  search_exclude_files: []
  verbose: INFO            # DEBUG | INFO | WARNING | ERROR | CRITICAL
  scan_metrics: false

# ============================================================================
# COLUMNS — dynamic columns extracted from filenames via regex.
# The "File" column is implicit and always appears first.
# ============================================================================
columns:
  File:
    width: 600
    expression: ".*"
    group: 0
    priority: 100
    default: ""
  Path:
    width: 200
    expression: "(.+[\\\\/])"
    group: 1
    priority: 40
    default: "."
  FileName:
    width: 150
    expression: "([^/\\\\]+)$"
    group: 1
    priority: 30
  Type:
    width: 80
    expression: "(PRO|ENG|DEV|TMP|DEBUG)(?!.*(?:PRO|ENG|DEV|TMP|DEBUG))"
    group: 1
    priority: 20
  Version:
    width: 100
    expression: "[-_]V(\\\\d+(?:\\\\.\\\\d+)*)(?=[^\\\\/]*\\\\.[a-zA-Z0-9]+$)"
    group: 1
    priority: 10

# ============================================================================
# HOOKS — execution hooks around file launches.
# ============================================================================
hooks:
  failmode: warn           # "warn" | "abort" | "skip"
  timeout: 30
  entries:
    # ".mttl":
    #   - when: before
    #     command: "logger.exe --file {{path}}"
    #   - when: after
    #     command: "notifier.exe --name {{name}}"
    # ".pdf":
    #   - command: "SumatraPDF.exe -reuse-instance {{path}}"

# ============================================================================
# CONFIGS — named configurations. Each may `extends` another config.
# The name is the dict key. `pc_hostname = All` acts as a catch-all.
# ============================================================================
configs:
  base:
    pc_name: Generic
    directory: "{cwd}"
    row_colors:
      - pattern: SPECIFIC
        color: "#FF0000"

  # production:
  #   extends: base
  #   pc_hostname: COMPUTER-1
  #   pc_ip: 172.16.40.143
  #   extensions: [.pdf, .docx, .lnk, .xlsx]
  #   filters: [tmp, dev, prod]
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/config/test_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/template.py tests/core/config/test_template.py
git commit -m "feat(config): rewrite starter template as YAML"
```

---

### Task 7: Update `loader.py`, delete INI files, update package exports

**Files:**
- Modify: `src/profiles/core/config/loader.py`
- Delete: `src/profiles/core/config/io/ini_primitives.py`, `src/profiles/core/config/io/writer.py`
- Modify: `src/profiles/core/config/io/__init__.py`
- Modify: `src/profiles/core/config/__init__.py`
- Modify: `src/profiles/core/__init__.py`
- Modify: `src/profiles/config.py`
- Delete: `tests/core/config/io/test_ini_primitives.py`, `tests/core/config/io/test_writer.py`
- Test: `tests/core/config/test_loader.py`

**Interfaces:**
- Consumes: `find_config_file` from `yaml_io.py`; `ConfigReader` from `reader.py`.
- Produces: `load_config(config_path=None) -> AppConfig` (searches `.profiles.yaml`), `propose_config_creation() -> bool`. Public exports updated so `from profiles.core import load_config, ConfigReader` still works.

- [ ] **Step 1: Rewrite `loader.py`**

Replace the imports and the `.profiles` references in `src/profiles/core/config/loader.py`:

```python
from profiles.core.config.io.yaml_io import find_config_file
from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
```

And in `load_config`, replace the fallback path:

```python
    # No .profiles.yaml found anywhere — use defaults from the default path
    return ConfigReader(Path.cwd() / ".profiles.yaml").load()
```

And in `propose_config_creation`, replace the target and messages:

```python
    target = Path.cwd() / ".profiles.yaml"
```

Update the printed strings from `.profiles` to `.profiles.yaml`.

- [ ] **Step 2: Delete INI files**

```bash
git rm src/profiles/core/config/io/ini_primitives.py src/profiles/core/config/io/writer.py
git rm tests/core/config/io/test_ini_primitives.py tests/core/config/io/test_writer.py
```

- [ ] **Step 3: Update `io/__init__.py`**

Replace its contents with:

```python
"""Low-level YAML I/O for the configuration subsystem."""

from profiles.core.config.io.yaml_io import find_config_file, read_yaml, write_value

__all__ = ["find_config_file", "read_yaml", "write_value"]
```

- [ ] **Step 4: Update `config/__init__.py`**

Remove the imports of `find_config_file`, `parse_bool`, `_write_config_value`, `save_config_bool`, `save_config_str` from `ini_primitives`/`writer`. Import `find_config_file` from `yaml_io` instead. Keep the rest. Update `__all__` accordingly (remove `parse_bool`, `save_config_bool`, `save_config_str`, `_write_config_value`).

- [ ] **Step 5: Update `core/__init__.py`**

Remove `parse_bool`, `save_config_bool`, `save_config_str`, `_write_config_value`, `find_config_file` from the imports and `__all__` (or re-export `find_config_file` from `yaml_io` if still needed). Keep `load_config`, `ConfigReader`, models, service ops, `STARTER_CONFIG_TEMPLATE`.

- [ ] **Step 6: Update `src/profiles/config.py`**

Remove `save_config_bool`, `save_config_str`, `_write_config_value` imports and `__all__` entries.

- [ ] **Step 7: Update `tests/core/config/test_loader.py`**

Change the fixture file name from `.profiles` to `.profiles.yaml` and the YAML content. Example:

```python
def test_load_config_explicit(tmp_path: Path) -> None:
    conf = tmp_path / ".profiles.yaml"
    conf.write_text("defaults:\n  theme: dark\n", encoding="utf-8")
    config = load_config(conf)
    assert config.theme == "dark"
```

- [ ] **Step 8: Run the config test suite**

Run: `pytest tests/core/config -v`
Expected: PASS (all config tests)

- [ ] **Step 9: Commit**

```bash
git add -A src/profiles/core/config tests/core/config src/profiles/config.py src/profiles/core/__init__.py
git commit -m "refactor(config): remove INI layer, update exports to YAML"
```

---

### Task 8: Update `app.py` (`--init`, `--config`)

**Files:**
- Modify: `src/profiles/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `STARTER_CONFIG_TEMPLATE` from `template.py`.
- Produces: `init_default_config(dest=None) -> Path` writes `.profiles.yaml`.

- [ ] **Step 1: Update `init_default_config`**

In `src/profiles/app.py`, change the target filename and docstring:

```python
    target = Path(dest) / ".profiles.yaml"
```

Update the docstring and the `--init`/`--config` help strings from `.profiles` to `.profiles.yaml`.

- [ ] **Step 2: Update `tests/test_app.py`**

Update any test that asserts the generated file is `.profiles` to expect `.profiles.yaml`. Example:

```python
def test_init_default_config_creates_yaml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = init_default_config(tmp_path)
    assert target.name == ".profiles.yaml"
    assert target.exists()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/profiles/app.py tests/test_app.py
git commit -m "feat(app): generate .profiles.yaml on --init"
```

---

### Task 9: Update GUI `main_window.py` (round-trip writes + file name)

**Files:**
- Modify: `src/profiles/gui/main_window.py`
- Modify: `src/profiles/gui/i18n.py`
- Test: `tests/gui/test_main_window.py`

**Interfaces:**
- Consumes: `write_value` from `yaml_io.py`; `STARTER_CONFIG_TEMPLATE` from `template.py`.
- Produces: GUI persists theme/language/recursive/close via `write_value`; creates `.profiles.yaml`.

- [ ] **Step 1: Update imports**

Replace the import of `save_config_bool, save_config_str` with:

```python
from profiles.core.config.io.yaml_io import write_value
```

- [ ] **Step 2: Update `_apply_theme`**

Replace the `save_config_str(...)` call with:

```python
        write_value(self._config.config_path, "defaults.theme", theme_name)
```

- [ ] **Step 3: Update `_on_toggle_language`**

Replace the `save_config_str(...)` call with:

```python
        write_value(self._config.config_path, "defaults.language", new_lang)
```

- [ ] **Step 4: Update `_on_recursive_toggle`**

Replace the `save_config_bool(...)` call with:

```python
        write_value(
            self._config.config_path,
            "defaults.recursive_search",
            self._recursive_var.get(),
        )
```

- [ ] **Step 5: Update `_on_close_toggle`**

Replace the `save_config_bool(...)` call with:

```python
        write_value(
            self._config.config_path,
            "defaults.close_after_execute",
            self._close_var.get(),
        )
```

- [ ] **Step 6: Update `_create_config_file`**

Change `target = Path.cwd() / ".profiles"` to `target = Path.cwd() / ".profiles.yaml"`. Update the user-facing message strings from `.profiles` to `.profiles.yaml`.

- [ ] **Step 7: Update `_check_config_file` and `_on_open_config` messages**

Change `.profiles` → `.profiles.yaml` in the prompt strings.

- [ ] **Step 8: Update `i18n.py` labels**

Change `"Open .profiles"` → `"Open .profiles.yaml"` and `"Ouvrir .profiles"` → `"Ouvrir .profiles.yaml"` (lines ~68 and ~141).

- [ ] **Step 9: Update `tests/gui/test_main_window.py`**

Update any test that writes/reads `.profiles` or mocks `save_config_bool`/`save_config_str` to use `.profiles.yaml` and `write_value`.

- [ ] **Step 10: Run GUI tests**

Run: `pytest tests/gui -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add src/profiles/gui/main_window.py src/profiles/gui/i18n.py tests/gui/test_main_window.py
git commit -m "feat(gui): write YAML config via round-trip, use .profiles.yaml"
```

---

### Task 10: Update `actions.py` `write_starter_config`

**Files:**
- Modify: `src/profiles/core/actions.py`
- Test: `tests/core/test_actions.py`

**Interfaces:**
- Consumes: `STARTER_CONFIG_TEMPLATE` from `template.py`.
- Produces: `write_starter_config(config_path, logger=None) -> ActionResult` writes a YAML starter.

- [ ] **Step 1: Update `write_starter_config`**

In `src/profiles/core/actions.py`, the function already formats `STARTER_CONFIG_TEMPLATE.format(cwd=...)`. Verify it writes to the given `config_path` (now `.profiles.yaml`). Update any docstring references from `.profiles` to `.profiles.yaml`.

- [ ] **Step 2: Update `tests/core/test_actions.py`**

Update tests that assert the starter content is INI to assert YAML. Example:

```python
def test_write_starter_config_writes_yaml(tmp_path: Path) -> None:
    target = tmp_path / ".profiles.yaml"
    result = write_starter_config(target)
    assert result.status is ActionStatus.SUCCESS
    body = target.read_text(encoding="utf-8")
    assert "version: 1" in body
    assert "defaults:" in body
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/core/test_actions.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/profiles/core/actions.py tests/core/test_actions.py
git commit -m "feat(actions): write YAML starter config"
```

---

### Task 11: Update shared fixtures + full suite + quality gates

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/core/config/test_models.py` (if needed)
- Modify: `tests/core/telemetry/test_metrics.py` (ConfigReader usage)
- Modify: `tests/core/environment/test_execution.py` (if needed)
- Modify: `tests/core/processing/test_scanner.py` (if needed)

**Interfaces:**
- Consumes: everything from prior tasks.
- Produces: a green test suite + passing quality gates.

- [ ] **Step 1: Update `tests/conftest.py` fixture**

Replace the `sample_profile_conf` fixture with a YAML version:

```python
@pytest.fixture
def sample_profile_conf(tmp_path: Path) -> Path:
    """Create a minimal .profiles.yaml configuration for testing."""
    content = """version: 1
defaults:
  gui_auto_launch: true
  close_after_execute: false
  extensions: [.mttl]
configs:
  base:
    pc_hostname: All
    pc_name: All
    directory: "M:\\\\test\\\\dir"
"""
    path = tmp_path / ".profiles.yaml"
    path.write_text(content, encoding="utf-8")
    return path
```

- [ ] **Step 2: Update `tests/core/config/test_models.py`**

The resolved dataclasses are unchanged, so most tests pass. Update any test that constructs `AppConfig(config_path=...)` expecting `.profiles` to `.profiles.yaml`.

- [ ] **Step 3: Update `tests/core/telemetry/test_metrics.py`**

Update the `ConfigReader` usages (lines ~191, 203) to point at a `.profiles.yaml` fixture.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 5: Run quality gates**

Run: `ruff format . && ruff check . && pylint src/profiles --fail-under=8.0`
Expected: clean

- [ ] **Step 6: Run coverage**

Run: `pytest --cov=src/profiles --cov-fail-under=85`
Expected: coverage ≥ 85%

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "test(config): migrate shared fixtures to YAML, green suite"
```

---

## Self-Review Notes

- **Spec coverage:** Every spec section maps to a task — schema (T1), yaml_io (T2), validator (T3), inheritance (T4), reader (T5), template (T6), loader/exports/INI removal (T7), app (T8), GUI (T9), actions (T10), fixtures/quality (T11). Round-trip, inheritance, validation, and `.profiles.yaml` naming are all covered.
- **Type consistency:** `ConfigError(path, message)` is defined once in `schema.py` and used by `validator.py` and `inheritance.py`. `read_yaml`/`write_value`/`find_config_file` signatures are consistent across `yaml_io.py`, `loader.py`, `reader.py`, and GUI. `resolve_configs(cfg: AppConfigYaml) -> dict[str, MachineConfig]` is used by `reader.py`.
- **Resolved interface preserved:** `AppConfig`, `MachineConfiguration`, `ColumnConfiguration`, `HookSpec` dataclasses keep their field names, so `service.py`, `scanner.py`, `execution.py`, and the GUI compile unchanged (except the explicit `write_value`/filename edits in Task 9).