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

from profiles.core.config import service as config_service
from profiles.core.config.models import AppConfig
from profiles.core.processing.column_extractor import ColumnExtractor
from profiles.core.processing.file_classifier import (
    _build_column_extractor,
    _extract_columns_with_defaults,
    get_file_info,
)
from profiles.core.telemetry import events as _events
from profiles.core.telemetry.metrics import ScanTimer
from profiles.utils.file_utils import (
    DEFAULT_MAX_SEARCH_DEPTH,  # noqa: F401  (re-export)
    scan_directory,
    suffix_of_name,
)
from profiles.utils.search_parser import match_filter, tokenize

# Thread pool configuration for parallel file processing
_MAX_PROCESSING_WORKERS = min(32, (os.cpu_count() or 1) * 2)

# Files at/above this count are processed through the thread pool.
_PARALLEL_THRESHOLD = 100

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ScannedFile(NamedTuple):
    """A processed and filtered file entry ready for display / launch.

    Attributes:
        rel_path: Path relative to the scanned directory (display path).
        version: Extracted version string (may be empty).
        path: Full filesystem path to the file.
    """

    rel_path: str
    version: str
    path: Path

    @property
    def filename(self) -> str:
        """Read-only alias for :attr:`rel_path` (pre-rename name)."""
        return self.rel_path


class ScannedFileDynamic(NamedTuple):
    """A processed and filtered file entry with dynamic column values.

    Attributes:
        path: Full filesystem path to the file.
        column_values: Dictionary mapping column names to extracted values.
        rel_path: Path relative to the scanned directory (for global search).
    """

    path: Path
    column_values: dict[str, str]
    rel_path: str


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
    if not tokens:
        # Quote-only extension ("" / "   "): tokens were all empty → simple.
        return True
    if len(tokens) != 1:
        return False
    token = tokens[0]
    return not (token.startswith("-") or token.startswith("+"))


def _merge_unique(*seqs: Sequence[str] | None) -> tuple[str, ...]:
    """Concatenate sequences, drop duplicates, keep first-seen order."""
    seen: set[str] = set()
    merged: list[str] = []
    for seq in seqs:
        if not seq:
            continue
        for pattern in seq:
            if pattern not in seen:
                seen.add(pattern)
                merged.append(pattern)
    return tuple(merged)


def _resolve_scan_config(
    directory: str,
    recursive: bool,
    exclude_dirs: Sequence[str] | None,
    exclude_files: Sequence[str] | None,
    config: AppConfig | None,
    *,
    recursive_override: bool | None = None,
) -> tuple[bool, int, tuple[str, ...], tuple[str, ...]]:
    """Resolve effective search configuration for a directory.

    Recursive precedence: ``recursive_override`` (explicit request-time
    intent, when not ``None``) → ``active.recursive_search`` (matching
    machine/directory config entry, when defined) → ``recursive`` param.
    """
    active = config_service.find_active_config(config, directory) if config else None
    if recursive_override is not None:
        eff_recursive = recursive_override
    elif active and active.recursive_search is not None:
        eff_recursive = active.recursive_search
    else:
        eff_recursive = recursive
    eff_depth = (
        active.max_search_depth
        if (active and active.max_search_depth is not None)
        else (config.max_search_depth if config else DEFAULT_MAX_SEARCH_DEPTH)
    )

    eff_exclude_dirs = _merge_unique(
        config.search_exclude_dirs if config else None,
        exclude_dirs,
        active.search_exclude_dirs if active else None,
    )
    eff_exclude_files = _merge_unique(
        config.search_exclude_files if config else None,
        exclude_files,
        active.search_exclude_files if active else None,
    )

    return eff_recursive, eff_depth, eff_exclude_dirs, eff_exclude_files


def _extension_filter(extension: str) -> Callable[[str], bool] | None:
    """Build a file-name predicate for *extension*, or ``None`` when not filtering.

    ``"all"`` (case-insensitive) and an empty expression mean "no extension
    filter": everything is a candidate.
    """
    stripped = extension.strip()
    if not stripped or stripped.lower() == "all":
        return None

    def _predicate(name: str) -> bool:
        # Substring (D1) matching on the file name's full compound suffix.
        return match_filter(suffix_of_name(name), extension)

    return _predicate


def _register_abs_path(file_path: Path, seen_paths: set[str]) -> bool:
    """Register the resolved absolute path of *file_path* in *seen_paths*.

    Returns ``False`` when the file was skipped (unresolvable, logged via
    ``SCAN_SKIPPED``) or already seen — so multi-root over-relapped scans
    yield each physical file exactly once.
    """
    try:
        abs_path = str(file_path.resolve())
    except OSError as exc:
        _events.scan_skipped(logger, path=str(file_path), error=str(exc))
        return False
    if abs_path in seen_paths:
        return False
    seen_paths.add(abs_path)
    return True


def _iter_directory_files(
    directory: str,
    *,
    extension: str,
    recursive: bool,
    exclude_dirs: Sequence[str] | None,
    exclude_files: Sequence[str] | None,
    config: AppConfig | None,
    recursive_override: bool | None = None,
) -> Iterator[Path]:
    """Scan one root directory and yield file paths passing the scan config.

    The extension filter is pushed into the scan: names that cannot pass
    the extension never become Path objects (Task 7). Scan-level errors
    are reported via ``SCAN_SKIPPED`` by :func:`scan_directory` itself.
    """
    (
        effective_recursive,
        effective_depth,
        effective_exclude_dirs,
        effective_exclude_files,
    ) = _resolve_scan_config(
        directory,
        recursive,
        exclude_dirs,
        exclude_files,
        config,
        recursive_override=recursive_override,
    )

    return scan_directory(
        directory,
        "",
        recursive=effective_recursive,
        exclude_dirs=effective_exclude_dirs,
        exclude_files=effective_exclude_files,
        max_depth=effective_depth,
        on_skip=lambda p, e: _events.scan_skipped(logger, path=p, error=e),
        name_filter=_extension_filter(extension),
    )


def _scan_and_filter(
    directories: Sequence[str] | str,
    *,
    extension: str = "",
    filter_text: str = "",
    recursive: bool = False,
    exclude_dirs: Sequence[str] | None = None,
    exclude_files: Sequence[str] | None = None,
    config: AppConfig | None = None,
    recursive_override: bool | None = None,
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
        config: Optional AppConfig for overrides and excludes.
        recursive_override: Explicit recursive-search override; \
``None`` = defer to config-entry/param precedence.

    Yields:
        Tuples of (absolute Path, display path str, full suffix str).
        When multiple directories are provided, files are deduplicated by their absolute path (so identical files reached via different paths will only be yielded once).
    """
    directory_list = [directories] if isinstance(directories, str) else list(directories)
    seen_paths: set[str] = set()
    # Deduplicate only when several roots could yield the same file
    # (e.g. ``A`` and ``A/sub``); a single root cannot repeat itself.
    dedupe = len(directory_list) > 1

    for directory in directory_list:
        if not directory:
            continue
        try:
            base_path = Path(directory)
            files = _iter_directory_files(
                directory,
                extension=extension,
                recursive=recursive,
                exclude_dirs=exclude_dirs,
                exclude_files=exclude_files,
                config=config,
                recursive_override=recursive_override,
            )
            for file_path in files:
                full_suffix = "".join(file_path.suffixes)

                if dedupe and not _register_abs_path(file_path, seen_paths):
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
    column_values = _extract_columns_with_defaults(
        full_path_str, extractor, column_names, extension
    )

    return ScannedFileDynamic(file_path, column_values, display_path)


def _metrics_enabled(log_metrics: bool, config: AppConfig | None) -> bool:
    """Return whether scan metrics should be collected and logged."""
    return log_metrics or (config is not None and config.scan_metrics)


# pylint: disable=too-many-arguments
# Facade multiplier: mirrors the kwargs of the public scan_* functions.
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
    config: AppConfig | None = None,
    recursive_override: bool | None = None,
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
        recursive_override: Explicit recursive-search override; \
``None`` = defer to config-entry/param precedence.

    Returns:
        Processed results in scan order (failing files are skipped).
    """
    if isinstance(directories, str):
        first_dir = directories
    else:
        first_dir = directories[0] if directories else ""
    timer = (
        ScanTimer(first_dir, recursive, extension=extension, filter_text=filter_text)
        if enable_metrics and first_dir
        else None
    )
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
                    config=config,
                    recursive_override=recursive_override,
                )
            )

            if files_to_process:
                # Use the thread pool at/above the threshold, inline below
                max_workers = (
                    _MAX_PROCESSING_WORKERS if len(files_to_process) >= _PARALLEL_THRESHOLD else 1
                )
                results, error_count = _process_files(files_to_process, worker, max_workers)

            return results
        finally:
            # Record metrics and close timer
            if timer:
                timer.error_count += error_count
                timer.finish(len(results))


def _process_files(
    files: list[tuple[Path, str, str]],
    worker: Callable[[Path, str, str], T],
    max_workers: int,
) -> tuple[list[T], int]:
    """Process *files* through *worker* — the single processing path.

    With ``max_workers <= 1`` tasks run inline (no pool). Otherwise a
    thread pool collects results in submission order, so output order
    always matches the input.  Per-file failures are logged via
    ``PROCESSING_FAILED`` and counted, never fatal (identical semantics
    on both modes).

    Args:
        files: List of (file_path, display_path, full_suffix) tuples.
        worker: Per-file processor (thread-safe when pooling).
        max_workers: 0/1 runs inline; > 1 builds a thread pool.

    Returns:
        Tuple of (results in input order, number of failed files).
    """
    results: list[T] = []
    error_count = 0

    if max_workers <= 1:
        for file_path, display_path, full_suffix in files:
            try:
                results.append(worker(file_path, display_path, full_suffix))
            except Exception as exc:
                _events.processing_failed(logger, path=str(file_path), error=str(exc))
                error_count += 1
        return results, error_count

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, *task) for task in files]
        # Submission order == input order: iterate futures as submitted.
        for future, (file_path, _display_path, _full_suffix) in zip(futures, files, strict=True):
            try:
                results.append(future.result())
            except Exception as exc:
                _events.processing_failed(logger, path=str(file_path), error=str(exc))
                error_count += 1

    return results, error_count


# pylint: disable=too-many-arguments
# Public facade with additive kwargs above the 8-arg design cap.
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
    recursive_override: bool | None = None,
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
        recursive_override: Explicit recursive-search override; \
``None`` = defer to config-entry/param precedence.

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
        config=config,
        recursive_override=recursive_override,
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
    recursive_override: bool | None = None,
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
        recursive_override: Explicit recursive-search override; \
``None`` = defer to config-entry/param precedence.

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
        config=config,
        recursive_override=recursive_override,
    )
