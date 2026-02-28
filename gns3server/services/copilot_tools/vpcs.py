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
import logging
import re
import threading
from time import sleep
from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from telnetlib3 import Telnet

from .base import GNS3ToolBase

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
            "Starting connection for device '%s' with %s commands",
            device_name, len(commands)
        )

        # Check if device has port information
        if device_name not in device_ports:
            log.warning(
                "Device '%s' not found in topology or missing console port",
                device_name
            )
            results_list[index] = {
                "device_name": device_name,
                "status": "error",
                "output": "Device '%s' not found in topology or missing console port" % device_name,
                "commands": commands,
            }
            return

        port = device_ports[device_name]["port"]
        host = device_ports[device_name]["host"]

        log.info("Connecting to device '%s' at %s:%s", device_name, host, port)

        tn = Telnet()
        try:
            tn.open(host=host, port=port, timeout=30)
            log.info("Successfully connected to device '%s' at %s:%s", device_name, host, port)

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
            log.info("Connection initialized for device '%s'", device_name)

            # Execute all commands and merge output
            combined_output = ""
            for i, command in enumerate(commands):
                log.info(
                    "Executing command %s/%s on device '%s': %s",
                    i+1, len(commands), device_name, command
                )
                tn.write(command.encode(encoding="ascii") + b"\n")
                sleep(5)  # Wait for command execution
                tn.expect([rb"PC\d+>"])
                output = tn.read_very_eager().decode("utf-8", errors="ignore")
                combined_output += output
                log.debug(
                    "Command '%s' executed on device '%s', output length: %s",
                    command, device_name, len(output)
                )

            # Add result to list
            results_list[index] = {
                "device_name": device_name,
                "status": "success",
                "output": combined_output,
                "commands": commands,
            }
            log.info(
                "Successfully executed all %s commands on device '%s'",
                len(commands), device_name
            )

        except Exception as e:
            log.error(
                "Error executing commands on device '%s': %s", device_name, e, exc_info=True
            )
            results_list[index] = {
                "device_name": device_name,
                "status": "error",
                "output": str(e),
                "commands": commands,
            }
        finally:
            tn.close()
            log.debug("Connection closed for device '%s'", device_name)

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
                log.info("Found VPCS device %s: telnet port %s", node.name, node.console)

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
            log.debug("project_id '%s' is valid UUID format", project_id)
        else:
            log.warning("project_id '%s' is not a valid UUID format", project_id)
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
                log.error("Invalid JSON string received as tool input: %s", e)
                return ([{"error": "Invalid JSON input: %s" % e}], "")
        else:
            parsed_input = tool_input
            log.info("Using tool input directly as type: %s", type(parsed_input).__name__)

        # Validate input is a dictionary
        if not isinstance(parsed_input, dict):
            error_msg = (
                "Tool input must be a JSON object containing 'project_id' and 'device_configs', "
                "but got %s" % type(parsed_input).__name__
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
            error_msg = "Invalid project_id format: %s. Expected UUID format." % project_id
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
            error_msg = "'device_configs' must be a list, but got %s" % type(device_configs).__name__
            log.error(error_msg)
            return ([{"error": error_msg}], "")

        # Handle empty list
        if not device_configs:
            log.warning("Device configs list is empty.")
            return [], ""

        # Validate each item in device_configs
        for i, item in enumerate(device_configs):
            if not isinstance(item, dict):
                error_msg = "Item at index %s must be a dictionary, got %s" % (i, type(item).__name__)
                log.error(error_msg)
                return ([{"error": error_msg}], "")

            # Validate required fields in each device config
            if "device_name" not in item:
                error_msg = "Item at index %s missing required field 'device_name'" % i
                log.error(error_msg)
                return ([{"error": error_msg}], "")

            if "commands" not in item:
                error_msg = "Item at index %s missing required field 'commands'" % i
                log.error(error_msg)
                return ([{"error": error_msg}], "")

            if not isinstance(item["commands"], list):
                error_msg = (
                    "'commands' in item at index %s must be a list, "
                    "but got %s" % (i, type(item['commands']).__name__)
                )
                log.error(error_msg)
                return ([{"error": error_msg}], "")

        log.info(
            "Input validated successfully. project_id=%s, device_configs_count=%s",
            project_id, len(device_configs)
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
        log.info("VPCS commands tool called with input: %s...", tool_input[:200])

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
            log.debug("Extracted device names: %s", list(device_names))

            # Get device console information
            log.debug("Retrieving device port mapping for project_id=%s", project_id)
            device_ports = self._get_vpcs_console_info(project, list(device_names))
            log.info(
                "Retrieved port mappings for %s devices: %s",
                len(device_ports), list(device_ports.keys())
            )

            # Initialize results list (pre-allocate space for concurrent writes)
            results = [{} for _ in range(len(device_configs))]
            threads = []

            # Create thread for each command group
            log.info("Starting parallel execution for %s devices", len(device_configs))
            for i, cmd_group in enumerate(device_configs):
                device_name = cmd_group["device_name"]
                log.debug(
                    "Creating thread for device '%s' (index %s) with %s commands",
                    device_name, i, len(cmd_group['commands'])
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
                log.debug("Thread started for device '%s'", device_name)

            # Wait for all threads to complete
            log.debug("Waiting for all threads to complete...")
            for thread in threads:
                thread.join()

            # Count successful and failed executions
            success_count = sum(1 for r in results if r.get("status") == "success")
            error_count = sum(1 for r in results if r.get("status") == "error")

            log.info(
                "Multi-device command execution completed. Total: %s, Success: %s, Error: %s",
                len(results), success_count, error_count
            )

            return self._format_success_response({"results": results})

        except ValueError as e:
            log.error("Error in VPCS commands tool: %s", e, exc_info=True)
            return self._format_error_response(str(e))
        except Exception as e:
            log.error("Unexpected error in VPCS commands tool: %s", e, exc_info=True)
            return self._format_error_response("Failed to execute VPCS commands: %s" % str(e))
