"""Path normalization helpers for user-supplied paths.

This module is stateless and framework-agnostic.
"""

from __future__ import annotations

import os
from pathlib import Path


def normalize_user_path(path: str | Path) -> Path:
    """Normalize a user-supplied path without canonicalizing it.

    Expands ``~`` and collapses redundant separators and ``..`` segments
    with :func:`os.path.normpath`, but — unlike :meth:`pathlib.Path.resolve`
    — never rewrites the path to its physical target.

    This matters on Windows, where ``resolve()`` canonicalizes a mapped
    network drive letter to its UNC target (``M:/projects`` becomes
    ``\\\\server\\share\\projects`` — stdlib behavior since Python 3.8,
    via ``GetFinalPathNameByHandle``). ``subst``-ed drives are rewritten
    the same way, and symlinks are collapsed on every platform. Users who
    configured a drive letter expect that form end to end: launched
    commands, ``{{path}}``/``{{dir}}`` hook tokens, result rows, reveal
    actions and barcode payloads.

    Reserve :meth:`~pathlib.Path.resolve` for places where *physical
    identity* matters (scan dedup keys, config-file discovery, instance
    handoff) — not for paths that are displayed or handed to user commands.

    Args:
        path: The user-supplied path string or Path object.

    Returns:
        The normalized path as a :class:`pathlib.Path`.
    """
    expanded = os.path.expanduser(os.fspath(path))
    return Path(os.path.normpath(expanded))
