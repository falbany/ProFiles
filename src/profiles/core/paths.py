"""Per-user path policy — one source of truth for user-level locations.

Single Responsibility: decide where ProFiles keeps per-user data (the
``~/.profiles`` folder shared by logs and the default configuration) and
which directories carry no information about the user's launch location.

Pure functions only: nothing here touches the filesystem beyond
existence/metadata checks, and nothing mutates state.

Why this module exists (issue #191): a Start-Menu shortcut with an empty
"Start in" field runs the process with ``CWD = %SystemRoot%\\System32``,
and a launcher whose CWD is the home folder collides with the
``~/.profiles`` **log directory**.  Both facts are path-policy concerns,
so every consumer (launch resolution, config loader, server state,
logger defaults) asks here instead of re-deriving them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from profiles.core.config.io.yaml_io import CONFIG_FILE_NAMES

#: Name of the per-user data directory (logs + default config).
USER_DATA_DIRNAME = ".profiles"


def user_data_dir() -> Path:
    """Return the per-user data directory: ``~/.profiles``.

    Holds ``profiles.log`` and the per-user default configuration, so
    both can never drift apart.

    Returns:
        Absolute path under the user's home folder.

    Raises:
        RuntimeError: When the home directory cannot be determined
            (same failure mode as :meth:`pathlib.Path.home`, which the
            logger already accepted before this module existed).
    """
    return Path.home() / USER_DATA_DIRNAME


def user_config_path() -> Path:
    """Return the per-user default configuration path: ``~/.profiles/.profiles``.

    Returns:
        Absolute path to the canonical primary config name inside
        :func:`user_data_dir`.
    """
    return user_data_dir() / CONFIG_FILE_NAMES[0]


def find_user_config() -> Path | None:
    """Return the per-user default configuration file, when one exists.

    Only the canonical names are checked, in priority order, directly
    inside :func:`user_data_dir` (depth 0, no wildcard search) — the
    per-user folder is not a project tree to walk.

    Returns:
        The first existing config **file**, or ``None``.
    """
    data_dir = user_data_dir()
    for name in CONFIG_FILE_NAMES:
        candidate = data_dir / name
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def is_uninformative_directory(path: Path | None) -> bool:
    """True when *path* says nothing about the user's launch location.

    A directory is uninformative when it was chosen by the OS or the
    runtime rather than by the user:

    * ``None`` or an unresolvable path;
    * a filesystem/drive root (``/``, ``C:\\``);
    * the home folder itself (a launcher CWD, and colliding with the
      ``~/.profiles`` data directory);
    * anything inside the Python runtime prefix (idle interpreter
      launches);
    * anything inside the running executable's directory (packaged-app
      install root);
    * on Windows-style environments: anything inside
      ``%SystemRoot%``/``%windir%`` (covers ``System32``, ``SysWOW64``)
      or ``%ProgramFiles%``/``%ProgramFiles(x86)%``.  The variables are
      consulted whenever they are set, so tests can monkeypatch them on
      any platform and real non-Windows environments (where they are
      unset) are unaffected.

    Args:
        path: Candidate directory (``None`` allowed).

    Returns:
        ``True`` when the directory must not be used to infer a project
        location or to host a proposed configuration file.
    """
    if path is None:
        return True

    try:
        resolved = path.resolve()
    except OSError:
        return True

    # Filesystem / drive root.
    if resolved.parent == resolved:
        return True

    # Home folder itself (launchers often start there; it also hosts the
    # ~/.profiles data directory, so it can never host a config file).
    try:
        if resolved == Path.home().resolve():
            return True
    except (OSError, RuntimeError):
        pass

    # Python runtime prefix (venv / system interpreter locations).
    try:
        if resolved.is_relative_to(Path(sys.prefix).resolve()):
            return True
    except OSError:
        return True

    # Running executable's directory (packaged-app install root).
    try:
        exe_dir = Path(sys.executable).resolve().parent
        if resolved.is_relative_to(exe_dir):
            return True
    except OSError:
        pass

    # Windows system / program locations, via env vars (see docstring).
    for var in ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(var)
        if not value:
            continue
        try:
            base = Path(value).resolve()
        except OSError:
            continue
        if resolved.is_relative_to(base):
            return True

    return False


def default_config_path(start: Path | None = None) -> Path:
    """Return the path a missing configuration should be proposed at.

    Args:
        start: Directory the launch happened in (default: the process
            CWD).  May be ``None`` when the CWD is unreadable.

    Returns:
        ``start / ".profiles"`` for an informative *start*, otherwise the
        per-user :func:`user_config_path`.  When the project candidate
        exists and is a **directory** (the ``CWD == home`` collision with
        the ``~/.profiles`` data folder), the per-user path is returned
        instead: the app never proposes a directory as its config file.
    """
    if start is None:
        try:
            start = Path.cwd()
        except OSError:
            start = None

    if is_uninformative_directory(start):
        return user_config_path()

    candidate = start / CONFIG_FILE_NAMES[0]
    try:
        if candidate.exists() and candidate.is_dir():
            return user_config_path()
    except OSError:
        pass
    return candidate


def default_search_directory(start: Path | None = None) -> Path:
    """Return the directory a starter configuration should scan.

    Args:
        start: Directory the launch happened in (default: the process
            CWD).  May be ``None`` when the CWD is unreadable.

    Returns:
        *start* when informative; the home folder otherwise (a launcher
        start must never scan ``System32`` or the interpreter's folder).
    """
    if start is None:
        try:
            start = Path.cwd()
        except OSError:
            start = None

    if is_uninformative_directory(start):
        return Path.home()
    return start


__all__ = [
    "USER_DATA_DIRNAME",
    "default_config_path",
    "default_search_directory",
    "find_user_config",
    "is_uninformative_directory",
    "user_config_path",
    "user_data_dir",
]
