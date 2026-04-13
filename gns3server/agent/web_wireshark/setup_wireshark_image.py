#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 YueGuobin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Setup Web Wireshark Docker image.

This script pulls or builds the gns3/web-wireshark Docker image.
Run with: pip install gns3server[wireshark] && gns3-wireshark-setup
"""

import os
import sys
import shutil
import subprocess
import argparse


DOCKER_IMAGE = "gns3/web-wireshark:latest"
DOCKERFILE_NAME = "Dockerfile"


def find_dockerfile():
    """Find the Dockerfile.

    The Dockerfile is expected to be in the 'docker' subdirectory
    relative to this script's location.
    """

    # This script is in: gns3server/agent/web_wireshark/setup_wireshark_image.py
    # The Dockerfile is in: gns3server/agent/web_wireshark/docker/Dockerfile
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dockerfile_path = os.path.join(script_dir, "docker", DOCKERFILE_NAME)

    if os.path.exists(dockerfile_path):
        return dockerfile_path

    return None


def check_docker():
    """Check if Docker is available."""

    if not shutil.which("docker"):
        print("Error: docker command not found", file=sys.stderr)
        print("Please install Docker first: https://docs.docker.com/get-docker/", file=sys.stderr)
        return False

    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("Error: Docker daemon is not running", file=sys.stderr)
            print("Please start Docker and try again", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Error: Cannot connect to Docker: {e}", file=sys.stderr)
        return False

    return True


def image_exists():
    """Check if the Docker image already exists."""

    try:
        result = subprocess.run(
            ["docker", "image", "inspect", DOCKER_IMAGE],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def pull_image():
    """Pull the Docker image from registry."""

    print(f"Pulling Docker image: {DOCKER_IMAGE}")
    print("-" * 60)

    result = subprocess.run(
        ["docker", "pull", DOCKER_IMAGE],
        pass_fds=(1, 2)  # Pass stdout and stderr to inherit
    )

    return result.returncode == 0


def build_image(dockerfile_path):
    """Build the Docker image locally."""

    dockerfile_dir = os.path.dirname(dockerfile_path)
    print(f"Building Docker image: {DOCKER_IMAGE}")
    print(f"Using Dockerfile: {dockerfile_path}")
    print("-" * 60)

    result = subprocess.run(
        ["docker", "build", "-t", DOCKER_IMAGE, "-f", dockerfile_path, "."],
        cwd=dockerfile_dir,
        pass_fds=(1, 2)
    )

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Setup Web Wireshark Docker image for GNS3"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if image exists"
    )
    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Only build locally, skip pull"
    )
    parser.add_argument(
        "--pull-only",
        action="store_true",
        help="Only pull from registry, skip build"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  GNS3 Web Wireshark Image Setup")
    print("=" * 60)
    print()

    # Check Docker
    if not check_docker():
        sys.exit(1)

    # Check if image already exists
    if image_exists() and not args.force:
        print(f"Image {DOCKER_IMAGE} already exists.")
        response = input("Do you want to rebuild it? [y/N]: ").strip().lower()
        if response != 'y':
            print("Setup cancelled.")
            sys.exit(0)
        print()

    # Try strategies in order
    success = False

    if not args.build_only:
        # Strategy 1: Pull from registry
        print("[Strategy 1/2] Attempting to pull image from Docker Hub...")
        print()
        if pull_image():
            success = True
            print()
            print(f"Successfully pulled {DOCKER_IMAGE}")
        else:
            print()
            print("Pull failed, trying local build...")

    if not success and not args.pull_only:
        # Strategy 2: Build locally
        print()
        print("[Strategy 2/2] Attempting local build...")
        print()

        dockerfile_path = find_dockerfile()
        if not dockerfile_path:
            print("Error: Cannot find Dockerfile", file=sys.stderr)
            print("Please ensure the GNS3 server package is correctly installed.", file=sys.stderr)
            sys.exit(1)

        if build_image(dockerfile_path):
            success = True
            print()
            print(f"Successfully built {DOCKER_IMAGE}")
        else:
            print()
            print("Build failed.")

    if success:
        print()
        print("=" * 60)
        print("  Setup completed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("  Setup failed!")
        print("=" * 60)
        print()
        print("Please check the errors above and try again.")
        print("You can also manually run:")
        print(f"  docker pull {DOCKER_IMAGE}")
        print(f"  docker build -t {DOCKER_IMAGE} -f <dockerfile_path> .")
        sys.exit(1)


if __name__ == "__main__":
    main()
