# ProFiles Advanced Guide

> 🏠 **[Documentation Home](../README.md)** |
> 📦 **[Installation](../installation-guide.en.md)** |
> ⚙️ **[Configuration](../configuration-profile.en.md)** |
> 🔧 **[Hooks](../hooks-guide.en.md)** |
> 📊 **[Dynamic Columns](../columns-guide.en.md)** |
> 🚀 **Advanced Guide** |
> 🇫🇷 **[Version Française](./guide-avance.fr.md)**

---

This guide covers advanced usage patterns, automation, and custom front-end development for ProFiles.

## Table of Contents

- [Headless Mode for Automation](#headless-mode-for-automation)
- [Custom Front-Ends](#custom-front-ends)
- [Programmatic API Usage](#programmatic-api-usage)
- [Performance Tuning](#performance-tuning)
- [Integration Patterns](#integration-patterns)

---

## Headless Mode for Automation

ProFiles can run without a GUI for automated workflows and scripting.

### Basic Usage

```bash
# Run in headless mode
python -m profiles --headless

# With specific configuration file
python -m profiles --headless --config /path/to/.profiles
```

### Use Cases

- **CI/CD pipelines**: Automate file launching in build processes
- **Scheduled tasks**: Run periodic scans or launches
- **Batch processing**: Process multiple files programmatically
- **Remote execution**: Run on servers without display capabilities

---

## Custom Front-Ends

ProFiles's architecture separates core logic from the presentation layer, enabling custom front-ends.

### Architecture Overview

```
┌─────────────────────────────────────────┐
│         Front-End Layer                 │
│  (GUI / CLI / TUI / Web / Custom)       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Core Layer                      │
│  (profiles.core.*)                      │
│  ├── config/       # models, service,   │
│  │                 # loader, reader, io  │
│  ├── environment/  # system, execution  │
│  │                 # (launch hooks)     │
│  ├── processing/   # scanner,           │
│  │                 # column_extractor   │
│  ├── telemetry/    # diagnostics        │
│  └── actions.py                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│         Utils Layer                      │
│  (profiles.utils.*)                     │
│  - file_utils.py                        │
│  - network.py                           │
│  - search_parser.py                     │
│  - shortcut.py                          │
└─────────────────────────────────────────┘
```

### Creating a CLI Front-End

```python
#!/usr/bin/env python3
"""Simple CLI front-end for ProFiles."""

import argparse
import sys
from profiles.core import load_config, scan_and_process, launch_selected_file, ActionStatus
from profiles.core.config import auto_select_directory


def main():
    parser = argparse.ArgumentParser(description="ProFiles CLI")
    parser.add_argument("--directory", type=str, help="Directory to scan")
    parser.add_argument("--extension", type=str, default=".lnk", help="File extension")
    parser.add_argument("--filter", type=str, default="", help="Filter text")
    parser.add_argument("--recursive", action="store_true", help="Recursive scan")
    parser.add_argument("--launch", type=str, help="Launch specific file by name")
    parser.add_argument("--config", type=str, help="Configuration file path")

    args = parser.parse_args()

    # Load configuration (auto-searches folder tree if path is None)
    config = load_config(args.config)

    # Determine directory
    directory = args.directory or auto_select_directory(config, None)

    if args.launch:
        # Launch a specific file
        result = launch_selected_file(
            directory=directory,
            filename=args.launch,
            release=config.release,
            username="cli",
        )
        print(f"Launch result: {result.status}")
        return 0 if result.status == ActionStatus.SUCCESS else 1
    else:
        # Scan and display results
        results = scan_and_process(
            directory=directory,
            extension=args.extension,
            recursive=args.recursive,
            filter_text=args.filter,
        )

        print(f"Found {len(results)} files:")
        for file in results:
            print(f"  {file.filename} - {file.version}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

> **Note**: `profiles.core` re-exports the public API. You can also import from the sub-packages directly: `profiles.core.processing.scanner`, `profiles.core.config.service`, `profiles.core.actions`, etc.

### Creating a Web Front-End

```python
from flask import Flask, jsonify, request
from profiles.core import scan_and_process, launch_selected_file, ActionStatus

app = Flask(__name__)


@app.route("/scan", methods=["GET"])
def scan():
    """Scan directory and return results."""
    directory = request.args.get("directory", "/path/to/dir")
    extension = request.args.get("extension", ".lnk")
    recursive = request.args.get("recursive", "false").lower() == "true"

    results = scan_and_process(
        directory=directory,
        extension=extension,
        recursive=recursive,
        filter_text="",
    )

    return jsonify([{
        "filename": f.filename,
        "version": f.version,
        "path": f.path
    } for f in results])


@app.route("/launch", methods=["POST"])
def launch():
    """Launch a file."""
    data = request.json
    result = launch_selected_file(
        directory=data["directory"],
        filename=data["filename"],
        release=data.get("release", "v1.0"),
        username=data.get("username", "web"),
    )

    return jsonify({
        "status": result.status.value,
        "message": result.message,
        "path": result.path,
    })


if __name__ == "__main__":
    app.run(debug=True)
```

---

## Programmatic API Usage

### Core Module Imports

The `profiles.core` package re-exports the full public API. You can import from it directly, or from the sub-packages for finer control:

```python
# Top-level convenience (recommended for most use cases)
from profiles.core import (
    # Scanner
    scan_and_process,
    ScannedFile,
    ScannedFileDynamic,
    is_simple_extension,
    # Config
    AppConfig,
    MachineConfiguration,
    ColumnConfiguration,
    load_config,
    auto_select_directory,
    find_active_config,
    merge_config_overrides,
    get_unique_directories,
    # Actions
    launch_selected_file,
    open_config_file,
    open_log_file,
    ActionResult,
    ActionStatus,
    # System info
    SystemInfo,
    collect_system_info,
    # Launch hooks
    HookOutcome,
    parse_hook_entries,
    run_hooks_for_file,
)

# Direct sub-package imports (for fine-grained control)
from profiles.core.processing.scanner import scan_and_process, ScannedFile
from profiles.core.processing.column_extractor import ColumnExtractor, ColumnRule
from profiles.core.config.service import auto_select_directory, find_active_config
from profiles.core.config.models import AppConfig, MachineConfiguration
from profiles.core.config.loader import load_config
from profiles.core.actions import launch_selected_file, ActionStatus, ActionResult
from profiles.core.environment.system import collect_system_info, SystemInfo
from profiles.core.telemetry.diagnostics import get_logger, configure_logger
```

### Example: Batch File Processing

```python
from profiles.core import scan_and_process, launch_selected_file, ActionStatus


def process_all_files(directory, extension=".lnk"):
    """Scan and launch all matching files."""
    results = scan_and_process(
        directory=directory,
        extension=extension,
        recursive=True,
        filter_text="",
    )

    success_count = 0
    for file in results:
        result = launch_selected_file(
            directory=directory,
            filename=file.filename,
            release="v1.0",
            username="batch",
        )

        if result.status == ActionStatus.SUCCESS:
            success_count += 1
            print(f"✓ Launched: {file.filename}")
        else:
            print(f"✗ Failed: {file.filename} - {result.message}")

    print(f"\nCompleted: {success_count}/{len(results)} successful")
    return success_count == len(results)
```

### Example: Custom Filter Pipeline

```python
from profiles.core import scan_and_process


def advanced_scan(directory, extension, min_version=None, exclude_patterns=None):
    """Scan with additional filtering logic."""
    results = scan_and_process(
        directory=directory,
        extension=extension,
        recursive=True,
        filter_text="",
    )

    filtered = []
    for file in results:
        # Filter by version
        if min_version and file.version < min_version:
            continue

        # Filter by exclusion patterns
        if exclude_patterns:
            if any(pattern in file.filename for pattern in exclude_patterns):
                continue

        filtered.append(file)

    return filtered


# Usage
files = advanced_scan(
    directory="/path/to/dir",
    extension=".lnk",
    min_version="v2.0",
    exclude_patterns=["backup", "temp", "old"],
)
```

---

## Performance Tuning

### Optimizing Large Scans

For directories with >10,000 files:

1. **Use selective extensions**:
   ```python
   results = scan_and_process(
       directory="/large/directory",
       extension=".lnk",  # Specific extension
       recursive=True,
       filter_text="",
   )
   ```

2. **Exclude common large directories**:
   ```ini
   [LAUNCHER]
   search_exclude_dirs = .git, node_modules, __pycache__, build, dist
   ```

3. **Use non-recursive mode initially**:
   ```python
   # First pass: non-recursive
   results = scan_and_process(
       directory="/path",
       extension=".lnk",
       recursive=False,
       filter_text="",
   )

   # Second pass: recursive only if needed
   if len(results) < expected_min:
       results = scan_and_process(
           directory="/path",
           extension=".lnk",
           recursive=True,
           filter_text="",
       )
   ```

### Memory Management

ProFiles uses chunked insertion for large file lists. For custom front-ends:

```python
from profiles.core import scan_and_process


def scan_with_pagination(directory, extension, page_size=100):
    """Scan with pagination support."""
    all_results = scan_and_process(
        directory=directory,
        extension=extension,
        recursive=True,
        filter_text="",
    )

    # Return paginated results
    total_pages = (len(all_results) + page_size - 1) // page_size

    def get_page(page_num):
        start = page_num * page_size
        end = start + page_size
        return all_results[start:end], total_pages

    return get_page
```

---

## Integration Patterns

### CI/CD Integration

```python
#!/usr/bin/env python3
"""CI/CD integration script."""

import sys
from profiles.core import scan_and_process


def ci_cd_validate(directory, extension, required_files):
    """Validate that required files exist in directory."""
    results = scan_and_process(
        directory=directory,
        extension=extension,
        recursive=False,
        filter_text="",
    )

    filenames = {f.filename for f in results}
    missing = set(required_files) - filenames

    if missing:
        print(f"ERROR: Missing required files: {missing}")
        return False

    print(f"✓ All {len(required_files)} required files present")
    return True


if __name__ == "__main__":
    # Example: Validate build artifacts
    required = ["build.exe", "config.json", "README.md"]
    success = ci_cd_validate("/build/output", ".exe", required)
    sys.exit(0 if success else 1)
```

### Logging Integration

```python
from profiles.core import collect_system_info
from profiles.core.telemetry.diagnostics import get_logger, configure_logger


def setup_audit_logging():
    """Setup audit logging for compliance."""
    info = collect_system_info()
    logger = configure_logger(
        log_path="audit.log",
        source=f"automation-{info.hostname}",
        level="INFO",
    )

    return logger


def log_launch_event(filename, username, success):
    """Log file launch event."""
    logger = setup_audit_logging()

    if success:
        logger.info(f"File launched: {filename} by {username}")
    else:
        logger.warning(f"Launch failed: {filename} by {username}")
```

### Monitoring Integration

```python
from profiles.core import scan_and_process
import time


def monitor_directory(directory, extension, interval=60):
    """Monitor directory for changes."""
    previous_files = set()

    while True:
        results = scan_and_process(
            directory=directory,
            extension=extension,
            recursive=False,
            filter_text="",
        )
        
        current_files = {f.filename for f in results}
        
        # Detect new files
        new_files = current_files - previous_files
        if new_files:
            print(f"New files detected: {new_files}")
        
        # Detect removed files
        removed_files = previous_files - current_files
        if removed_files:
            print(f"Files removed: {removed_files}")
        
        previous_files = current_files
        time.sleep(interval)
```

---

## Best Practices

### Error Handling

```python
from profiles.core import launch_selected_file, ActionStatus


def safe_launch(directory, filename):
    """Launch with comprehensive error handling."""
    try:
        result = launch_selected_file(
            directory=directory,
            filename=filename,
            release="v1.0",
            username="system"
        )

        if result.status == ActionStatus.SUCCESS:
            return True, "Success"
        elif result.status == ActionStatus.NOT_FOUND:
            return False, f"File not found: {filename}"
        elif result.status == ActionStatus.FAILED:
            return False, f"Launch failed: {result.message}"
        else:
            return False, f"Unknown status: {result.status}"

    except Exception as e:
        return False, f"Exception: {str(e)}"
```

### Configuration Validation

```python
from profiles.core import auto_select_directory


def validate_configuration(hostname, expected_directory):
    """Validate configuration before use."""
    selected = auto_select_directory(None, hostname)
    
    if not selected:
        return False, "No configuration found for hostname"
    
    if selected != expected_directory:
        return False, f"Directory mismatch: {selected} != {expected_directory}"
    
    return True, "Configuration valid"
```

---

## Troubleshooting

### Issue: Headless mode not finding configuration

**Solution**: Explicitly specify configuration path:

```bash
python -m profiles --headless --config /absolute/path/.profiles
```

### Issue: Custom front-end import errors

**Solution**: Ensure `src/` is in Python path:

```python
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from profiles.core.scanner import scan_and_process
```

### Issue: Performance degradation with large directories

**Solution**: Implement pagination or filtering:

```python
# Use filter to reduce result set
results = scan_and_process(
    directory="/large/dir",
    extension=".lnk",
    recursive=True,
    filter_text="production"  # Narrow down results
)
```

---

## Resources

- **Core API**: See `src/profiles/core/` for module documentation
- **Architecture**: See `AGENTS.md` for layered architecture details
- **Tests**: See `tests/test_core_*` for usage examples
- **Configuration**: See [configuration-pylaunch.en.md](../configuration-pylaunch.en.md)

---

*Last updated: 2026-07-13*
