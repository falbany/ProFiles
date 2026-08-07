# Configurable Columns Refactoring Guide

## Overview

This document describes the migration from the legacy `expression`/`group`
column model to the unified `match`/`transform` model with `stretch` and
`name` fields.

## Motivation

The previous column configuration used two separate concepts:

- **`expression`** — a raw regex pattern applied to filenames.
- **`group`** — an integer selecting which capture group to extract.

This split made it impossible to express common use-cases cleanly:

- Built-in macros (e.g. `version`, `date`, `git_commit`) required
  special-casing outside the regex engine.
- Friendly header names were conflated with the internal column key.
- Stretch behaviour was hardcoded per column index.

The new model unifies everything into a single, declarative rule:

| Field        | Type             | Description                                              |
| ------------ | ---------------- | --------------------------------------------------------
| `name`       | `str`            | User-friendly header label (falls back to key).          |
| `width`      | `int`            | Pixel width when `stretch=False`.                        |
| `stretch`    | `bool`           | Whether the column stretches to fill available space.    |
| `match`      | `str`            | Built-in keyword (`version`, `date`, …) or raw regex.   |
| `transform`  | `str \| None`    | Replacement pattern with group backreferences.           |
| `priority`   | `int`            | Extraction priority (higher = first).                  |
| `default`    | `str`            | Fallback value when no match.                            |

## Built-in Pattern Macros

The `match` field accepts case-insensitive keywords that map to predefined
regex patterns:

| Keyword       | Regex Pattern                                           |
| ------------- | ------------------------------------------------------- |
| `version`     | `v?(\d+\.\d+(?:\.\d+)?)`                                |
| `date`        | `(\d{4}-\d{2}-\d{2})`                                   |
| `git_commit`  | `([0-9a-f]{7,40})`                                      |
| `type`        | `(\w+)`                                                 |
| `filename`    | `([^.]+)`                                               |
| `extension`   | `(\.[^.]+)$`                                            |

If `match` does not match a keyword, it is treated as a raw regex pattern.

## Migration

### YAML Configuration

**Before (legacy):**

```ini
[COLUMN_Version]
expression = v?(\d+\.\d+(?:\.\d+)?)
group = 1
width = 150
```

**After (new):**

```ini
[COLUMN_Version]
match = version
transform = v{group:1}
width = 150
stretch = false
name = Version
```

### Python API

**Before:**

```python
from profiles.core.config.models import ColumnConfiguration

col = ColumnConfiguration(
    expression=r"v?(\d+\.\d+(?:\.\d+)?)",
    group=1,
    width=150,
)
```

**After:**

```python
from profiles.config import ColumnConfiguration

col = ColumnConfiguration(
    match="version",
    transform="v{group:1}",
    width=150,
    stretch=False,
    name="Version",
)
```

### ColumnRule (extraction engine)

The `ColumnRule` class in `column_extractor.py` now accepts `match` and
`transform` parameters. The legacy `group` parameter is retained for
backward compatibility with `load_column_rules_from_config`:

```python
from profiles.core.processing.column_extractor import ColumnRule

# New style
rule = ColumnRule(match="version", transform="v{group:1}")

# Legacy style (still supported)
rule = ColumnRule(match=r"v?(\d+\.\d+)", group=1)
```

**Extraction logic:**

1. If `transform` is set → `match.expand(transform)` (supports `{group:N}`
   backreferences).
2. Else if `group != 1` → legacy group indexing (`match.group(group)`).
3. Else → group 1 if it exists, otherwise group 0 (whole match).

### AppConfig fields

`AppConfig` now carries four parallel tuples built from `[COLUMN_*]`
sections:

| Field            | Type              | Description                          |
| ---------------- | ----------------- | ------------------------------------ |
| `column_names`   | `tuple[str, ...]` | Internal column keys (legacy).       |
| `column_headers` | `tuple[str, ...]` | Display names from `ColumnConfiguration.name`. |
| `column_widths`  | `tuple[int, ...]` | Pixel widths.                        |
| `column_stretches` | `tuple[bool, ...]` | Stretch flags.                     |

The GUI `ui.py` column loop now zips all four:

```python
for i, (header, width, stretch) in enumerate(
    zip(config.column_headers, config.column_widths, config.column_stretches, strict=True)
):
    tree.heading(i, text=header)
    tree.column(i, width=width, stretch=stretch)
```

## Backward Compatibility

- `ColumnRule.group` defaults to `1` and is still honoured by `extract()`.
- `load_column_rules_from_config` still parses the legacy colon format
  (`"pattern:group"`).
- `column_names` and `column_widths` remain on `AppConfig` for any
  downstream code that has not yet migrated.
- `ColumnConfiguration` defaults (`match=".*"`, `transform=None`) ensure
  that a column with no explicit rule matches everything and returns the
  whole filename.
