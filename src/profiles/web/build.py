#!/usr/bin/env python3
"""CLI tool to rebuild the web frontend."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent

# Standard Node.js install locations per platform, used when the npm first
# on PATH is unusable (e.g. a conda env installed under another user's
# profile whose node cannot be executed by the current account).
_NODE_FALLBACK_DIRS: dict[str, list[str]] = {
    "win32": [r"C:\Program Files\nodejs", r"C:\Program Files (x86)\nodejs"],
    "darwin": ["/opt/homebrew/bin", "/usr/local/bin"],
    "linux": ["/usr/local/bin", "/usr/bin"],
}


def _npm_runs(env: dict[str, str]) -> bool:
    """Check that the npm resolved from env's PATH actually executes.

    A broken installation fails here rather than at build time, so it can
    be detected before any work is done.
    """
    try:
        result = subprocess.run(
            "npm --version",
            shell=True,
            capture_output=True,
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _has_npm(directory: Path) -> bool:
    """Check whether a directory contains an npm launcher."""
    name = "npm.cmd" if sys.platform == "win32" else "npm"
    return (directory / name).exists()


def _build_env() -> dict[str, str] | None:
    """Return an environment whose PATH provides a working npm.

    Returns os.environ unchanged when the first npm on PATH works;
    otherwise tries the platform's standard Node.js install locations,
    prepending the first healthy one. Returns None when no usable npm
    is found.
    """
    if _npm_runs(os.environ.copy()):
        return os.environ.copy()
    for directory in _NODE_FALLBACK_DIRS.get(sys.platform, []):
        if _has_npm(Path(directory)):
            env = os.environ.copy()
            env["PATH"] = directory + os.pathsep + env.get("PATH", "")
            if _npm_runs(env):
                print(f"INFO: Using Node.js from {directory}")
                return env
    return None


def _needs_rebuild(marker_file: Path) -> bool:
    """Check if rebuild is needed by scanning all source files.

    Checks:
    - package.json (dependency changes)
    - All TypeScript/React source files (.tsx, .ts)
    - Stylesheet files (.css, .scss, .sass)
    - HTML template files (.html)

    Returns:
        True if any source file is newer than the marker file
    """
    if not marker_file.exists():
        return True

    marker_mtime = marker_file.stat().st_mtime

    # Check package.json for dependency changes
    package_json = WEB_ROOT / "package.json"
    if package_json.exists() and package_json.stat().st_mtime > marker_mtime:
        return True

    # Check all source files for modifications
    source_patterns = [
        "**/*.tsx",  # React/TypeScript JSX
        "**/*.ts",  # TypeScript
        "**/*.css",  # Stylesheets
        "**/*.scss",  # Sass styles
        "**/*.html",  # HTML templates
    ]

    for pattern in source_patterns:
        for source_file in WEB_ROOT.glob(pattern):
            # Skip node_modules and dist directories
            if "node_modules" in str(source_file) or "dist" in str(source_file):
                continue
            if source_file.stat().st_mtime > marker_mtime:
                return True

    return False


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

    # Resolve a working npm (falls back to standard install locations
    # when the one first on PATH is unusable)
    env = _build_env()
    if env is None:
        print("ERROR: npm not found or not usable.", file=sys.stderr)
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
            subprocess.run(command, cwd=WEB_ROOT, check=True, shell=True, env=env)

        # Build
        command = "npm run build"
        print(f"> {command}", flush=True)
        subprocess.run(command, cwd=WEB_ROOT, check=True, shell=True, env=env)

        marker_file.touch()
        print("SUCCESS: Build successful.")
        return 0
    except subprocess.CalledProcessError as error:
        print(f"ERROR: Build failed: {error}", file=sys.stderr)
        return error.returncode


if __name__ == "__main__":
    sys.exit(main())
