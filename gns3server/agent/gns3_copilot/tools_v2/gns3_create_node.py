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

GNS3 node creation tool for network topology building.

Provides functionality to create multiple nodes in GNS3 projects
using specified templates and coordinates through the GNS3 API.
"""

import json
import logging
from pprint import pprint
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client import Node
from gns3server.agent.gns3_copilot.gns3_client import get_gns3_connector

# Configure logging
logger = logging.getLogger(__name__)


class GNS3CreateNodeTool(BaseTool):
    """
    A LangChain tool to create multiple nodes in a GNS3 project
    using specified templates and coordinates.

    **Input:**
    A JSON object with project_id and array of nodes with template_id,
    x, y coordinates, and optional name.

    Example input:
        {
            "project_id": "uuid-of-project",
            "nodes": [
                {
                    "template_id": "uuid-of-template",
                    "x": 100,
                    "y": -200,
                    "name": "R1"
                },
                {
                    "template_id": "uuid-of-template2",
                    "x": -200,
                    "y": 300,
                    "name": "R2"
                }
            ]
        }

    **Output:**
    A dictionary containing the creation results for all nodes.
    Example output:
        {
            "project_id": "uuid-of-project",
            "created_nodes": [
                {
                    "node_id": "uuid-of-node1",
                    "name": "R1",
                    "status": "success"
                },
                {
                    "node_id": "uuid-of-node2",
                    "name": "R2",
                    "status": "success"
                }
            ],
            "total_nodes": 2,
            "successful_nodes": 2,
            "failed_nodes": 0
        }
    If error occurs during validation, returns dict with error message.
    """

    name: str = "create_gns3_node"
    description: str = """
    Creates multiple nodes in a GNS3 project using templates and coordinates.
    Input is a JSON object with project_id and array of nodes.
    Each node requires: template_id, x, y. Optional: name (to set node name directly).
    Example input:
        {
            "project_id": "uuid-of-project",
            "nodes": [
                {
                    "template_id": "uuid-of-template",
                    "x": 100,
                    "y": -200,
                    "name": "R1"
                },
                {
                    "template_id": "uuid-of-template2",
                    "x": -200,
                    "y": 300,
                    "name": "R2"
                }
            ]
        }
    IMPORTANT: Ensure distance between any two nodes is greater than 250 px.
    This spacing is necessary to display interface numbers clearly for better
    topology visualization.
    Returns a dictionary with creation results for all nodes, including
    success/failure status.
    If the operation fails during input validation, returns a dictionary with
    an error message.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Creates nodes in a GNS3 project with templates and coordinates.

        Args:
            tool_input: A JSON string with project_id and an array of nodes.
            run_manager: LangChain run manager (unused).

        Returns:
            dict: A dictionary with creation results for all nodes or an error
                message.
        """
        # Log received input
        logger.info("Received input: %s", tool_input)

        try:
            # Parse input JSON
            input_data = json.loads(tool_input)
            project_id = input_data.get("project_id")
            nodes = input_data.get("nodes", [])

            # Validate input
            if not project_id:
                logger.error("Invalid input: Missing project_id.")
                return {"error": "Missing project_id."}

            if not isinstance(nodes, list) or len(nodes) == 0:
                logger.error("Invalid input: nodes must be a non-empty array.")
                return {"error": "nodes must be a non-empty array."}

            # Validate each node in the array
            for i, node_data in enumerate(nodes):
                if not isinstance(node_data, dict):
                    logger.error(
                        "Invalid input: Node %d must be a dictionary.", i + 1
                    )
                    return {"error": f"Node {i + 1} must be a dictionary."}

                template_id = node_data.get("template_id")
                x = node_data.get("x")
                y = node_data.get("y")
                name = node_data.get("name")

                if not all(
                    [
                        template_id,
                        isinstance(x, (int, float)),
                        isinstance(y, (int, float)),
                    ]
                ):
                    logger.error(
                        "Invalid input: Node %d missing or invalid "
                        "template_id, x, or y.",
                        i + 1,
                    )
                    return {
                        "error": f"Node {i + 1} missing or invalid "
                        f"template_id, x, or y."
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

            # Create nodes
            logger.info(
                "Creating %d nodes in project %s...", len(nodes), project_id
            )
            results: list[dict[str, Any]] = []

            for i, node_data in enumerate(nodes):
                try:
                    template_id = node_data.get("template_id")
                    x = node_data.get("x")
                    y = node_data.get("y")
                    name = node_data.get("name")

                    logger.info(
                        "Creating node %d/%d with template %s at (%s, %s), name=%s...",
                        i + 1,
                        len(nodes),
                        template_id,
                        x,
                        y,
                        name,
                    )

                    # Create node
                    node = Node(
                        project_id=project_id,
                        template_id=template_id,
                        x=x,
                        y=y,
                        name=name,
                        connector=gns3_server,
                    )
                    node.create()

                    # Retrieve node details
                    node.get()
                    node_info = {
                        "node_id": node.node_id,
                        "name": node.name,
                        "status": "success",
                    }

                    results.append(node_info)

                except Exception as e:
                    error_info = {
                        "error": f"Node {i + 1} creation failed: {str(e)}",
                        "status": "failed",
                    }
                    results.append(error_info)
                    logger.error("Failed to create node %d: %s", i + 1, e)
                    # Continue with next node even if one fails

            # Calculate summary statistics
            successful_nodes = len(
                [r for r in results if r.get("status") == "success"]
            )
            failed_nodes = len(
                [r for r in results if r.get("status") == "failed"]
            )

            # Prepare final result
            final_result = {
                "project_id": project_id,
                "created_nodes": results,
                "total_nodes": len(nodes),
                "successful_nodes": successful_nodes,
                "failed_nodes": failed_nodes,
            }

            # Log the final result
            logger.info(
                "Node creation completed: %d successful, %d failed, %d total.",
                successful_nodes,
                failed_nodes,
                len(nodes),
            )

            # Return JSON-formatted result
            return final_result

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            logger.error("Failed to process node creation request: %s", e)
            return {
                "error": f"Failed to process node creation request: {str(e)}"
            }


if __name__ == "__main__":
    # Test the tool locally with multiple nodes
    test_input = json.dumps(
        {
            # TODO: Replace with actual project UUID
            "project_id": "d7fc094c-685e-4db1-ac11-5e33a1b2e066",
            "nodes": [
                {
                    # TODO: Replace with actual template UUID
                    "template_id": "b923a635-b7cc-4cb5-9a86-9357e04c02f7",
                    "x": 100,
                    "y": -200,
                    "name": "R1",
                },
                {
                    # TODO: Replace with actual template UUID
                    "template_id": "b923a635-b7cc-4cb5-9a86-9357e04c02f7",
                    "x": 200,
                    "y": -300,
                    "name": "R2",
                },
            ],
        }
    )
    tool = GNS3CreateNodeTool()
    result = tool._run(test_input)
    pprint(result)
