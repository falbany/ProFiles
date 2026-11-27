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
from profiles.core.config.models import AppConfig, ColumnConfiguration
from profiles.core.processing.column_extractor import ColumnExtractor
from profiles.core.processing.file_classifier import (
    _build_column_extractor,
    _extract_columns_with_defaults,
    get_file_info,
)
from profiles.core.processing.file_metadata import FileAttrs, collect_file_attrs
from profiles.core.telemetry import events as _events
from profiles.core.telemetry.metrics import ScanTimer
from profiles.utils.file_utils import (
    DEFAULT_MAX_SEARCH_DEPTH,  # noqa: F401  (re-export)
    scan_directory,
    suffix_of_name,
)
from profiles.utils.search_parser import (
    match_file,
    match_filter,
    query_needs_attributes,
    tokenize,
)

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
        attrs: Optional stat snapshot backing attribute columns and \
operator-filtered rows; ``None`` when the scan never needed one.
    """

    path: Path
    column_values: dict[str, str]
    rel_path: str
    attrs: FileAttrs | None = None


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
    max_depth_override: int | None = None,
) -> tuple[bool, int, tuple[str, ...], tuple[str, ...]]:
    """Resolve effective search configuration for a directory.

    Recursive precedence: ``recursive_override`` (explicit request-time
    intent, when not ``None``) → ``active.recursive_search`` (matching
    machine/directory config entry, when defined) → ``recursive`` param.

    Depth precedence: ``max_depth_override`` (explicit request-time
    intent, when not ``None``) → ``active.max_search_depth`` (matching
    machine/directory config entry, when defined) →
    ``config.max_search_depth`` → ``DEFAULT_MAX_SEARCH_DEPTH``.
    """
    active = config_service.find_active_config(config, directory) if config else None
    if recursive_override is not None:
        eff_recursive = recursive_override
    elif active and active.recursive_search is not None:
        eff_recursive = active.recursive_search
    else:
        eff_recursive = recursive
    eff_depth = (
        max_depth_override
        if max_depth_override is not None
        else (
            active.max_search_depth
            if (active and active.max_search_depth is not None)
            else (config.max_search_depth if config else DEFAULT_MAX_SEARCH_DEPTH)
        )
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


def effective_search_boundary(
    directory: str,
    config: AppConfig | None,
    *,
    recursive: bool,
    max_depth_override: int | None = None,
) -> tuple[int, tuple[str, ...]]:
    """Resolve the effective search boundary ``(max_depth, exclude_dirs)``.

    Public, thin wrapper over :func:`_resolve_scan_config`: the depth and
    exclusion patterns returned are exactly the ones a scan of *directory*
    would apply (active machine/directory entry → ``config`` → defaults).
    The watch-mode probe (issue #223) uses it to sample the same tree a
    scan of the same root would walk.

    Args:
        directory: Root directory the boundary applies to.
        config: Optional application configuration for the merge.
        recursive: Whether the search descends below the root. A
            non-recursive boundary forces depth ``0`` (root only) while
            keeping the merged excludes.
        max_depth_override: Explicit depth override; \
``None`` = defer to config-entry/config/default precedence.

    Returns:
        Tuple ``(max_depth, exclude_dirs)`` — depth levels below the
        root, and the merged directory-exclusion patterns.
    """
    (
        _eff_recursive,
        eff_depth,
        eff_exclude_dirs,
        _eff_exclude_files,
    ) = _resolve_scan_config(
        directory,
        True,
        None,
        None,
        config,
        max_depth_override=max_depth_override,
    )
    return (eff_depth if recursive else 0, eff_exclude_dirs)


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
    max_depth_override: int | None = None,
) -> list[Path]:
    """Scan one root directory and return file paths passing the scan config.

    The extension filter is pushed into the scan: names that cannot pass
    the extension never become Path objects (Task 7). Scan-level errors
    are reported via ``SCAN_SKIPPED`` by :func:`scan_directory` itself.
    Both overrides thread straight into :func:`_resolve_scan_config`;
    *max_depth_override* is an explicit depth override; ``None`` = defer
    to config-entry/config/default precedence.
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
        max_depth_override=max_depth_override,
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


# pylint: disable=too-many-arguments,too-many-locals
# Shared pipeline: mirrors the kwargs of the public scan_* functions
# (facade kwargs also count as pylint locals).
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
    max_depth_override: int | None = None,
) -> Iterator[tuple[Path, str, str, FileAttrs | None]]:
    """Shared scanning + filtering generator used by all ``scan_*`` functions.

    Yields ``(file_path, display_path, full_suffix, attrs)`` for every file
    that passes both the extension and keyword filters.

    When *filter_text* carries attribute operators (``size:>1mb`` …), each
    extension-passing candidate is statted **once** — via
    :func:`collect_file_attrs`, the only stat path added by #227 — and the
    snapshot rides along on the candidate tuple. Plain and substring-only
    queries never stat (zero-stat gate: ``attrs`` is ``None`` everywhere).

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
        max_depth_override: Explicit depth override; \
``None`` = defer to config-entry/config/default precedence.

    Yields:
        Tuples of (absolute Path, display path str, full suffix str, \
stat snapshot or ``None``). When multiple directories are provided, \
files are deduplicated by their absolute path (so identical files \
reached via different paths will only be yielded once).
    """
    directory_list = [directories] if isinstance(directories, str) else list(directories)
    seen_paths: set[str] = set()
    # Deduplicate only when several roots could yield the same file
    # (e.g. ``A`` and ``A/sub``); a single root cannot repeat itself.
    dedupe = len(directory_list) > 1

    # The query is identical for every directory: decide once per scan
    # whether candidates need a stat snapshot (#227 zero-stat gate).
    collect_attrs = bool(filter_text) and query_needs_attributes(filter_text)

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
                max_depth_override=max_depth_override,
            )
            for file_path in files:
                full_suffix = "".join(file_path.suffixes)

                if dedupe and not _register_abs_path(file_path, seen_paths):
                    continue

                display_path = _compute_display_path(file_path, base_path)

                if filter_text:
                    # One stat per extension-passing candidate, only when the
                    # query actually carries attribute operators; a deleted
                    # file simply yields None (attr terms evaluate False).
                    attrs = collect_file_attrs(file_path) if collect_attrs else None
                    if collect_attrs:
                        if not match_file(display_path, filter_text, attrs):
                            continue
                    elif not match_filter(display_path, filter_text):
                        continue
                else:
                    attrs = None

                yield file_path, display_path, full_suffix, attrs
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


def _process_file(
    file_path: Path,
    display_path: str,
    full_suffix: str,
    attrs: FileAttrs | None,
) -> ScannedFile:
    """Process a single file (thread-safe worker).

    Args:
        file_path: Absolute path to the file.
        display_path: Path for display (relative to scan directory).
        full_suffix: Full file suffix (e.g. ``".mttx.lnk"``) used for
            version extraction.
        attrs: Candidate stat snapshot — accepted for the unified worker
            signature and ignored: the plain worker never stats.

    Returns:
        ScannedFile with filename (display path) and version.
    """
    _, version = get_file_info(file_path, full_suffix.lstrip("."))
    return ScannedFile(display_path, version, file_path)


def _process_file_dynamic(
    file_path: Path,
    display_path: str,
    full_suffix: str,
    attrs: FileAttrs | None,
    extractor: ColumnExtractor,
    column_names: tuple[str, ...],
    extension: str,
) -> ScannedFileDynamic:
    """Process a single file for dynamic columns (thread-safe worker).

    The stat snapshot arrives pre-computed when the query carries attribute
    operators (collected once per candidate in the scan loop). When absent
    and a rendered column is attribute-backed, the worker collects it here —
    the only worker-side stat site (#227).

    Args:
        file_path: Absolute path to the file.
        display_path: Path for display (relative to scan directory).
        full_suffix: Full file suffix — accepted for the unified worker
            signature; version stripping uses *extension*.
        attrs: Pre-computed stat snapshot, or ``None`` when the scan loop
            did not collect one.
        extractor: Pre-built ColumnExtractor instance.
        column_names: Ordered list of column names to extract.
        extension: File extension for version stripping.

    Returns:
        ScannedFileDynamic with extracted column values and the stat
        snapshot actually used (``None`` when none was needed).
    """
    if attrs is None and extractor.has_attribute_rules(column_names):
        attrs = collect_file_attrs(file_path)

    full_path_str = str(display_path)
    column_values = _extract_columns_with_defaults(
        full_path_str, extractor, column_names, extension, attrs
    )

    return ScannedFileDynamic(file_path, column_values, display_path, attrs)


def _metrics_enabled(log_metrics: bool, config: AppConfig | None) -> bool:
    """Return whether scan metrics should be collected and logged."""
    return log_metrics or (config is not None and config.scan_metrics)


# pylint: disable=too-many-arguments,too-many-locals
# Facade multiplier: mirrors the kwargs of the public scan_* functions
# (facade kwargs also count as pylint locals).
def _run_scan_pipeline(
    directories: Sequence[str] | str,
    *,
    extension: str,
    filter_text: str,
    recursive: bool,
    exclude_dirs: Sequence[str] | None,
    exclude_files: Sequence[str] | None,
    enable_metrics: bool,
    worker: Callable[[Path, str, str, FileAttrs | None], T],
    config: AppConfig | None = None,
    recursive_override: bool | None = None,
    max_depth_override: int | None = None,
    on_progress: Callable[[int], None] | None = None,
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
        worker: Per-file processor \
``(file_path, display_path, full_suffix, attrs) -> T``.
        recursive_override: Explicit recursive-search override; \
``None`` = defer to config-entry/param precedence.
        max_depth_override: Explicit depth override; \
``None`` = defer to config-entry/config/default precedence.
        on_progress: Called with the running count of filter-passing \
candidates during collection. Must not raise.

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
            # Collect all files first (needed for parallel processing);
            # the counting loop reports filter-passing candidates as they
            # are yielded so a caller can surface live progress (#152).
            # Candidates are the worker-input shape: 4-tuples of
            # (file_path, display_path, full_suffix, attrs) (#152, #227).
            files_to_process: list[tuple[Path, str, str, FileAttrs | None]] = []
            for count, candidate in enumerate(
                _scan_and_filter(
                    directories,
                    extension=extension,
                    filter_text=filter_text,
                    recursive=recursive,
                    exclude_dirs=exclude_dirs,
                    exclude_files=exclude_files,
                    config=config,
                    recursive_override=recursive_override,
                    max_depth_override=max_depth_override,
                ),
                start=1,
            ):
                files_to_process.append(candidate)
                if on_progress is not None:
                    on_progress(count)

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
    files: list[tuple[Path, str, str, FileAttrs | None]],
    worker: Callable[[Path, str, str, FileAttrs | None], T],
    max_workers: int,
) -> tuple[list[T], int]:
    """Process *files* through *worker* — the single processing path.

    With ``max_workers <= 1`` tasks run inline (no pool). Otherwise a
    thread pool collects results in submission order, so output order
    always matches the input.  Per-file failures are logged via
    ``PROCESSING_FAILED`` and counted, never fatal (identical semantics
    on both modes).

    Args:
        files: List of (file_path, display_path, full_suffix, attrs) tuples.
        worker: Per-file processor (thread-safe when pooling).
        max_workers: 0/1 runs inline; > 1 builds a thread pool.

    Returns:
        Tuple of (results in input order, number of failed files).
    """
    results: list[T] = []
    error_count = 0

    if max_workers <= 1:
        for file_path, display_path, full_suffix, attrs in files:
            try:
                results.append(worker(file_path, display_path, full_suffix, attrs))
            except Exception as exc:
                _events.processing_failed(logger, path=str(file_path), error=str(exc))
                error_count += 1
        return results, error_count

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, *task) for task in files]
        # Submission order == input order: iterate futures as submitted.
        for future, (file_path, _display_path, _full_suffix, _attrs) in zip(
            futures, files, strict=True
        ):
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
    max_depth_override: int | None = None,
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
        max_depth_override: Explicit depth override; \
``None`` = defer to config-entry/config/default precedence.

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
        max_depth_override=max_depth_override,
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
    columns: dict[str, ColumnConfiguration] | None = None,
    log_metrics: bool = False,
    config: AppConfig | None = None,
    recursive_override: bool | None = None,
    max_depth_override: int | None = None,
    on_progress: Callable[[int], None] | None = None,
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
        max_depth_override: Explicit depth override; \
``None`` = defer to config-entry/config/default precedence.
        on_progress: Called with the running count of filter-passing \
candidates during collection. Must not raise.

    Returns:
        List of ``ScannedFileDynamic`` entries with column values (files
        that fail per-file processing are logged and skipped).
    """
    extractor = _build_column_extractor(columns, column_names)

    def dynamic_worker(
        file_path: Path, display_path: str, full_suffix: str, attrs: FileAttrs | None
    ) -> ScannedFileDynamic:
        return _process_file_dynamic(
            file_path, display_path, full_suffix, attrs, extractor, column_names, extension
        )

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
        max_depth_override=max_depth_override,
        on_progress=on_progress,
    )
