"""Notify message dialog with blocking/non-blocking support."""

from __future__ import annotations

from profiles.core.environment.render import render_text


def _print_headless(content: str, title: str) -> None:
    """Print the rendered message to the console (headless fallback)."""
    rendered = render_text(content, headless=True)
    if isinstance(rendered, str):
        print(f"[{title}] {rendered}")


def render_into_text_widget(text_widget, content: str) -> None:
    """Render Markdown *content* into a Tk ``Text`` widget.

    Configures the standard style tags and inserts the rendered
    :func:`render_text` segments. Shared by the notify dialog and the
    3-way confirmation dialog's optional pre-message.
    """
    rendered_tree = render_text(content, headless=False)

    text_widget.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
    text_widget.tag_configure("italic", font=("TkDefaultFont", 10, "italic"))
    text_widget.tag_configure("heading", font=("TkDefaultFont", 14, "bold"))
    text_widget.tag_configure("code", font=("TkFixedFont", 10))

    if isinstance(rendered_tree, list):
        for seg in rendered_tree:
            if seg.style == "normal":
                text_widget.insert("end", seg.text)
            else:
                text_widget.insert("end", seg.text, (seg.style,))
    else:
        text_widget.insert("1.0", str(rendered_tree))


def show_notify_dialog(
    content: str,
    title: str = "Message",
    blocking: bool = True,
    headless: bool = False,
) -> None:
    """Show a notify message dialog.

    Args:
        content: Message content (may include Markdown / escape sequences).
        title: Dialog title.
        blocking: If True, blocks until closed by user.
        headless: If True, prints formatted message to console instead of GUI.
    """
    if headless:
        _print_headless(content, title)
        return

    try:
        import tkinter as tk

        root = tk.Tk()
        root.title(title)

        text_widget = tk.Text(root, wrap="word", width=60, height=15)
        render_into_text_widget(text_widget, content)

        text_widget.pack(padx=10, pady=10)

        if blocking:
            tk.Button(root, text="OK", width=10, command=root.destroy).pack(pady=10)
            root.wait_window(root)
        else:
            root.attributes("-topmost", True)
            root.after(3000, root.destroy)  # Auto-close after 3 seconds in non-blocking
    except (ImportError, tk.TclError):
        # Fallback to headless
        _print_headless(content, title)


__all__ = ["render_into_text_widget", "show_notify_dialog"]
