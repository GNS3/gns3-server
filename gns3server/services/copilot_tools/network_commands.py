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
Network Command Execution Tools

Provides tools for executing display and configuration commands on network devices
using Nornir and Netmiko.
"""

import json
import re
from typing import Any, Optional, List
from langchain_core.callbacks import CallbackManagerForToolRun
from netmiko.exceptions import ReadTimeout
from nornir import InitNornir
from nornir.core.task import Task, Result
from nornir_netmiko.tasks import netmiko_multiline

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class ReadDeviceInfoTool(GNS3ToolBase):
    """
    A tool to execute display (show) commands on multiple network devices.

    **Input:**
    A JSON object containing project_id and device configurations.

    Example input:
        {
            "project_id": "uuid-of-project",
            "device_configs": [
                {
                    "device_name": "R1",
                    "commands": ["show version", "show ip interface brief"]
                },
                {
                    "device_name": "R2",
                    "commands": ["show version", "show ip route"]
                }
            ]
        }

    **Output:**
    A list of dictionaries containing device names and command outputs.

    **IMPORTANT:** This tool is strictly for read-only operations.
    Only use 'show' or display commands. Do NOT use for configuration commands.
    """

    name: str = "read_device_info"
    description: str = """
    Executes display (show) commands on network devices to read device information.
    Input is a JSON object with project_id and device_configs array.
    Example input: {"project_id": "uuid", "device_configs": [{"device_name": "R1", "commands": ["show version"]}]}
    Returns device information outputs.
    **IMPORTANT: This is a READ-ONLY tool for show/display commands. NOT for configuration.**
    """

    def _get_device_console_info(self, project, device_names: List[str]) -> dict:
        """
        Get console connection information for devices.

        :param project: GNS3 project
        :param device_names: List of device names
        :return: Dictionary mapping device names to console info
        :raises: ValueError if no devices can be connected due to missing platform
        """
        hosts_data = {}
        skipped_devices = []

        for node in project.nodes.values():
            if node.name in device_names:
                # Get console information
                if node.console_type == "telnet":
                    # Get platform from template tags
                    platform = self._get_platform_from_node(node)
                    if not platform:
                        skipped_devices.append(node.name)
                        log.error(
                            f"No netmiko platform found for device '{node.name}' (type: {node.node_type}). "
                            f"Please add a 'netmiko:<platform>' tag to the template."
                        )
                        continue

                    hosts_data[node.name] = {
                        "hostname": "127.0.0.1",  # GNS3 console binding
                        "port": node.console,
                        "username": "",
                        "password": "",
                        "platform": platform,
                        "connection_type": "telnet",
                        "device_type": node.node_type,
                    }
                    log.info(f"Found device {node.name}: telnet port {node.console}, platform {platform}")

        # If no devices could be connected, raise error
        if not hosts_data and skipped_devices:
            raise ValueError(
                f"No netmiko platform configured for devices: {', '.join(skipped_devices)}. "
                f"Please add 'netmiko:<platform>' tag to device templates. "
                f"Example tags: ['netmiko:cisco_ios_telnet'] for Cisco devices."
            )

        return hosts_data

    def _get_platform_from_node(self, node) -> str:
        """
        Get Netmiko platform from node's template tags.

        Expected tag format: "netmiko:<platform>"
        Example: "netmiko:cisco_ios_telnet"

        :param node: GNS3 node instance
        :return: Platform string or None if not found
        """
        # First, try to get platform from template tags
        if node.template_id:
            try:
                template = self.controller.template.get_template(node.template_id)
                if template and template.get("tags"):
                    tags = template.get("tags", [])
                    for tag in tags:
                        if isinstance(tag, str) and tag.startswith("netmiko:"):
                            # Extract platform: netmiko:cisco_ios_telnet -> cisco_ios_telnet
                            platform = tag.split(":", 1)[1]
                            log.debug(f"Found netmiko platform '{platform}' from template tags for node {node.name}")
                            return platform
            except Exception as e:
                log.warning(f"Error getting template for node {node.name}: {e}")

        # Fallback: try to get platform from node type
        # This is a basic fallback for templates without netmiko tags
        platform = self._get_platform_from_node_type(node.node_type)
        if platform:
            log.debug(f"Using fallback platform '{platform}' from node_type for node {node.name}")
        return platform

    def _get_platform_from_node_type(self, node_type: str) -> str:
        """
        Fallback: Map GNS3 node type to Netmiko platform.

        This is used when template tags don't specify netmiko platform.

        Note: All GNS3 devices use telnet connections, so we use cisco_ios_telnet.

        :param node_type: GNS3 node type
        :return: Netmiko platform string, or None if not supported
        """
        platform_map = {
            "dynamips": "cisco_ios_telnet",  # Cisco routers via Dynamips
            "iou": "cisco_ios_telnet",       # Cisco IOU/IOL devices
        }
        return platform_map.get(node_type)  # Returns None if not found

    def _initialize_nornir(self, hosts_data: dict):
        """
        Initialize Nornir with device hosts data.

        :param hosts_data: Dictionary of device connection info
        :return: Nornir instance
        """
        defaults = {
            "username": "",
            "password": "",
            "platform": "term",
        }

        # Create inventory for Nornir
        inventory = {
            "hosts": {},
            "groups": {},
            "defaults": defaults,
        }

        for device_name, host_info in hosts_data.items():
            inventory["hosts"][device_name] = {
                "hostname": host_info["hostname"],
                "port": host_info["port"],
                "username": host_info.get("username", ""),
                "password": host_info.get("password", ""),
                "platform": host_info.get("platform", "term"),
                "connection_options": {
                    "netmiko": {
                        "extras": {"port": host_info["port"]},
                    }
                },
            }

        try:
            nr = InitNornir(inventory=inventory)
            log.info(f"Initialized Nornir with {len(hosts_data)} hosts")
            return nr
        except Exception as e:
            log.error(f"Failed to initialize Nornir: {e}")
            raise ValueError(f"Failed to initialize Nornir: {e}")

    def _run_commands_task(self, task: Task, commands_map: dict) -> Result:
        """
        Nornir task to execute commands on a device.

        :param task: Nornir task
        :param commands_map: Dictionary mapping device names to command lists
        :return: Nornir result
        """
        device_name = task.host.name
        commands = commands_map.get(device_name, [])

        if not commands:
            return Result(host=task.host, result="No commands to execute")

        try:
            result = task.run(
                task=netmiko_multiline,
                commands=commands,
                enable=True,
                read_timeout=60,
            )
            return Result(host=task.host, result=result.result)

        except ReadTimeout as e:
            log.error(f"ReadTimeout for device {device_name}: {e}")
            return Result(
                host=task.host,
                result=f"Command execution failed (ReadTimeout): {str(e)}",
                failed=True,
            )
        except Exception as e:
            log.error(f"Command execution failed for {device_name}: {e}")
            return Result(
                host=task.host,
                result=f"Command execution failed: {str(e)}",
                failed=True,
            )

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute display commands on multiple devices.

        :param tool_input: JSON string with project_id and device_configs
        :param run_manager: Callback manager
        :return: JSON string with command outputs
        """
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

            # Extract device names and commands
            device_names = [config["device_name"] for config in device_configs]
            commands_map = {config["device_name"]: config["commands"] for config in device_configs}

            # Get device console information
            hosts_data = self._get_device_console_info(project, device_names)

            if not hosts_data:
                return self._format_error_response(
                    f"No valid devices found. Make sure devices are started and have console ports."
                )

            # Initialize Nornir
            nr = self._initialize_nornir(hosts_data)

            # Execute commands on all devices
            results = []
            task_result = nr.run(
                task=self._run_commands_task,
                commands_map=commands_map,
            )

            # Process results
            for device_name, device_config in device_configs:
                result_item = {
                    "device_name": device_name,
                    "commands": device_config["commands"],
                    "outputs": [],
                }

                if device_name in task_result:
                    task_result_obj = task_result[device_name]
                    if task_result_obj.failed:
                        result_item["error"] = task_result_obj.result
                    else:
                        # Parse multi-command result
                        if isinstance(task_result_obj.result, str):
                            result_item["outputs"] = [task_result_obj.result]
                        elif isinstance(task_result_obj.result, list):
                            result_item["outputs"] = task_result_obj.result
                else:
                    result_item["error"] = "Device not found in results"

                results.append(result_item)

            return self._format_success_response({"results": results})

        except ValueError as e:
            log.error(f"Error in display commands tool: {e}")
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in display commands tool: {e}")
            return self._format_error_response(f"Failed to execute commands: {str(e)}")


class ApplyDeviceConfigTool(GNS3ToolBase):
    """
    A tool to apply configuration commands on multiple network devices.

    **Input:**
    A JSON object containing project_id and device configurations.

    Example input:
        {
            "project_id": "uuid-of-project",
            "device_configs": [
                {
                    "device_name": "R1",
                    "commands": [
                        "interface GigabitEthernet0/0",
                        "ip address 192.168.1.1 255.255.255.0",
                        "no shutdown"
                    ]
                }
            ]
        }

    **Output:**
    A list of dictionaries containing device names and configuration results.

    **WARNING:** This tool modifies device configuration. Use with caution.
    """

    name: str = "apply_device_config"
    description: str = """
    Applies configuration commands to network devices (MODIFIES device settings).
    Input is a JSON object with project_id and device_configs array.
    Example input: {"project_id": "uuid", "device_configs": [{"device_name": "R1", "commands": ["interface g0/0", "ip address 1.1.1.1 255.255.255.0"]}]}
    Returns configuration results.
    **WARNING: This MODIFIES device configuration. Use with caution.**
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute configuration commands on multiple devices.

        :param tool_input: JSON string with project_id and device_configs
        :param run_manager: Callback manager
        :return: JSON string with configuration results
        """
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

            # Extract device names and commands
            device_names = [config["device_name"] for config in device_configs]
            commands_map = {config["device_name"]: config["commands"] for config in device_configs}

            # Get device console information
            display_tool = ReadDeviceInfoTool(controller=self.controller)
            hosts_data = display_tool._get_device_console_info(project, device_names)

            if not hosts_data:
                return self._format_error_response(
                    f"No valid devices found. Make sure devices are started and have console ports."
                )

            # Initialize Nornir
            nr = display_tool._initialize_nornir(hosts_data)

            # Execute config commands on all devices
            results = []

            for device_config in device_configs:
                device_name = device_config["device_name"]
                commands = device_config["commands"]

                result_item = {
                    "device_name": device_name,
                    "commands": commands,
                    "outputs": [],
                }

                if device_name in nr.inventory.hosts:
                    try:
                        # Use send_config for config commands
                        task_result = nr.run(
                            task=device_configuration_task,
                            commands=commands,
                            name=device_name,
                        )

                        if device_name in task_result:
                            task_result_obj = task_result[device_name]
                            if task_result_obj.failed:
                                result_item["error"] = task_result_obj.result
                            else:
                                result_item["outputs"] = [task_result_obj.result]
                        else:
                            result_item["error"] = "Execution failed"

                    except Exception as e:
                        result_item["error"] = str(e)
                else:
                    result_item["error"] = "Device not found in inventory"

                results.append(result_item)

            return self._format_success_response({"results": results})

        except ValueError as e:
            log.error(f"Error in config commands tool: {e}")
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in config commands tool: {e}")
            return self._format_error_response(f"Failed to execute config commands: {str(e)}")


def device_configuration_task(task: Task, commands: list) -> Result:
    """
    Nornir task to send configuration commands to a device.

    :param task: Nornir task
    :param commands: List of configuration commands
    :return: Nornir result
    """
    from netmiko import ConfigEnableNetmiko

    try:
        # Use send_config to send config commands
        result_obj = task.run(
            task=ConfigEnableNetmiko,
            config_commands=commands,
            read_timeout=60,
        )
        return Result(host=task.host, result=result_obj.result)

    except Exception as e:
        log.error(f"Configuration failed for {task.host.name}: {e}")
        return Result(
            host=task.host,
            result=f"Configuration failed: {str(e)}",
            failed=True,
        )
