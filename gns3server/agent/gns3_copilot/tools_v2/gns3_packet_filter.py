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

GNS3 packet filter management tool for network simulation.

Provides functionality to manage packet filters on GNS3 links,
including latency, packet loss, corruption, and BPF filtering.
"""

import json
import logging
import subprocess
from pprint import pprint
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client import Link
from gns3server.agent.gns3_copilot.gns3_client import get_gns3_connector

# Configure logging
logger = logging.getLogger(__name__)


class GNS3PacketFilterTool(BaseTool):
    """
    A LangChain tool to manage packet filters on GNS3 links.

    Supports getting available filters, setting filters, and clearing filters
    on network links to simulate various network conditions.

    **Input:**
    A JSON object with project_id, link_id, action, and optional filter parameters.
    Note: show_filters_icon is automatically set to false by default to hide the filter
    icon in the GNS3 Web UI.

    Example input for getting available filters:
        {
            "project_id": "uuid-of-project",
            "link_id": "uuid-of-link",
            "action": "get_available"
        }

    Example input for setting filters:
        {
            "project_id": "uuid-of-project",
            "link_id": "uuid-of-link",
            "action": "set",
            "filters": {
                "delay": [100, 10],
                "packet_loss": [5]
            },
            "show_filters_icon": false
        }

    Example input for getting current filters:
        {
            "project_id": "uuid-of-project",
            "link_id": "uuid-of-link",
            "action": "get"
        }

    Example input for clearing filters:
        {
            "project_id": "uuid-of-project",
            "link_id": "uuid-of-link",
            "action": "clear"
        }

    **Output:**
    A dictionary containing the action result.

    For "get_available": returns list of available filter types
    For "set": returns updated link information with applied filters
    For "get": returns current filters configured on the link
    For "clear": returns confirmation that filters were cleared
    """

    name: str = "manage_gns3_packet_filter"
    description: str = """
    Manages packet filters on GNS3 links to inject network faults and simulate network conditions.

    This tool is primarily used for fault injection scenarios to create realistic network problems
    for troubleshooting practice, such as latency, packet loss, and corruption.

    By default, the filter icon in the GNS3 Web UI is hidden (show_filters_icon=false) to avoid
    visual clutter when injecting faults for troubleshooting exercises.

    Supported actions:
    - "get_available": Get list of available filter types for the link
    - "set": Set packet filters on the link to inject network faults
    - "get": Get current filters configured on the link

    Common filter types for fault injection:
    - "frequency_drop": Drop every Nth packet (parameter: frequency, -1 to 32767)
    - "packet_loss": Packet loss percentage (parameter: chance, 0-100)
    - "delay": Delay in ms with optional jitter (parameters: latency 0-32767, jitter 0-32767)
    - "corrupt": Packet corruption percentage (parameter: chance, 0-100)
    - "bpf": Berkeley Packet Filter (parameter: filter expression text)

    Input is a JSON object with:
    - project_id (str): GNS3 project UUID
    - link_id (str): GNS3 link UUID
    - action (str): One of "get_available", "set", "get", "clear"
    - filters (dict, optional): Filter configuration for "set" action

    Example for getting available filters:
    {
        "project_id": "uuid-of-project",
        "link_id": "uuid-of-link",
        "action": "get_available"
    }

    Example for setting delay and packet loss:
    {
        "project_id": "uuid-of-project",
        "link_id": "uuid-of-link",
        "action": "set",
        "filters": {
            "delay": [100, 10],
            "packet_loss": [5]
        }
    }

    Returns a dictionary with action result, filter information, or error message.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Manages packet filters on a GNS3 link.

        Args:
            tool_input: A JSON string with project_id, link_id, action, and optional filters.
            run_manager: LangChain run manager (unused).

        Returns:
            dict: A dictionary with action result or an error message.
        """
        # Log received input
        logger.info("Received input: %s", tool_input)

        try:
            # Parse input JSON
            input_data = json.loads(tool_input)
            project_id = input_data.get("project_id")
            link_id = input_data.get("link_id")
            action = input_data.get("action")
            show_filters_icon = input_data.get("show_filters_icon", False)

            # Validate required fields
            if not project_id:
                logger.error("Invalid input: Missing project_id.")
                return {"error": "Missing project_id."}

            if not link_id:
                logger.error("Invalid input: Missing link_id.")
                return {"error": "Missing link_id."}

            if not action:
                logger.error("Invalid input: Missing action.")
                return {"error": "Missing action."}

            # Validate action
            valid_actions = ["get_available", "set", "get", "clear"]
            if action not in valid_actions:
                logger.error("Invalid action: %s. Must be one of %s", action, valid_actions)
                return {
                    "error": f"Invalid action: {action}. Must be one of {valid_actions}"
                }

            # Validate filters for "set" action
            if action == "set":
                filters = input_data.get("filters")
                if not filters or not isinstance(filters, dict):
                    logger.error("Invalid input: 'set' action requires 'filters' dict.")
                    return {
                        "error": "'set' action requires 'filters' dict with filter configuration."
                    }

            # Initialize Gns3Connector using factory function
            logger.info("Connecting to GNS3 server...")
            gns3_server = get_gns3_connector()

            if gns3_server is None:
                logger.error("Failed to create GNS3 connector")
                return {
                    "error": "Failed to connect to GNS3 server. "
                    "Please check your configuration."
                }

            # Create Link object
            logger.info(
                "Processing packet filter action '%s' for link %s...", action, link_id
            )
            link = Link(
                project_id=project_id, link_id=link_id, connector=gns3_server
            )

            # Execute action
            if action == "get_available":
                result = self._get_available_filters(link)
            elif action == "set":
                filters = input_data.get("filters", {})
                result = self._set_filters(link, filters, show_filters_icon)
            elif action == "get":
                result = self._get_filters(link)
            elif action == "clear":
                result = self._clear_filters(link, show_filters_icon)
            else:
                result = {"error": f"Unknown action: {action}"}

            # Log result
            logger.info("Packet filter action '%s' completed successfully.", action)

            return result

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            logger.error("Failed to process packet filter request: %s", e)
            return {
                "error": f"Failed to process packet filter request: {str(e)}"
            }

    def _get_available_filters(self, link: Link) -> dict[str, Any]:
        """Get available filter types for the link."""
        try:
            filters = link.available_filters()
            logger.info("Retrieved %d available filter types.", len(filters))
            return {
                "action": "get_available",
                "link_id": link.link_id,
                "available_filters": filters,
                "count": len(filters),
                "status": "success",
            }
        except Exception as e:
            logger.error("Failed to get available filters: %s", e)
            return {
                "action": "get_available",
                "link_id": link.link_id,
                "error": f"Failed to get available filters: {str(e)}",
                "status": "failed",
            }

    def _validate_bpf_syntax(self, bpf_expression: str) -> dict[str, Any]:
        """
        Validate BPF filter expression syntax using tshark.

        Args:
            bpf_expression: BPF filter expression to validate

        Returns:
            dict with 'valid' (bool) and 'error' (str or None) keys
        """
        try:
            # Use tshark to validate BPF syntax with 1 second timeout
            # Use -i lo (loopback) to avoid "(null)" interface in error messages
            result = subprocess.run(
                ["tshark", "-f", bpf_expression, "-i", "lo"],
                timeout=1,
                capture_output=True,
                text=True,
            )

            # Check if output contains "Invalid" indicating syntax error
            if "Invalid" in result.stdout or "Invalid" in result.stderr:
                error_lines = []
                if "Invalid" in result.stderr:
                    error_lines.extend(
                        line for line in result.stderr.split("\n") if "Invalid" in line
                    )
                if "Invalid" in result.stdout:
                    error_lines.extend(
                        line for line in result.stdout.split("\n") if "Invalid" in line
                    )

                # Strip interface suffix (e.g., "for interface 'lo'") for cleaner error
                error_msg_parts = []
                for line in error_lines:
                    clean = line.split(" for interface")[0].strip()
                    if clean:
                        error_msg_parts.append(clean)
                error_msg = " ".join(error_msg_parts) if error_msg_parts else "Invalid BPF syntax"
                logger.warning("BPF syntax validation failed: %s", error_msg)
                return {"valid": False, "error": error_msg}

            logger.info("BPF syntax validation passed")
            return {"valid": True, "error": None}

        except subprocess.TimeoutExpired:
            # Timeout is expected behavior - tshark waits for traffic
            # No "Invalid" in output means syntax is correct
            logger.info("BPF syntax validation passed (timeout expected)")
            return {"valid": True, "error": None}

        except FileNotFoundError:
            # tshark not installed - skip validation
            logger.warning(
                "tshark not found, skipping BPF syntax validation. "
                "Install tshark to enable BPF validation."
            )
            return {"valid": True, "error": None}

        except Exception as e:
            logger.error("Unexpected error during BPF validation: %s", e)
            return {"valid": False, "error": f"BPF validation error: {str(e)}"}

    def _set_filters(
        self, link: Link, filters: dict[str, Any], show_filters_icon: bool = False
    ) -> dict[str, Any]:
        """Set packet filters on the link."""
        try:
            # Validate BPF syntax if BPF filter is present
            if "bpf" in filters:
                bpf_filters = filters["bpf"]
                if isinstance(bpf_filters, list):
                    # Validate each BPF expression
                    for idx, bpf_expr in enumerate(bpf_filters):
                        if isinstance(bpf_expr, str):
                            validation = self._validate_bpf_syntax(bpf_expr)
                            if not validation["valid"]:
                                return {
                                    "action": "set",
                                    "link_id": link.link_id,
                                    "error": f"BPF syntax error at index {idx}: {validation['error']}",
                                    "status": "failed",
                                }
                elif isinstance(bpf_filters, str):
                    # Single BPF expression
                    validation = self._validate_bpf_syntax(bpf_filters)
                    if not validation["valid"]:
                        return {
                            "action": "set",
                            "link_id": link.link_id,
                            "error": f"BPF syntax error: {validation['error']}",
                            "status": "failed",
                        }

            # Update filters
            link.update(filters=filters, show_filters_icon=show_filters_icon)

            # Get updated link info
            link.get()

            logger.info("Successfully set filters on link %s", link.link_id)
            return {
                "action": "set",
                "link_id": link.link_id,
                "filters": link.filters,
                "status": "success",
                "message": "Filters applied successfully",
            }
        except Exception as e:
            logger.error("Failed to set filters: %s", e)
            return {
                "action": "set",
                "link_id": link.link_id,
                "error": f"Failed to set filters: {str(e)}",
                "status": "failed",
            }

    def _get_filters(self, link: Link) -> dict[str, Any]:
        """Get current filters configured on the link."""
        try:
            # Get link information
            link.get()

            logger.info("Retrieved current filters for link %s", link.link_id)
            return {
                "action": "get",
                "link_id": link.link_id,
                "filters": link.filters,
                "status": "success",
            }
        except Exception as e:
            logger.error("Failed to get filters: %s", e)
            return {
                "action": "get",
                "link_id": link.link_id,
                "error": f"Failed to get filters: {str(e)}",
                "status": "failed",
            }

    def _clear_filters(
        self, link: Link, show_filters_icon: bool = False
    ) -> dict[str, Any]:
        """Clear all filters from the link."""
        try:
            # Clear filters by setting empty dict
            link.update(filters={}, show_filters_icon=show_filters_icon)

            # Get updated link info to confirm
            link.get()

            logger.info("Successfully cleared filters on link %s", link.link_id)
            return {
                "action": "clear",
                "link_id": link.link_id,
                "filters": link.filters,
                "status": "success",
                "message": "Filters cleared successfully",
            }
        except Exception as e:
            logger.error("Failed to clear filters: %s", e)
            return {
                "action": "clear",
                "link_id": link.link_id,
                "error": f"Failed to clear filters: {str(e)}",
                "status": "failed",
            }


if __name__ == "__main__":
    # Test the tool locally
    # TODO: Replace with actual project and link UUIDs
    test_input = json.dumps(
        {
            "project_id": "d7fc094c-685e-4db1-ac11-5e33a1b2e066",
            "link_id": "link-uuid-here",
            "action": "get_available",
        }
    )

    tool = GNS3PacketFilterTool()
    result = tool._run(test_input)
    pprint(result)
