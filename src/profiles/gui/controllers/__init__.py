"""Controllers — orchestrate widgets with core actions.

Tk-dependent, no I/O knowledge. Each controller encapsulates a cluster
of related methods that previously lived on :class:`MainWindow`.
"""
from profiles.gui.controllers.directory_manager import (
    DirectoryManager,
    format_dir_entry,
    strip_dir_label,
)
from profiles.gui.controllers.scan_controller import (
    ScanQueue,
    ScanResult,
    run_scan,
)
from profiles.gui.controllers.window_actions import WindowActions

__all__ = [
    "DirectoryManager",
    "ScanQueue",
    "ScanResult",
    "WindowActions",
    "format_dir_entry",
    "run_scan",
    "strip_dir_label",
]
