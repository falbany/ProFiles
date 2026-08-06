#!/usr/bin/env python3
"""ProFiles desktop shortcut.

Double-click this file to launch the ProFiles GUI on Windows, macOS, or Linux.

Behavior:
    * Resolves the right Python automatically:
        1. ``.venv`` next to this file (created by ``install.py``)
        2. ``pythonw`` / ``python3`` already on ``PATH``
    * Bootstraps the ``src/`` layout if the package isn't installed.
    * On Windows, no console flashes because the ``.pyw`` association uses
      ``pythonw.exe``. On macOS, open the file once with the Python Launcher
      (or ``python3``) and tick "Always Open With" for one-click launches.
    * On Linux, mark this file executable (``chmod +x ProFiles.pyw``) and
      your file manager will run it with ``/usr/bin/env python3``.

Run from a terminal for verbose output::

    python3 ProFiles.pyw
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    """Directory containing this script (the ProFiles repo root)."""
    return Path(__file__).resolve().parent


def _venv_python(root: Path) -> str | None:
    """Return the venv interpreter path if one exists, else None."""
    is_windows = os.name == "nt"
    sub = "Scripts" if is_windows else "bin"
    for name in ("pythonw", "python", "python3"):
        candidate = (
            root / ".venv" / sub / f"{name}.exe" if is_windows else root / ".venv" / sub / name
        )
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _system_python() -> str:
    """Fallback interpreter from PATH, preferring Python 3.11+."""
    # First, try to find a recent Python version from PATH
    import shutil

    # List of Python executables to try (in order of preference)
    python_names = ["python3.14", "python3.13", "python3.12", "python3.11", "python3", "python"]

    for name in python_names:
        try:
            path = shutil.which(name)
            if path:
                # Verify it's Python 3.11+ (required for StrEnum)
                import subprocess
                result = subprocess.run(
                    [path, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
                    major, minor = map(int, version.split('.'))
                    if major > 3 or (major == 3 and minor >= 11):
                        return path
        except Exception:
            continue

    # Last resort: use current interpreter
    return sys.executable


def _add_src_to_path(root: Path) -> None:
    """Make the ``src`` layout importable when running from a clone.

    Forces ``src/`` to the front of ``sys.path`` so our ``profiles``
    package wins against stdlib's single-file ``profiles`` module
    (the profiler). The editable-install .pth puts src/ at the tail;
    stdlib wins by default unless we reorder.
    """
    src = root / "src"
    if not src.is_dir():
        return
    src_str = str(src.resolve())
    sys.path[:] = [src_str] + [p for p in sys.path if Path(p).resolve() != Path(src_str).resolve()]
    for name in list(sys.modules):
        if name == "profiles" or name.startswith("profiles."):
            del sys.modules[name]


def _run() -> None:
    root = _project_root()

    # When invoked as ``python3 ProFiles.pyw`` (already inside the right env),
    # we run the GUI in-process — no extra subprocess, faster double-click.
    _add_src_to_path(root)
    os.chdir(root)

    try:
        from profiles.app import ProFileApp  # noqa: E402
    except ModuleNotFoundError as e:
        print(f"ERROR: Cannot import profiles module: {e}")
        print("\nPossible solutions:")
        print("1. Install the package: pip install -e .")
        print("2. Make sure you're in the project root directory")
        print("\nPress Enter to exit...")
        input()
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to import profiles: {e}")
        import traceback
        traceback.print_exc()
        print("\nPress Enter to exit...")
        input()
        sys.exit(1)

    try:
        app = ProFileApp()
        app.run()
    except Exception as e:
        print(f"ERROR: Application failed to start: {e}")
        import traceback
        traceback.print_exc()
        print("\nPress Enter to exit...")
        input()
        sys.exit(1)


def _relaunch_in_venv() -> None:
    """If the current interpreter is *not* the project's venv, hand off to it."""
    root = _project_root()
    venv_py = _venv_python(root)
    if not venv_py or os.path.normcase(venv_py) == os.path.normcase(sys.executable):
        _run()
        return

    print(f"ProFiles: using venv interpreter {venv_py}")
    raise SystemExit(subprocess.call([venv_py, str(__file__)]))


if __name__ == "__main__":
    try:
        _relaunch_in_venv()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        # Catch any unhandled exceptions and display them
        # This prevents the terminal from closing immediately on double-click
        print(f"ERROR: ProFiles failed to start: {e}")
        import traceback
        traceback.print_exc()
        print("\nPress Enter to exit...")
        input()  # Wait for user to press Enter
        sys.exit(1)
