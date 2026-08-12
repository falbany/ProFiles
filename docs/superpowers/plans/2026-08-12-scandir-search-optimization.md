# Implementation Plan: Low-Level `os.scandir` File Search Optimization

**Spec:** `docs/superpowers/specs/2026-08-12-scandir-search-optimization-design.md`  
**Goal:** Refactor directory traversing functions in `src/profiles/utils/file_utils.py` to use `os.scandir` for faster multi-OS directory scans without breaking any existing behavior or public function signatures.

---

### Task 1: Refactor `_matches_extension` to support raw strings and `Path` objects

**File:** `src/profiles/utils/file_utils.py`

* Replace or overload `_matches_extension(file: Path | str, ext_lower: str)` so it can extract suffixes from plain string paths as well as `Path` objects without creating `Path` instances unnecessarily.
* Add helper `_full_suffix_str(filename: str) -> str` or optimize string suffix slicing.

```python
def _full_suffix_str(name: str) -> str:
    """Extract compound suffix (e.g. '.mttx.lnk') from string filename."""
    pos = name.find(".")
    return name[pos:] if pos != -1 else ""
```

---

### Task 2: Refactor `_scan_subtree` using `os.scandir`

**File:** `src/profiles/utils/file_utils.py`

* Refactor `_scan_subtree` to use `with os.scandir(root) as entries:` loop.
* Filter directory exclusions and recurse using `entry.is_dir(follow_symlinks=False)`.
* Filter file extensions and file exclusions using `entry.is_file(follow_symlinks=False)` and string matching before creating `Path(entry.path)`.
* Wrap in `try...except (PermissionError, OSError): pass`.

---

### Task 3: Refactor `scan_directory` using `os.scandir`

**File:** `src/profiles/utils/file_utils.py`

* **Non-recursive pass**: Refactor to scan with `with os.scandir(scan_path) as entries:` directly.
* **Recursive pass**: Refactor top-level collection of subdirectories and root files to use `with os.scandir(scan_path) as entries:`.

---

### Task 4: Run test suite & verify performance

**Command:**
```bash
pytest tests/utils/test_file_utils.py tests/core/processing/test_scanner.py --no-cov -v
```

* Ensure all 132 tests pass.
* Measure scan speed on workspace directory tree.
