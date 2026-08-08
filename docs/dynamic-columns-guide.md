# Dynamic Column Configuration

> 🏠 **[Documentation Home](./README.md)** | 
> 📦 **[Installation](./installation-guide.en.md)** | 
> ⚙️ **[Configuration](./configuration-profile.en.md)** | 
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **Dynamic Columns** | 
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

--- Guide — Updated

## 📚 Quick Reference: Column Library

**New!** A comprehensive library of ready-to-use column configurations is now available:

👉 **[Column Library Guide](./column-library.md)** - 50+ pre-configured columns for common use cases

### What's in the Library?

- ✅ **Base columns**: File, FileName, Extension, Path
- ✅ **Versions**: Version, Build, Revision, SemVer, Date
- ✅ **Environments**: PRO, DEV, TEST, TMP, Prod, Dev, Test
- ✅ **Projects**: Project, Device, Model, Client
- ✅ **Locations**: Site, Region, Country, Department
- ✅ **Technical**: Architecture, Language, Platform, Runtime
- ✅ **Metadata**: Author, Commit, Branch, Tag, Ticket
- ✅ **Ready combinations**: Production, Development, Multi-site configs

---

## Overview

ProFiles now supports **dynamic column extraction** via dedicated `[COLUMN_<Name>]` sections in the `.profiles` configuration file. This allows you to:

- Extract custom information from filenames (Device names, Project codes, etc.)
- Define multiple columns beyond the default "File" and "Version"
- Configure extraction rules per deployment without code changes
- Use regex capture groups for precise data extraction
- Set column widths and default values per column

---

## Quick Start Examples

### Example 1: Extract Version Number

```ini
[COLUMN_Version]
width = 100
expression = _V([^\\/]+)
group = 1
priority = 20
```

**Files:**
- `Device_ABC123_V01-Rel6.2.1.mttl` → Version: `01-Rel6.2.1`
- `Tool_XYZ789_V02-Rel6.3.0.mttl` → Version: `02-Rel6.3.0`

### Example 2: Extract Environment Type

```ini
[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP|DEBUG)
group = 1
priority = 15
```

**Files:**
- `App_PRO_V01.mttl` → Type: `PRO`
- `Tool_DEV_V02.mttl` → Type: `DEV`

### Example 3: Extract Device ID

```ini
[COLUMN_DeviceID]
width = 100
expression = Device_([A-Z0-9]+)
group = 1
priority = 20
```

**Files:**
- `Device_ABC123_V01.mttl` → DeviceID: `ABC123`
- `Device_XYZ789_V02.mttl` → DeviceID: `XYZ789`

### Example 4: Last Match Priority (from end)

```ini
[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP|DEBUG)(?!.*(PRO|ENG|DEV|TMP|DEBUG))
group = 1
priority = 15
```

**Files:**
- `Tool_PRO_DEV.mttl` → Type: `DEV` (last occurrence)
- `App_TMP_TEST.mttl` → Type: `TEST` (last occurrence)

---

## Common Configurations

### Production Setup
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP)(?!.*(PRO|ENG|DEV|TMP))
group = 1
priority = 15

[COLUMN_Version]
width = 120
expression = _V([^-]+-Rel[^\\/]+)
group = 1
priority = 20

[COLUMN_Site]
width = 100
expression = (LOUVAIN|PESSAC|ULIS)
group = 1
priority = 14
```

### Development Setup
```ini
[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_Project]
width = 100
expression = (PROJ|DEV|MTT)
group = 1
priority = 25

[COLUMN_VersionNum]
width = 60
expression = _V(\d+)
group = 1
priority = 20

[COLUMN_Build]
width = 70
expression = build(\d+)
group = 1
priority = 9

[COLUMN_Commit]
width = 90
expression = _g([a-f0-9]{7})
group = 2
priority = 7
```

---

## Architecture

The system consists of three main components:

1. **`core/processing/column_extractor.py`** - Regex-based extraction engine
2. **`core/processing/file_classifier.py`** - Dynamic file info extraction (`get_file_info_dynamic`)
3. **`core/processing/scanner.py`** - Enhanced scanning with `scan_and_process_dynamic()`
4. **`core/config/`** sub-package - Parses `[COLUMN_<Name>]` sections and builds column configuration

### Data Flow

```
.profiles file
    ↓
[core/config/loader.py] load_config()
    ↓
[core/config/reader.py] ConfigReader — _read_column_sections()
    ↓
AppConfig.columns: dict[str, ColumnConfiguration]
    ↓
[core/config/reader.py] builds column_names & column_widths
    ↓
config.column_names: tuple[str, ...]
config.column_widths: tuple[int, ...]
    ↓
[gui/main_window.py] Build Treeview with columns=column_names
    ↓
[scanner.py] scan_and_process_dynamic() — single unified scan path
    ↓
[column_extractor.py] extract_all()
    ↓
ScannedFileDynamic.column_values: dict[str, str]
    ↓
[gui/main_window.py] _insert_chunk() — builds rows from column_names
    ↓
Treeview populated with extracted values
```

---

## Column Construction Logic

The column system is built through a multi-step process in `core/config/reader.py`:

### Step 1: Parse `[COLUMN_*]` Sections

```python
# In ConfigReader._read_column_sections()
columns: dict[str, ColumnConfiguration] = {}

for section in parser.sections():
    if section.upper().startswith("COLUMN_"):
        col_name = section[7:]  # Remove "COLUMN_" prefix
        column = ColumnConfiguration(
            name=col_name,
            width=parser.getint(section, "width", fallback=150),
            expression=parser.get(section, "expression", fallback=""),
            group=parser.getint(section, "group", fallback=1),
            priority=parser.getint(section, "priority", fallback=0),
            default=parser.get(section, "default", fallback=""),
        )
        columns[col_name] = column
```

### Step 2: Build `column_names` Tuple

The `column_names` tuple determines the order and presence of columns in the GUI:

```python
# In ConfigReader.load() - column construction logic
if config.columns:  # Dynamic mode
    has_file_column = "File" in config.columns

    column_list = []
    if has_file_column:
        # User defined COLUMN_File - include it first
        column_list.append("File")
        column_list.extend(name for name in config.columns if name != "File")
    else:
        # No COLUMN_File defined - add default "File" first, then all defined columns
        column_list.append("File")
        column_list.extend(config.columns.keys())

    config.column_names = tuple(column_list)
```

**Key behaviors:**
- **File column always first**: Whether implicit or explicit, "File" is always the first column
- **Implicit File**: If no `[COLUMN_File]` section exists, "File" is added automatically with default behavior (full path)
- **Explicit File**: If `[COLUMN_File]` exists, it's used with custom extraction rules
- **Order preservation**: Other columns follow in the order they appear in the config file

### Step 3: Build `column_widths` Tuple

```python
config.column_widths = tuple(
    config.columns[name].width
    if name in config.columns
    else (600 if name == "File" else 150)
    for name in column_list
)
```

**Default widths:**
- `File` column: 600 pixels (if not explicitly defined)
- Other columns: 150 pixels (if not explicitly defined)

### Step 4: Single Scan Path

The GUI always routes through the same scan function; the reader
normalises `column_names` so no mode detection is needed:

```python
# In main_window._bg_scan_and_process()
processed_items = scanner.scan_and_process_dynamic(
    directory,
    extension=extension,
    filter_text=filter_text,
    column_names=self._config.column_names,
    columns=self._config.columns,
    config=self._config,
)
```

- **Custom columns** (`config.columns` is not empty): `column_names`
  lists them and the extractor applies the configured regex rules.
- **Default layout** (`config.columns` is empty): `column_names` is
  `("File",)` and the extractor has no rules.

---

## Runtime Column Extraction

### File Service: `get_file_info_dynamic()`

```python
def get_file_info_dynamic(
    file_path: Path,
    extension: str,
    column_names: tuple[str, ...],
    columns: dict[str, ColumnConfiguration],
) -> dict[str, str]:
    """Extract column values from a file path using regex patterns."""
    full_path = str(file_path)
    
    # Create extractor with custom rules
    extractor = ColumnExtractor()
    
    # Load column rules from configuration
    if columns:
        for col_name, col_config in columns.items():
            if col_config.expression:  # Only add if expression is defined
                extractor.add_rule(
                    col_name,
                    col_config.expression,
                    col_config.group,
                    col_config.priority,
                    col_config.default,
                )
    
    # Extract all column values from the full path
    result = extractor.extract_all(full_path, column_names)
    
    # File column: only set if not already extracted from COLUMN_File config
    if "File" in column_names and "File" not in result:
        result["File"] = full_path
    
    return result
```

**Key behaviors:**
- **Expressions applied to full path**: All regex patterns match against the complete file path, not just the filename
- **File column override**: If user defines `[COLUMN_File]` with custom extraction, it takes precedence
- **Default File behavior**: If no `[COLUMN_File]` defined, File column gets the full path automatically

### Column Extractor: `extract_all()`

```python
def extract_all(self, text: str, column_names: tuple[str, ...]) -> dict[str, str]:
    """Extract values for all requested columns."""
    result: dict[str, str] = {}
    
    # Sort rules by priority (highest first)
    sorted_rules = sorted(self._rules, key=lambda r: r.priority, reverse=True)
    
    for col_name in column_names:
        result[col_name] = ""  # Initialize with empty string
    
    # Apply each rule
    for rule in sorted_rules:
        if rule.name in result:  # Only extract if column is requested
            match = re.search(rule.pattern, text, re.IGNORECASE)
            if match:
                try:
                    extracted = match.group(rule.group)
                    result[rule.name] = extracted
                except IndexError:
                    result[rule.name] = rule.default
            elif rule.default:
                result[rule.name] = rule.default
    
    return result
```

**Extraction process:**
1. Initialize all requested columns with empty strings
2. Sort rules by priority (highest first)
3. For each rule, attempt regex match on the full path
4. If match found, extract the specified group
5. If no match and default is set, use default value
6. Return dictionary mapping column names to extracted values

---

## GUI Integration

### Treeview Construction

The GUI builds the Treeview based on `config.column_names`:

```python
# In gui/ui.py - MainWindowUI.build()
self.window._tree = ttk.Treeview(
    self.window._list_container,
    columns=self.window._config.column_names,
    show="headings",
    selectmode="browse",
    style="FileList.Treeview",
)

# Configure columns with widths
for i, (name, width) in enumerate(
    zip(
        self.window._config.column_names,
        self.window._config.column_widths,
        strict=True,
    )
):
    self.window._tree.heading(
        i,
        text=name,
        anchor=tk.W,
        command=lambda idx=i: self.window._sort_treeview(idx),
    )
    self.window._tree.column(i, width=width, minwidth=50, anchor=tk.W)
```

### Single Unified Scan Path

The GUI uses **one** scan path for every mode (the reader normalises
`column_names` to `("File",)` when no custom columns are configured):

```python
# In main_window._bg_scan_and_process()
processed_items = scanner.scan_and_process_dynamic(
    directory,
    extension=extension,
    filter_text=filter_text,
    recursive=recursive,
    column_names=self._config.column_names,
    columns=self._config.columns,
    config=self._config,
)
```

- **With custom columns** (`config.columns` is not empty): the extractor
  uses the configured regex rules and each row contains a `column_values`
  dict with all extracted values.
- **Without custom columns**: `column_names` is `("File",)` and the
  extractor has no rules, so rows carry the file path only.

Both cases populate the Treeview through the same `_insert_chunk()`,
which builds each row's values from `self._config.column_names`.

### Refreshing Column Configuration

When the user clicks the **🔄 Refresh** button, the GUI:

1. **Reloads configuration** from `.profiles` file
2. **Detects column changes** by comparing old vs new `column_names` and `column_widths`
3. **Recreates Treeview** with new column configuration
4. **Repopulates data** using the new column extraction rules

```python
# In main_window._on_refresh()
def _on_refresh(self) -> None:
    """Handle refresh button: reload config and refresh list."""
    try:
        fresh_config = load_config(self._config.config_path)
        
        # Check if column configuration changed
        columns_changed = (
            self._config.column_names != fresh_config.column_names
            or self._config.column_widths != fresh_config.column_widths
            or bool(self._config.columns) != bool(fresh_config.columns)
        )
        
        self._config = fresh_config
        
        # Reconfigure Treeview columns if configuration changed
        if columns_changed:
            self._reconfigure_treeview_columns()
        
        self._populate_directories()
        self._auto_select_directory()
        self._apply_config_overrides()
        self._configure_row_colors()
        
    except (FileNotFoundError, OSError) as exc:
        self._logger.error("Failed to reload configuration: %s", exc)
        messagebox.showerror("Configuration Error", f"Failed to reload configuration:\n{exc}")
```

---

## Best Practices

### 1. Choose Appropriate Priorities

```ini
# High priority (100) for File column
[COLUMN_File]
priority = 100

# Medium priority (20-30) for versions, projects
[COLUMN_Version]
priority = 20

[COLUMN_Project]
priority = 25

# Lower priority (5-15) for environments, types
[COLUMN_Type]
priority = 15

[COLUMN_Environment]
priority = 10
```

### 2. Use Default Values

```ini
[COLUMN_Device]
width = 120
expression = Device_([A-Z0-9]+)
group = 1
priority = 20
default = Unknown  # Prevents empty cells
```

### 3. Test Your Patterns

```python
import re

pattern = r"Device_([A-Z0-9]+)"
filename = "Device_ABC123_V01.mttl"

match = re.search(pattern, filename, re.IGNORECASE)
if match:
    print(match.group(1))  # Output: ABC123
```

### 4. Optimize Column Widths

```ini
[COLUMN_File]
width = 400  # Long paths

[COLUMN_Version]
width = 120  # Medium length

[COLUMN_Type]
width = 70   # Short codes
```

---

## Troubleshooting

### Column Shows Empty

**Possible causes:**
1. Regex pattern doesn't match your files
2. Wrong group number
3. Pattern syntax error

**Solution:**
- Test pattern with Python (see "Test Your Patterns" above)
- Verify `group` matches the correct capture group
- Simplify the pattern and test incrementally

### Wrong Values Extracted

**Cause:** Pattern captures too much or too little

**Solution:**
- Make pattern more specific
- Adjust `group` number if needed
- Use `group = 0` for full match

### File Column Disappears

**Cause:** `[COLUMN_File]` defined but pattern doesn't match

**Solution:**
```ini
[COLUMN_File]
width = 600
expression = .*
group = 0
priority = 100
```

Or remove `[COLUMN_File]` section to use default behavior.

---

## Related Documentation

- **[Column Library Guide](./column-library.md)** - 50+ ready-to-use column configurations
- **[Usage Guide (French)](./dynamic-columns-usage.md)** - Guide d'utilisation en français
- **[Advanced Guide](./advanced/advanced-guide.en.md)** - Advanced patterns and techniques

---

## Example Complete Configuration

```ini
[LAUNCHER]
title = MuTool Project Launcher
gui_auto_launch = Vrai
close_after_execute = Faux
theme = light
search_dir = \\st-pes-mtp\MuTEST\03-Production\01-Programmes
recursive_search = Vrai
extensions = mttl OR mttx -backup, mttl, mttx, All, .lnk
filters = , ST_PRO, ST_ENG, LOUVAIN, PESSAC, ULIS
search_exclude_dirs = .*, .git, __pycache__, bin, obj, tmp, Obsolete, Debug
row_colors = TMP:#757575

[COLUMN_File]
width = 60
expression = .*
group = 0
priority = 100

[COLUMN_FileName]
width = 200
expression = ([^/\\]+)\.[^.]+$
group = 1
priority = 90

[COLUMN_Type]
width = 70
expression = (PRO|ENG|DEV|TMP|DEBUG)(?!.*(PRO|ENG|DEV|TMP|DEBUG))
group = 1
priority = 15

[COLUMN_Version]
width = 120
expression = _V([^-]+-Rel[^\\/]+)
group = 1
priority = 20

[COLUMN_Site]
width = 100
expression = (LOUVAIN|PESSAC|ULIS)
group = 1
priority = 14

[CONFIGURATION_1]
match.hostname = ["*"]
scan = \\st-pes-mtp\MuTEST\03-Production\01-Programmes
extensions =
filters = -tmp
row_colors = ST_DEV:#C01565, ST_ENG:#C01565, ST_PRO:#1565C0
```
