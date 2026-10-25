"""Skip every test collected under ``tests/gui`` — the Tkinter GUI is deprecated.

The web/React frontend is the default (phase 1 of the removal plan already
moved business logic into ``profiles.core``); phase 2 will delete
``src/profiles/gui`` together with this directory. Until then, every test
here stays collected but skipped, so the deprecation remains visible in the
suite summary instead of silently passing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent

TKINTER_DEPRECATION_REASON = (
    "Tkinter GUI is deprecated — web frontend is the default. "
    "Skipped in preparation for removal (phase 2 deletes src/profiles/gui)."
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark every item collected under tests/gui as skipped."""
    for item in items:
        if item.path.is_relative_to(_HERE):
            item.add_marker(pytest.mark.skip(reason=TKINTER_DEPRECATION_REASON))
