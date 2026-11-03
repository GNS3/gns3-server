#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: YueGuobin
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

The actual execution lives in the shared runners under
``gns3_copilot/gns3_client/`` (plain classes, no LangChain): the MCP handlers
below and the copilot (through the MCP tool bridge) call the same code.

Prerequisites:
  - Device must be started (use node_start / node_start_all)
  - Device must have a 'device_type:<type>' tag set in GNS3
    (right-click → Configure → Tags → add 'device_type:cisco_ios_telnet')
  - Device must have a console port assigned
"""

from typing import Any

from gns3server.agent.gns3_copilot.gns3_client.device_config_commands import DeviceConfigCommandRunner
from gns3server.agent.gns3_copilot.gns3_client.device_show_commands import DeviceShowCommandRunner
from gns3server.agent.gns3_copilot.gns3_client.vpcs_commands import VpcsCommandRunner


def device_config_send_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Send configuration commands to network devices via console."""
    return DeviceConfigCommandRunner().run(params, gns3_ctx)


def device_show_run_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Run read-only diagnostic (show) commands on network devices."""
    return DeviceShowCommandRunner().run(params, gns3_ctx)


def vpcs_config_set_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Configure VPCS devices (set IP, gateway, etc.)."""
    return VpcsCommandRunner().run(params, gns3_ctx)
