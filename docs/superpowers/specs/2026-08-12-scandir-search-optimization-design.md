# Design Spec: Low-Level `os.scandir` File Search Performance Optimization

**Date:** 2026-08-12  
**Status:** Approved  

---

## 🎯 Goal
Improve directory scanning and file search speed across macOS, Windows, and Linux by refactoring directory traversal in `profiles.utils.file_utils` to use Python stdlib `os.scandir` rather than `Path.iterdir()` / `Path.glob()`.

---

## 🏗️ Architecture & Changes

### Component: `src/profiles/utils/file_utils.py`

1. **`_matches_extension_str(name: str, ext_lower: str) -> bool`**:
   * Pure string-based extension matching on entry/file names (supporting single and compound extensions like `.mttx.lnk`).
   * Avoids constructing `Path` objects prior to extension filtering.

2. **`_scan_subtree(root: Path | str, ...)`**:
   * Uses `with os.scandir(root) as entries:` context manager for prompt directory stream handle cleanup.
   * Leverages `entry.is_dir(follow_symlinks=False)` and `entry.is_file(follow_symlinks=False)` cached filesystem entry flags without triggering extra `stat()` system calls.
   * Filters directory and file exclusions (`_is_excluded`) directly against `entry.name`.
   * Instantiates `Path(entry.path)` *only* for entries that pass all filters.
   * Catches `PermissionError` and `OSError` cleanly.

3. **`scan_directory(...)`**:
   * **Non-recursive pass**: Replaces `Path.iterdir()` / `Path.glob()` with `os.scandir()`. Filters `entry.name` directly, returning sorted `list[Path]`.
   * **Recursive pass**: Replaces initial directory top-level collection loop with `os.scandir()`. Dispatches subdirectories to the thread pool as before.

---

## 🛡️ Cross-OS & Platform Safety
* **macOS / Linux**: Uses directory stream `d_type` information directly from kernel directory listing buffers.
* **Windows**: Uses Win32 `FindFirstFile` / `FindNextFile` flags cached in `DirEntry`.
* **Robustness**: Always uses `with os.scandir(...)` to prevent file descriptor leaks.

---

## 🧪 Verification Plan

1. Run existing test suite:
   ```bash
   pytest tests/utils/test_file_utils.py tests/core/processing/test_scanner.py --no-cov
   ```
2. Verify all 132 scanner and file utility unit tests pass with zero regressions.
