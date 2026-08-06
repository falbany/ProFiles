# .profiles Configuration File

> 🏠 **[Documentation Home](./README.md)** | 
> 📦 **[Installation](./installation-guide.en.md)** | 
> ⚙️ **Configuration** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **[Dynamic Columns](./dynamic-columns-guide.md)** | 
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)** | 
> 🇫🇷 **[Version Française](./configuration-profile.fr.md)**

---

## Overview

The `.profiles` file is an INI-format configuration file that customizes ProFiles's behavior. This file is searched for starting from the current working directory (CWD) and descending into subdirectories up to **5 levels deep**. The first match found is used.

**Important**: Search is limited to 5 levels of subdirectories to maintain good performance on large file trees.

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

The file uses standard INI format with sections and keys. All section keys are **case-insensitive**.

### Available Sections

- `[LAUNCHER]` — Global configuration
- `[CONFIGURATION_N]` — Per-machine configurations (N = 1, 2, 3, ...)

---

## `[LAUNCHER]` Section — Global Configuration

This section defines default parameters applicable to all machines.

### Parameters

| Key                   | Type               | Default              | Description                                                                                                                                                       |
| --------------------- | ------------------ | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`               | string             | `""`                 | Custom title appended to main window                                                                                                                              |
| `gui_auto_launch`     | bool               | `true`               | Show GUI on `python -m profiles`                                                                                                                                |
| `close_after_execute` | bool               | `false`              | Close window after successful launch                                                                                                                              |
| `theme`               | enum               | `"light"`            | UI theme: `"light"` or `"dark"` (Material Design 3)                                                                                                               |
| `language`            | enum               | `"en"`               | GUI language: `"en"` (English) or `"fr"` (French); toggled from the status-bar language button (cycles en → fr → en)                                                  |
| `search_dir`          | absolute path      | `""`                 | Default search directory for Directory field                                                                                                                      |
| `recursive_search`    | bool               | `false`              | Initial state of Recursive checkbox                                                                                                                               |
| `columns`             | csv string         | `"File, Version"`    | Treeview column headers (first reserved for filename)                                                                                                             |
| `column_widths`       | csv int            | `"600, 150"`         | Pixel widths, MUST match `columns` count                                                                                                                          |
| `extensions`          | csv string         | `"All, .lnk"`        | Extension combobox presets (fallback for `[CONFIGURATION_N]`)                                                                                                     |
| `filters`             | csv string         | `", ST_PRO, ST_ENG"` | Filter combobox presets ("" = show all files)                                                                                                                     |
| `row_colors`          | csv "PATTERN:#HEX" | `""`                 | Generic row-coloring rules applied to ALL configurations                                                                                                          |
| `search_exclude_dirs` | csv glob-pattern   | `".git"`             | Directory basenames (case-insensitive glob patterns) skipped during recursive scan. Supports `*`, `?`, `[seq]` wildcards (`*tmp`, `node_modules`, `Debug*`, etc.) |
| `search_exclude_files` | csv glob-pattern   | `""`                 | File basenames (case-insensitive glob patterns) skipped during scan. Applies to recursive AND non-recursive scans. Same wildcard syntax as `search_exclude_dirs` (`*backup*`, `~$*`, `*.tmp`). Per-config `[CONFIGURATION_N].search_exclude_files` are APPENDED. |

### Accepted Boolean Values

- English: `true` / `false` / `yes` / `no` / `1` / `0` / `on` / `off`
- French: `Vrai` / `Faux`

### Example `[LAUNCHER]` Configuration

```ini
[LAUNCHER]
title = My Project
gui_auto_launch = true
close_after_execute = false
theme = dark
search_dir = /path/to/production/directory
recursive_search = true
columns = File, Version, Classification
column_widths = 600, 150, 100
extensions = All, .lnk, .pdf, .docx
filters = , ST_PRO, ST_ENG, DEV
row_colors = PROD:#1565C0, DEV:#757575, TMP:#BAC015
search_exclude_dirs = .git, tmp, Obsolete, Debug
search_exclude_files = *backup*, ~$*, *.tmp
```

### Glob Exclusion (`search_exclude_dirs` / `search_exclude_files`)

Both keys accept case-insensitive glob patterns with `*`, `?`, `[seq]` wildcards (via Python's `fnmatch`).

| Key | Scope | Default | Example |
| --- | --- | --- | --- |
| `search_exclude_dirs` | Directory basenames skipped during **recursive** scan | `.git` | `node_modules`, `Debug*`, `*tmp` |
| `search_exclude_files` | File basenames skipped during scan (**recursive and non-recursive**) | `""` | `*backup*`, `~$*`, `*.tmp` |

**Per-configuration appending**: `search_exclude_files` in a `[CONFIGURATION_N]` section is appended to the `[LAUNCHER]` base list — both sets of patterns apply for that configuration. Directory exclusion (`search_exclude_dirs`) is global only.

---

## `[CONFIGURATION_N]` Sections — Per-Machine Configurations

These sections define machine-specific parameters. Sections are numbered sequentially (CONFIGURATION_1, CONFIGURATION_2, ...).

ProFiles selects the section whose `pc_hostname` matches the local hostname (exact match, case-insensitive).

A section with `pc_hostname = All` acts as a catch-all — place it **LAST** so it doesn't shadow specific hostnames.

### Parameters

| Key           | Type               | Required | Description                                                       |
| ------------- | ------------------ | -------- | ----------------------------------------------------------------- |
| `pc_ip`       | string             | No       | Display-only IP label (NOT used for matching)                     |
| `pc_hostname` | string             | Yes\*    | Local hostname targeted by this section (\*except if `All`)       |
| `pc_name`     | string             | No       | Friendly label (logs, status)                                     |
| `directory`   | absolute path      | No       | Production directory scanned for this machine                     |
| `extensions`  | csv string         | No       | Per-station Extension presets (overrides `[LAUNCHER].extensions`) |
| `filters`     | csv string         | No       | Per-station Filter presets (overrides `[LAUNCHER].filters`)       |
| `row_colors`  | csv "PATTERN:#HEX" | No       | Configuration-specific coloring rules                             |
| `search_exclude_files` | csv glob-pattern | No | Per-station file exclusion patterns. APPENDED to `[LAUNCHER].search_exclude_files`. Same wildcard syntax. |

### Example Per-Machine Configuration

```ini
[CONFIGURATION_1]
pc_hostname = WORKSTATION-01
pc_name = Production Station
pc_ip = 192.168.1.100
directory = /path/to/production/station1
extensions = .pdf, .docx, .lnk, .xlsx
filters = , tmp, dev, prod
row_colors = PROD:#1565C0, DEV:#757575
search_exclude_files = *draft*, *.bak

[CONFIGURATION_2]
pc_hostname = All
pc_name = Generic
directory = /path/to/production
extensions = .lnk
filters = , ST_PRO
row_colors =
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

```ini
[LAUNCHER]
row_colors = PROD:#1565C0, DEV:#757575

[CONFIGURATION_1]
row_colors = SPECIFIC:#FF0000, PROD:#00FF00
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

```ini
[LAUNCHER]
title = Production Launch System
gui_auto_launch = true
close_after_execute = false
theme = dark
search_dir = /path/to/production/root
recursive_search = true
columns = File, Version, Classification, Date
column_widths = 500, 120, 150, 100
extensions = All, .lnk, .pdf, .docx, .xlsx
filters = , ST_PRO, ST_ENG, DEV, TMP
row_colors = PROD:#1565C0, DEV:#757575, TMP:#BAC015, TEST:#FF6F00
search_exclude_dirs = .git, tmp, Obsolete, Debug, Backup

[CONFIGURATION_1]
pc_hostname = WORKSTATION-PROD-01
pc_name = Production Station 1
pc_ip = 192.168.1.101
directory = /path/to/production/station1
extensions = .lnk, .pdf
filters = , prod, specific
row_colors = CRITICAL:#B71C1C, PROD:#0D47A1

[CONFIGURATION_2]
pc_hostname = WORKSTATION-ENG-05
pc_name = Engineering Workstation
pc_ip = 192.168.1.105
directory = /path/to/engineering/tests
extensions = .lnk, .txt, .log
filters = , dev, test, debug
row_colors = DEV:#4A148C, TEST:#E65100, DEBUG:#006064

[CONFIGURATION_3]
pc_hostname = All
pc_name = Default Configuration
directory = /path/to/production
extensions = .lnk
filters = , ST_PRO
row_colors =
```

### Minimal Production Setup

```ini
[LAUNCHER]
theme = dark
row_colors = PROD:#1565C0

[CONFIGURATION_1]
pc_hostname = All
directory = /path/to/production
extensions = .lnk
```

### Development Environment with Color Coding

```ini
[LAUNCHER]
theme = light
row_colors = DEV:#757575, TEST:#FF6F00, TMP:#BAC015

[CONFIGURATION_1]
pc_hostname = All
directory = /path/to/development/project
extensions = .lnk, .py, .sh
filters = , dev, test, tmp
row_colors = FEATURE:#2E7D32, BUG:#C62828, REFACTOR:#6A1B9A
```

---

## Search Operator Deep Dive

### Complex Search Expressions

```ini
# Find production files, exclude backups, include specific version
extensions = .lnk
filters = Prod -backup +V2026.7

# Multiple alternatives with exact phrases
filters = "Production Program" OR "Test Suite" -deprecated

# Combine AND and OR logic
filters = (Prod OR Dev) -tmp "V2026.*"
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

```ini
[LAUNCHER]
row_colors = PROD:#1565C0, DEV:#757575

[CONFIGURATION_1]
row_colors = PROD:#0D47A1, SPECIFIC:#FF0000
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

```ini
# ✅ CORRECT format
row_colors = PROD:#1565C0, DEV:#757575

# ❌ WRONG formats (will be ignored)
row_colors = PROD:#1565C, DEV:#75757  # Too short
row_colors = PROD:1565C0, DEV:757575  # Missing #
row_colors = PROD = #1565C0           # Wrong separator
```

### Issue: Extensions not matching

**Symptoms**: Files with expected extensions don't appear in results.

**Diagnosis**:

1. Extension field matches **full suffix** (no leading dot required)
2. Comparison is case-insensitive
3. "All" option shows all file types

**Solution**:

```ini
# Match .lnk files (both .lnk and .LNK)
extensions = All, .lnk, .LNK  # All equivalent

# Match multiple extensions
extensions = All, .lnk, .pdf, .docx, .xlsx

# To match ALL files regardless of extension
extensions = All
```

### Issue: Recursive search too slow

**Symptoms**: Scanning takes a long time on large directory trees.

**Solution**:

```ini
[LAUNCHER]
# Exclude common large directories
search_exclude_dirs = .git, node_modules, __pycache__, bin, obj, Debug, Release, tmp

# Or disable recursive search for initial scan
recursive_search = false
```

---

## Performance Tips

### Optimize Scan Speed

1. **Exclude unnecessary directories**:

   ```ini
   search_exclude_dirs = .git, node_modules, __pycache__, bin, obj
   ```

2. **Limit file extensions**:

   ```ini
   extensions = .lnk, .pdf  # Only scan these types
   ```

3. **Use specific search directory**:
   ```ini
   search_dir = /path/to/production/specific_folder  # Narrower scope
   ```

### Memory Optimization

For very large directories (>10,000 files):

- Disable recursive search initially
- Use filter patterns to narrow results
- Consider splitting into multiple configuration sections

---

## Migration Guide

### From Old Configuration Format

If you have an older configuration format, migrate as follows:

```ini
; OLD FORMAT (deprecated)
[MAIN]
path = /path/to/production
ext = .lnk, .pdf

; NEW FORMAT
[LAUNCHER]
search_dir = /path/to/production
extensions = All, .lnk, .pdf

[CONFIGURATION_1]
pc_hostname = All
directory = /path/to/production
extensions = .lnk, .pdf
```

---

## FAQ

**Q: Can I have multiple `.profiles` files?**  
A: Yes, but only the first one found (from CWD upward) is used. Use `--config` for explicit selection.

**Q: How do I test a configuration without launching?**  
A: Use `--headless` mode: `python -m profiles --headless --config path/.profiles`

**Q: Can I use environment variables?**  
A: Not currently supported. Use absolute paths or configure per-machine sections.

**Q: What happens if two sections match the hostname?**  
A: The first matching section (by number) is used. `All` should be last.

**Q: How do I reset to defaults?**  
A: Delete `.profiles` or run `python -m profiles --init` to regenerate.

---

## Changelog

### Version 1.0 (Current)

- Full INI-format configuration support
- Per-machine `[CONFIGURATION_N]` sections
- Row coloring with pattern matching
- Advanced search operators (-, +, OR, quotes)
- CLI flags for explicit configuration

### Planned Features

- Environment variable substitution
- Configuration validation tool
- GUI configuration editor
- Configuration import/export
