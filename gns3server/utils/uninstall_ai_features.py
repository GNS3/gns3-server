#!/usr/bin/env python3
"""
Uninstall AI Features dependencies (AI Copilot + MCP).

Usage:
    gns3server-uninstall-ai-features
    gns3server-uninstall-ai-features -y
"""

import os
import sys
import subprocess
import argparse


def _find_base_dir():
    """Find the project root directory."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_requirements(filename):
    """Read packages from a requirements file."""
    base_dir = _find_base_dir()
    filepath = os.path.join(base_dir, filename)
    packages = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            package = line.split(">=")[0].split("==")[0].split("~=")[0]
            packages.append(package)
    return packages


def get_ai_packages():
    """Read packages from all AI features requirements files."""
    packages = []
    packages.extend(_read_requirements("ai-requirements.txt"))
    packages.extend(_read_requirements("mcp-requirements.txt"))
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for pkg in packages:
        if pkg not in seen:
            seen.add(pkg)
            unique.append(pkg)
    return unique


def uninstall(packages, yes=False):
    """Uninstall packages."""
    if not packages:
        print("No packages found to uninstall.")
        return

    print(f"Found {len(packages)} AI Features dependencies:")
    for pkg in packages:
        print(f"  - {pkg}")
    print()

    if not yes:
        response = input("Do you want to uninstall these packages? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled.")
            return

    print("Uninstalling...")
    for package in packages:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", package],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"  Removed: {package}")
            else:
                print(f"  Failed to remove {package} (may not be installed)")
        except Exception as e:
            print(f"  Error removing {package}: {e}")

    print("\nAI Features dependencies have been uninstalled.")
    print("You can reinstall them with: pip install gns3-server[ai-features]")


def main():
    parser = argparse.ArgumentParser(
        description="Uninstall AI Features dependencies (AI Copilot + MCP)"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Automatically confirm uninstallation"
    )
    args = parser.parse_args()

    packages = get_ai_packages()
    uninstall(packages, yes=args.yes)


if __name__ == "__main__":
    main()
