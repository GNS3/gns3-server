#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
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
VPCS Command Execution Tool

Provides tool for executing commands on VPCS (Virtual PC Simulator) devices
using Telnet.
"""

import asyncio
import re
from typing import Any, Optional, List
from langchain_core.callbacks import CallbackManagerForToolRun
from telnetlib3 import Telnet

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class VPCSCommandsTool(GNS3ToolBase):
    """
    A tool to execute commands on multiple VPCS devices.

    **Input:**
    A JSON object containing project_id and device configurations.

    Example input:
        {
            "project_id": "uuid-of-project",
            "device_configs": [
                {
                    "device_name": "PC1",
                    "commands": ["ip 10.10.0.12/24 10.10.0.254", "ping 10.10.0.254"]
                },
                {
                    "device_name": "PC2",
                    "commands": ["ip 10.10.0.13/24 10.10.0.254"]
                }
            ]
        }

    **Output:**
    A list of results for each VPCS device.
    """

    name: str = "execute_vpcs_commands"
    description: str = """
    Executes commands on multiple VPCS (Virtual PC Simulator) devices.
    Input is a JSON object with project_id and device_configs array.
    Example input: {"project_id": "uuid", "device_configs": [{"device_name": "PC1", "commands": ["ip 1.1.1.1/24 1.1.1.254"]}]}
    Supports VPCS commands like: ip, ping, traceroute, arp, etc.
    Returns command outputs for each VPCS device.
    """

    def _get_vpcs_console_info(self, project, device_names: List[str]) -> dict:
        """
        Get console connection information for VPCS devices.

        :param project: GNS3 project
        :param device_names: List of VPCS device names
        :return: Dictionary mapping device names to console info
        """
        hosts_data = {}

        for node in project.nodes:
            if node.name in device_names and node.node_type == "vpcs":
                hosts_data[node.name] = {
                    "host": "127.0.0.1",  # GNS3 console binding
                    "port": node.console,
                }
                log.info(f"Found VPCS device {node.name}: telnet port {node.console}")

        return hosts_data

    async def _execute_commands_on_device(
        self, device_name: str, commands: List[str], host_info: dict
    ) -> dict:
        """
        Execute commands on a single VPCS device.

        :param device_name: Name of the VPCS device
        :param commands: List of commands to execute
        :param host_info: Dictionary with host and port
        :return: Result dictionary
        """
        host = host_info["host"]
        port = host_info["port"]

        result = {
            "device_name": device_name,
            "commands": commands,
            "output": "",
            "status": "success",
        }

        try:
            # Connect to VPCS via Telnet
            reader, writer = await Telnet(host, port).open()

            # Initialize connection
            await asyncio.sleep(0.5)
            for _ in range(4):
                writer.write(b"\n")
                await asyncio.sleep(0.5)

            # Wait for VPCS prompt
            await asyncio.sleep(1)

            # Execute commands
            outputs = []
            for command in commands:
                log.info(f"Executing on {device_name}: {command}")
                writer.write(command.encode("ascii") + b"\n")
                await asyncio.sleep(3)  # Wait for command execution

                # Read output
                try:
                    output = await asyncio.wait_for(
                        reader.read(4096), timeout=5
                    )
                    output_str = output.decode("utf-8", errors="ignore")
                    outputs.append(output_str)
                except asyncio.TimeoutError:
                    outputs.append("")

            result["output"] = "\n".join(outputs)
            writer.close()
            await writer.wait_closed()

        except Exception as e:
            log.error(f"Error executing commands on {device_name}: {e}")
            result["status"] = "error"
            result["output"] = str(e)

        return result

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute commands on multiple VPCS devices.

        :param tool_input: JSON string with project_id and device_configs
        :param run_manager: Callback manager
        :return: JSON string with command outputs
        """
        async def _async_execute():
            try:
                # Parse input
                input_data = self._parse_json_input(tool_input)
                project_id = input_data.get("project_id")
                device_configs = input_data.get("device_configs", [])

                # Validate required fields
                if not project_id:
                    return self._format_error_response("Missing project_id")

                if not device_configs:
                    return self._format_error_response("Missing device_configs")

                # Get project
                project = self._get_project(project_id)

                # Extract VPCS device names
                device_names = [config["device_name"] for config in device_configs]

                # Get VPCS console information
                hosts_data = self._get_vpcs_console_info(project, device_names)

                if not hosts_data:
                    return self._format_error_response(
                        "No VPCS devices found. Make sure devices are started and have console ports."
                    )

                # Execute commands on all devices concurrently
                results = []
                tasks = []

                for device_config in device_configs:
                    device_name = device_config["device_name"]
                    commands = device_config["commands"]

                    if device_name in hosts_data:
                        task = self._execute_commands_on_device(
                            device_name, commands, hosts_data[device_name]
                        )
                        tasks.append(task)
                    else:
                        results.append({
                            "device_name": device_name,
                            "commands": commands,
                            "status": "error",
                            "output": f"Device {device_name} not found or is not a VPCS device"
                        })

                # Wait for all tasks to complete
                if tasks:
                    task_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for task_result in task_results:
                        if isinstance(task_result, Exception):
                            results.append({
                                "device_name": "unknown",
                                "commands": [],
                                "status": "error",
                                "output": str(task_result)
                            })
                        else:
                            results.append(task_result)

                return self._format_success_response({"results": results})

            except ValueError as e:
                log.error(f"Error in VPCS commands tool: {e}")
                return self._format_error_response(str(e))
            except Exception as e:
                log.error(f"Unexpected error in VPCS commands tool: {e}")
                return self._format_error_response(f"Failed to execute VPCS commands: {str(e)}")

        # Run async function in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(_async_execute())
