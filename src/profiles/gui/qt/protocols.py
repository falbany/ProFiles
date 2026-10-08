"""Qt protocol definitions for type-safe GUI interfaces."""

from typing import Protocol


class DirectoryView(Protocol):
    """Protocol for directory view components."""

    dir_combo: object
    ext_combo: object
    filter_combo: object

    dir_text: str
    ext_text: str
    filter_text: str

    def set_dir_text(self, text: str) -> None: ...
    def set_ext_text(self, text: str) -> None: ...
    def set_filter_text(self, text: str) -> None: ...


class DialogsProtocol(Protocol):
    """Protocol for dialog operations."""

    def show_error(self, title: str, message: str) -> None: ...
    def show_info(self, title: str, message: str) -> None: ...
    def ask_yes_no(self, title: str, message: str) -> bool: ...
    def select_directory(self, initial_path: str = "") -> str | None: ...
    def select_file(self, filter: str = "", initial_path: str = "") -> str | None: ...
