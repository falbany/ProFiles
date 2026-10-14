"""Build the ProFiles web frontend from this folder or the repository root."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent


def _run_npm(*arguments: str) -> None:
    """Run npm in the web package directory."""
    command = " ".join(("npm", *arguments))
    print(f"> {command}", flush=True)
    subprocess.run(command, cwd=WEB_ROOT, check=True, shell=True)


def main() -> int:
    """Install missing dependencies and build the production frontend."""
    if shutil.which("npm") is None:
        print("npm was not found. Install Node.js with npm and try again.", file=sys.stderr)
        return 1

    try:
        if not (WEB_ROOT / "node_modules").is_dir():
            _run_npm("ci")
        _run_npm("run", "build")
    except subprocess.CalledProcessError as error:
        return error.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
