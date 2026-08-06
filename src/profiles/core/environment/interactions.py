"""User interaction primitives — confirmation dialogs for launch hooks.

Single Responsibility: provide user-facing interaction primitives that work in
both GUI and headless modes. No Tkinter imports at module level.
"""

from __future__ import annotations

import sys


def confirm_dialog(
    message: str,
    title: str = "Confirmation",
    timeout: int | None = None,
) -> bool:
    """Show a yes/no confirmation dialog.

    In GUI mode (Tkinter available): displays a messagebox.askyesno() dialog.
    In headless mode: prompts the user via terminal input.

    Args:
        message: The confirmation message to display.
        title: Dialog/window title.
        timeout: Ignored in the initial implementation (reserved for future use).

    Returns:
        True if user confirms (Yes/y), False if cancelled (No/n/timeout).

    Raises:
        KeyboardInterrupt: If user interrupts during headless input.
    """
    # Try GUI mode first
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()  # Hide main window
        result = bool(messagebox.askyesno(title, message))
        root.destroy()
        return result
    except ImportError:
        pass  # No Tkinter — fall back to headless
    except tk.TclError:
        pass  # No display available — fall back to headless

    # Headless mode
    response = input(f"{title}: {message} [y/N]: ").strip().lower()
    return response in ("y", "yes")


__all__ = [
    "confirm_dialog",
]