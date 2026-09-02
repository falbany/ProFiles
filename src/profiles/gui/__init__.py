"""GUI modules for ProFiles."""

from __future__ import annotations

import os

_BACKEND = os.environ.get("PROFILES_GUI_BACKEND", "tk").lower()

if _BACKEND == "qt":
    from profiles.gui.qt import context_menu, main_window, search_bar, status_bar, styles, ui
    from profiles.gui.qt.controllers import (
        directory_manager,
        scan_controller,
        window_actions,
    )
else:
    from profiles.gui.tk import context_menu, main_window, search_bar, status_bar, styles, ui
    from profiles.gui.tk.controllers import (
        directory_manager,
        scan_controller,
        window_actions,
    )

# Shared, always imported from the canonical location.
from profiles.gui import i18n, theme  # noqa: E402
from profiles.gui.presentation import row_colors  # noqa: E402

__all__ = [
    "main_window",
    "search_bar",
    "status_bar",
    "context_menu",
    "styles",
    "ui",
    "theme",
    "i18n",
    "row_colors",
    "directory_manager",
    "scan_controller",
    "window_actions",
]
