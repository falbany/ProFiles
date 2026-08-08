# .profiles Configuration File

> 🏠 **[Documentation Home](./README.md)** | 
> 📦 **[Installation](./installation-guide.en.md)** | 
> ⚙️ **Configuration** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **[Dynamic Columns](./columns-guide.en.md)** | 
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)** | 
> 🇫🇷 **[Version Française](./configuration-profile.fr.md)**

---

## Overview

The `.profiles` file is a **YAML-format** configuration file that customizes ProFiles's behavior. This file is searched for starting from the current working directory (CWD) and descending into subdirectories. The first match found is used.

If no `.profiles` file is found:

- In GUI mode: ProFiles proposes to create a default configuration file
- In headless mode: ProFiles uses default values identical to those presented in this document

## Creating the Configuration File

### Method 1: Automatic Proposal (GUI Mode)

On first launch in GUI mode, if no `.profiles` file is found, ProFiles proposes to create a default configuration file in the current working directory.

### Method 2: Command Line

```bash
python -m profiles --init
```

This command creates a `.profiles` file with default values in the current working directory.

### Method 3: Manual Creation

Create a file named `.profiles` in your working directory and copy the template content below into it.

## File Structure

The file uses standard **YAML format** with hierarchical keys. All keys are **case-insensitive**.

### Top-Level Keys

- `version` — Configuration schema version (currently `1`)
- `defaults` — Global configuration inherited by all machine-specific configs
- `columns` — Dynamic column definitions for filename metadata extraction
- `hooks` — Execution hooks for file launches (before/after/confirm/abort/instead)
- `configs` — Machine-specific configurations (named dictionary)

---

## `defaults` Section — Global Configuration

This section defines default parameters applicable to all machines.

### Parameters

| Key                   | Type               | Default              | Description                                                                                                                                                       |
| --------------------- | ------------------ | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`               | string             | `""`                 | Custom title appended to main window                                                                                                                              |
| `gui_auto_launch`     | bool               | `true`               | Show GUI on `python -m profiles`                                                                                                                                |
| `close_after_execute` | bool               | `false`              | Close window after successful launch                                                                                                                              |
| `theme`               | enum               | `"light"`            | UI theme: `"light"`, `"dark"`, or `"auto"` (Material Design 3; `"auto"` detects system theme via `darkdetect`)                                                                                                               |
| `language`            | enum               | `"en"`               | GUI language: `"en"` (English) or `"fr"` (French); toggled from the status-bar language button (cycles en → fr → en)                                                  |
| `search_dir`          | string             | `""`                 | Default search directory for Directory field                                                                                                                      |
| `recursive_search`    | bool               | `false`              | Initial state of Recursive checkbox                                                                                                                               |
| `extensions`          | array of strings   | `[All, .lnk]`        | Extension combobox presets (fallback for `configs` sections)                                                                                                     |
| `filters`             | array of strings   | `["", ST_PRO, ST_ENG]` | Filter combobox presets ("" = show all files)                                                                                                                     |
| `row_colors`          | array of objects   | `[]`                 | Generic row-coloring rules applied to ALL configurations. Each object has `pattern` (string) and `color` (#RRGGBB)                                                |
| `search_exclude_dirs` | array of strings   | `[.git, __pycache__]` | Directory basenames (case-insensitive glob patterns) skipped during recursive scan. Supports `*`, `?`, `[seq]` wildcards (`*tmp`, `node_modules`, `Debug*`, etc.) |
| `search_exclude_files` | array of strings | `[]`                 | File basenames (case-insensitive glob patterns) skipped during scan. Applies to recursive AND non-recursive scans. Same wildcard syntax as `search_exclude_dirs` (`*backup*`, `~$*`, `*.tmp`). Per-config entries are APPENDED. |
| `verbose`             | enum               | `"INFO"`             | Logging verbosity: `"DEBUG"` | `"INFO"` | `"WARNING"` | `"ERROR"` | `"CRITICAL"`                                              |
| `scan_metrics`        | bool               | `false`              | Log performance metrics after each scan                                                                                                                           |

### Accepted Boolean Values

YAML standard: `true` / `false` / `yes` / `no` / `1` / `0` / `on` / `off`

### Example `defaults` Configuration

```yaml
defaults:
  title: "My Project"
  gui_auto_launch: true
  close_after_execute: false
  theme: dark
  language: en
  search_dir: "C:/Users/YourName/Workspace"
  recursive_search: true
  extensions: [All, .lnk, .pdf, .docx]
  filters: ["", ST_PRO, ST_ENG, DEV]
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"
    - pattern: TMP
      color: "#BAC015"
  search_exclude_dirs: [.git, tmp, Obsolete, Debug, __pycache__, node_modules]
  search_exclude_files: [*backup*, ~$*, *.tmp]
  verbose: INFO
  scan_metrics: false
```

### Glob Exclusion (`search_exclude_dirs` / `search_exclude_files`)

Both keys accept case-insensitive glob patterns with `*`, `?`, `[seq]` wildcards (via Python's `fnmatch`).

| Key | Scope | Default | Example |
| --- | --- | --- | --- |
| `search_exclude_dirs` | Directory basenames skipped during **recursive** scan | `.git` | `node_modules`, `Debug*`, `*tmp` |
| `search_exclude_files` | File basenames skipped during scan (**recursive and non-recursive**) | `""` | `*backup*`, `~$*`, `*.tmp` |

**Per-configuration appending**: `search_exclude_files` in a `configs` section is appended to the `defaults.search_exclude_files` base list — both sets of patterns apply for that configuration. Directory exclusion (`search_exclude_dirs`) is global only.

---

## `configs` Section — Per-Machine Configurations

This section is a dictionary where each key is a named configuration. ProFiles auto-selects the configuration whose `match` criteria matches the local runtime environment (hostname, IP address, or filesystem path).

Matching uses **OR logic**: if any pattern in any `match` field matches, the configuration is selected. Patterns support glob wildcards (`*`, `?`, `[seq]`) and regex (prefix with `re:`). Matching is case-insensitive.

A configuration with `match.hostname: ["*"]` (or an empty `match` block) acts as a catch-all — place it **LAST** so it doesn't shadow specific hostnames.

Configurations can `extend` another configuration to inherit settings. Lists are merged: local items first, then inherited items not already present.

### Parameters

| Key           | Type               | Required | Description                                                       |
| ------------- | ------------------ | -------- | ----------------------------------------------------------------- |
| `extends`     | string             | No       | Name of another config to inherit from                           |
| `match`       | object             | No       | Auto-selection criteria (see below)                              |
| `scan`        | string or array    | No       | Directory path(s) to scan for this machine. Single string is auto-coerced to a list. |
| `extensions`  | array of strings   | No       | Per-station Extension presets (overrides `defaults.extensions`)  |
| `filters`     | array of strings   | No       | Per-station Filter presets (overrides `defaults.filters`)        |
| `row_colors`  | array of objects   | No       | Configuration-specific coloring rules. APPENDED to `defaults.row_colors` and checked first |
| `search_exclude_files` | array of strings | No | Per-station file exclusion patterns. APPENDED to `defaults.search_exclude_files`. Same wildcard syntax. |

### `match` Field

The `match` field is an object with three optional list properties. Any single match in any field is sufficient (OR logic):

| Sub-key   | Type           | Description                                                                 |
| --------- | -------------- | --------------------------------------------------------------------------- |
| `hostname` | list of strings | Glob/regex patterns matched against the machine's hostname (case-insensitive) |
| `ip`       | list of strings | Glob/regex patterns matched against the machine's IP address (case-insensitive) |
| `path`     | list of strings | Glob/regex patterns matched against the current working directory path (cross-platform normalized) |

**Pattern syntax:**
- **Glob**: `WORKSTATION-*`, `10.0.0.*`, `/projects/*` — uses `fnmatch` with case-insensitive matching
- **Regex**: Prefix with `re:` — e.g. `re:^192\.168\.\d+\.\d+$`, `re:^/projects/.*$`
- **Path normalization**: Paths are normalized via `os.path.normpath` + `os.path.expanduser`, with backslashes converted to forward slashes for cross-platform matching

### Example Per-Machine Configuration

```yaml
configs:
  base:
    match:
      hostname: ["*"]
    scan: "C:/Users/YourName/Workspace"
    extensions: [All, .lnk]
    filters: ["", ST_PRO]
    row_colors:
      - pattern: SPECIFIC
        color: "#FF0000"

  production:
    extends: base
    match:
      hostname: ["WORKSTATION-01", "re:^WORKSTATION-\\d+$"]
      ip: ["192.168.1.100", "10.0.0.*"]
      path: ["/projects/engineering", "re:^/data/.*$"]
    scan:
      - "Z:/Projects/Engineering/station1"
      - "Z:/Projects/Shared"
    extensions: [.pdf, .docx, .lnk, .xlsx]
    filters: [tmp, dev, prod]
    row_colors:
      - pattern: PROD
        color: "#1565C0"
      - pattern: DEV
        color: "#757575"
    search_exclude_files: [*draft*, *.bak]
```

---

## Search Operators

The **Extension** and **Filter** fields are editable and accept Google-style expressions:

### Syntax

| Operator     | Symbol  | Example              | Description                       |
| ------------ | ------- | -------------------- | --------------------------------- |
| NOT          | `-`     | `Prod -backup`       | Rejects files containing "backup" |
| include      | `+`     | `+Prod`              | Explicit inclusion (= plain)      |
| OR           | `OR`    | `Prod OR Dev`        | Accepts either term               |
| exact phrase | `"..."` | `"V2026.7"`          | Literal substring in quotes       |
| implicit AND | space   | `Production Program` | Both terms must match             |

### Precedence (highest to lowest)

1. Quoted phrases → one literal term
2. `-` or `+` prefix → binds to immediately following term
3. Space (AND) → all terms in a group must match
4. OR → separates alternative groups

### Usage Examples

```
# Files containing "Prod" but not "backup"
Prod -backup

# Files containing "Prod" or "Dev"
Prod OR Dev

# Files containing exactly "V2026.7"
"V2026.7"

# Files containing "Production" AND "Program"
Production Program
```

---

## Row Coloring (`row_colors`)

Row coloring allows highlighting files based on their name.

### Syntax

```
row_colors = PATTERN1:#HEX1, PATTERN2:#HEX2, ...
```

- `PATTERN`: Substring to search for in filename (case-insensitive)
- `#HEX`: Hex color code in RRGGBB format

### Priority Rules

1. `[LAUNCHER]` rules are applied first (base)
2. `[CONFIGURATION_N]` rules are **appended** after
3. Per-config rules have priority (checked first)

### Example

```yaml
defaults:
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"

configs:
  configuration_1:
    row_colors:
      - pattern: SPECIFIC
        color: "#FF0000"
      - pattern: PROD
        color: "#00FF00"
```

In this example:

- Files containing "SPECIFIC" will be red (#FF0000) — priority
- Files containing "PROD" will be green (#00FF00) — priority
- Files containing "DEV" will be gray (#757575) — base

---

## CLI Command Lines

```bash
# GUI mode (reads .profiles)
python -m profiles

# Explicit configuration file
python -m profiles --config PATH/.profiles

# Headless mode (no GUI)
python -m profiles --headless

# Regenerate starter configuration file
python -m profiles --init
```

---

## Advanced Configuration Examples

### Complete Multi-Machine Setup

```yaml
defaults:
  title: Production Launch System
  gui_auto_launch: true
  close_after_execute: false
  theme: dark
  search_dir: /path/to/production/root
  recursive_search: true
  columns: File, Version, Classification, Date
  column_widths: 500, 120, 150, 100
  extensions: [All, .lnk, .pdf, .docx, .xlsx]
  filters: ["", ST_PRO, ST_ENG, DEV, TMP]
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"
    - pattern: TMP
      color: "#BAC015"
    - pattern: TEST
      color: "#FF6F00"
  search_exclude_dirs: [.git, tmp, Obsolete, Debug, Backup]

configs:
  configuration_1:
    match:
      hostname: ["WORKSTATION-PROD-01"]
    scan: /path/to/production/station1
    extensions: [.lnk, .pdf]
    filters: ["", prod, specific]
    row_colors:
      - pattern: CRITICAL
        color: "#B71C1C"
      - pattern: PROD
        color: "#0D47A1"

  configuration_2:
    match:
      hostname: ["WORKSTATION-ENG-05"]
    scan: /path/to/engineering/tests
    extensions: [.lnk, .txt, .log]
    filters: ["", dev, test, debug]
    row_colors:
      - pattern: DEV
        color: "#4A148C"
      - pattern: TEST
        color: "#E65100"
      - pattern: DEBUG
        color: "#006064"

  configuration_3:
    match:
      hostname: ["*"]
    scan: /path/to/production
    extensions: [.lnk]
    filters: ["", ST_PRO]
    row_colors: []
```

### Minimal Production Setup

```yaml
defaults:
  theme: dark
  row_colors:
    - pattern: PROD
      color: "#1565C0"

configs:
  configuration_1:
    match:
      hostname: ["*"]
    scan: /path/to/production
    extensions: [.lnk]
```

### Development Environment with Color Coding

```yaml
defaults:
  theme: light
  row_colors:
    - pattern: DEV
      color: "#757575"
    - pattern: TEST
      color: "#FF6F00"
    - pattern: TMP
      color: "#BAC015"

configs:
  configuration_1:
    match:
      hostname: ["*"]
    scan: /path/to/development/project
    extensions: [.lnk, .py, .sh]
    filters: ["", dev, test, tmp]
    row_colors:
      - pattern: FEATURE
        color: "#2E7D32"
      - pattern: BUG
        color: "#C62828"
      - pattern: REFACTOR
        color: "#6A1B9A"
```

---

## Search Operator Deep Dive

### Complex Search Expressions

```yaml
# Find production files, exclude backups, include specific version
  extensions: [.lnk]
  filters: [Prod -backup +V2026.7]

# Multiple alternatives with exact phrases
  filters: ["Production Program" OR "Test Suite" -deprecated]

# Combine AND and OR logic
  filters: [(Prod OR Dev) -tmp "V2026.*"]
```

### Operator Precedence Examples

| Expression     | Meaning             | Matches                                                   |
| -------------- | ------------------- | --------------------------------------------------------- |
| `Prod -backup` | Prod AND NOT backup | `prod_file.lnk` ✅, `prod_backup.lnk` ❌                  |
| `Prod OR Dev`  | Prod OR Dev         | `prod_file.lnk` ✅, `dev_file.lnk` ✅, `test_file.lnk` ❌ |
| `"V2026.7"`    | Exact phrase        | `file_V2026.7.lnk` ✅, `V2026.7_test.lnk` ✅              |
| `Prod Program` | Prod AND Program    | `prod_program.lnk` ✅, `prod_file.lnk` ❌                 |

---

## Row Coloring Best Practices

### Color Palette Recommendations

| Category        | Hex Code          | Use Case            | Example Pattern      |
| --------------- | ----------------- | ------------------- | -------------------- |
| **Production**  | `#1565C0` (Blue)  | Production files    | `PROD`, `PROD_`      |
| **Development** | `#757575` (Gray)  | Development files   | `DEV`, `DEV_`        |
| **Testing**     | `#FF6F00` (Amber) | Test files          | `TEST`, `TEST_`      |
| **Temporary**   | `#BAC015` (Olive) | Temporary files     | `TMP`, `TEMP`        |
| **Critical**    | `#B71C1C` (Red)   | Critical production | `CRITICAL`, `URGENT` |
| **Feature**     | `#2E7D32` (Green) | Feature branches    | `FEATURE`, `FEAT`    |
| **Bug Fix**     | `#C62828` (Red)   | Bug fixes           | `BUG`, `FIX`         |

### Priority Resolution Example

```yaml
defaults:
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"

configs:
  configuration_1:
    row_colors:
      - pattern: PROD
        color: "#0D47A1"
      - pattern: SPECIFIC
        color: "#FF0000"
```

**Resolution order for file `PROD_test.lnk`:**

1. Check `[CONFIGURATION_1]` rules first → `PROD:#0D47A1` (darker blue) ✅
2. If no match, check `[LAUNCHER]` rules → `PROD:#1565C0` (standard blue)
3. Final: `SPECIFIC:#FF0000` (red) for files containing "SPECIFIC"

---

## Troubleshooting

### Issue: Configuration not applied

**Symptoms**: GUI shows default values instead of configured values.

**Diagnosis**:

1. Verify file location: `.profiles` must be in CWD or parent directories
2. Check file name: Must be exactly `.profiles` (hidden file on Unix)
3. Use explicit path: `python -m profiles --config /path/to/.profiles`

**Solution**:

```bash
# Check if file exists
ls -la .profiles          # Linux/macOS
dir .profiles            # Windows

# Use explicit configuration
python -m profiles --config C:\path\to\.profiles
```

### Issue: Colors not applied correctly

**Symptoms**: Files appear with default colors instead of configured colors.

**Diagnosis**:

1. Check hex format: Must be `#RRGGBB` (7 characters including #)
2. Verify pattern matching: Pattern is case-insensitive substring match
3. Check priority: Per-config rules override global rules

**Solution**:

```yaml
# ✅ CORRECT format
  row_colors:
    - pattern: PROD
      color: "#1565C0"
    - pattern: DEV
      color: "#757575"

# ❌ WRONG formats (will be ignored)
  row_colors:
    - pattern: PROD
      color: "#1565C"
    - pattern: DEV
      color: "#75757  # Too short"
  row_colors:
    - pattern: PROD
      color: "1565C0"
    - pattern: DEV
      color: "757575  # Missing #"
  row_colors:
```

### Issue: Extensions not matching

**Symptoms**: Files with expected extensions don't appear in results.

**Diagnosis**:

1. Extension field matches **full suffix** (no leading dot required)
2. Comparison is case-insensitive
3. "All" option shows all file types

**Solution**:

```yaml
# Match .lnk files (both .lnk and .LNK)
  extensions: [All, .lnk, .LNK  # All equivalent]

# Match multiple extensions
  extensions: [All, .lnk, .pdf, .docx, .xlsx]

# To match ALL files regardless of extension
  extensions: [All]
```

### Issue: Recursive search too slow

**Symptoms**: Scanning takes a long time on large directory trees.

**Solution**:

```yaml
defaults:
# Exclude common large directories
  search_exclude_dirs: [.git, node_modules, __pycache__, bin, obj, Debug, Release, tmp]

# Or disable recursive search for initial scan
  recursive_search: false
```

---

## Performance Tips

### Optimize Scan Speed

1. **Exclude unnecessary directories**:

   ```yaml
  search_exclude_dirs: [.git, node_modules, __pycache__, bin, obj]
```

2. **Limit file extensions**:

```yaml
  extensions: [.lnk, .pdf  # Only scan these types]
```

3. **Use specific search directory**:
```yaml
  search_dir: /path/to/production/specific_folder  # Narrower scope
```

### Memory Optimization

For very large directories (>10,000 files):

- Disable recursive search initially
- Use filter patterns to narrow results
- Consider splitting into multiple configuration sections

---

## FAQ

**Q: Can I have multiple `.profiles` files?**  
A: Yes, but only the first one found (from CWD upward) is used. Use `--config` for explicit selection.

**Q: How do I test a configuration without launching?**  
A: Use `--headless` mode: `python -m profiles --headless --config path/.profiles`

**Q: Can I use environment variables?**  
A: Not currently supported. Use absolute paths or configure per-machine sections.

**Q: What happens if two sections match?**  
A: The first matching section (by order in the `configs` dictionary) is used. The catch-all (`match.hostname: ["*"]`) should be last.

**Q: How do I reset to defaults?**  
A: Delete `.profiles` or run `python -m profiles --init` to regenerate.

---

## Changelog

### Version 1.0 (Current)

- Full YAML-format configuration support
- Per-machine `[CONFIGURATION_N]` sections
- Row coloring with pattern matching
- Advanced search operators (-, +, OR, quotes)
- CLI flags for explicit configuration

### Planned Features

- Environment variable substitution
- Configuration validation tool
- GUI configuration editor
- Configuration import/export
