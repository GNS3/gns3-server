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
using Telnet with threading for concurrent execution.
"""

import json
import re
import threading
from time import sleep
from typing import Any, Optional, List
from langchain_core.callbacks import CallbackManagerForToolRun
from telnetlib3 import Telnet

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class VPCSTerminalTool(GNS3ToolBase):
    """
    A tool to execute multiple command groups across multiple VPCS devices concurrently.
    Supports parallel execution with threading for improved performance.

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
    A list of results, one for each command group.
    """

    name: str = "vpcs_terminal"
    description: str = """
    Executes commands on VPCS (Virtual PC Simulator) devices via telnet.
    Supports concurrent execution on multiple VPCS devices using threading.
    Input is a JSON object with project_id and device_configs array.
    Example input: {"project_id": "uuid", "device_configs": [{"device_name": "PC1", "commands": ["ip 1.1.1.1/24 1.1.1.254"]}]}
    Supports VPCS commands: ip, ping, traceroute, arp, save, etc.
    Returns command outputs for each VPCS device.
    """

    def _connect_and_execute_commands(
        self,
        device_name: str,
        commands: List[str],
        results_list: List[Any],
        index: int,
        device_ports: dict,
    ) -> None:
        """
        Internal method to connect to device and execute multiple commands.

        :param device_name: Name of the VPCS device
        :param commands: List of commands to execute
        :param results_list: Pre-allocated list for thread-safe results
        :param index: Index in results list
        :param device_ports: Dictionary mapping device names to port info
        """
        log.info(
            f"Starting connection for device '{device_name}' with {len(commands)} commands"
        )

        # Check if device has port information
        if device_name not in device_ports:
            log.warning(
                f"Device '{device_name}' not found in topology or missing console port"
            )
            results_list[index] = {
                "device_name": device_name,
                "status": "error",
                "output": f"Device '{device_name}' not found in topology or missing console port",
                "commands": commands,
            }
            return

        port = device_ports[device_name]["port"]
        host = device_ports[device_name]["host"]

        log.info(f"Connecting to device '{device_name}' at {host}:{port}")

        tn = Telnet()
        try:
            tn.open(host=host, port=port, timeout=30)
            log.info(f"Successfully connected to device '{device_name}' at {host}:{port}")

            # Initialize connection - send newlines and wait for prompt
            tn.write(b"\n")
            sleep(0.5)
            tn.write(b"\n")
            sleep(0.5)
            tn.write(b"\n")
            sleep(0.5)
            tn.write(b"\n")
            sleep(0.5)
            tn.expect([rb"PC\d+>"])
            log.info(f"Connection initialized for device '{device_name}'")

            # Execute all commands and merge output
            combined_output = ""
            for i, command in enumerate(commands):
                log.info(
                    f"Executing command {i+1}/{len(commands)} on device '{device_name}': {command}"
                )
                tn.write(command.encode(encoding="ascii") + b"\n")
                sleep(5)  # Wait for command execution
                tn.expect([rb"PC\d+>"])
                output = tn.read_very_eager().decode("utf-8", errors="ignore")
                combined_output += output
                log.debug(
                    f"Command '{command}' executed on device '{device_name}', output length: {len(output)}"
                )

            # Add result to list
            results_list[index] = {
                "device_name": device_name,
                "status": "success",
                "output": combined_output,
                "commands": commands,
            }
            log.info(
                f"Successfully executed all {len(commands)} commands on device '{device_name}'"
            )

        except Exception as e:
            log.error(
                f"Error executing commands on device '{device_name}': {e}", exc_info=True
            )
            results_list[index] = {
                "device_name": device_name,
                "status": "error",
                "output": str(e),
                "commands": commands,
            }
        finally:
            tn.close()
            log.debug(f"Connection closed for device '{device_name}'")

    def _get_vpcs_console_info(self, project, device_names: List[str]) -> dict:
        """
        Get console connection information for VPCS devices.

        :param project: GNS3 project
        :param device_names: List of VPCS device names
        :return: Dictionary mapping device names to console info
        """
        hosts_data = {}

        for node in project.nodes.values():
            if node.name in device_names and node.node_type == "vpcs":
                hosts_data[node.name] = {
                    "host": "127.0.0.1",  # GNS3 console binding
                    "port": node.console,
                }
                log.info(f"Found VPCS device {node.name}: telnet port {node.console}")

        return hosts_data

    def _validate_project_id(self, project_id: str) -> bool:
        """
        Validate project_id format (UUID).

        :param project_id: The project ID to validate
        :return: True if valid UUID format, False otherwise
        """
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        is_valid = bool(re.match(uuid_pattern, project_id, re.IGNORECASE))
        if is_valid:
            log.debug(f"project_id '{project_id}' is valid UUID format")
        else:
            log.warning(f"project_id '{project_id}' is not a valid UUID format")
        return is_valid

    def _validate_tool_input(self, tool_input: str) -> tuple:
        """
        Validate device command input and extract project_id and device_configs.

        :param tool_input: The input received from the tool call
        :return: Tuple containing (device_configs_list, project_id) or (error_list, "")
        """
        parsed_input = None

        # Parse JSON input
        if isinstance(tool_input, (str, bytes, bytearray)):
            try:
                parsed_input = json.loads(tool_input)
                log.info("Successfully parsed tool input from JSON string.")
            except json.JSONDecodeError as e:
                log.error(f"Invalid JSON string received as tool input: {e}")
                return ([{"error": f"Invalid JSON input: {e}"}], "")
        else:
            parsed_input = tool_input
            log.info(f"Using tool input directly as type: {type(parsed_input).__name__}")

        # Validate input is a dictionary
        if not isinstance(parsed_input, dict):
            error_msg = (
                "Tool input must be a JSON object containing 'project_id' and 'device_configs', "
                f"but got {type(parsed_input).__name__}"
            )
            log.error(error_msg)
            return ([{"error": error_msg}], "")

        # Extract and validate project_id
        project_id = parsed_input.get("project_id")
        if not project_id:
            error_msg = "Missing required field 'project_id' in input"
            log.error(error_msg)
            return ([{"error": error_msg}], "")

        # Validate project_id format
        if not self._validate_project_id(project_id):
            error_msg = f"Invalid project_id format: {project_id}. Expected UUID format."
            log.error(error_msg)
            return ([{"error": error_msg}], "")

        # Extract and validate device_configs
        device_configs = parsed_input.get("device_configs")
        if device_configs is None:
            error_msg = "Missing required field 'device_configs' in input"
            log.error(error_msg)
            return ([{"error": error_msg}], "")

        # Validate device_configs is a list
        if not isinstance(device_configs, list):
            error_msg = f"'device_configs' must be a list, but got {type(device_configs).__name__}"
            log.error(error_msg)
            return ([{"error": error_msg}], "")

        # Handle empty list
        if not device_configs:
            log.warning("Device configs list is empty.")
            return [], ""

        # Validate each item in device_configs
        for i, item in enumerate(device_configs):
            if not isinstance(item, dict):
                error_msg = f"Item at index {i} must be a dictionary, got {type(item).__name__}"
                log.error(error_msg)
                return ([{"error": error_msg}], "")

            # Validate required fields in each device config
            if "device_name" not in item:
                error_msg = f"Item at index {i} missing required field 'device_name'"
                log.error(error_msg)
                return ([{"error": error_msg}], "")

            if "commands" not in item:
                error_msg = f"Item at index {i} missing required field 'commands'"
                log.error(error_msg)
                return ([{"error": error_msg}], "")

            if not isinstance(item["commands"], list):
                error_msg = (
                    f"'commands' in item at index {i} must be a list, "
                    f"but got {type(item['commands']).__name__}"
                )
                log.error(error_msg)
                return ([{"error": error_msg}], "")

        log.info(
            f"Input validated successfully. project_id={project_id}, device_configs_count={len(device_configs)}"
        )
        return device_configs, project_id

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute commands on multiple VPCS devices concurrently.

        :param tool_input: JSON string with project_id and device_configs
        :param run_manager: Callback manager
        :return: JSON string with command outputs
        """
        log.info(f"VPCS commands tool called with input: {tool_input[:200]}...")

        # Validate tool input and extract project_id and device_configs
        device_configs, project_id = self._validate_tool_input(tool_input)

        # Check if validation returned an error
        if (
            isinstance(device_configs, list)
            and len(device_configs) > 0
            and "error" in device_configs[0]
        ):
            return self._format_error_response(device_configs[0]["error"])

        # Empty device configs
        if not device_configs:
            return self._format_success_response({"results": []})

        try:
            # Get project
            project = self._get_project(project_id)

            # Extract all device names from input
            device_names = {config["device_name"] for config in device_configs}
            log.debug(f"Extracted device names: {list(device_names)}")

            # Get device console information
            log.debug(f"Retrieving device port mapping for project_id={project_id}")
            device_ports = self._get_vpcs_console_info(project, list(device_names))
            log.info(
                f"Retrieved port mappings for {len(device_ports)} devices: {list(device_ports.keys())}"
            )

            # Initialize results list (pre-allocate space for concurrent writes)
            results = [{} for _ in range(len(device_configs))]
            threads = []

            # Create thread for each command group
            log.info(f"Starting parallel execution for {len(device_configs)} devices")
            for i, cmd_group in enumerate(device_configs):
                device_name = cmd_group["device_name"]
                log.debug(
                    f"Creating thread for device '{device_name}' (index {i}) with {len(cmd_group['commands'])} commands"
                )
                thread = threading.Thread(
                    target=self._connect_and_execute_commands,
                    args=(
                        cmd_group["device_name"],
                        cmd_group["commands"],
                        results,
                        i,
                        device_ports,
                    ),
                )
                threads.append(thread)
                thread.start()
                log.debug(f"Thread started for device '{device_name}'")

            # Wait for all threads to complete
            log.debug("Waiting for all threads to complete...")
            for thread in threads:
                thread.join()

            # Count successful and failed executions
            success_count = sum(1 for r in results if r.get("status") == "success")
            error_count = sum(1 for r in results if r.get("status") == "error")

            log.info(
                f"Multi-device command execution completed. Total: {len(results)}, Success: {success_count}, Error: {error_count}"
            )

            return self._format_success_response({"results": results})

        except ValueError as e:
            log.error(f"Error in VPCS commands tool: {e}", exc_info=True)
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in VPCS commands tool: {e}", exc_info=True)
            return self._format_error_response(f"Failed to execute VPCS commands: {str(e)}")
