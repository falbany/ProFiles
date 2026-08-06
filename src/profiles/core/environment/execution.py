"""Launch hooks engine — runs user-configured commands around file launches.

Single Responsibility: orchestrate the ``[HOOKS]`` pipeline (parse → token
substitute → run). No Tkinter / GUI imports. Pure stdlib. Called by the
:mod:`profiles.core.actions` module and by any future front-end (CLI, TUI).

Phases (per extension):

* ``before`` — synchronous; failure respects ``launch_hook_failmode``
* ``abort`` — synchronous; non-zero ⇒ always :attr:`HookOutcome.ABORT`
* ``instead`` — synchronous; zero ⇒ :attr:`HookOutcome.SKIP`,
  non-zero falls back to ``launch_hook_failmode``
* ``after`` — fire-and-forget via :func:`subprocess.Popen`

A non-empty ``template`` is mandatory; empty entries are dropped at parse time.
"""

from __future__ import annotations

import datetime
import logging
import shlex
import socket
import subprocess
import sys
from enum import Enum
from pathlib import Path

from profiles.core.config.models import AppConfig, HookSpec
from profiles.core.environment.interactions import confirm_dialog

_logger = logging.getLogger("profiles")

_TOKEN_MAP_ATTR = "path"
_TOKEN_DIR = "dir"
_TOKEN_NAME = "name"
_TOKEN_CWD = "cwd"
_TOKEN_EXT = "ext"
_TOKEN_DATE = "date"
_TOKEN_HOSTNAME = "hostname"

_KNOWN_TOKENS = (
    _TOKEN_MAP_ATTR,
    _TOKEN_DIR,
    _TOKEN_NAME,
    _TOKEN_CWD,
    _TOKEN_EXT,
    _TOKEN_DATE,
    _TOKEN_HOSTNAME,
)


class HookOutcome(Enum):
    """Decision returned by :func:`run_hooks_for_file`.

    Attributes:
        CONTINUE: Run the OS file association (the default OS launch).
        SKIP: Skip the OS launch — an ``instead`` hook already succeeded.
        ABORT: Halt the launch pipeline; caller surfaces failure.
    """

    CONTINUE = "continue"
    SKIP = "skip"
    ABORT = "abort"


def parse_hook_entries(raw_value: str) -> tuple[HookSpec, ...]:
    """Parse a raw ``[HOOKS]`` value into a tuple of :class:`HookSpec`.

    Entries are comma-separated; commas inside double-quoted substrings are
    preserved. Each entry is ``[when]|template`` — a missing ``|`` defaults to
    ``when="before"``. Empty templates are dropped.

    This is the canonical parser. ``ConfigReader._parse_hook_entries`` is a
    thin static wrapper preserved for back-compat.

    Args:
        raw_value: Raw option value from the ``[HOOKS]`` section.

    Returns:
        Tuple of parsed :class:`HookSpec` instances.
    """
    parts: list[str] = []
    current: list[str] = []
    inside_quote = False

    for char in raw_value:
        if char == '"':
            inside_quote = not inside_quote
        if char == "," and not inside_quote:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))

    hooks: list[HookSpec] = []
    for part in parts:
        entry = part.strip()
        if not entry:
            continue
        if "|" not in entry:
            hooks.append(HookSpec(template=entry))
        else:
            when, _, template = entry.partition("|")
            hooks.append(HookSpec(when=when.strip().lower(), template=template.strip()))

    return tuple(hook for hook in hooks if hook.template)


def _substitute_tokens(template: str, file_path: Path) -> str:
    """Replace ``{token}`` placeholders in *template* with file/runtime values.

    Supported tokens: ``{path}``, ``{dir}``, ``{name}``, ``{cwd}``, ``{ext}``,
    ``{date}``, ``{hostname}``. Unknown tokens are left intact.

    Args:
        template: Command template containing ``{token}`` placeholders.
        file_path: File the hook is being run for.

    Returns:
        Template with placeholders substituted.
    """
    replacements = {
        _TOKEN_MAP_ATTR: str(file_path.resolve()),
        _TOKEN_DIR: str(file_path.parent.resolve()),
        _TOKEN_NAME: file_path.name,
        _TOKEN_CWD: str(Path.cwd().resolve()),
        _TOKEN_EXT: file_path.suffix,
        _TOKEN_DATE: datetime.date.today().isoformat(),
        _TOKEN_HOSTNAME: socket.gethostname(),
    }

    result = template
    for token, value in replacements.items():
        result = result.replace("{" + token + "}", value)
    return result


def _build_argv(template: str, file_path: Path) -> list[str]:
    """Token-substitute *template* then shell-split it into an argv list.

    POSIX splitting on POSIX platforms, Windows-native (non-POSIX) splitting
    on Windows to match the platform's escaping rules.

    Args:
        template: Raw command template (with ``{token}`` placeholders).
        file_path: File the hook is being run for.

    Returns:
        Argv list suitable for ``subprocess.run(..., shell=False)``.

    Raises:
        ValueError: If *template* has unbalanced quotes (propagated from
            :func:`shlex.split` so the caller surfaces a clear error).
    """
    substituted = _substitute_tokens(template, file_path)
    return shlex.split(substituted, posix=sys.platform != "win32")


def run_blocking_hook(template: str, file_path: Path, *, timeout: int) -> int:
    """Run *template* synchronously and return its process returncode.

    Output is captured (not echoed). A timeout raises :class:`TimeoutError`.

    Args:
        template: Raw command template (with ``{token}`` placeholders).
        file_path: File the hook is being run for.
        timeout: Wall-clock timeout in seconds.

    Returns:
        The process ``returncode`` (zero on success).

    Raises:
        TimeoutError: If the hook process did not finish within *timeout*
            seconds.
        ValueError: If *template* has unbalanced quotes.
    """
    args = _build_argv(template, file_path)
    try:
        completed = subprocess.run(  # noqa: UP022 — spec mandates explicit stdout/stderr=PIPE
            args,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Hook timed out after {timeout}s: {template}") from exc
    return completed.returncode


def spawn_background_hook(template: str, file_path: Path) -> None:
    """Spawn *template* detached in the background and return immediately.

    Output is discarded. On Windows the process gets
    ``CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS``; on POSIX we use
    ``start_new_session=True``. Missing executables are swallowed so a
    misconfigured hook never crashes the caller.

    Args:
        template: Raw command template (with ``{token}`` placeholders).
        file_path: File the hook is being run for.

    Returns:
        ``None``. Output is intentionally discarded.
    """
    args = _build_argv(template, file_path)
    popen_kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        subprocess.Popen(args, **popen_kwargs)  # pylint: disable=consider-using-with
    except FileNotFoundError:
        # Best-effort: don't crash the caller if the hook binary is missing.
        return
    except OSError:
        # Same posture for any other OS-level spawn failure (permissions, etc.).
        return


def run_hooks_for_file(
    file_path: Path,
    config: AppConfig,
    *,
    logger: logging.Logger | None = None,
) -> HookOutcome:
    """Run the hook pipeline for *file_path* and return the launch decision.

    Order of phases is fixed (``before`` → ``confirm`` → ``abort`` → ``instead``);
    a phase short-circuiting with :attr:`HookOutcome.ABORT` or
    :attr:`HookOutcome.SKIP` stops the pipeline. ``after`` hooks are
    fire-and-forget and run only when the pipeline resolves to
    :attr:`HookOutcome.CONTINUE`.

    Args:
        file_path: File the caller is about to launch.
        config: Loaded :class:`AppConfig`; consulted for hooks + failmode
            + timeout.
        logger: Optional logger for warnings. When ``None``, the module-level
            ``"profiles"`` logger is used.

    Returns:
        The :class:`HookOutcome` decision for the caller.
    """
    log = logger if logger is not None else _logger
    ext_key = file_path.suffix.lower()

    if not ext_key or ext_key not in config.launch_hooks:
        return HookOutcome.CONTINUE

    hooks = config.launch_hooks.get(ext_key, ())
    if not hooks:
        return HookOutcome.CONTINUE

    synchronous: list[HookSpec] = [hook for hook in hooks if hook.when != "after"]
    after_hooks: list[HookSpec] = [hook for hook in hooks if hook.when == "after"]

    for hook in synchronous:
        if hook.when == "confirm":
            outcome = _run_confirmation_hook(hook, file_path, log)
            if outcome is not HookOutcome.CONTINUE:
                return outcome
        else:
            outcome = _run_synchronous_hook(hook, file_path, config, log)
            if outcome is not None:
                return outcome

    for hook in after_hooks:
        _spawn_after_hook(hook, file_path, log)

    return HookOutcome.CONTINUE


def _run_confirmation_hook(
    hook: HookSpec,
    file_path: Path,
    log: logging.Logger,
) -> HookOutcome:
    """Run a confirmation hook and return the user's launch decision.

    Args:
        hook: Confirmation hook spec.
        file_path: File being launched.
        log: Logger for warnings and info.

    Returns:
        HookOutcome.CONTINUE if confirmed, HookOutcome.ABORT if cancelled/closed.
    """
    try:
        # Substitute tokens in confirmation message
        message = _substitute_tokens(hook.template, file_path)
        confirmed = confirm_dialog(message, title="Launch Confirmation")

        if confirmed:
            return HookOutcome.CONTINUE

        log.info("Launch cancelled by user: %s", file_path)
        return HookOutcome.ABORT
    except Exception as exc:
        log.warning("Confirmation hook failed: %s", exc)
        return HookOutcome.ABORT


def _run_synchronous_hook(
    hook: HookSpec,
    file_path: Path,
    config: AppConfig,
    log: logging.Logger,
) -> HookOutcome | None:
    """Run a single synchronous hook and return an outcome or ``None``.

    Returns ``None`` when the hook succeeded (or non-fatally failed) and the
    pipeline should continue to the next hook.
    """
    try:
        returncode = run_blocking_hook(
            hook.template,
            file_path,
            timeout=config.launch_hook_timeout,
        )
    except TimeoutError as exc:
        log.warning("Hook (%s) timed out: %s", hook.when, exc)
        outcome = _failmode_outcome(config.launch_hook_failmode)
        if hook.requires_success and outcome is HookOutcome.ABORT:
            return HookOutcome.ABORT
        return None

    if returncode == 0:
        return _outcome_on_success(hook.when)

    # Hook failed (non-zero return code)
    log.warning(
        "Hook (%s) failed with return code %d: %s",
        hook.when,
        returncode,
        hook.template,
    )

    if hook.when == "abort":
        return HookOutcome.ABORT

    if hook.requires_success:
        outcome = _failmode_outcome(config.launch_hook_failmode)
        if outcome is not None:
            return outcome
        return None  # "warn" failmode continues pipeline

    return None


def _outcome_on_success(when: str) -> HookOutcome | None:
    """Map a successful synchronous hook to its outcome.

    ``before`` returns ``None`` (continue pipeline). ``abort`` returning 0
    means the abort hook succeeded ⇒ proceed. ``instead`` returning 0 means
    the OS launch is replaced ⇒ :attr:`HookOutcome.SKIP`.
    """
    if when == "instead":
        return HookOutcome.SKIP
    if when == "abort":
        return HookOutcome.CONTINUE
    return None


def _failmode_outcome(failmode: str) -> HookOutcome | None:
    """Map ``launch_hook_failmode`` to the corresponding :class:`HookOutcome`.

    Returns ``None`` for ``"warn"`` (continue, log warning) so the caller
    can decide the next phase.
    """
    if failmode == "abort":
        return HookOutcome.ABORT
    if failmode == "skip":
        return HookOutcome.SKIP
    return None


def _spawn_after_hook(
    hook: HookSpec,
    file_path: Path,
    log: logging.Logger,
) -> None:
    """Spawn an ``after`` hook and log any unexpected failure."""
    try:
        spawn_background_hook(hook.template, file_path)
    except (ValueError, OSError) as exc:
        log.warning("after hook failed to spawn: %s", exc)


__all__ = [
    "HookOutcome",
    "parse_hook_entries",
    "run_hooks_for_file",
    "run_blocking_hook",
    "spawn_background_hook",
]
