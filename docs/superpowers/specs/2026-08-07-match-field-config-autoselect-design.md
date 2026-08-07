# Design Specification: `match` Field for Config Auto-Selection & Multi-Directory Scanning

**Date:** 2026-08-07  
**Status:** Approved  

---

## 1. Overview & Architecture Goal

This specification defines a new matching layer and multi-directory scanning capability for ProFiles configurations.
It replaces the legacy single-string `pc_hostname`, `pc_ip`, and `directory` fields with a flexible, multi-criteria `match` layer and multi-path `scan` list.

### Key Separation of Concerns
- **`match`**: Determines **when** to auto-select and activate a configuration based on runtime environment properties (hostname, IP address, active path).
- **`scan`**: Defines **where** to scan for files (`list[str]`).
- **`name`**: Display label for UI/logging.

---

## 2. Schema Changes & Data Models

### 2.1 Pydantic Schema (`src/profiles/core/config/schema.py`)

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

### 2.2 Dataclasses (`src/profiles/core/config/models.py`)

```python
@dataclass
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

---

## 3. Pattern Matching Engine (`src/profiles/core/config/matcher.py`)

### 3.1 Pattern Evaluation Rules
- **Regex**: Patterns starting with `re:` use `re.search(pattern[3:], value, re.IGNORECASE)`.
- **Glob**: All other patterns use `fnmatch.fnmatch(value.lower(), pattern.lower())`.

### 3.2 OR-based Criteria Evaluation
A `MachineConfiguration` matches the environment if **any** non-empty criteria list (`hostname`, `ip`, or `path`) has at least one pattern matching the current environment value.

```python
def matches_machine_config(
    config: MachineConfiguration,
    current_hostname: str,
    current_ip: str,
    current_path: str,
) -> bool:
    if config.match.hostname and eval_criteria_list(config.match.hostname, current_hostname):
        return True
    if config.match.ip and eval_criteria_list(config.match.ip, current_ip):
        return True
    if config.match.path and eval_criteria_list(config.match.path, current_path):
        return True
    return False
```

---

## 4. High-Performance Multi-Directory Scanner (`src/profiles/core/scanner.py`)

### 4.1 Requirements
- Support scanning multiple directory paths (`scan: tuple[str, ...]`).
- High performance scanning using `os.scandir` / parallel traversal when multiple scan directories are provided.
- Deduplicate scanned files across overlapping directories by resolved real path (`os.path.realpath`).

---

## 5. System Integration & Backward Compatibility

- **No Backward Compatibility**: `pc_hostname`, `pc_ip`, and `directory` are completely replaced by `match` and `scan`.
- **UI Integration**: Auto-selection on app launch invokes `select_active_configuration` and sets up the scanner with the configuration's scan paths.
