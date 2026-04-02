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

Public module for getting device port information from GNS3 topology
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_device_ports_from_topology(
    device_names: list[str],
    project_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Get device connection information from GNS3 topology

    Args:
        device_names: List of device names to look up
        project_id: UUID of the specific GNS3 project to retrieve topology from

    Returns:
        Dictionary mapping device names to their connection data:
        {
            "device_name": {
                "port": console_port,
                "platform": "huawei",  # Extracted from tags
                "groups": ["network_devices"],  # For inheriting shared settings
                "connection_options": {
                    "netmiko": {
                        "extras": {"device_type": "huawei_telnet"}  # Extracted from tags
                    }
                }
            }
        }
        Devices that don't exist or missing console_port will not be included
    """
    # Log received parameters
    logger.info(
        "Called with device_names=%s, project_id=%s", device_names, project_id
    )

    try:
        # Lazy import to avoid circular dependency
        from gns3server.agent.gns3_copilot.gns3_client import GNS3TopologyTool

        # Get topology information
        topo = GNS3TopologyTool()
        topology = topo._run(project_id=project_id)

        # Dynamically build hosts_data from topology
        hosts_data: dict[str, dict[str, Any]] = {}

        if not topology:
            logger.warning("Unable to get topology information")
            return hosts_data

        for device_name in device_names:
            # Check if device exists in topology
            if device_name not in topology.get("nodes", {}):
                logger.warning(
                    "Device '%s' not found in topology", device_name
                )
                continue

            node_info = topology["nodes"][device_name]
            if "console_port" not in node_info:
                logger.warning("Device '%s' missing console_port", device_name)
                continue

            # Extract device_type and platform from tags
            device_type = None
            platform = None
            tags = node_info.get("tags", [])

            for tag in tags:
                if tag.startswith("device_type:"):
                    device_type = tag.split(":", 1)[1].strip()
                elif tag.startswith("platform:"):
                    platform = tag.split(":", 1)[1].strip()

            # Return error if device_type not found in tags
            # Using a default would cause command execution errors
            if device_type is None:
                tested_device_types = (
                    "cisco_ios_telnet (Netmiko built-in), gns3_huawei_telnet_ce (custom Huawei), "
                    "gns3_ruijie_telnet (custom Ruijie)"
                )
                error_msg = (
                    f"Device '{device_name}': device_type tag not found. "
                    f"Please add 'device_type:<type>' tag to this device in GNS3. "
                    f"To configure via Web UI: right-click the device -> Configure -> Tags -> add 'device_type:<type>'. "
                    f"Tested types: {tested_device_types}. "
                    f"Current tags: {tags}"
                )
                logger.error(error_msg)
                hosts_data[device_name] = {
                    "error": error_msg
                }
                continue

            logger.debug(
                "Device '%s': extracted device_type=%s from tags",
                device_name,
                device_type,
            )

            if platform is None:
                platform = "cisco_ios"
                logger.debug(
                    "Device '%s': platform not found in tags, using default: cisco_ios",
                    device_name,
                )
            else:
                logger.debug(
                    "Device '%s': extracted platform=%s from tags",
                    device_name,
                    platform,
                )

            # Add device to hosts_data with connection_options at host level
            # This is the Nornir best practice - each host has its own
            # connection configuration (device_type), while sharing common
            # settings (hostname, timeout) via group inheritance.
            hosts_data[device_name] = {
                "port": node_info["console_port"],
                "platform": platform,
                "groups": ["network_devices"],  # For inheriting hostname, timeout, etc.
                "connection_options": {
                    "netmiko": {
                        "extras": {"device_type": device_type}
                    }
                },
            }

        logger.info("Returning %d device port mappings", len(hosts_data))

        return hosts_data

    except Exception as e:
        logger.error("Error getting device port information: %s", e)
        return {}
