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
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Command filter module for GNS3-Copilot.

This module provides functionality to filter out dangerous or long-running
commands that may cause issues with tool execution timeouts or device console
availability.

Forbidden commands are loaded from the external GNS3-Skills repository
(config/forbidden_commands.txt) via SkillsManager.
"""

import logging

from gns3server.agent.gns3_copilot.skills.registry import get_skills_manager

logger = logging.getLogger(__name__)

# Default forbidden commands (fallback if skills repository is not available)
DEFAULT_FORBIDDEN_COMMANDS = [
    "traceroute",
    "tracepath",
    "tracert",
    "ping -f",
    "debug",
    "test",
]

# Cache for forbidden commands
_forbidden_commands_cache: list[str] | None = None


def _load_forbidden_commands() -> list[str]:
    """
    Load forbidden commands, preferring the skills repository.

    Tries to load from the external GNS3-Skills repository first.
    Falls back to hardcoded defaults if the repo is unavailable.

    Returns:
        List of forbidden command patterns.
    """
    global _forbidden_commands_cache

    # Return cached value if available
    if _forbidden_commands_cache is not None:
        return _forbidden_commands_cache

    # Try to load from skills repository
    manager = get_skills_manager()
    if manager is not None:
            commands = manager.load_forbidden_commands()
            if commands:
                logger.info(
                    "Loaded %d forbidden command patterns from skills repository",
                    len(commands),
                )
                _forbidden_commands_cache = commands
                return _forbidden_commands_cache

    # Fallback to defaults
    logger.warning("Using default forbidden commands list")
    _forbidden_commands_cache = DEFAULT_FORBIDDEN_COMMANDS.copy()
    return _forbidden_commands_cache


def reload_forbidden_commands() -> None:
    """
    Reload the forbidden commands list from the skills repository.

    Directly loads and caches the commands from the repository.
    Falls back to defaults if the repository is unavailable.
    """
    global _forbidden_commands_cache

    from gns3server.agent.gns3_copilot.skills.registry import get_skills_manager

    manager = get_skills_manager()
    if manager is not None:
        commands = manager.load_forbidden_commands()
        if commands:
            logger.info(
                "Loaded %d forbidden command patterns from skills repository",
                len(commands),
            )
            _forbidden_commands_cache = commands
            return

    logger.warning("Using default forbidden commands list")
    _forbidden_commands_cache = DEFAULT_FORBIDDEN_COMMANDS.copy()


def get_forbidden_commands() -> list[str]:
    """
    Get the current list of forbidden command patterns.

    Returns:
        List of forbidden command patterns (lowercase).
    """
    return _load_forbidden_commands()


def is_command_forbidden(command: str) -> bool:
    """
    Check if a single command is forbidden.

    Args:
        command: The command string to check.

    Returns:
        True if the command matches a forbidden pattern, False otherwise.
    """
    forbidden_commands = _load_forbidden_commands()
    command_lower = command.strip().lower()

    for forbidden_pattern in forbidden_commands:
        if command_lower.startswith(forbidden_pattern):
            return True

    return False


def filter_forbidden_commands(
    commands: list[str],
) -> tuple[list[str], dict[str, str]]:
    """
    Filter out forbidden commands from a list of commands.

    Args:
        commands: List of command strings to filter.

    Returns:
        A tuple of (allowed_commands, blocked_commands_info):
        - allowed_commands: List of commands that are not forbidden.
        - blocked_commands_info: Dict mapping blocked commands to their reasons.
    """
    allowed_commands: list[str] = []
    blocked_commands_info: dict[str, str] = {}

    for command in commands:
        if is_command_forbidden(command):
            # Find which pattern matched
            forbidden_commands = _load_forbidden_commands()
            command_lower = command.strip().lower()
            matched_pattern = None

            for pattern in forbidden_commands:
                if command_lower.startswith(pattern):
                    matched_pattern = pattern
                    break

            reason = (
                f"Command '{command}' is not allowed because it matches the "
                f"forbidden pattern '{matched_pattern}'. "
                f"This command may run longer than the tool timeout or leave "
                f"the device console unavailable for subsequent commands."
            )
            blocked_commands_info[command] = reason
        else:
            allowed_commands.append(command)

    if blocked_commands_info:
        logger.info(
            "Filtered %d command(s): %s",
            len(blocked_commands_info),
            list(blocked_commands_info.keys()),
        )

    return allowed_commands, blocked_commands_info
