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

GNS3 link creation tool for connecting network nodes.

Provides functionality to create links between nodes in GNS3 projects
using the GNS3 API connector.
"""

import json
import logging
from pprint import pprint
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client import Link
from gns3server.agent.gns3_copilot.gns3_client import get_gns3_connector

# Configure logging
logger = logging.getLogger(__name__)


class GNS3LinkTool(BaseTool):
    """
    Tool for creating network links between GNS3 nodes.

    Creates one or more links between specified nodes in a GNS3 project
    by connecting their network ports. Supports batch link creation
    with error handling for individual link failures.
    """

    name: str = "create_gns3_link"
    description: str = """
    Creates one or more links between nodes in a GNS3 project.

    Input: A JSON string with:
    - `project_id` (str): The UUID of the GNS3 project.
    - `links` (list): A non-empty array of link definitions, each containing:
    - `node_id1` (str): UUID of the first node.
    - `port1` (str): Port name of the first node (e.g., 'Ethernet0/0').
    - `node_id2` (str): UUID of the second node.
    - `port2` (str): Port name of the second node (e.g., 'Ethernet0/0').
    Note: Port names must match those from `gns3_topology_reader` tool.

    Example Input:
    {
        "project_id": "uuid-of-project",
        "links": [
            {
                "node_id1": "uuid-of-node1",
                "port1": "Ethernet0/0",
                "node_id2": "uuid-of-node2",
                "port2": "Ethernet0/0"
            }
        ]
    }
    Output: A list of dicts, each containing:
    - For successful links: link_id, node_id1, port1, node_id2, port2.
    - For failed links: error(str) with error message.

    Example Output:
    [
        {
            "link_id": "uuid-of-link",
            "node_id1": "uuid-of-node1",
            "port1" : "Ethernet0/0",
            "node_id2": "uuid-of-node2",
            "port2": "Ethernet0/0"
        },
        {
            "error": "Port not found in link 1"
        },
    ]
    """

    def _run(
        self,
        tool_input: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> list[dict[str, Any]]:
        """
        Creates one or multiple links between nodes in a GNS3 project.

        Args:
            tool_input: JSON string with project_id and links array.
            run_manager: LangChain run manager (unused).

        Returns:
            list: A list with created link details or error messages.
        """
        # Log received input
        logger.debug("Received input: %s", tool_input)

        try:
            # Parse input JSON
            input_data = json.loads(tool_input)
            project_id = input_data.get("project_id")
            links_data = input_data.get("links", [])

            # Validate input
            if not project_id:
                logger.error("Missing required field: project_id")
                return [{"error": "Missing required field: project_id"}]

            if not isinstance(links_data, list) or len(links_data) == 0:
                logger.error("Invalid links data: must be a non-empty array")
                return [
                    {"error": "Invalid links data: must be a non-empty array"}
                ]

            # Initialize Gns3Connector using factory function
            logger.info("Connecting to GNS3 server...")
            gns3_server = get_gns3_connector()

            if gns3_server is None:
                logger.error("Failed to create GNS3 connector")
                return [
                    {
                        "error": (
                            "Failed to connect to GNS3 server. "
                            "Please check your configuration."
                        )
                    }
                ]

            created_links = []

            # Process each link definition
            for i, link_data in enumerate(links_data):
                try:
                    logger.info("Creating link %d/%d", i + 1, len(links_data))

                    # Extract link parameters
                    node_id1 = link_data.get("node_id1")
                    port1 = link_data.get("port1")
                    node_id2 = link_data.get("node_id2")
                    port2 = link_data.get("port2")

                    # Validate link parameters
                    if not all([node_id1, port1, node_id2, port2]):
                        error_msg = (
                            f"Missing required fields in link definition {i}"
                        )
                        logger.error(error_msg)
                        created_links.append({"error": error_msg})
                        continue

                    # Get node details
                    node1 = gns3_server.get_node(
                        project_id=project_id, node_id=node_id1
                    )
                    node2 = gns3_server.get_node(
                        project_id=project_id, node_id=node_id2
                    )
                    if not node1 or not node2:
                        error_msg = f"Node not found in link {i}"
                        logger.error(error_msg)
                        created_links.append({"error": error_msg})
                        continue

                    # Find port information - match by name or short_name
                    port1_info = next(
                        (
                            port
                            for port in node1.get("ports", [])
                            if port.get("name") == port1 or port.get("short_name") == port1
                        ),
                        None,
                    )
                    port2_info = next(
                        (
                            port
                            for port in node2.get("ports", [])
                            if port.get("name") == port2 or port.get("short_name") == port2
                        ),
                        None,
                    )
                    if not port1_info or not port2_info:
                        error_msg = f"Port not found in link {i}"
                        logger.error(error_msg)
                        created_links.append({"error": error_msg})
                        continue

                    # Create the link
                    link = Link(
                        project_id=project_id,
                        connector=gns3_server,
                        nodes=[
                            {
                                "node_id": node_id1,
                                "adapter_number": port1_info.get(
                                    "adapter_number", 0
                                ),
                                "port_number": port1_info.get(
                                    "port_number", 0
                                ),
                                "label": {"text": port1_info.get("short_name") or port1},
                            },
                            {
                                "node_id": node_id2,
                                "adapter_number": port2_info.get(
                                    "adapter_number", 0
                                ),
                                "port_number": port2_info.get(
                                    "port_number", 0
                                ),
                                "label": {"text": port2_info.get("short_name") or port2},
                            },
                        ],
                    )
                    link.create()
                    link.get()

                    # Collect link details
                    link_info = {
                        "link_id": link.link_id,
                        "node_id1": node_id1,
                        "port1": port1,
                        "node_id2": node_id2,
                        "port2": port2,
                    }
                    created_links.append(link_info)

                except Exception as e:
                    error_msg = f"Failed to create link {i}: {str(e)}"
                    logger.error(error_msg)
                    created_links.append({"error": error_msg})

            # Log final results
            success_count = len(
                [link for link in created_links if "error" not in link]
            )
            logger.info(
                "Link creation completed: %d successful, %d failed",
                success_count,
                len(links_data) - success_count,
            )

            return created_links

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return [{"error": f"Invalid JSON input: {e}"}]
        except Exception as e:
            logger.error("Failed to process link creation: %s", e)
            return [{"error": f"Failed to process link creation: {str(e)}"}]


if __name__ == "__main__":
    # Test with single link
    single_link_input = json.dumps(
        {
            "project_id": "your-project-uuid",
            "links": [
                {
                    "node_id1": "your-node1-uuid",
                    "port1": "Ethernet0/0",
                    "node_id2": "your-node2-uuid",
                    "port2": "Ethernet0/0",
                }
            ],
        }
    )

    # Test with multiple links
    multiple_links_input = json.dumps(
        {
            "project_id": "your-project-uuid",
            "links": [
                {
                    "node_id1": "your-node1-uuid",
                    "port1": "Ethernet0/0",
                    "node_id2": "your-node2-uuid",
                    "port2": "Ethernet0/0",
                },
                {
                    "node_id1": "your-node1-uuid",
                    "port1": "Ethernet0/1",
                    "node_id2": "your-node3-uuid",
                    "port2": "Ethernet0/0",
                },
            ],
        }
    )

    tool = GNS3LinkTool()

    print("=== Testing Single Link Creation ===")
    result = tool._run(single_link_input)
    pprint(result)

    print("\n=== Testing Multiple Links Creation ===")
    result = tool._run(multiple_links_input)
    pprint(result)
