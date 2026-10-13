"""Configuration creation logic for ProFiles.

Single Responsibility: decide *whether* to offer creation of a starter
``.profiles`` file and actually write it when asked.

This module is the only place that initiates config file creation.  It
reuses the existing ``STARTER_CONFIG_TEMPLATE`` and the domain action
``write_starter_config`` so the behaviour is identical to the GUI's
"create config" flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from profiles.core.actions import ActionStatus
from profiles.core.actions import write_starter_config as _write_starter


@dataclass(frozen=True)
class CreationResult:
    """Result of a proposed configuration creation attempt."""

    status: Literal["CREATED", "SKIPPED", "FAILED"]
    path: Path
    message: str


def propose_creation(target: Path) -> CreationResult:
    """Offer to write a starter ``.profiles`` at *target*.

    Args:
        target: Directory where the starter should be written.  The file
            will be created as ``target / ".profiles"``.

    Returns:
        A :class:`CreationResult` with the outcome.  Never raises: every
        failure is encoded in the ``status`` and ``message``.

    Notes:
        - If ``.profiles`` already exists at *target*, the action is
          skipped and the existing file is left untouched.
        - The parent directory is created if it does not exist.
    """
    config_path = target / ".profiles"

    # Do not clobber an existing configuration.
    if config_path.exists():
        return CreationResult(
            status="SKIPPED",
            path=config_path,
            message=f"Configuration already exists at {config_path}",
        )

    # Ensure the parent directory exists.
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return CreationResult(
            status="FAILED",
            path=config_path,
            message=f"Could not create directory {config_path.parent}: {exc}",
        )

    # Delegate to the existing domain action.
    result = _write_starter(config_path)

    if result.status == ActionStatus.SUCCESS:
        return CreationResult(
            status="CREATED",
            path=config_path,
            message=f"Created starter configuration at {config_path}",
        )
    else:
        return CreationResult(
            status="FAILED",
            path=config_path,
            message=result.message,
        )


__all__ = ["CreationResult", "propose_creation"]
