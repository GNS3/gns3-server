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
This module provides a tool to execute commands on VPCS devices
in a GNS3 topology using Nornir with Netmiko.
"""

import json
import logging
import re
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from netmiko.exceptions import ReadTimeout
from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.task import AggregatedResult
from nornir.core.task import Result
from nornir.core.task import Task
from nornir_netmiko.tasks import netmiko_multiline

from gns3server.agent.gns3_copilot.gns3_client import get_gns3_server_host
from gns3server.agent.gns3_copilot.utils import get_device_ports_from_topology

# Import custom Netmiko device types for GNS3 emulation
# This registers gns3_vpcs_telnet and other custom device types
# NOTE: Must be imported BEFORE any Nornir operations to ensure device types are registered
from gns3server.agent.gns3_copilot.utils import custom_netmiko  # noqa: F401

# Explicitly register VPCS device type to ensure it is available
try:
    from gns3server.agent.gns3_copilot.utils.custom_netmiko.vpcs_telnet import (
        register_custom_device_type as register_vpcs_device_type,
    )

    # Register VPCS device type
    register_vpcs_device_type()

    # CRITICAL: Update netmiko.ssh_dispatcher platforms lists
    import importlib

    sd = importlib.import_module("netmiko.ssh_dispatcher")

    # Recalculate platforms lists to include custom device types
    sd.platforms = list(sd.CLASS_MAPPER.keys())
    sd.platforms.sort()

    sd.platforms_base = list(sd.CLASS_MAPPER_BASE.keys())
    sd.platforms_base.sort()

    sd.telnet_platforms = [x for x in sd.platforms if "telnet" in x]

    # Update platform strings used in error messages
    sd.platforms_str = "\n" + "\n".join(sd.platforms_base)
    sd.telnet_platforms_str = "\n" + "\n".join(sd.telnet_platforms)
except Exception:
    # Fail silently - the import-time registration should have worked
    pass

logger = logging.getLogger(__name__)

# Suppress nornir INFO logs in console (reduce verbosity)
logging.getLogger("nornir.core").setLevel(logging.WARNING)
logging.getLogger("nornir").setLevel(logging.WARNING)


def _get_nornir_defaults() -> dict[str, Any]:
    """Get Nornir default configuration."""
    return {"data": {"location": "gns3"}}


class VPCSCommands(BaseTool):
    """
    A tool for VPCS (Virtual PC Simulator) devices.

    **VPCS-SPECIFIC TOOL** - This tool ONLY works with VPCS virtual PC devices.

    **IMPORTANT DISTINCTION:**
    Unlike network devices (routers/switches), VPCS devices are lightweight virtual PCs.
    Commands like 'ip' are basic PC IP config, NOT network device config.

    **Allowed VPCS Commands:**
    - IP configuration: ip <address>/<mask> <gateway>
    - View configuration: ip, show ip
    - Connectivity testing: ping <destination>
    - Display ARP: arp
    - Display version: version
    - Save/Load: save, load
    """

    name: str = "execute_vpcs_commands"
    description: str = """
    **VPCS VIRTUAL PC TOOL** - Configure and test Virtual PC Simulator devices.

    This tool ONLY works with VPCS devices, NOT routers/switches.

    **IMPORTANT: VPCS vs Network Devices**
    - VPCS = Lightweight virtual PCs for lab testing (NOT network infra)
    - 'ip' command on VPCS = Basic PC IP config (like 'ipconfig' on Windows)
    - NOT the same as configuring router interfaces or routing protocols

    **When to Use This Tool:**
    - Configure IP addresses on virtual PCs: ip 10.10.0.12/24 10.10.0.254
    - Test connectivity from PCs: ping 10.10.0.254
    - View PC IP configuration: ip, show ip
    - Display ARP table: arp
    - Check PC version: version

    **Input Format:**
        {
            "project_id": "<PROJECT_UUID>",
            "device_configs": [
                {
                    "device_name": "PC1",
                    "commands": ["ip", "ping 10.10.0.254"]
                },
                {
                    "device_name": "PC2",
                    "commands": ["show ip"]
                }
            ]
        }

    **Returns:** PC command outputs for IP config and connectivity testing.

    **Note:** For network devices, use execute_multiple_device_commands.
    """

    def _run(
        self,
        tool_input: str | bytes | list[Any] | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Execute commands on multiple VPCS devices in GNS3 topology.

        Args:
            tool_input: JSON string with project_id and VPCS commands.

        Returns:
            List of dicts with device names and command outputs.
        """
        # Log received input
        logger.debug("Received input: %s", tool_input)

        # Validate input
        device_configs_list, project_id = self._validate_tool_input(tool_input)
        if (
            isinstance(device_configs_list, list)
            and len(device_configs_list) > 0
            and "error" in device_configs_list[0]
        ):
            return device_configs_list

        # Create a mapping of device names to their commands
        device_configs_map = self._configs_map(device_configs_list)

        # Prepare device hosts data
        try:
            hosts_data = self._prepare_device_hosts_data(
                device_configs_list, project_id
            )
        except ValueError as e:
            logger.error("Failed to prepare device hosts data: %s", e)
            return [{"error": str(e)}]

        # Check if any devices have errors (e.g., missing device)
        error_devices = {
            name: data
            for name, data in hosts_data.items()
            if "error" in data
        }
        if error_devices:
            logger.error(
                "Devices with configuration errors: %s",
                list(error_devices.keys())
            )
            return [
                {
                    "device_name": name,
                    "status": "failed",
                    "error": data["error"]
                }
                for name, data in error_devices.items()
            ]

        # Initialize Nornir
        try:
            dynamic_nr = self._initialize_nornir(hosts_data)
        except ValueError as e:
            logger.error("Failed to initialize Nornir: %s", e)
            return [{"error": str(e)}]

        results = []

        # Execute all devices concurrently in a single run
        try:
            task_result = dynamic_nr.run(
                task=self._run_vpcs_commands,
                device_configs_map=device_configs_map,
            )

            # Process results for all devices
            results = self._process_task_results(
                device_configs_list,
                hosts_data,
                task_result,
            )

        except Exception as e:
            # Overall execution failed
            logger.error("Error executing commands on all VPCS devices: %s", e)
            return [{"error": f"Execution error: {str(e)}"}]

        logger.debug(
            "VPCS command execution completed. Results: %s",
            json.dumps(results, indent=2, ensure_ascii=False),
        )

        return results

    def _run_vpcs_commands(
        self, task: Task, device_configs_map: dict[str, list[str]]
    ) -> Result:
        """Execute VPCS commands with single retry."""
        device_name = task.host.name
        commands = device_configs_map.get(device_name, [])

        if not commands:
            return Result(
                host=task.host, result="No commands to execute"
            )

        try:
            # Use netmiko_multiline for VPCS commands
            # This works well with simple commands and ping output
            _result = task.run(
                task=netmiko_multiline,
                commands=commands,
                read_timeout=30,
            )
            return Result(host=task.host, result=_result.result)

        except ReadTimeout as e:
            logger.error(
                "ReadTimeout occurred for VPCS device %s: %s",
                device_name,
                str(e),
            )
            return Result(
                host=task.host,
                result=f"Command failed (ReadTimeout): {str(e)}",
                failed=True,
            )

        except Exception as e:
            # Retry once for transient failures
            logger.warning(
                "First attempt failed for VPCS device %s, retrying: %s",
                device_name,
                str(e),
            )
            try:
                _result = task.run(
                    task=netmiko_multiline,
                    commands=commands,
                    read_timeout=30,
                )
                return Result(host=task.host, result=_result.result)
            except Exception as retry_e:
                logger.error(
                    "VPCS command failed for device %s: %s (Exception: %s)",
                    device_name,
                    str(retry_e),
                    type(retry_e).__name__,
                )
                return Result(
                    host=task.host,
                    result=f"Command failed: {str(retry_e)}",
                    failed=True,
                )

    def _validate_tool_input(
        self, tool_input: str | bytes | list[Any] | dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Validate VPCS command input.

        Args:
            tool_input: Input from LangChain/LangGraph tool call.

        Returns:
            Tuple of (device_configs_list, project_id) or (error_list, None)
        """
        parsed_input = None

        # Compatibility Check and Parsing
        if isinstance(tool_input, (str, bytes, bytearray)):
            try:
                parsed_input = json.loads(tool_input)
                logger.info("Successfully parsed tool input from JSON string.")
            except json.JSONDecodeError as e:
                logger.error(
                    "Invalid JSON string received as tool input: %s", e
                )
                return (
                    [{"error": f"Invalid JSON string input from model: {e}"}],
                    None,
                )
        else:
            parsed_input = tool_input
            logger.info(
                "Using tool input directly as type: %s",
                type(parsed_input).__name__,
            )

        # Handle new format: {"project_id": "...", "device_configs": [...]}
        if isinstance(parsed_input, dict):
            project_id = parsed_input.get("project_id")
            device_configs = parsed_input.get("device_configs")

            # Validate project_id
            if not project_id:
                error_msg = "Missing required 'project_id' field in input"
                logger.error(error_msg)
                return ([{"error": error_msg}], None)

            if not self._validate_project_id(project_id):
                error_msg = f"Invalid project_id: {project_id}. Expected UUID."
                logger.error(error_msg)
                return ([{"error": error_msg}], None)

            # Validate device_configs
            if not isinstance(device_configs, list):
                error_msg = "'device_configs' must be an array"
                logger.error(error_msg)
                return ([{"error": error_msg}], None)

            if not device_configs:
                logger.warning("Device configs list is empty.")
                return [], project_id

            return device_configs, project_id

        else:
            error_msg = (
                "Tool input must be JSON with project_id and device_configs, "
                f"got {type(parsed_input).__name__}"
            )
            logger.error(error_msg)
            return ([{"error": error_msg}], None)

    def _validate_project_id(self, project_id: str) -> bool:
        """
        Validate project_id format (UUID).

        Args:
            project_id: The project ID to validate

        Returns:
            True if valid UUID format, False otherwise
        """
        uuid_pattern = (
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        return bool(re.match(uuid_pattern, project_id, re.IGNORECASE))

    def _configs_map(
        self, device_config_list: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """
        Create a mapping of device names to their command lists.

        Args:
            device_config_list: List of device configurations

        Returns:
            Dictionary mapping device names to command lists
        """
        return {
            config["device_name"]: config["commands"]
            for config in device_config_list
        }

    def _prepare_device_hosts_data(
        self, device_configs_list: list[dict[str, Any]], project_id: str
    ) -> dict[str, dict[str, Any]]:
        """
        Prepare Nornir inventory hosts data for VPCS devices.

        Args:
            device_configs_list: List of device configurations
            project_id: GNS3 project ID

        Returns:
            Dictionary mapping device names to their host data

        Raises:
            ValueError: If device not found in topology or missing port
        """
        # Get GNS3 server host
        gns3_host = get_gns3_server_host()

        # Extract all device names from input
        device_names = [config["device_name"] for config in device_configs_list]

        # Get device port mappings from topology
        device_ports = get_device_ports_from_topology(
            device_names, project_id=project_id
        )

        # Build Nornir inventory hosts data
        hosts_data = {}
        for device_name in device_names:
            if device_name not in device_ports:
                logger.error("Device '%s' not found in topology", device_name)
                hosts_data[device_name] = {
                    "error": f"Device '{device_name}' not found in topology"
                }
                continue

            port = device_ports[device_name]["port"]

            # VPCS devices use gns3_vpcs_telnet device type
            hosts_data[device_name] = {
                "port": port,
                "platform": "vpcs",
                "groups": ["vpcs_devices"],  # All VPCS devices share one group
                "connection_options": {
                    "netmiko": {
                        "extras": {
                            "device_type": "gns3_vpcs_telnet",
                            "fast_cli": False,
                            "global_delay_factor": 2.0,
                        }
                    }
                },
            }

        return hosts_data

    def _initialize_nornir(
        self, hosts_data: dict[str, dict[str, Any]]
    ) -> "Nornir":
        """
        Initialize Nornir with VPCS device inventory.

        Args:
            hosts_data: Dictionary of device host data

        Returns:
            Initialized Nornir instance

        Raises:
            ValueError: If initialization fails
        """
        try:
            defaults = _get_nornir_defaults()
            gns3_host = get_gns3_server_host()

            # Create a single generic group for shared configuration
            groups_data = {
                "vpcs_devices": {
                    "hostname": gns3_host,
                    "timeout": 30,
                    "username": "",  # VPCS doesn't require authentication
                    "password": "",  # VPCS doesn't require authentication
                }
            }

            logger.info(
                "Initializing Nornir for VPCS: host=%s, devices=%d",
                gns3_host,
                len(hosts_data),
            )

            return InitNornir(
                inventory={
                    "plugin": "DictInventory",
                    "options": {
                        "hosts": hosts_data,
                        "groups": groups_data,
                        "defaults": defaults,
                    },
                },
                runner={
                    "plugin": "threaded",
                    "options": {"num_workers": 10},
                },
                logging={"enabled": False},
            )
        except Exception as e:
            logger.error("Failed to initialize Nornir: %s", e)
            raise ValueError(f"Failed to initialize Nornir: {e}") from e

    def _process_task_results(
        self,
        device_configs_list: list[dict[str, Any]],
        hosts_data: dict[str, dict[str, Any]],
        task_result: AggregatedResult,
    ) -> list[dict[str, Any]]:
        """
        Process Nornir task results into the format expected by the tool.

        Args:
            device_configs_list: Original device configurations list
            hosts_data: Device hosts data
            task_result: Nornir aggregated task result

        Returns:
            List of result dictionaries
        """
        results = []

        for device_config in device_configs_list:
            device_name = device_config["device_name"]

            # Check if device had an error during preparation
            if device_name in hosts_data and "error" in hosts_data[device_name]:
                results.append({
                    "device_name": device_name,
                    "status": "error",
                    "output": hosts_data[device_name]["error"],
                    "commands": device_config["commands"],
                })
                continue

            # Get result from Nornir task
            if device_name in task_result:
                host_result = task_result[device_name]

                if host_result.failed:
                    # Task failed
                    error_msg = str(host_result.result) if host_result.result else "Unknown error"
                    results.append({
                        "device_name": device_name,
                        "status": "error",
                        "output": error_msg,
                        "commands": device_config["commands"],
                    })
                else:
                    # Task succeeded
                    results.append({
                        "device_name": device_name,
                        "status": "success",
                        "output": host_result.result,
                        "commands": device_config["commands"],
                    })
            else:
                # Device not in task result (shouldn't happen)
                results.append({
                    "device_name": device_name,
                    "status": "error",
                    "output": f"Device '{device_name}' not in task results",
                    "commands": device_config["commands"],
                })

        return results


if __name__ == "__main__":
    # Example usage
    import sys

    command_groups = json.dumps(
        {
            "project_id": "<PROJECT_UUID>",
            "device_configs": [
                {
                    "device_name": "PC1",
                    "commands": [
                        "ip 10.10.0.12/24 10.10.0.254",
                        "ping 10.10.0.254",
                    ],
                },
                {
                    "device_name": "PC2",
                    "commands": ["ip 10.10.0.13/24 10.10.0.254"],
                },
            ],
        }
    )

    exe_cmd = VPCSCommands()
    result = exe_cmd._run(tool_input=command_groups)
    print("Execution results:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
