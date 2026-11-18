"""Top-level configuration entry points — ``load_config`` and ``propose_config_creation``.

Single Responsibility: discover / load ``.profiles`` (with ``.profiles.yaml``
as a fallback) and offer to bootstrap one when absent. Composes
:class:`ConfigReader` and :func:`find_config_file`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from profiles.core.config.io.yaml_io import (
    find_config_file,
)
from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
from profiles.core.paths import (
    default_config_path,
    default_search_directory,
    find_user_config,
    is_uninformative_directory,
    user_data_dir,
)


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Load the application configuration.

    With *config_path*, uses that directly. Otherwise searches the folder
    tree for a configuration file starting from the working directory
    (canonical ``.profiles`` names first, then any ``*.profiles``-style
    file, ascending) — skipping the search when the working directory is
    uninformative (``System32``, home, interpreter/app install roots;
    issue #191). When no project config is found, the per-user default
    ``~/.profiles/.profiles`` is loaded when it exists; failing that,
    defaults are returned bound to :func:`default_config_path` (the
    per-user path for launcher-style launches, the project folder for
    terminal launches).

    Args:
        config_path: Optional explicit path to the configuration file.

    Returns:
        An :class:`AppConfig` instance (with defaults if no file is found).
    """
    if config_path is not None:
        return ConfigReader(config_path).load()

    try:
        start = Path.cwd()
    except OSError:
        start = None

    if not is_uninformative_directory(start):
        found = find_config_file()
        if found is not None:
            return ConfigReader(found).load()

    user_config = find_user_config()
    if user_config is not None:
        return ConfigReader(user_config).load()

    # No .profiles found anywhere — use defaults bound to the policy-chosen
    # default path (~/.profiles/.profiles for launcher starts).
    return ConfigReader(default_config_path(start)).load()


def propose_config_creation() -> bool:
    """Propose to create a default ``.profiles`` configuration file.

    Prompts the user in CLI mode to create a default configuration
    file at :func:`default_config_path` (the project folder for a
    terminal launch, ``~/.profiles/.profiles`` for launcher-style
    launches; issue #191).

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
        target = default_config_path()
        if target.exists():
            print(f"Warning: {target} already exists. Creation skipped.")
            return False

        try:
            # The per-user data directory may not exist yet on a fresh
            # install; write_starter_config requires an existing parent.
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"\n✗ Error creating configuration directory: {exc}", file=sys.stderr)
            return False

        from profiles.core.actions import ActionStatus, write_starter_config

        # Same rule as profiles.launch.creation (#191): a normal project
        # target scans itself; the per-user data directory only holds logs
        # and configs, so the template falls back to the policy default.
        search_dir = (
            default_search_directory() if target.parent == user_data_dir() else target.parent
        )
        result = write_starter_config(target, cwd=search_dir)
        if result.status is ActionStatus.SUCCESS:
            print(f"\n✓ Default configuration created: {target}")
            print("\nYou can now customize this file to suit your needs.")
            return True
        else:
            print(f"\n✗ Error creating configuration file: {result.message}", file=sys.stderr)
            return False

    print("\nContinuing with default settings.")
    print("You can create a configuration later with: python -m profiles --init")
    return False


__all__ = ["load_config", "propose_config_creation"]
