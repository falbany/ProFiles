"""Launch-time configuration resolution for ProFiles.

Single Responsibility: decide *which configuration file* this process
should use, given the signals in :class:`LaunchContext`.

The decision is pure and side-effect free: it receives a context and
returns a path (or ``None``).  It never reads a file, never prompts, and
never writes — those are :mod:`profiles.launch.creation`'s jobs.

Resolution order (spec §1, issue #191):
    1. ``--config`` when supplied — explicit always wins
    2. a ``*.profiles`` document opened by the user
    3. a ``.profiles`` found by searching the working directory, 5 deep —
       only when the working directory is informative (System32, the
       home folder, the interpreter/app install root are skipped: they
       say nothing about the user's project)
    4. the per-user default ``~/.profiles/.profiles`` when it exists
    5. ``None`` — the caller decides whether to propose creating one
"""

from __future__ import annotations

from pathlib import Path

from profiles.core.config.io.yaml_io import CONFIG_FILE_NAMES, find_config_file
from profiles.core.paths import find_user_config, is_uninformative_directory
from profiles.launch.context import LaunchContext

#: How many directory levels to search.  Matches ``find_config_file``'s
#: documented default and the config file's own comment.
_CONFIG_SEARCH_DEPTH = 5


def _is_config_file(path: Path) -> bool:
    """True when *path* looks like a ProFiles configuration file."""
    return path.name.endswith(CONFIG_FILE_NAMES)


def resolve_config_path(ctx: LaunchContext) -> Path | None:
    """Return the configuration file this launch should use.

    Args:
        ctx: Detected launch context.

    Returns:
        The path to use, or ``None`` when nothing could be resolved (the
        caller then offers to create a starter file).

    Notes:
        An explicit ``--config`` is returned exactly as given, **without**
        an existence check: reporting a typo'd path is the reader's job,
        and silently substituting a different file would be worse than
        the error the user is about to see.

        The working-directory tree search is skipped for uninformative
        directories (issue #191): a Start-Menu launch must not walk
        ``System32`` looking for a config, and a home-CWD launch must not
        walk the whole user profile.  The per-user default
        (``~/.profiles/.profiles``) is the final fallback, so a launcher
        start picks up the config created by an earlier session.
    """
    if ctx.explicit_config is not None:
        return ctx.explicit_config

    for document in ctx.document_paths:
        if _is_config_file(document):
            return document

    start = ctx.working_directory or Path.cwd()
    if not is_uninformative_directory(start):
        try:
            found = find_config_file(start, max_depth=_CONFIG_SEARCH_DEPTH)
        except OSError:
            found = None
        if found is not None:
            return found

    return find_user_config()


__all__ = ["resolve_config_path"]
