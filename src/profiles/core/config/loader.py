"""Top-level configuration entry points — ``load_config`` and ``propose_config_creation``.

Single Responsibility: discover / load ``.profiles`` (with ``.profiles.yaml``
as a fallback) and offer to bootstrap one when absent. Composes
:class:`ConfigReader` and :func:`find_config_file`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from profiles.core.config.io.yaml_io import (
    PRIMARY_CONFIG_NAME,
    find_config_file,
)
from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Load the application configuration.

    Searches the folder tree for a ``.profiles`` file starting from the
    working directory. If *config_path* is provided, uses that directly.
    Falls back to ``.profiles.yaml`` (backward compatibility) when no
    ``.profiles`` file is found, then to defaults.

    Args:
        config_path: Optional explicit path to the configuration file.

    Returns:
        An :class:`AppConfig` instance (with defaults if no file is found).
    """
    if config_path is not None:
        return ConfigReader(config_path).load()

    found = find_config_file()
    if found is not None:
        return ConfigReader(found).load()

    # No .profiles found anywhere — use defaults from the primary path
    return ConfigReader(Path.cwd() / PRIMARY_CONFIG_NAME).load()


def propose_config_creation() -> bool:
    """Propose to create a default ``.profiles`` configuration file.

    Prompts the user in CLI mode to create a default configuration
    file in the current working directory.

    Returns:
        ``True`` if user accepts and the file is created, ``False`` otherwise.
    """
    print("\n" + "=" * 70)
    print("No .profiles configuration file found.")
    print("=" * 70)
    print("\nProFile searches for '.profiles' (or the legacy '.profiles.yaml')")
    print("in the current directory and up to 5 levels of subdirectories.")
    print("No configuration was found.")
    print("\nWould you like to create a default configuration file now? [y/N]: ", end="")
    sys.stdout.flush()

    try:
        response = input().strip().lower()
    except EOFError:
        return False

    if response in ("y", "yes"):
        target = Path.cwd() / PRIMARY_CONFIG_NAME
        if target.exists():
            print(f"Warning: {target} already exists. Creation skipped.")
            return False

        from profiles.core.config.template import STARTER_CONFIG_TEMPLATE

        body = STARTER_CONFIG_TEMPLATE.format(cwd=str(Path.cwd()))
        try:
            target.write_text(body, encoding="utf-8")
            print(f"\n✓ Default configuration created: {target}")
            print("\nYou can now customize this file to suit your needs.")
            return True
        except OSError as exc:
            print(f"\n✗ Error creating configuration file: {exc}", file=sys.stderr)
            return False

    print("\nContinuing with default settings.")
    print("You can create a configuration later with: python -m profiles --init")
    return False


__all__ = ["load_config", "propose_config_creation"]
