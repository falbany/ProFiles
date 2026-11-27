"""Tests for ``scanner.effective_search_boundary`` — watch-mode boundary (#223).

The boundary helper is the single source of truth for what the watch
probe samples: the same depth/excludes merge a scan of the same root
would apply, with a non-recursive boundary forcing depth 0 (root only).
"""

from __future__ import annotations

from profiles.core.config.models import AppConfig
from profiles.core.processing.scanner import effective_search_boundary


def _boundary_config() -> AppConfig:
    """Config with a non-default depth and exclusion to observe the merge."""
    return AppConfig(
        search_dir="/programs",
        max_search_depth=4,
        search_exclude_dirs=("node_modules",),
    )


def test_boundary_recursive_uses_config_depth_and_excludes() -> None:
    """A recursive boundary carries the config depth and exclude merge."""
    depth, excludes = effective_search_boundary("/programs", _boundary_config(), recursive=True)

    assert depth == 4
    assert excludes == ("node_modules",)


def test_boundary_non_recursive_is_depth_zero() -> None:
    """A non-recursive boundary forces depth 0 but keeps the excludes."""
    depth, excludes = effective_search_boundary("/programs", _boundary_config(), recursive=False)

    assert depth == 0
    assert excludes == ("node_modules",)
