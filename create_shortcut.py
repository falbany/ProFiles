#!/usr/bin/env python3
"""Create desktop shortcut for ProFiles.

Usage:
    python create_shortcut.py

This script copies ProFiles.pyw to the desktop for easy access.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    """Main entry point."""
    # Get the project root (where this script is located)
    project_root = Path(__file__).resolve().parent

    # Source file to copy
    source_file = project_root / "ProFiles.pyw"

    if not source_file.exists():
        print(f"✗ ERROR: {source_file} not found!")
        print("  Make sure ProFiles.pyw exists in the project root.")
        sys.exit(1)

    # Import the utility function
    sys.path.insert(0, str(project_root / "src"))
    from profiles.utils.shortcut import create_shortcut

    print("Creating ProFiles shortcut on desktop...")
    print(f"Source: {source_file}")

    try:
        copied_file = create_shortcut(source_file)
        print(f"✓ File copied: {copied_file}")
        print()
        print("You can now:")
        print("  - Double-click ProFiles.pyw on your desktop to launch")
        print("  - Move the file to any location - it will work from there")
        print("  - The file uses its own directory as CWD")
    except Exception as e:
        print(f"✗ Failed to create shortcut: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
