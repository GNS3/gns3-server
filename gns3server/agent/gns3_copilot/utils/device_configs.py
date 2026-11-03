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
Device config entry normalization shared by the device command runners.

Callers (LLM agents via MCP, or the copilot through the MCP tool bridge)
may send the same device several times in one batch. Every downstream
stage keys by device_name, so duplicates must merge before execution, not
after. This module also renders the optional per-device Jinja2 template
into the commands field.
"""

import logging
from typing import Any

from jinja2 import Template as JinjaTemplate
from jinja2 import TemplateError as JinjaError

logger = logging.getLogger(__name__)


def merge_duplicate_device_configs(
    device_configs: list[Any],
    commands_field: str,
) -> list[dict[str, Any]]:
    """
    Merge entries that share a device_name, concatenating their command lists.

    Without this merge the per-device command map keeps only the last
    entry's commands while result processing iterates every original entry —
    duplicate devices would silently drop all but the last command batch and
    every row would report that same output.

    Args:
        device_configs: Device config entries (parsed tool input, validated
            here); each holds device_name and a command list under
            commands_field.
        commands_field: Field carrying the commands ("commands" or
            "config_commands" depending on the tool).

    Returns:
        One entry per device_name, in first-appearance order. The first
        entry's extra fields are preserved; later duplicates only contribute
        their commands.

    Raises:
        ValueError: An entry is not an object or has no usable device_name.
            Such an entry cannot be addressed; dropping it silently would
            let a malformed batch execute partially while every returned
            row reports success.
    """
    merged: dict[str, dict[str, Any]] = {}
    for index, config in enumerate(device_configs):
        if not isinstance(config, dict) or not config.get("device_name"):
            raise ValueError(f"device_configs[{index}] must be an object with a non-empty 'device_name' field")
        name = config["device_name"]
        commands = list(config.get(commands_field, []))
        if name in merged:
            merged[name][commands_field].extend(commands)
        else:
            entry = dict(config)
            entry[commands_field] = commands
            merged[name] = entry
    return list(merged.values())


def render_device_template(
    template: str,
    device_configs: list[dict[str, Any]],
    commands_field: str = "config_commands",
) -> list[dict[str, Any]]:
    """
    Render a Jinja2 template for each device's vars into the commands field.

    Entries with the same device_name are merged into a single entry
    so they share one Nornir session and avoid output fragmentation.

    Each device in device_configs can have:
      - "vars": dict of template variables (rendered into commands_field)
      - commands_field: existing commands merged after rendering if present

    Returns a one-entry error list on template failure so callers can pass
    it straight through to the LLM.

    Args:
        commands_field: field name for the rendered commands, e.g. "config_commands", "commands"
    """
    try:
        jinja = JinjaTemplate(template)
    except JinjaError as e:
        # a syntactically invalid template must not escape as a raw exception
        error_msg = f"Template rendering failed: {e}"
        logger.error(error_msg)
        return [{"status": "failed", "error": error_msg}]
    merged: dict[str, dict[str, Any]] = {}
    for dev in device_configs:
        name = dev.get("device_name")
        if not name:
            continue
        vars_data = dev.get("vars", {})
        if name not in merged:
            merged[name] = {"device_name": name, commands_field: list(dev.get(commands_field, []))}
        entry = merged[name]
        if vars_data:
            try:
                output = jinja.render(**vars_data)
                lines = [line for line in output.splitlines() if line.strip()]
                entry[commands_field].extend(lines)
            except JinjaError as e:
                error_msg = f"Template rendering failed for '{name}': {e}"
                logger.error(error_msg)
                return [{"status": "failed", "error": error_msg}]
    return list(merged.values())
