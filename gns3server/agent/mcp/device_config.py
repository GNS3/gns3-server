#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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
MCP tool handlers for device configuration via Nornir + Netmiko.

These tools connect to network device consoles via telnet/SSH and execute
configuration or diagnostic commands. Device connection info is automatically
discovered from the project topology using the device's tags for device_type.

Prerequisites:
  - Device must be started (use node_start / node_start_all)
  - Device must have a 'device_type:<type>' tag set in GNS3
    (right-click → Configure → Tags → add 'device_type:cisco_ios_telnet')
  - Device must have a console port assigned
"""

import json
import logging
from typing import Any

from jinja2 import Template as JinjaTemplate, TemplateError as JinjaError

log = logging.getLogger(__name__)


def _render_template(template: str, device_configs: list[dict], commands_field: str = "config_commands") -> list[dict]:
    """Render a Jinja2 template for each device's vars into the specified commands field.

    Entries with the same device_name are merged into a single entry
    so they share one Nornir session and avoid output fragmentation.

    Each device in device_configs can have:
      - "vars": dict of template variables (rendered into commands_field)
      - commands_field: existing commands merged after rendering if present

    Args:
        commands_field: field name for the rendered commands, e.g. "config_commands", "commands"
    """
    try:
        jinja = JinjaTemplate(template)
    except JinjaError as e:
        # a syntactically invalid template must not escape as a raw exception
        error_msg = f"Template rendering failed: {e}"
        log.error(error_msg)
        return [{"status": "failed", "error": error_msg}]
    merged: dict[str, dict] = {}
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
                lines = [l for l in output.splitlines() if l.strip()]
                entry[commands_field].extend(lines)
            except JinjaError as e:
                error_msg = f"Template rendering failed for '{name}': {e}"
                log.error(error_msg)
                return [{"status": "failed", "error": error_msg}]
    return list(merged.values())


# ── Tool handlers ──────────────────────────────────────────────────────────

def device_config_send_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Send configuration commands to network devices via console."""
    project_id = params.get("project_id")
    device_configs = params.get("device_configs")
    template = params.get("template")
    if not project_id or not device_configs:
        return [{"status": "failed", "error": "project_id and device_configs are required"}]

    if template:
        device_configs = _render_template(template, device_configs, commands_field="config_commands")
        if len(device_configs) == 1 and "error" in device_configs[0]:
            return device_configs

    from gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir import ExecuteMultipleDeviceConfigCommands

    tool = ExecuteMultipleDeviceConfigCommands()
    input_data = json.dumps({
        "project_id": project_id,
        "device_configs": device_configs,
    })
    return tool._run(
        input_data,
        jwt_token=gns3_ctx["jwt_token"],
        url=gns3_ctx["server_url"],
    )


def device_show_run_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Run read-only diagnostic (show) commands on network devices."""
    project_id = params.get("project_id")
    device_configs = params.get("device_configs")
    template = params.get("template")
    if not project_id or not device_configs:
        return [{"status": "failed", "error": "project_id and device_configs (list of {device_name, commands}) are required"}]

    if template:
        device_configs = _render_template(template, device_configs, commands_field="commands")
        if len(device_configs) == 1 and "error" in device_configs[0]:
            return device_configs

    from gns3server.agent.gns3_copilot.tools_v2.display_tools_nornir import ExecuteMultipleDeviceCommands

    tool = ExecuteMultipleDeviceCommands()
    input_data = json.dumps({
        "project_id": project_id,
        "device_configs": device_configs,
    })
    return tool._run(
        input_data,
        jwt_token=gns3_ctx["jwt_token"],
        url=gns3_ctx["server_url"],
    )


def vpcs_config_set_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Configure VPCS devices (set IP, gateway, etc.)."""
    project_id = params.get("project_id")
    device_configs = params.get("device_configs")
    if not project_id or not device_configs:
        return [{"status": "failed", "error": "project_id and device_configs are required"}]

    from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

    tool = VPCSCommands()
    input_data = json.dumps({
        "project_id": project_id,
        "device_configs": device_configs,
    })
    return tool._run(
        input_data,
        jwt_token=gns3_ctx["jwt_token"],
        url=gns3_ctx["server_url"],
    )
