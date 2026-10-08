"""GUI event bus for Qt backend communication."""

from PySide6.QtCore import QObject, Signal


class GuiEventBus(QObject):
    """Event bus for GUI communication with typed signals."""

    scan_started: Signal = Signal(int)
    scan_finished: Signal = Signal(int, list)
    scan_failed: Signal = Signal(int, str)
    directory_changed: Signal = Signal(str)
    theme_changed: Signal = Signal(str)
