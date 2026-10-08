"""Qt layout helpers for consistent UI structure."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget


def create_vertical_layout(
    parent: QWidget | None = None,
    spacing: int = 8,
    margin: int = 8,
) -> QVBoxLayout:
    """Create a vertical layout with consistent spacing and margins.

    Args:
        parent: Parent widget to set as layout parent.
        spacing: Spacing between widgets in pixels.
        margin: Layout margin in pixels.

    Returns:
        Configured QVBoxLayout instance.
    """
    layout = QVBoxLayout(parent)
    layout.setSpacing(spacing)
    layout.setContentsMargins(margin, margin, margin, margin)
    return layout


def create_horizontal_layout(
    parent: QWidget | None = None,
    spacing: int = 8,
    margin: int = 8,
) -> QHBoxLayout:
    """Create a horizontal layout with consistent spacing and margins.

    Args:
        parent: Parent widget to set as layout parent.
        spacing: Spacing between widgets in pixels.
        margin: Layout margin in pixels.

    Returns:
        Configured QHBoxLayout instance.
    """
    layout = QHBoxLayout(parent)
    layout.setSpacing(spacing)
    layout.setContentsMargins(margin, margin, margin, margin)
    return layout


def create_splitter(
    orientation: str = "vertical",
    children: list[QWidget] | None = None,
) -> QSplitter:
    """Create a QSplitter with specified orientation.

    Args:
        orientation: "vertical" or "horizontal".
        children: Optional list of widgets to add as children.

    Returns:
        Configured QSplitter instance.
    """
    from PySide6.QtCore import Qt

    splitter = QSplitter(
        Qt.Orientation.Vertical if orientation == "vertical" else Qt.Orientation.Horizontal
    )
    if children:
        for widget in children:
            splitter.addWidget(widget)
    return splitter
