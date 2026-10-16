#!/usr/bin/env python3
"""CLI tool to rebuild the web frontend."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent


def _needs_rebuild(marker_file: Path) -> bool:
    """Check if rebuild is needed."""
    if not marker_file.exists():
        return True

    package_json = WEB_ROOT / "package.json"
    return package_json.stat().st_mtime > marker_file.stat().st_mtime


def main() -> int:
    """Main entry point for web build CLI."""
    parser = argparse.ArgumentParser(description="Build the ProFiles web frontend")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if assets are up to date",
    )
    args = parser.parse_args()

    dist_dir = WEB_ROOT / "dist"
    marker_file = dist_dir / ".web-build-marker"

    # Check npm availability
    if shutil.which("npm") is None:
        print("ERROR: npm not found.", file=sys.stderr)
        print("   Please install Node.js: https://nodejs.org", file=sys.stderr)
        return 1

    # Skip if not forced and no rebuild needed
    if not args.force and not _needs_rebuild(marker_file):
        print("INFO: Web assets are up to date. Use --force to rebuild.")
        return 0

    # Run build
    print("Building web frontend...")
    try:
        # Install dependencies
        if not (WEB_ROOT / "node_modules").is_dir():
            command = "npm ci"
            print(f"> {command}", flush=True)
            subprocess.run(command, cwd=WEB_ROOT, check=True, shell=True)

        # Build
        command = "npm run build"
        print(f"> {command}", flush=True)
        subprocess.run(command, cwd=WEB_ROOT, check=True, shell=True)

        marker_file.touch()
        print("SUCCESS: Build successful.")
        return 0
    except subprocess.CalledProcessError as error:
        print(f"ERROR: Build failed: {error}", file=sys.stderr)
        return error.returncode


if __name__ == "__main__":
    sys.exit(main())
