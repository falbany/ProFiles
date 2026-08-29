"""Presentation layer — pure rendering helpers, no business logic.

Each module here must be importable without instantiating Tk widgets
and must not touch the filesystem or core configuration.
"""

from profiles.gui.presentation.row_colors import (
    RowColorRules,
    default_tag_name,
    make_rule_tag_name,
)

__all__ = [
    "RowColorRules",
    "default_tag_name",
    "make_rule_tag_name",
]
