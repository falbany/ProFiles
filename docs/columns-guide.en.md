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
| `match`      | String  | **Required**              | Built-in keyword (`version`, `date`, `git_commit`, `type`, `filename`, `extension`, `path`, `size`, `size_bytes`, `modified`, `created`) or a raw regex pattern. |
| `transform`  | String  | `None`                    | Replacement pattern with group backreferences. Supports `{group:N}` (e.g. `v{group:1}`) or standard `\g<N>` / `\N` syntax. Falls back to the whole match if omitted. For `modified`/`created`, `transform` is a strftime pattern (default `%Y-%m-%d %H:%M:%S`, local time); it is ignored for `path`. |
| `priority`   | Integer | `0`                       | Order of extraction evaluation (higher numbers are evaluated first).                   |
| `default`    | String  | `""`                      | Fallback value displayed if the pattern does not match.                                |

### Transform Backreference Syntax

The `transform` field supports two equivalent backreference syntaxes:

| Syntax       | Example              | Description                          |
| ------------ | -------------------- | ------------------------------------ |
| `{group:N}`  | `v{group:1}`         | User-friendly syntax (recommended).    |
| `\g<N>`      | `v\g<1>`             | Standard Python regex syntax.        |
| `\N`         | `v\1`                | Shorthand for `\g<N>`.               |

The `{group:N}` syntax is translated to `\g<N>` internally before calling
`re.Pattern.expand()`, so all three forms are equivalent.

---

## Built-in Pattern Macros

Instead of writing a custom regex, you can use a **built-in keyword** as the
`match` value. Keywords are matched case-insensitively. If the `match` value
doesn't match a keyword, it's treated as a raw regex pattern.

| Keyword       | Regex Pattern                                           | Extracts                          |
| ------------- | ------------------------------------------------------- | --------------------------------- |
| `version`     | `[-_]V(\d+(?:\.\d+)*)(?=[^\\/]*\.[a-zA-Z0-9]+$)`       | Version number after `_V` or `-V` |
| `date`        | `(\d{4}[-_]\d{2}[-_]\d{2}\|\d{8})`                      | ISO date or YYYYMMDD              |
| `git_commit`  | `_g([a-f0-9]{7})`                                       | Short git commit hash             |
| `type`        | `(PRO\|ENG\|DEV\|TMP\|DEBUG)(?!.*(?:PRO\|ENG\|DEV\|TMP\|DEBUG))` | Last environment type tag       |
| `filename`    | `([^/\\]+)$`                                            | Filename without directory path   |
| `extension`   | `\.([^./\\]+)$`                                         | File extension (without dot)      |

### File Attribute and Path Keywords

Five keywords are not regexes: four resolve from a per-file `stat` snapshot and one
from the display path itself. Like the macros above, they are matched
case-insensitively in the `match` field.

| Keyword       | Extracts                                                                 | Example               |
| ------------- | ------------------------------------------------------------------------ | --------------------- |
| `size`        | Human-readable size, binary base (1 KB = 1024 B); exact bytes below 1 KB | `12.4 MB`, `512 B`    |
| `size_bytes`  | Raw byte count (integer)                                                 | `13002394`            |
| `modified`    | Last-modified time; `transform` is a strftime pattern (default `%Y-%m-%d %H:%M:%S`, local time) | `2026-11-25 14:03:07` |
| `created`     | Creation time (on Linux, falls back to the inode-change time)            | `2026-11-25 09:41:22` |
| `path`        | Containing directory of the display path (`transform` is ignored)        | `subdir` (`.` at the scan root) |

> **Performance note** — the four attribute keywords cost one `stat` per file,
> executed in the parallel worker pool, and only when such a column is configured
> (or the filter query carries attribute operators). `path` is string-derived and
> never triggers a stat. A configuration with no attribute column and no attribute
> operator in the filter performs zero stats.

```yaml
columns:
  Size:
    name: Size
    width: 110
    stretch: false
    match: size              # attribute keyword — human-readable size
    priority: 20

  Modified:
    name: Modified
    width: 150
    stretch: false
    match: modified          # transform = strftime pattern (local time)
    transform: "%Y-%m-%d %H:%M"
    priority: 10
```

### Using Built-in Macros

```yaml
columns:
  Version:
    name: Version
    width: 100
    stretch: false
    match: version           # built-in keyword
    transform: "{group:1}"
    priority: 10

  Date:
    name: Date
    width: 120
    stretch: false
    match: date              # built-in keyword
    transform: "{group:1}"
    priority: 15

  Commit:
    name: Commit
    width: 100
    stretch: false
    match: git_commit        # built-in keyword
    transform: "{group:1}"
    priority: 20
```

---

## Filtering with Attribute Operators

The **Filter** field (and the web UI filter bar) accepts attribute operators built
on the same keys as the keyword table above: `size`, `size_bytes` (aliases — same
bytes), `modified` and `created`. Keys and units are **case-insensitive**
(`SIZE:>10MB`). A token shaped `key:value` with a parseable value is evaluated
against the file's attributes; everything else — quoted phrases and malformed
operators included — falls back to the plain substring grammar documented in the
[configuration reference](./configuration-profile.en.md#search-operators). There is
deliberately no `path` key: plain terms already substring-match the display path.

### Comparison Forms

| Expression               | Meaning                                                                        |
| ------------------------ | ------------------------------------------------------------------------------ |
| `size:>10mb`             | Size strictly greater than 10 MB (binary units)                                |
| `size:<500kb`            | Size strictly less than 500 KB                                                 |
| `size:1048576`           | Size equal to the operand (bare magnitude = equality)                          |
| `size:1kb..1mb`          | Size range — inclusive on both ends                                            |
| `modified:>2026-11-01`   | Modified on or after the local midnight of that date (Nov 1 files match)       |
| `modified:<2026-11-01`   | Modified strictly before that local midnight (the whole day is excluded)       |
| `modified:2026-11-01`    | Modified during that local day (bare date)                                     |
| `modified:today`         | Modified during the local day of evaluation                                    |
| `modified:<7d`           | Modified **within the last 7 days** (recent files)                             |
| `modified:>7d`           | Modified **more than 7 days ago** (older files)                                |
| `modified:1d..7d`        | File age between 1 and 7 days — inclusive                                      |
| `created:…`              | Same grammar as `modified`, applied to the creation time                       |
| `-size:>10mb`            | Negation — flips the operator's outcome                                        |
| `"size:>10mb"`           | Quoted — literal substring, never an operator                                  |

> **⚠️ Duration reading (GNU-find style)** — a duration bounds the file's **age**,
> not its timestamp. The comparison direction is inverted compared to a naive
> reading of the timestamp:
>
> - `modified:<7d` = age **less** than 7 days = modified **within the last 7 days** (recent files)
> - `modified:>7d` = age **greater** than 7 days = modified **more than 7 days ago** (old files)

### Operands

| Kind     | Syntax                | Notes                                                                                                                                             |
| -------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Size     | `10`, `10mb`, `1.5kb` | Binary units `b` `kb` `mb` `gb` `tb` (1 KB = 1024 B); a plain number is bytes; decimals allowed and floored to whole bytes                         |
| Duration | `7d`, `12h`, `0.5w`   | Units `s` `m` `h` `d` `w` (seconds, minutes, hours, days, weeks); decimals floored (`<0.5d` = 12 hours)                                            |
| Date     | `2026-11-01`, `today` | `YYYY-MM-DD` in local time; a date denotes its local midnight; `today` anchors to the local midnight of evaluation                                 |
| Range    | `a..b` (no spaces)    | Inclusive at the named granularity: bytes for sizes, whole days for dates, ages for durations; each side resolves independently by its own kind (a date and a duration may be mixed), but mixing size with a date/duration side is invalid |

### Fallback and Composition

- **Fallback**: malformed operators are not errors — `size:abc`, a size operand on a
  time key (`modified:>10mb`), a bare duration (`modified:7d`) or a broken range
  (`1..2..3`) are matched as literal substrings, exactly like any plain term.
- **Composition** follows the Google-style grammar: a space is an implicit AND, `OR`
  separates alternatives, `-term` excludes and `+term` forces inclusion.
- **Clock**: date and duration comparisons read the clock **at evaluation time**, so
  `today` and `<7d` stay honest in a long-lived session.
- **Cost**: a filter carrying at least one attribute operator makes the scan perform
  one `stat` per candidate file (in the parallel worker pool); a filter without
  attribute operators never stats.
- **Parity**: the web UI filter bar implements the identical grammar (both parsers
  are tested against the same shared fixtures).

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

Given filenames containing version tags like `_V1.0.2-beta`:

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
    match:
      hostname: ["*"]
    scan: .
    extensions: [.mttl]
```

---

## Troubleshooting & Tips

- **YAML Format Only**: Configuration is fully YAML-based (`.profiles`). Ensure proper indentation and syntax.
- **Regex on Full Path**: Regular expressions are matched against the _full path_ of the file, allowing you to extract folder names or drive letters if needed.
- **Refresh GUI**: After modifying `.profiles`, click the **🔄 Refresh** button in the app or press `Ctrl+R` to reload the configuration and apply new columns.
- **Missing Column**: Ensure your capture group `()` correctly matches the expected pattern; otherwise, the `default` value will be shown.
