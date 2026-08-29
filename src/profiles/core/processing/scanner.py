"""File scanning and processing pipeline.

Extracted from ``profiles.gui.main_window`` so that the same scanning
and filtering logic is available to CLI and future TUI front-ends.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import logging
import os
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import NamedTuple, TypeVar

from profiles.core.config.models import AppConfig
from profiles.core.processing.column_extractor import ColumnExtractor
from profiles.core.processing.file_classifier import (
    _build_column_extractor,
    _strip_extension_from_version,
    get_file_info,
)
from profiles.core.telemetry import events as _events
from profiles.core.telemetry.metrics import ScanTimer
from profiles.utils.file_utils import scan_directory
from profiles.utils.search_parser import match_filter, tokenize

# Thread pool configuration for parallel file processing
_MAX_PROCESSING_WORKERS = min(32, (os.cpu_count() or 1) * 2)

# Files at/above this count are processed through the thread pool.
_PARALLEL_THRESHOLD = 100

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ScannedFile(NamedTuple):
    """A processed and filtered file entry ready for display / launch."""

    filename: str
    version: str
    path: Path


class ScannedFileDynamic(NamedTuple):
    """A processed and filtered file entry with dynamic column values.

    Attributes:
        path: Full filesystem path to the file.
        column_values: Dictionary mapping column names to extracted values.
        rel_path: Path relative to the scanned directory (for global search).
    """

    path: Path
    column_values: dict[str, str]
    rel_path: str = ""


def is_simple_extension(ext: str) -> bool:
    """Check whether *ext* is a simple extension (no search operators).

    A "simple" extension is plain text without ``OR``, ``-``, ``+``, or
    implicit-AND (space) operators.  Quoted strings that resolve to one
    token are also considered simple.
    """
    stripped = ext.strip()
    if not stripped or stripped.lower() == "all":
        return True
    tokens = tokenize(stripped)
    if len(tokens) != 1:
        return False
    token = tokens[0]
    return not (token.startswith("-") or token.startswith("+"))


def _passes_extension_filter(
    full_suffix: str,
    extension: str,
    ext_stripped: str,
) -> bool:
    """Check whether *full_suffix* passes the extension filter.

    Returns ``True`` when the file should be **kept** (i.e. the filter
    does not reject it).  An empty / ``"All"`` extension always passes.
    """
    return not (
        ext_stripped and ext_stripped.lower() != "all" and not match_filter(full_suffix, extension)
    )


def _scan_and_filter(
    directories: Sequence[str] | str,
    *,
    extension: str = "",
    filter_text: str = "",
    recursive: bool = False,
    exclude_dirs: Sequence[str] | None = None,
    exclude_files: Sequence[str] | None = None,
) -> Iterator[tuple[Path, str, str]]:
    """Shared scanning + filtering generator used by all ``scan_*`` functions.

    Yields ``(file_path, display_path, full_suffix)`` for every file
    that passes both the extension and keyword filters.

    Args:
        directories: Filesystem path(s) to scan.
        extension: Extension filter expression (supports operators).
        filter_text: Keyword filter expression (supports operators).
        recursive: Whether to descend into subdirectories.
        exclude_dirs: Directory names to skip during recursion.
        exclude_files: File name glob patterns to skip during scanning.

    Yields:
        Tuples of (absolute Path, display path str, full suffix str).
        When multiple directories are provided, files are deduplicated by their absolute path (so identical files reached via different paths will only be yielded once).
    """
    if isinstance(directories, str):
        directory_list = [directories]
    else:
        directory_list = list(directories)

    ext_stripped = extension.strip()
    seen_paths: set[str] = set()

    for directory in directory_list:
        if not directory:
            continue
        try:
            base_path = Path(directory)
            files = scan_directory(
                directory,
                "",
                recursive=recursive,
                exclude_dirs=tuple(exclude_dirs) if exclude_dirs else (),
                exclude_files=tuple(exclude_files) if exclude_files else (),
            )
            for file_path in files:
                abs_path = str(file_path.resolve())
                if abs_path in seen_paths:
                    continue
                seen_paths.add(abs_path)

                full_suffix = "".join(file_path.suffixes)

                if not _passes_extension_filter(full_suffix, extension, ext_stripped):
                    continue

                display_path = _compute_display_path(file_path, base_path)

                if filter_text and not match_filter(display_path, filter_text):
                    continue

                yield file_path, display_path, full_suffix
        except Exception as e:
            _events.scan_failed(logger, directory=directory, error=str(e))


def _compute_display_path(file_path: Path, base_path: Path) -> str:
    """Compute the display path relative to *base_path*.

    Falls back to the absolute path when the file is outside *base_path*.
    """
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        return str(file_path)


def _process_file(file_path: Path, display_path: str, full_suffix: str) -> ScannedFile:
    """Process a single file (thread-safe worker).

    Args:
        file_path: Absolute path to the file.
        display_path: Path for display (relative to scan directory).
        full_suffix: Full file suffix (e.g. ``".mttx.lnk"``) used for
            version extraction.

    Returns:
        ScannedFile with filename (display path) and version.
    """
    _, version = get_file_info(file_path, full_suffix.lstrip("."))
    return ScannedFile(display_path, version, file_path)


def _process_file_dynamic(
    file_path: Path,
    display_path: str,
    extractor: ColumnExtractor,
    column_names: tuple[str, ...],
    extension: str,
) -> ScannedFileDynamic:
    """Process a single file for dynamic columns (thread-safe worker).

    Args:
        file_path: Absolute path to the file.
        display_path: Path for display (relative to scan directory).
        extractor: Pre-built ColumnExtractor instance.
        column_names: Ordered list of column names to extract.
        extension: File extension for version stripping.

    Returns:
        ScannedFileDynamic with extracted column values.
    """
    full_path_str = str(display_path)
    column_values = extractor.extract_all(full_path_str, column_names)

    # File column always gets the full path
    if "File" in column_names and "File" not in column_values:
        column_values["File"] = full_path_str

    # Strip extension from Version if present
    if "Version" in column_values and extension:
        column_values["Version"] = _strip_extension_from_version(
            column_values["Version"], extension
        )

    return ScannedFileDynamic(file_path, column_values, display_path)


def _metrics_enabled(log_metrics: bool, config: AppConfig | None) -> bool:
    """Return whether scan metrics should be collected and logged."""
    return log_metrics or (config is not None and config.scan_metrics)


def _run_scan_pipeline(
    directories: Sequence[str] | str,
    *,
    extension: str,
    filter_text: str,
    recursive: bool,
    exclude_dirs: Sequence[str] | None,
    exclude_files: Sequence[str] | None,
    enable_metrics: bool,
    worker: Callable[[Path, str, str], T],
) -> list[T]:
    """Shared scan → filter → process orchestration for all ``scan_*`` functions.

    Collects candidate files via ``_scan_and_filter``, dispatches them to
    ``_process_files_sequential`` below ``_PARALLEL_THRESHOLD`` files or to
    ``_process_files_parallel`` at/above it, and wraps the whole pipeline
    in the performance timer when metrics are enabled. Per-file failures
    are logged and skipped (never fatal) with identical semantics on both
    processing paths, and reported through ``ScanMetrics.error_count``.

    Args:
        directories: Filesystem path(s) to scan.
        extension: Extension filter expression (supports operators).
        filter_text: Keyword filter expression (supports operators).
        recursive: Whether to descend into subdirectories.
        exclude_dirs: Directory names to skip during recursion.
        exclude_files: File name glob patterns to skip during scanning.
        enable_metrics: If True, time the scan and log DEBUG metrics.
        worker: Per-file processor ``(file_path, display_path, full_suffix) -> T``.

    Returns:
        Processed results in scan order (failing files are skipped).
    """
    if isinstance(directories, str):
        first_dir = directories
    else:
        first_dir = directories[0] if directories else ""
    timer = ScanTimer(first_dir, recursive) if enable_metrics and first_dir else None
    timer_cm = timer if timer is not None else contextlib.nullcontext()

    with timer_cm:
        results: list[T] = []
        error_count = 0
        try:
            # Collect all files first (needed for parallel processing)
            files_to_process = list(
                _scan_and_filter(
                    directories,
                    extension=extension,
                    filter_text=filter_text,
                    recursive=recursive,
                    exclude_dirs=exclude_dirs,
                    exclude_files=exclude_files,
                )
            )

            if files_to_process:
                # Use the thread pool at/above the threshold, sequential below
                if len(files_to_process) >= _PARALLEL_THRESHOLD:
                    results, error_count = _process_files_parallel(files_to_process, worker)
                else:
                    results, error_count = _process_files_sequential(files_to_process, worker)

            return results
        finally:
            # Record metrics and close timer
            if timer:
                timer.error_count += error_count
                timer.finish(len(results))


def _process_files_sequential(
    files: list[tuple[Path, str, str]],
    worker: Callable[[Path, str, str], T],
) -> tuple[list[T], int]:
    """Process files sequentially (below the parallelism threshold).

    Args:
        files: List of (file_path, display_path, full_suffix) tuples.
        worker: Per-file processor.

    Returns:
        Tuple of (results in input order, number of failed files).
    """
    results: list[T] = []
    error_count = 0
    for file_path, display_path, full_suffix in files:
        try:
            results.append(worker(file_path, display_path, full_suffix))
        except Exception as exc:
            _events.processing_failed(logger, path=str(file_path), error=str(exc))
            error_count += 1
    return results, error_count


def _process_files_parallel(
    files: list[tuple[Path, str, str]],
    worker: Callable[[Path, str, str], T],
) -> tuple[list[T], int]:
    """Process files in parallel using a thread pool.

    Preserves input order. Per-file failures are logged and skipped so a
    single bad file never aborts the whole scan.

    Args:
        files: List of (file_path, display_path, full_suffix) tuples.
        worker: Per-file processor (thread-safe).

    Returns:
        Tuple of (results in input order, number of failed files).
    """
    results: dict[int, T] = {}
    error_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_PROCESSING_WORKERS) as executor:
        # Submit all tasks with their index for order preservation
        future_to_index = {
            executor.submit(worker, file_path, display_path, full_suffix): idx
            for idx, (file_path, display_path, full_suffix) in enumerate(files)
        }

        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                file_path, _display_path, _full_suffix = files[idx]
                _events.processing_failed(logger, path=str(file_path), error=str(exc))
                error_count += 1

    return [results[idx] for idx in sorted(results)], error_count


def scan_and_process(
    directories: Sequence[str] | str,
    *,
    extension: str = "",
    filter_text: str = "",
    recursive: bool = False,
    exclude_dirs: Sequence[str] | None = None,
    exclude_files: Sequence[str] | None = None,
    log_metrics: bool = False,
    config: AppConfig | None = None,
) -> list[ScannedFile]:
    """Scan directory(ies), process each file, apply filters, return matches.

    Performs the same scanning + filtering pipeline the GUI uses, but
    without any Tkinter dependency.  Callers run this however they like
    (sync in a thread, sync in a subprocess, etc.).

    Args:
        directories: Filesystem path(s) to scan.
        extension: Extension filter expression (supports operators).
        filter_text: Keyword filter expression (supports operators).
        recursive: Whether to descend into subdirectories.
        exclude_dirs: Directory names to skip during recursion.
        exclude_files: File name glob patterns to skip during scanning.
        log_metrics: If True, log performance metrics at DEBUG level.
        config: Optional AppConfig to check scan_metrics setting.

    Returns:
        List of ``ScannedFile`` entries that pass both filters (files that
        fail per-file processing are logged and skipped).
    """
    return _run_scan_pipeline(
        directories,
        extension=extension,
        filter_text=filter_text,
        recursive=recursive,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        enable_metrics=_metrics_enabled(log_metrics, config),
        worker=_process_file,
    )


# pylint: disable=too-many-arguments
# Public facade mirroring the column config surface; kwargs are additive.
def scan_and_process_dynamic(
    directories: Sequence[str] | str,
    *,
    extension: str = "",
    filter_text: str = "",
    recursive: bool = False,
    exclude_dirs: Sequence[str] | None = None,
    exclude_files: Sequence[str] | None = None,
    column_names: tuple[str, ...] = ("File",),
    columns: dict[str, object] | None = None,
    log_metrics: bool = False,
    config: AppConfig | None = None,
) -> list[ScannedFileDynamic]:
    """Scan directory(ies) with dynamic column extraction.

    Similar to scan_and_process but uses dynamic column extraction rules
    to populate multiple columns based on regex patterns.

    Args:
        directories: Filesystem path(s) to scan.
        extension: Extension filter expression (supports operators).
        filter_text: Keyword filter expression (supports operators).
        recursive: Whether to descend into subdirectories.
        exclude_dirs: Directory names to skip during recursion.
        exclude_files: File name glob patterns to skip during scanning.
        column_names: Ordered list of column names to extract.
        columns: Dictionary of ColumnConfiguration objects from config.
        log_metrics: If True, log performance metrics at DEBUG level.
        config: Optional AppConfig to check scan_metrics setting.

    Returns:
        List of ``ScannedFileDynamic`` entries with column values (files
        that fail per-file processing are logged and skipped).
    """
    extractor = _build_column_extractor(columns, column_names)

    def dynamic_worker(file_path: Path, display_path: str, _full_suffix: str) -> ScannedFileDynamic:
        return _process_file_dynamic(file_path, display_path, extractor, column_names, extension)

    return _run_scan_pipeline(
        directories,
        extension=extension,
        filter_text=filter_text,
        recursive=recursive,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        enable_metrics=_metrics_enabled(log_metrics, config),
        worker=dynamic_worker,
    )
