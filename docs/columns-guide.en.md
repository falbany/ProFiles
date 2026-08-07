# Dynamic Column Configuration

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.en.md)** |
> ⚙️ **[Configuration](./configuration-profile.en.md)** |
> 🔧 **[Hooks](./hooks-guide.en.md)** | 
> 📊 **Dynamic Columns** |
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

---

## Overview

ProFiles supports **dynamic column extraction** via the `columns:` mapping in your YAML configuration file (`.profiles`). This allows you to automatically extract custom metadata from your filenames and display them in dedicated columns in the GUI.

---

## Configuration Reference

Each column is defined under the `columns:` block with the following parameters:

| Parameter    | Type    | Default                   | Description                                                                            |
| ------------ | ------- | ------------------------- | -------------------------------------------------------------------------------------- |
| `name`       | String  | *(falls back to key)*     | Friendly header label displayed in the GUI column heading.                             |
| `width`      | Integer | `150` (or `600` for File) | Width of the column in pixels (used when `stretch` is `false`).                        |
| `stretch`    | Boolean | `false`                   | Whether the column stretches to fill available space in the Treeview.                    |
| `match`      | String  | **Required**              | Built-in keyword (`version`, `date`, `git_commit`, `type`, `filename`, `extension`) or a raw regex pattern. |
| `transform`  | String  | `None`                    | Replacement pattern with `{group:N}` backreferences (e.g. `v{group:1}`). Falls back to the whole match if omitted. |
| `priority`   | Integer | `0`                       | Order of extraction evaluation (higher numbers are evaluated first).                   |
| `default`    | String  | `""`                      | Fallback value displayed if the pattern does not match.                                |

---

## Step-by-Step Examples

### 1. Extracting Device Codes

Given filenames formatted as:

```text
Device_ABC123_V01.mttl
Device_XYZ789_V02.mttl
```

Add this to your YAML configuration file:

```yaml
columns:
  Device:
    name: Device
    width: 120
    stretch: false
    match: "Device_([A-Z0-9]+)"
    transform: "{group:1}"
    priority: 10
    default: "Unknown"
```

### 2. Extracting Versions

Given filenames containing version tags like `_V01-Rel6.2.1`:

```yaml
columns:
  Version:
    name: Version
    width: 150
    stretch: false
    match: '_V([^\\/]+)'
    transform: "{group:1}"
    priority: 20
```

---

## Complete YAML Configuration Example

```yaml
defaults:
  title: ProFiles Launcher
  search_dir: .
  extensions: [.mttl, .exe]

columns:
  File:
    name: File
    width: 400
    stretch: true
    match: ".*"
    transform: "{group:0}"
    priority: 100

  Device:
    name: Device
    width: 120
    stretch: false
    match: "Device_([A-Z0-9]+)"
    transform: "{group:1}"
    priority: 15
    default: "N/A"

  Version:
    name: Version
    width: 130
    stretch: false
    match: "_V([^-]+)"
    transform: "{group:1}"
    priority: 20
    default: "Latest"

configs:
  configuration_1:
    pc_hostname: All
    directory: .
    extensions: [.mttl]
```

---

## Troubleshooting & Tips

- **YAML Format Only**: Configuration is fully YAML-based (`.profiles`). Ensure proper indentation and syntax.
- **Regex on Full Path**: Regular expressions are matched against the _full path_ of the file, allowing you to extract folder names or drive letters if needed.
- **Refresh GUI**: After modifying `.profiles`, click the **🔄 Refresh** button in the app or press `Ctrl+R` to reload the configuration and apply new columns.
- **Missing Column**: Ensure your capture group `()` correctly matches the expected pattern; otherwise, the `default` value will be shown.
