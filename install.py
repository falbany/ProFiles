"""ProFiles Installation Wizard
A modern, interactive installer for the ProFiles package.
"""

import platform
import subprocess
import sys
from pathlib import Path


# --- Bootstrap Rich ---
def bootstrap_rich():
    """Bootstrap the 'rich' library, installing it if necessary."""
    try:
        import importlib.util

        # Check if rich is available without importing all submodules
        if importlib.util.find_spec("rich") is None:
            raise ImportError("rich not found")

        return True
    except ImportError:
        print("Installing 'rich' for a better experience...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])

            # Relaunch the script to load the new module
            print("Relaunching installer...")
            subprocess.check_call([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception as e:
            print(f"Failed to install 'rich': {e}. Proceeding with standard output.")
            return False


if bootstrap_rich():
    from rich import box
    from rich.align import Align
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import IntPrompt, Prompt
    from rich.status import Status
    from rich.table import Table
else:
    # Minimal fallback if rich fails to install
    class FakeConsole:
        def print(self, *args, **kwargs):
            print(*args)

        def clear(self):
            pass

    console = FakeConsole()
    sys.exit("Critical error: 'rich' library is required but could not be installed.")

console = Console()


def command_run(cmd, shell=False):
    """Runs a command and returns True if successful."""
    try:
        subprocess.run(cmd, check=True, shell=shell)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        console.print(f"\n[bold red]Error:[/bold red] Command not found: {cmd[0]}")
        return False


def print_header():
    """Prints the header for the installer."""
    console.clear()
    title = "[bold cyan]ProFiles[/bold cyan]"
    subtitle = "[italic white]Python Flexible File Launcher — Browse, filter, and launch Files[/italic white]"

    header_panel = Panel(
        Align.center(f"{title}\n{subtitle}"),
        box=box.ROUNDED,
        padding=(1, 2),
        style="on black",
        border_style="bright_blue",
    )
    console.print(header_panel)


def main():
    """The main function of the installer."""
    print_header()

    # --- 1. Installation Target ---
    console.print("\n[bold cyan]Step 1: Installation Target[/bold cyan]")
    console.print(
        "  [1] [bold green]New Virtual Environment (.venv)[/bold green] [dim](Isolation recommended)[/dim]"
    )
    console.print(
        "  [2] [bold yellow]System Python[/bold yellow] [dim](Requires global permissions)[/dim]"
    )

    target_choice = IntPrompt.ask("Select your preference", choices=["1", "2"], default=1)

    # --- 2. Installation Mode ---
    console.print("\n[bold cyan]Step 2: Workflow Mode[/bold cyan]")
    console.print("  [1] [bold blue]Standard[/bold blue] [dim](Ready to use tools)[/dim]")
    console.print(
        "  [2] [bold magenta]Development[/bold magenta] [dim](Editable install + full dev suite)[/dim]"
    )

    mode_choice = IntPrompt.ask("Select your workflow", choices=["1", "2"], default=1)

    # --- Configuration Logic ---
    venv_dir = Path(".venv")
    is_windows = platform.system() == "Windows"
    target_str = (
        "Isolated Virtual Environment" if target_choice == 1 else "System Python environment"
    )
    mode_str = "Standard (User)" if mode_choice == 1 else "Development (Editable)"

    # --- Summary ---
    summary_table = Table(box=None, show_header=False, padding=(0, 2))
    summary_table.add_row("Target Location:", f"[bold white]{target_str}[/bold white]")
    summary_table.add_row("Operation Mode:", f"[bold white]{mode_str}[/bold white]")
    summary_table.add_row(
        "Python Version:", f"[bold white]{platform.python_version()}[/bold white]"
    )

    console.print("\n")
    console.print(
        Panel(
            summary_table,
            title="[bold blue]Installation Summary[/bold blue]",
            box=box.ROUNDED,
            border_style="blue",
            padding=(1, 2),
        )
    )

    if Prompt.ask("\nReady to proceed?", choices=["y", "n"], default="y") != "y":
        console.print("\n[bold yellow]Operation aborted by user.[/bold yellow]")
        return

    # --- Execution ---
    with Status("[bold green]Setting up ProFiles...", console=console) as status:
        if target_choice == 1:
            status.update("[bold blue]Creating Virtual Environment...")
            if not command_run([sys.executable, "-m", "venv", str(venv_dir)]):
                console.print("[bold red]Failed to create virtual environment.[/bold red]")
                return
            pip_executable = str(venv_dir / ("Scripts" if is_windows else "bin") / "pip")
        else:
            pip_executable = "pip3" if not is_windows else "pip"

        status.update("[bold magenta]Installing dependencies and package...")

        # Prepare final command
        # In development mode, install with dev dependencies
        if mode_choice == 2:
            # For editable install with extras, use: pip install -e ".[dev]"
            cmd = [pip_executable, "install", "-e", ".[dev]"]
        else:
            cmd = [pip_executable, "install", "."]

        # Sudo handling for system install on Unix
        use_sudo = False
        if target_choice == 2 and not is_windows:
            use_sudo = True
            cmd = ["sudo"] + cmd

        if use_sudo:
            status.stop()
            console.print(
                "\n[bold yellow]System installation requires administrator privileges.[/bold yellow]"
            )
            if not command_run(cmd):
                console.print("\n[bold red]Installation failed. Check permissions.[/bold red]")
                return
        else:
            if not command_run(cmd):
                console.print("\n[bold red]Installation failed.[/bold red]")
                return

    # --- Success Message ---
    success_msg = (
        "[bold green]✨ ProFiles successfully installed![/bold green]\n\n"
        "[bold underline white]Quick Start:[/bold underline white]\n"
    )

    if target_choice == 1:
        activate_cmd = ".venv\\Scripts\\activate" if is_windows else "source .venv/bin/activate"
        success_msg += f"1. Activate venv:    [bold cyan]{activate_cmd}[/bold cyan]\n"
        if mode_choice == 2:
            success_msg += "   [dim]Dev dependencies included[/dim]\n"

    success_msg += "2. Launch GUI:      [bold cyan]ProFiles[/bold cyan]\n"
    success_msg += "3. Headless mode:   [bold cyan]ProFiles --headless[/bold cyan]\n"
    success_msg += "4. Run as module:   [bold cyan]python -m profiles[/bold cyan]\n"
    if mode_choice == 1:
        success_msg += (
            '\n[dim]For development tools, reinstall with: pip install -e ".[dev]"[/dim]\n'
        )

    console.print("\n")
    console.print(Panel(success_msg, border_style="bright_green", padding=(1, 2)))

    # --- Create Desktop Shortcut ---
    console.print("\n[bold cyan]Step 3: Desktop Shortcut[/bold cyan]")
    create_shortcut = Prompt.ask(
        "Create a desktop shortcut for quick access?",
        choices=["y", "n"],
        default="y",
    )

    if create_shortcut == "y":
        try:
            # Import the shortcut creation utility (after adding src to path)
            sys.path.insert(0, str(Path(__file__).parent / "src"))
            from profiles.utils.shortcut import create_shortcut as create_shortcut_file

            source_file = Path(__file__).parent / "ProFiles.pyw"
            if not source_file.exists():
                console.print(
                    "[bold yellow]⚠ ProFiles.pyw not found. Skipping shortcut creation.[/bold yellow]"
                )
            else:
                shortcut_path = create_shortcut_file(source_file)
                console.print(
                    f"\n[bold green]✓ Desktop shortcut created:[/bold green] {shortcut_path}"
                )
                console.print(
                    "  You can now double-click [bold]ProFiles.pyw[/bold] on your desktop to launch."
                )
        except Exception as e:
            console.print(f"\n[bold yellow]⚠ Failed to create shortcut: {e}[/bold yellow]")
            console.print("  You can create it manually later with: python create_shortcut.py")
    else:
        console.print("\n[bold yellow]⚠ Shortcut creation skipped.[/bold yellow]")
        console.print("  You can create it later with: python create_shortcut.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted.[/bold red]")
        sys.exit(1)
