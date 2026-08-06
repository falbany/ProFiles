"""Notify message dialog with blocking/non-blocking support."""

from __future__ import annotations

from profiles.core.environment.render import render_text

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
        rendered = render_text(content, headless=True)
        if isinstance(rendered, str):
            print(f"[{title}] {rendered}")
        return

    try:
        import tkinter as tk

        root = tk.Tk()
        root.title(title)

        text_widget = tk.Text(root, wrap="word", width=60, height=15)
        rendered_tree = render_text(content, headless=False)

        if isinstance(rendered_tree, list):
            # Simple rendering into Tk Text widget
            text_widget.tag_configure("bold", font=("TkDefaultFont", 10, "bold"))
            text_widget.tag_configure("italic", font=("TkDefaultFont", 10, "italic"))
            text_widget.tag_configure("heading", font=("TkDefaultFont", 14, "bold"))
            text_widget.tag_configure("code", font=("TkFixedFont", 10))

            for seg in rendered_tree:
                if seg.style == "normal":
                    text_widget.insert(tk.END, seg.text)
                else:
                    text_widget.insert(tk.END, seg.text, (seg.style,))
        else:
            text_widget.insert("1.0", str(rendered_tree))

        text_widget.pack(padx=10, pady=10)

        if blocking:
            tk.Button(root, text="OK", width=10, command=root.destroy).pack(pady=10)
            root.wait_window(root)
        else:
            root.attributes("-topmost", True)
            root.after(3000, root.destroy)  # Auto-close after 3 seconds in non-blocking
    except (ImportError, tk.TclError):
        # Fallback to headless
        rendered = render_text(content, headless=True)
        if isinstance(rendered, str):
            print(f"[{title}] {rendered}")

__all__ = ["show_notify_dialog"]
