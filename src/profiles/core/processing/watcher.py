"""Directory-mtime snapshot for the watch-mode probe (#223).

Foundation module for the dependency-free polling watcher: a cheap walk
that stats *directories only* — create/delete/rename all mutate a parent
directory's mtime, which is the dominant change pattern on the target
workload (probe-only by design; in-place content edits are not detected).

Pure, UI-free, server-free core logic.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from profiles.utils.file_utils import _is_excluded

# Watcher cadence defaults (spec-decided values; consumed by the polling
# DirectoryWatcher that lives in this same module).
DEFAULT_DEBOUNCE_S: float = 0.5
DEFAULT_BASE_INTERVAL_S: float = 1.0
DEFAULT_MAX_INTERVAL_S: float = 5.0


def snapshot_dir_mtimes(
    root: Path,
    exclude_dirs: Sequence[str] | None = None,
    *,
    max_depth: int | None = None,
) -> dict[str, float]:
    """Snapshot the mtime of *root* and every non-excluded subdirectory.

    The walk is top-down and prunes excluded subtrees *before* descending,
    so an excluded tree is never even walked. Exclusion semantics match the
    scan walk's ``exclude_dirs``: case-insensitive fnmatch on directory
    basenames (see :func:`profiles.utils.file_utils._is_excluded`).

    Args:
        root: Directory to snapshot. Must exist — a missing root raises.
        exclude_dirs: Glob patterns (``*``, ``?``, ``[seq]``) matched
            case-insensitively against directory basenames to prune from
            the walk. ``None`` or empty excludes nothing.
        max_depth: Levels of subdirectories to descend **below root**
            (``0`` = root only; ``None`` = unlimited). Directories beyond
            the budget are absent from the snapshot.

    Returns:
        ``{directory_path: mtime}`` keyed by ``str()`` of the path, with
        the root itself always included.

    Raises:
        OSError: *root* does not exist or cannot be statted.
    """
    patterns = tuple(exclude_dirs or ())
    root_stat = root.stat()  # A missing root raises before any walk.
    snapshot: dict[str, float] = {str(root): root_stat.st_mtime}
    root_parts = len(root.parts)
    for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
        # Directories listed by this yield sit one level below *dirpath*.
        depth = len(Path(dirpath).parts) - root_parts
        if max_depth is not None and depth >= max_depth:
            # Depth budget exhausted: one level too deep to stat, so clear
            # (which also stops the descent).
            dirnames.clear()
        else:
            dirnames[:] = [d for d in dirnames if not _is_excluded(d, patterns)]
        for name in dirnames:
            sub = Path(dirpath) / name
            snapshot[str(sub)] = sub.stat().st_mtime
    return snapshot
