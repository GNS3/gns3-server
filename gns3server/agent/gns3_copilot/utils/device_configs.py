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
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
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
Device config entry normalization shared by the tools_v2 executors.

Callers (LLM agents via MCP, or gns3-copilot directly) may send the same
device several times in one batch. Every downstream stage keys by
device_name, so duplicates must merge before execution, not after.
"""

from typing import Any


def merge_duplicate_device_configs(
    device_configs: list[dict[str, Any]],
    commands_field: str,
) -> list[dict[str, Any]]:
    """
    Merge entries that share a device_name, concatenating their command lists.

    Without this merge the per-device command map keeps only the last
    entry's commands while result processing iterates every original entry —
    duplicate devices would silently drop all but the last command batch and
    every row would report that same output.

    Args:
        device_configs: Device config entries; each holds device_name and a
            command list under commands_field.
        commands_field: Field carrying the commands ("commands" or
            "config_commands" depending on the tool).

    Returns:
        One entry per device_name, in first-appearance order. The first
        entry's extra fields are preserved; later duplicates only contribute
        their commands.
    """
    merged: dict[str, dict[str, Any]] = {}
    for config in device_configs:
        name = config.get("device_name")
        if not name:
            continue
        commands = list(config.get(commands_field, []))
        if name in merged:
            merged[name][commands_field].extend(commands)
        else:
            entry = dict(config)
            entry[commands_field] = commands
            merged[name] = entry
    return list(merged.values())
