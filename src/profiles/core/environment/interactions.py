"""User interaction primitives — confirmation dialogs for launch hooks.

Single Responsibility: provide user-facing interaction primitives that work in
both GUI and headless modes. No Tkinter imports at module level.
"""

from __future__ import annotations

from typing import Literal


def confirm_dialog(
    message: str,
    title: str = "Confirmation",
    timeout: int | None = None,  # pylint: disable=unused-argument  (reserved)
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


def _headless_3way_choice(
    message: str,
    title: str,
    pre_message: str | None = None,
) -> Literal["yes", "skip", "no"]:
    """Prompt the user via terminal input and map the answer to a 3-way choice."""
    if pre_message:
        from profiles.core.environment.render import render_text

        rendered = render_text(pre_message, headless=True)
        if isinstance(rendered, str) and rendered.strip():
            print(rendered)
    response = input(f"{title}: {message} [y/s/N]: ").strip().lower()
    if response in ("y", "yes"):
        return "yes"
    if response in ("s", "skip"):
        return "skip"
    return "no"


def confirm_dialog_3way(
    message: str,
    title: str = "Confirmation",
    headless: bool = False,
    pre_message: str | None = None,
) -> Literal["yes", "skip", "no"]:
    """Show a yes/skip/no confirmation dialog.

    Args:
        message: The message/question to ask.
        title: Dialog title.
        headless: If True, uses console input instead of Tkinter.
        pre_message: Optional Markdown message rendered ABOVE the question
            text (a workflow step's ``message`` shown in the same dialog).
            Ignored when empty/None.

    Returns:
        "yes", "skip", or "no".
    """
    if headless:
        return _headless_3way_choice(message, title, pre_message)

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()

        result: list[Literal["yes", "skip", "no"]] = ["no"]

        def on_yes():
            result[0] = "yes"
            dialog.destroy()

        def on_skip():
            result[0] = "skip"
            dialog.destroy()

        def on_no():
            result[0] = "no"
            dialog.destroy()

        dialog = tk.Toplevel(root)
        dialog.title(title)
        dialog.protocol("WM_DELETE_WINDOW", on_no)

        if pre_message:
            from profiles.core.environment.message_dialog import render_into_text_widget

            pre_text = tk.Text(
                dialog, wrap="word", width=54, height=8, borderwidth=0, highlightthickness=0
            )
            render_into_text_widget(pre_text, pre_message)
            pre_text.configure(state="disabled")
            pre_text.pack(padx=20, pady=(15, 5))

        tk.Label(dialog, text=message, wraplength=400, justify="left").pack(padx=20, pady=10)
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(padx=20, pady=10)

        tk.Button(btn_frame, text="Yes", width=8, command=on_yes).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Skip", width=8, command=on_skip).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="No", width=8, command=on_no).pack(side=tk.LEFT, padx=5)

        root.wait_window(dialog)
        root.destroy()
        return result[0]
    except (ImportError, tk.TclError):
        # Fallback to headless if Tkinter unavailable or no display
        return _headless_3way_choice(message, title, pre_message)


__all__ = [
    "confirm_dialog",
    "confirm_dialog_3way",
]
