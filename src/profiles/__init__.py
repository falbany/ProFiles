"""ProFiles - A modern GUI launcher for production test programs.

ProFiles propose a graphical interface to browse, filter,
and launch files with flexible configuration.
"""

from __future__ import annotations

__author__ = "Florent ALBANY"
__license__ = "MIT"


def _resolve_version() -> str:
    """Return the package version.

    Resolution order: installed package metadata (dist-info), the
    hatch-vcs generated ``profiles._version`` module (editable/dev
    builds), then a development sentinel for git-less source trees.
    """
    # Primary: use importlib.metadata for installed packages. The PEP 621
    # distribution name is "profiles-app"; "profiles" covers legacy
    # setuptools installs. The import stays function-local (importlib.metadata
    # is stdlib on every supported Python) to keep ``import profiles`` cheap.
    from importlib.metadata import PackageNotFoundError, version

    try:
        try:
            return version("profiles-app")
        except PackageNotFoundError:
            return version("profiles")
    except Exception:
        # Not installed via pip, or metadata unreadable (permissions,
        # corrupted install, etc.) — fall through to the vcs module.
        pass

    # Fallback: version module generated at build time by hatch-vcs
    try:
        from profiles._version import version as vcs_version
    except ImportError:
        return "0.0.0-dev"
    return str(vcs_version)


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
