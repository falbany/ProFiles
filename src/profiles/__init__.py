"""ProFiles - A modern GUI launcher for production test programs.

ProFiles propose a graphical interface to browse, filter,
and launch files with flexible configuration.
"""

from __future__ import annotations

import re
from pathlib import Path

__author__ = "Florent ALBANY"
__license__ = "MIT"


def _resolve_version() -> str:
    """Return the package version.

    Source of truth is ``pyproject.toml`` at the repo root. We first try
    ``importlib.metadata`` for installed packages, then fall back to parsing
    ``pyproject.toml`` for editable installs or development environments.
    """
    # Primary: use importlib.metadata for installed packages
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("profiles")
    except PackageNotFoundError:
        # Package not installed via pip, fall back to pyproject.toml
        pass
    except Exception:
        # Any other error (permissions, corrupted install, etc.)
        pass

    # Fallback: parse pyproject.toml for editable installs
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.exists():
        match = re.search(
            r'^version\s*=\s*"([^"]+)"',
            pyproject.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return match.group(1)

    # Last resort: return a development version string
    return "0.0.0-dev"


__version__ = _resolve_version()


def __getattr__(name: str):
    """Expose selected callables lazily (PEP 562).

    The Briefcase stub resolves ``profiles.main``; keep it a lazy attribute
    so ``import profiles`` stays cheap for headless/web usage.
    """
    if name == "main":
        from profiles.app import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
