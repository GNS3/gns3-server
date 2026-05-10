# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin
# Author: Yue Guobin
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Skills Configuration

This module contains configuration for the external skills repository.
"""

from gns3server.config import Config

# Default skills repository configuration
SKILLS_CONFIG = {
    # Git repository URL for skills
    "repo_url": "https://github.com/yueguobin/GNS3-Skills.git",

    # Git branch to use
    "branch": "main",

    # Automatically pull updates on reload
    "auto_update": True,

    # Enable external skills loading
    # If False, use the built-in hardcoded skills
    "enabled": True,
}


def get_skills_config() -> dict:
    """
    Get the skills configuration.

    Priority:
    1. GNS3 server config (gns3_server.conf → [Server] → skills_*)
    2. Hardcoded defaults

    Returns:
        Dictionary containing skills configuration
    """
    config = SKILLS_CONFIG.copy()
    try:
        server = Config.instance().settings.Server
        if server.skills_repo_url:
            config["repo_url"] = server.skills_repo_url
        if server.skills_repo_branch:
            config["branch"] = server.skills_repo_branch
        config["auto_update"] = server.skills_auto_update
    except Exception:
        pass
    return config


def update_skills_config(**kwargs):
    """
    Update skills configuration.

    Args:
        **kwargs: Configuration key-value pairs to update
    """
    for key, value in kwargs.items():
        if key in SKILLS_CONFIG:
            SKILLS_CONFIG[key] = value
        else:
            raise ValueError(f"Unknown configuration key: {key}")
