#!/usr/bin/env python3
"""
Uninstall AI Copilot dependencies.

Usage:
    gns3server-uninstall-ai-copilot
    gns3server-uninstall-ai-copilot -y
"""

import os
import sys
import subprocess
import argparse


def get_ai_packages():
    """Read packages from ai-requirements.txt."""
    # Find the requirements file
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle
        base_dir = os.path.dirname(sys.executable)
    else:
        # __file__ = gns3server/utils/uninstall_ai_copilot.py
        # Need to go up 2 levels to reach project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    requirements_file = os.path.join(base_dir, "ai-requirements.txt")

    packages = []
    with open(requirements_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Remove version specifiers
            package = line.split(">=")[0].split("==")[0].split("~=")[0]
            packages.append(package)
    return packages


def uninstall(packages, yes=False):
    """Uninstall packages."""
    if not packages:
        print("No packages found to uninstall.")
        return

    print(f"Found {len(packages)} AI Copilot dependencies:")
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

    print("\nAI Copilot dependencies have been uninstalled.")
    print("You can reinstall them with: pip install gns3-server[ai-copilot]")


def main():
    parser = argparse.ArgumentParser(
        description="Uninstall AI Copilot dependencies"
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
