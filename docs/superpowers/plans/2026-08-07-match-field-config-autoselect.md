# Match Field Config Auto-Selection & Multi-Directory Scanning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy single-string configuration matching (`pc_hostname`, `pc_ip`, `directory`) with a multi-criteria `match` layer (hostname, IP, path matching via glob/regex OR logic) and multi-directory `scan` lists across Windows, Linux, and macOS.

**Architecture:** 
1. Pydantic schema coercion (`MatchCriteriaSchema` and `scan: list[str]`) mapping to frozen dataclasses (`MatchCriteria` and `MachineConfiguration`).
2. A pure pattern-matching engine in `src/profiles/core/config/matcher.py` with cross-platform OS path normalization and OR evaluation.
3. High-performance scanner updates in `src/profiles/core/scanner.py` for multi-directory traversal and resolved-path deduplication.

**Tech Stack:** Python 3.10+, Pydantic v2, `fnmatch`, `re`, `pytest`, `dataclasses`.

## Global Constraints

- Pydantic models in `src/profiles/core/config/schema.py` must coerce single strings into `list[str]`.
- Dataclasses in `src/profiles/core/config/models.py` must be frozen and use `tuple[str, ...]`.
- Pattern matching (`matcher.py`) must support `re:` prefixes for regex, case-insensitive globs via `fnmatch`, and cross-platform path normalization using `os.path.normpath(os.path.expanduser(...))`.
- Scanner (`scanner.py`) must scan all directories in `scan` and deduplicate files by `os.path.realpath`.
- Code must follow `AGENTS.md`: pure core functions, zero Tkinter imports in core layer, full type hints, docstrings, and tests passing.

---

## File Structure & Responsibilities

- `src/profiles/core/config/schema.py`: Pydantic models for `MatchCriteriaSchema` and `MachineConfig` (`match` & `scan: list[str]`).
- `src/profiles/core/config/models.py`: Frozen dataclass models `MatchCriteria` and updated `MachineConfiguration` (`match` & `scan: tuple[str, ...]`).
- `src/profiles/core/config/matcher.py` *(New)*: Core pattern evaluation and config selection logic (`match_pattern`, `matches_machine_config`, `select_active_configuration`).
- `src/profiles/core/config/service.py`: Service functions updated to delegate configuration matching and directory auto-selection to `matcher.py`.
- `src/profiles/core/scanner.py`: High-performance multi-directory scanner pipeline supporting `scan: tuple[str, ...]`.
- `tests/test_config_matcher.py` *(New)*: Unit tests for pattern matching and configuration selection across cross-platform path formats.
- `tests/test_scanner.py`: Updated unit tests verifying multi-directory scanning and path deduplication.

---

### Task 1: Schema Models & Dataclasses Update

**Files:**
- Modify: `src/profiles/core/config/schema.py`
- Modify: `src/profiles/core/config/models.py`
- Test: `tests/test_config_schema.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `Field`, `field_validator`, dataclasses `dataclass`, `field`.
- Produces: `MatchCriteriaSchema`, updated `MachineConfig` (`match: MatchCriteriaSchema`, `scan: list[str]`), `MatchCriteria`, updated `MachineConfiguration` (`match: MatchCriteria`, `scan: tuple[str, ...]`).

- [ ] **Step 1: Write failing schema tests**

Create/update `tests/test_config_schema.py`:
```python
from profiles.core.config.schema import MachineConfig, MatchCriteriaSchema
from profiles.core.config.models import MachineConfiguration, MatchCriteria

def test_match_criteria_schema_coercion():
    data = {
        "match": {
            "hostname": "WORKSTATION-1",
            "ip": ["192.168.1.1", "10.0.0.1"],
            "path": "/data/tests",
        },
        "scan": "/data/tests",
    }
    cfg = MachineConfig.model_validate(data)
    assert cfg.match.hostname == ["WORKSTATION-1"]
    assert cfg.match.ip == ["192.168.1.1", "10.0.0.1"]
    assert cfg.match.path == ["/data/tests"]
    assert cfg.scan == ["/data/tests"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_schema.py::test_match_criteria_schema_coercion -v`
Expected: FAIL (AttributeError or ValidationError)

- [ ] **Step 3: Update schema.py and models.py**

In `src/profiles/core/config/schema.py`:
```python
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
    """A named configuration block in YAML configs dict."""

    extends: str | None = None
    match: MatchCriteriaSchema = Field(default_factory=MatchCriteriaSchema)
    scan: list[str] = Field(default_factory=list)
    extensions: list[str] | None = None
    filters: list[str] | None = None
    row_colors: list[RowColor] | None = None
    search_exclude_files: list[str] | None = None

    @field_validator("scan", mode="before")
    @classmethod
    def _coerce_scan_list(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value]
        return []
```

In `src/profiles/core/config/models.py`:
```python
@dataclass(frozen=True)
class MatchCriteria:
    hostname: tuple[str, ...] = ()
    ip: tuple[str, ...] = ()
    path: tuple[str, ...] = ()


@dataclass
class MachineConfiguration:
    name: str = ""
    match: MatchCriteria = field(default_factory=MatchCriteria)
    scan: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()
    filters: tuple[str, ...] = ()
    row_colors: tuple[tuple[str, str], ...] = ()
    search_exclude_files: tuple[str, ...] = ()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_schema.py::test_match_criteria_schema_coercion -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/schema.py src/profiles/core/config/models.py tests/test_config_schema.py
git commit -m "feat(config): add MatchCriteria schema and dataclass models"
```

---

### Task 2: Core Pattern Matcher & Selection Engine

**Files:**
- Create: `src/profiles/core/config/matcher.py`
- Test: `tests/test_config_matcher.py`

**Interfaces:**
- Consumes: `MachineConfiguration`, `MatchCriteria`, `AppConfig`.
- Produces: `match_pattern(pattern: str, value: str) -> bool`, `matches_machine_config(config: MachineConfiguration, hostname: str, ip: str, path: str) -> bool`, `select_active_configuration(config: AppConfig, hostname: str, ip: str, path: str) -> MachineConfiguration | None`.

- [ ] **Step 1: Write failing tests for pattern matcher**

Create `tests/test_config_matcher.py`:
```python
from profiles.core.config.matcher import match_pattern, matches_machine_config, select_active_configuration
from profiles.core.config.models import MachineConfiguration, MatchCriteria, AppConfig

def test_match_pattern_glob_and_regex():
    assert match_pattern("WORKSTATION-*", "workstation-1")
    assert match_pattern("re:^192\\.168\\.\\d+\\.\\d+$", "192.168.1.50")
    assert not match_pattern("WORKSTATION-*", "SERVER-1")

def test_matches_machine_config_or_logic():
    cfg = MachineConfiguration(
        name="test",
        match=MatchCriteria(
            hostname=("HOST-1",),
            ip=("10.0.0.*",),
            path=("/projects/*",)
        )
    )
    assert matches_machine_config(cfg, "HOST-1", "192.168.0.1", "/tmp")
    assert matches_machine_config(cfg, "OTHER-HOST", "10.0.0.5", "/tmp")
    assert matches_machine_config(cfg, "OTHER-HOST", "192.168.0.1", "/projects/app")
    assert not matches_machine_config(cfg, "OTHER-HOST", "192.168.0.1", "/tmp")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_matcher.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'profiles.core.config.matcher')

- [ ] **Step 3: Implement `matcher.py`**

Create `src/profiles/core/config/matcher.py`:
```python
"""Pattern matching engine for configuration auto-selection."""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Sequence

from profiles.core.config.models import AppConfig, MachineConfiguration


def _normalize_path(path: str) -> str:
    """Normalize filesystem path for cross-platform matching."""
    if not path:
        return ""
    expanded = os.path.expanduser(path)
    norm = os.path.normpath(expanded)
    return norm.replace("\\", "/").lower()


def match_pattern(pattern: str, value: str, is_path: bool = False) -> bool:
    """Match value against pattern (glob or regex)."""
    if not pattern or not value:
        return False

    if pattern.startswith("re:"):
        regex = pattern[3:]
        target = _normalize_path(value) if is_path else value
        return bool(re.search(regex, target, re.IGNORECASE))

    if is_path:
        norm_pattern = _normalize_path(pattern)
        norm_value = _normalize_path(value)
        return fnmatch.fnmatch(norm_value, norm_pattern)

    return fnmatch.fnmatch(value.lower(), pattern.lower())


def eval_criteria_list(patterns: Sequence[str], candidate: str, is_path: bool = False) -> bool:
    """Return True if any pattern in patterns matches candidate."""
    return any(match_pattern(pat, candidate, is_path=is_path) for pat in patterns)


def matches_machine_config(
    config: MachineConfiguration,
    hostname: str,
    ip: str,
    path: str,
) -> bool:
    """Evaluate if machine config matches current environment (OR logic)."""
    m = config.match
    if m.hostname and eval_criteria_list(m.hostname, hostname):
        return True
    if m.ip and eval_criteria_list(m.ip, ip):
        return True
    if m.path and eval_criteria_list(m.path, path, is_path=True):
        return True
    return False


def select_active_configuration(
    config: AppConfig,
    hostname: str,
    ip: str,
    path: str,
) -> MachineConfiguration | None:
    """Select the first matching configuration or default fallback."""
    for machine in config.configurations:
        if matches_machine_config(machine, hostname, ip, path):
            return machine

    return config.configurations[0] if config.configurations else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_matcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/config/matcher.py tests/test_config_matcher.py
git commit -m "feat(config): implement core pattern matcher and selection engine"
```

---

### Task 3: High-Performance Multi-Directory Scanner Updates

**Files:**
- Modify: `src/profiles/core/scanner.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `directories: Sequence[str] | str`.
- Produces: `scan_directory(directories: Sequence[str] | str, ...) -> list[FileInfo]` deduplicated by `os.path.realpath`.

- [ ] **Step 1: Write failing test for multi-directory scanning**

Add test in `tests/test_scanner.py`:
```python
from profiles.core.scanner import scan_directory

def test_scan_multiple_directories_deduplicates(tmp_path):
    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    f1 = dir1 / "test1.txt"
    f2 = dir2 / "test2.txt"
    f1.write_text("a")
    f2.write_text("b")

    results = scan_directory(directories=[str(dir1), str(dir2)], recursive=False)
    filenames = [r.filename for r in results]
    assert "test1.txt" in filenames
    assert "test2.txt" in filenames
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scanner.py::test_scan_multiple_directories_deduplicates -v`
Expected: FAIL (TypeError or wrong arguments)

- [ ] **Step 3: Update `src/profiles/core/scanner.py`**

In `src/profiles/core/scanner.py`:
Ensure `scan_directory` accepts `directories: Sequence[str] | str`, normalizes them into a list of valid directory paths, iterates over each directory using `os.scandir`, and tracks seen realpaths using `seen_paths: set[str] = set()` to deduplicate files.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scanner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/core/scanner.py tests/test_scanner.py
git commit -m "feat(scanner): support high-performance multi-directory scanning and deduplication"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-07-match-field-config-autoselect.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
