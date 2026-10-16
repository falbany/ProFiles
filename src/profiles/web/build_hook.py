"""Hatch build hook for web frontend build."""

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface

    HAS_HATCHLING = True
except ImportError:
    HAS_HATCHLING = False
    BuildHookInterface = object  # type: ignore


def _needs_rebuild(web_dir: Path, marker_file: Path) -> bool:
    """Check if frontend needs to be rebuilt."""
    # If marker doesn't exist, rebuild needed
    if not marker_file.exists():
        return True

    # Check if package.json changed
    package_json = web_dir / "package.json"
    marker_mtime = marker_file.stat().st_mtime
    package_mtime = package_json.stat().st_mtime

    return package_mtime > marker_mtime


def _handle_no_npm(dist_dir: Path, marker_file: Path) -> None:
    """Handle case when npm is not installed."""
    has_marker = marker_file.exists()
    if has_marker:
        print("ℹ️  Using pre-built web assets (npm not found).")
    else:
        print("⚠️  WARNING: npm not found. Using pre-built web assets.", file=sys.stderr)
        print("   For the latest version, install Node.js and run:", file=sys.stderr)
        print("     python -m profiles.web.build", file=sys.stderr)
        print("   Download Node.js: https://nodejs.org", file=sys.stderr)


def _handle_build_failure(dist_dir: Path, marker_file: Path) -> None:
    """Handle build failure gracefully."""
    has_content = any(dist_dir.iterdir()) if dist_dir.exists() else False
    if has_content:
        print("⚠️  WARNING: Web build failed. Using existing assets.", file=sys.stderr)
        print("   To rebuild: python -m profiles.web.build", file=sys.stderr)
    else:
        print("⚠️  WARNING: Web build failed and no fallback available.", file=sys.stderr)
        print("   The web frontend will not be functional.", file=sys.stderr)


def _run_npm_build(web_dir: Path, npm_path: str) -> bool:
    """Execute npm build command."""
    try:
        # Install dependencies
        subprocess.run(
            [npm_path, "ci"],
            cwd=web_dir,
            check=True,
            capture_output=True,
        )

        # Build
        subprocess.run(
            [npm_path, "run", "build"],
            cwd=web_dir,
            check=True,
            capture_output=True,
        )

        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ npm build failed: {e}", file=sys.stderr)
        return False


class WebBuildHook(BuildHookInterface):
    """Build hook to compile React frontend during installation."""

    def initialize(self, version: str, build_data: dict) -> None:
        """Run before building the package."""
        web_dir = Path(self.root) / "src" / "profiles" / "web"
        dist_dir = web_dir / "dist"
        marker_file = dist_dir / ".web-build-marker"

        # Skip if dist doesn't exist at all
        if not dist_dir.exists():
            print("⚠️  WARNING: Web dist/ directory not found.", file=sys.stderr)
            print("   The web frontend will not be available.", file=sys.stderr)
            return

        # Check if npm is available
        npm_path = shutil.which("npm")
        if not npm_path:
            _handle_no_npm(dist_dir, marker_file)
            return

        # Check if rebuild is needed
        if not _needs_rebuild(web_dir, marker_file):
            print("ℹ️  Web assets already built, skipping...")
            return

        # Run npm build
        print("🌐 Building web frontend...")
        success = _run_npm_build(web_dir, npm_path)

        if success:
            marker_file.touch()
            print("✅ Web build successful.")
        else:
            _handle_build_failure(dist_dir, marker_file)
