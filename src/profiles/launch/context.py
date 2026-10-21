"""Launch-signal detection for ProFiles.

Single Responsibility: gather every signal the operating system offers
about *how this process was started* — a document handed over by a
double-click, the folder the user was in, an explicit ``--config`` — and
package it into an immutable :class:`LaunchContext`.

This module is deliberately the **only** place in ``profiles`` that talks
to the OS about launching.  Nothing here decides what to *do* with the
signals; that is :mod:`profiles.launch.resolution`.

Platform notes
--------------
* ``document_paths`` is inferred from ``sys.argv`` on every platform, so
  a document can always be named explicitly.  On macOS a double-click is
  additionally delivered as an ``odoc`` AppleEvent and merged in by
  ``profiles.desktop.appkit_events`` before startup config is read.
* ``working_directory`` comes from the OS on Windows/Linux (the CWD is
  set to the invoking file's folder).  macOS *removes* it, so there the
  front Finder window's target is probed instead — best effort, with a
  hard timeout, because a probe failure must never block startup.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from profiles.core.config.io.yaml_io import (
    CONFIG_FILE_NAMES,
    FALLBACK_CONFIG_NAMES,
    PRIMARY_CONFIG_NAME,
)

#: Canonical primary configuration file name (``.profiles``).
CONFIG_SUFFIX = PRIMARY_CONFIG_NAME

#: Backward-compatible legacy configuration file name.
FALLBACK_CONFIG_SUFFIX = ".profiles.yaml"

#: All backward-compatible fallback configuration file names, in priority order.
FALLBACK_CONFIG_SUFFIXES = FALLBACK_CONFIG_NAMES

#: Every accepted configuration file name (primary first).
_CONFIG_SUFFIXES = CONFIG_FILE_NAMES

#: Hard timeout for the macOS Finder probe.  Short enough that a hung
#: AppleScript dialog cannot delay startup by more than a beat.
_FINDER_PROBE_TIMEOUT_S = 2.0

_IS_MACOS = sys.platform == "darwin"


def _cwd_is_uninformative(cwd: Path | None) -> bool:
    """True when *cwd* says nothing about the user's launch location.

    GUI-style launches (double-click / Finder) typically inherit
    ``CWD == "/"`` or an idle Python-runtime directory; only then is the
    Finder probe worth consulting for the real launch folder.
    """
    if cwd is None or cwd == Path("/"):
        return True
    try:
        return cwd.resolve().is_relative_to(Path(sys.prefix).resolve())
    except OSError:
        return True


@dataclass(frozen=True)
class LaunchContext:
    """Everything known about how ProFiles was started.

    Attributes:
        document_paths: ``*.profiles`` files handed over by the OS, in the
            order the OS supplied them.  Empty when nothing was opened.
        working_directory: The folder the user was in, when detectable.
            ``None`` means "unknown" — callers must fall back to the CWD.
        explicit_config: Value of ``--config``, if any.  Always wins.
        source: Which signal describes this launch.  One of
            ``"document"``, ``"launcher"``, ``"cwd"``, ``"explicit"``.
    """

    document_paths: tuple[Path, ...]
    working_directory: Path | None
    explicit_config: Path | None
    source: str


def _documents_from_argv(argv: list[str]) -> tuple[Path, ...]:
    """Extract ``*.profiles`` documents from *argv*.

    Anything that is not an existing-or-not configuration path is ignored,
    including flags and unrelated file types, so a headless
    ``profiles file.mttl`` invocation contributes no documents.

    Returns absolute paths; relative entries resolve against the CWD.
    """
    found: list[Path] = []
    for token in argv[1:]:
        if not isinstance(token, str):
            continue
        candidate = token.strip()
        if not candidate or candidate.startswith("-"):
            continue
        if not candidate.endswith(_CONFIG_SUFFIXES):
            continue
        try:
            found.append(Path(candidate).expanduser().resolve())
        except (OSError, RuntimeError):
            continue
    return tuple(found)


def _finder_working_directory() -> Path | None:
    """Return the front Finder window's target (macOS only).

    Best effort by design: a timeout, a permission denial, a missing
    ``osascript`` or a folder that has since moved all yield ``None``
    rather than an exception, so a failed probe can never stop the app
    from starting.  Returns ``None`` immediately on other platforms.
    """
    if not _IS_MACOS:
        return None

    script = 'tell application "Finder" to get POSIX path of (target of front window as alias)'
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=_FINDER_PROBE_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    raw = (completed.stdout or "").strip()
    if not raw:
        return None

    try:
        candidate = Path(raw).expanduser()
    except (OSError, RuntimeError):
        return None

    return candidate if candidate.is_dir() else None


def detect_launch_context(argv: list[str] | None = None) -> LaunchContext:
    """Detect how this process was started.

    Args:
        argv: Argument list to inspect (default ``sys.argv``).

    Returns:
        A :class:`LaunchContext`.  Never raises: every failure degrades to
        whatever signal is still available.

    Notes:
        ``explicit_config`` is intentionally left ``None`` here — parsing
        ``--config`` is the job of the CLI layer, which knows the flag
        grammar.  Use :func:`with_explicit_config` to attach it.
        The macOS Finder probe is consulted only when the process CWD is
        uninformative (``CWD ==  "/"`` or inside the Python runtime
        directory) — the signature of a GUI-style, double-click launch.
        A terminal launch always keeps its real CWD.
    """
    tokens = list(sys.argv if argv is None else argv)
    documents = _documents_from_argv(tokens)

    try:
        cwd = Path.cwd()
    except OSError:
        cwd = None

    probed = _finder_working_directory() if cwd is not None and _cwd_is_uninformative(cwd) else None

    if probed is not None:
        working_directory = probed
        source = "launcher"
    elif cwd is not None:
        working_directory = cwd
        source = "cwd"
    else:
        working_directory = None
        source = "cwd"

    if documents:
        source = "document"

    return LaunchContext(
        document_paths=documents,
        working_directory=working_directory,
        explicit_config=None,
        source=source,
    )


def with_explicit_config(
    ctx: LaunchContext,
    explicit_config: Path | str | None,
) -> LaunchContext:
    """Return *ctx* with ``explicit_config`` set.

    A truthy value also flips ``source`` to ``"explicit"`` and clears any
    inferred documents, because an explicit flag describes the launch
    better than an inference does.
    """
    if not explicit_config:
        return replace(ctx, explicit_config=None)

    path = Path(explicit_config).expanduser()
    return LaunchContext(
        document_paths=(),
        working_directory=ctx.working_directory,
        explicit_config=path,
        source="explicit",
    )


__all__ = [
    "CONFIG_SUFFIX",
    "FALLBACK_CONFIG_SUFFIX",
    "FALLBACK_CONFIG_SUFFIXES",
    "LaunchContext",
    "detect_launch_context",
    "with_explicit_config",
]
