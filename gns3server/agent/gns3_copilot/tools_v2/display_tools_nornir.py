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

This module provides a tool to execute display commands on multiple devices
 in a GNS3 topology using Nornir.
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
from gns3server.agent.gns3_copilot.utils.command_filter import (
    filter_forbidden_commands,
)

# Import custom Netmiko device types for GNS3 emulation
# This registers gns3_huawei_telnet_ce and other custom device types
# NOTE: Must be imported BEFORE any Nornir operations to ensure device types are registered
from gns3server.agent.gns3_copilot.utils import custom_netmiko  # noqa: F401

# Explicitly register custom device types to ensure they are available
# This is a safety measure in case the auto-registration on import doesn't work
try:
    from gns3server.agent.gns3_copilot.utils.custom_netmiko import huawei_ce
    from gns3server.agent.gns3_copilot.utils.custom_netmiko.ruijie_telnet import (
        register_custom_device_type as register_ruijie_device_type,
    )

    # Re-register to ensure device types are available
    huawei_ce.register_custom_device_type()
    register_ruijie_device_type()

    # CRITICAL: Update netmiko.ssh_dispatcher platforms lists
    # The platforms variable is calculated at module import time in ssh_dispatcher
    # We need to update it after registering custom device types.
    # NOTE: netmiko.ssh_dispatcher is aliased to ConnectHandler function,
    # so we use importlib to get the actual module
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

# config log
logger = logging.getLogger(__name__)

# Suppress nornir INFO logs in console (reduce verbosity)
# The logging={"enabled": False} in InitNornir only disables plugin
# internal logs, but nornir.core still logs task execution at INFO level.
# Set to WARNING to suppress these.
logging.getLogger("nornir.core").setLevel(logging.WARNING)
logging.getLogger("nornir").setLevel(logging.WARNING)


# Local Nornir configuration functions for network devices
def _get_nornir_defaults() -> dict[str, Any]:
    """Get Nornir default configuration."""
    return {"data": {"location": "gns3"}}


class ExecuteMultipleDeviceCommands(BaseTool):
    """
    A READ-ONLY diagnostic tool for viewing network device configurations.

    **CRITICAL: DIAGNOSIS ONLY - NO CONFIGURATION PERMISSIONS**

    This tool is exclusively designed for read-only operations to inspect and
    diagnose network devices. It CANNOT and MUST NOT be used for configuration.

    **Allowed Command Types:**
    - Display commands: show, display (Cisco/Huawei)
    - Debug commands: debug ip routing, debug ospf events
    - Verification commands: ping, traceroute, telnet
    - Status commands: show version, show running-config, show ip route

    **Strictly Prohibited:**
    - Configuration mode: configure terminal, config t
    - Interface configuration: interface, ip address
    - Protocol configuration: router ospf, router bgp
    - Any command that modifies device state
    """

    name: str = "execute_multiple_device_commands"
    description: str = """
    **READ-ONLY DIAGNOSTIC TOOL** - View network device configurations.

    Use this tool to inspect device information without making any changes.

    **PERMITTED USE CASES:**
    - View device status: show version, show running-config
    - Check routing: show ip route, show ip ospf neighbor, show bgp summary
    - Interface status: show ip interface brief, show interfaces
    - Protocol diagnostics: show ospf database, show bgp routes, debug commands
    - Connectivity testing: ping, traceroute

    **STRICTLY FORBIDDEN:**
    - NO configuration commands (configure terminal, interface, router, etc.)
    - NO commands that modify device state
    - NEVER use 'exit' command - this disconnects the session and breaks subsequent commands
    - If you need to configure, provide guidance to the student instead

    **Input Format:**
        {
            "project_id": "<PROJECT_UUID>",
            "device_configs": [
                {
                    "device_name": "R-1",
                    "commands": ["show version", "show ip interface brief"]
                },
                {
                    "device_name": "R-2",
                    "commands": ["show version", "show ip ospf neighbor"]
                }
            ]
        }

    **Returns:** List of device outputs for diagnostic analysis.
    """

    def _run(
        self,
        tool_input: str | bytes | list[Any] | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Executes READ-ONLY diagnostic commands on multiple devices in GNS3.

        This method only permits display/show commands and does not allow
        configuration changes to network devices.

        Args:
            tool_input: JSON string with project_id and diagnostic commands.

        Returns:
            List[Dict]: A list of dicts with device names and outputs.
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

        # Filter forbidden commands and store blocked commands info
        device_configs_list, blocked_commands_map = (
            self._filter_forbidden_commands_from_device_configs(
                device_configs_list
            )
        )

        # Create a mapping of device names to their display commands
        device_configs_map = self._configs_map(device_configs_list)

        # Prepare device hosts data
        try:
            hosts_data = self._prepare_device_hosts_data(
                device_configs_list, project_id
            )
        except ValueError as e:
            logger.error("Failed to prepare device hosts data: %s", e)
            return [{"error": str(e)}]

        # Check if any devices have errors (e.g., missing device_type tag)
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
                task=self._run_all_device_configs_with_single_retry,
                device_configs_map=device_configs_map,
            )

            # Process results for all devices
            results = self._process_task_results(
                device_configs_list,
                hosts_data,
                task_result,
                blocked_commands_map,
            )

        except Exception as e:
            # Overall execution failed
            logger.error("Error executing display on all devices: %s", e)
            return [{"error": f"Execution error: {str(e)}"}]

        logger.debug(
            "Multiple device display execution completed. Results: %s",
            json.dumps(results, indent=2, ensure_ascii=False),
        )

        return results

    def _run_all_device_configs_with_single_retry(
        self, task: Task, device_configs_map: dict[str, list[str]]
    ) -> Result:
        """Execute READ-ONLY diagnostic commands with single retry."""
        device_name = task.host.name
        diagnostic_commands = device_configs_map.get(device_name, [])

        if not diagnostic_commands:
            return Result(
                host=task.host, result="No diagnostic commands to execute"
            )

        try:
            _result = task.run(
                task=netmiko_multiline,
                commands=diagnostic_commands,
                enable=True,
                read_timeout=60,
            )
            return Result(host=task.host, result=_result.result)

        except ReadTimeout as e:
            # Log ReadTimeout exception with full details
            logger.error(
                "ReadTimeout occurred for device %s: %s",
                device_name,
                str(e),
            )
            return Result(
                host=task.host,
                result=f"diagnostic command failed (ReadTimeout): {str(e)}",
                failed=True,
            )

        except Exception as e:
            # Handle Cisco IOSv L2 where '#' prompt char may be delayed,
            # causing Netmiko failures. Implements retry logic.
            if "netmiko_multiline (failed)" in str(e):
                _result = task.run(
                    task=netmiko_multiline,
                    commands=diagnostic_commands,
                    enable=True,
                    read_timeout=60,
                )
                return Result(host=task.host, result=_result.result)

            # Log any other exceptions with full details
            logger.error(
                "diagnostic command failed for device %s: %s (Exception: %s)",
                device_name,
                str(e),
                type(e).__name__,
            )
            return Result(
                host=task.host,
                result=f"diagnostic command failed (Unhandled): {str(e)}",
                failed=True,
            )

    def _validate_tool_input(
        self, tool_input: str | bytes | list[Any] | dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Validate diagnostic command input for read-only device inspection.

        Handles both new and legacy input formats. Supports new format with
        project_id and device_configs, as well as legacy array format.

        Args:
            tool_input: Input from LangChain/LangGraph tool call.

        Returns:
            Tuple of (device_configs_list, project_id) or (error_list, None)
        """

        parsed_input = None

        # Compatibility Check and Parsing ---
        # Check if the input is a string (or bytes) which needs to be parsed.
        if isinstance(tool_input, (str, bytes, bytearray)):
            # Handle models (like DeepSeek) that return a raw JSON string.
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
            # Handle standard models (like GPT/OpenAI) where the framework
            # has already parsed the JSON into a Python object (dict or list).
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

        # Handle legacy format: [...]
        elif isinstance(parsed_input, list):
            logger.warning(
                "Legacy input format without project_id. Use new format."
            )
            return parsed_input, None

        else:
            error_msg = (
                "Tool input must be JSON with project_id and device_configs, "
                f"or legacy JSON array, got {type(parsed_input).__name__}"
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

    def _filter_forbidden_commands_from_device_configs(
        self, device_configs_list: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
        """
        Filter out forbidden commands from device configurations.

        Args:
            device_configs_list: List of device configurations with commands.

        Returns:
            Tuple of (filtered_configs, blocked_map):
            - filtered_configs: Device configs with forbidden removed.
            - blocked_map: Dict mapping device names to blocked commands.
        """
        filtered_list = []
        blocked_commands_map: dict[str, dict[str, str]] = {}

        for device_config in device_configs_list:
            device_name = device_config["device_name"]
            commands = device_config["commands"]

            # Filter commands
            allowed_commands, blocked_info = filter_forbidden_commands(
                commands
            )

            # Update device config with allowed commands only
            filtered_config = device_config.copy()
            filtered_config["commands"] = allowed_commands
            filtered_list.append(filtered_config)

            # Store blocked commands info if any
            if blocked_info:
                blocked_commands_map[device_name] = blocked_info
                logger.info(
                    "Device %s: %d command(s) blocked: %s",
                    device_name,
                    len(blocked_info),
                    list(blocked_info.keys()),
                )

        return filtered_list, blocked_commands_map

    def _configs_map(
        self, device_config_list: list[dict[str, Any]]
    ) -> dict[str, list[str]]:
        """Create a mapping of device names to their diagnostic commands."""
        device_diagnostic_map = {}
        for device_config in device_config_list:
            device_name = device_config["device_name"]
            diagnostic_commands = device_config["commands"]
            device_diagnostic_map[device_name] = diagnostic_commands

        return device_diagnostic_map

    def _prepare_device_hosts_data(
        self,
        device_config_list: list[dict[str, Any]],
        project_id: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Prepare device hosts data from topology information."""
        # Extract device names list
        device_names = [
            device_config["device_name"]
            for device_config in device_config_list
        ]

        # Get device port information with project_id
        hosts_data = get_device_ports_from_topology(device_names, project_id)

        if not hosts_data:
            error_msg = (
                f"Failed to get device info from topology. "
                f"Project: {project_id}, Devices: {device_names}"
            )
            raise ValueError(error_msg)

        # Check for missing devices
        missing_devices = set(device_names) - set(hosts_data.keys())
        if missing_devices:
            logger.warning(
                "Some devices not found in topology (Project ID: %s): %s",
                project_id or "default",
                missing_devices,
            )

        return hosts_data

    def _initialize_nornir(
        self, hosts_data: dict[str, dict[str, Any]]
    ) -> Nornir:
        """
        Initialize Nornir with the provided hosts data.

        Each host now has its own connection_options (device_type), so we only
        need a single generic group for shared configuration (hostname, timeout, etc.).
        This is the Nornir best practice for multi-vendor environments.
        """
        try:
            defaults = _get_nornir_defaults()
            gns3_host = get_gns3_server_host()

            # Create a single generic group for shared configuration
            # Individual device types are handled at host level via connection_options
            groups_data = {
                "network_devices": {
                    "hostname": gns3_host,
                    "timeout": 120,
                    "username": "",
                    "password": "",
                }
            }

            # Log device types being configured
            device_types = [
                host["connection_options"]["netmiko"]["extras"]["device_type"]
                for host in hosts_data.values()
            ]
            logger.info(
                "Initializing Nornir: host=%s, device_types=%s, hosts=%d",
                gns3_host,
                list(set(device_types)),
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
        blocked_commands_map: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Process the task results and format them for return."""
        results = []

        for device_config in device_configs_list:
            device_name = device_config["device_name"]
            diagnostic_commands = device_config["commands"]
            blocked_commands_info = blocked_commands_map.get(device_name, {})

            # Check if device is in topology
            if device_name not in hosts_data:
                device_result = {
                    "device_name": device_name,
                    "status": "failed",
                    "error": (
                        f"Device '{device_name}' not found in topology "
                        "or missing console_port"
                    ),
                }
                # Add blocked commands info if any
                if blocked_commands_info:
                    device_result["blocked_commands"] = list(
                        blocked_commands_info.keys()
                    )
                    device_result["blocked_info"] = blocked_commands_info
                results.append(device_result)
                continue

            # Check if device has execution results
            if device_name not in task_result:
                device_result = {
                    "device_name": device_name,
                    "status": "failed",
                    "error": (
                        f"Device '{device_name}' not found in task results"
                    ),
                }
                # Add blocked commands info if any
                if blocked_commands_info:
                    device_result["blocked_commands"] = list(
                        blocked_commands_info.keys()
                    )
                    device_result["blocked_info"] = blocked_commands_info
                results.append(device_result)
                continue

            # Process execution results
            multi_result = task_result[device_name]
            device_result = {"device_name": device_name}

            if multi_result[0].failed:
                # Execution failed
                device_result["status"] = "failed"
                device_result["error"] = (
                    f"Diagnostic command failed: {multi_result[0].result}"
                )
                device_result["output"] = multi_result[0].result
            else:
                # Execution successful
                device_result["status"] = "success"
                device_result["output"] = multi_result[0].result
                device_result["diagnostic_commands"] = diagnostic_commands

            # Add blocked commands info if any
            if blocked_commands_info:
                device_result["blocked_commands"] = list(
                    blocked_commands_info.keys()
                )
                device_result["blocked_info"] = blocked_commands_info
                # Update status if some commands were blocked but succeeded
                if device_result["status"] == "success":
                    device_result["status"] = "partial_success"

            results.append(device_result)

        return results


if __name__ == "__main__":
    # Example usage with new format
    device_commands = json.dumps(
        {
            "project_id": "<PROJECT_UUID>",
            "device_configs": [
                {
                    "device_name": "R-2",
                    "commands": ["show version", "show ip interface brief"],
                },
                {
                    "device_name": "R-1",
                    "commands": ["show version", "show ip interface brief"],
                },
                {
                    "device_name": "SW-1",
                    "commands": ["show version", "show ip interface brief"],
                },
                {
                    "device_name": "SW-2",
                    "commands": ["show version", "show ip interface brief"],
                },
            ],
        }
    )

    exe_cmd = ExecuteMultipleDeviceCommands()

    failed_count = 0

    for _i in range(0, 1):
        exe_results = exe_cmd._run(tool_input=device_commands)
        for result in exe_results:
            for result in exe_results:
                if result.get("status") == "failed":
                    failed_count += 1

    print(f"Failed Count: {failed_count}")

    # print("Execution results:")
    # print(json.dumps(result, indent=2, ensure_ascii=False))
