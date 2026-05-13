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

GNS3 node name update tool for renaming network devices.

Provides functionality to update the name of one or multiple nodes
    in GNS3 projects.
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


class GNS3UpdateNodeNameTool(BaseTool):
    """
    A LangChain tool to update the name of one or multiple nodes
        in a GNS3 project.

    **Input**:
    A JSON object with project_id and nodes array containing
        node_id and new_name.
    Example:
        {
            "project_id": "uuid-of-project",
            "nodes": [
                {"node_id": "uuid-of-node-1", "new_name": "Router1"},
                {"node_id": "uuid-of-node-2", "new_name": "Switch1"}
            ]
        }

    **Output**:
    A dictionary with all nodes' update results:
    {
        "project_id": "...",
        "total_nodes": 2,
        "successful": 2,
        "failed": 0,
        "nodes": [
            {
                "node_id": "...",
                "old_name": "...",
                "new_name": "...",
                "status": "success"
            },
            {
                "node_id": "...",
                "old_name": "...",
                "new_name": "...",
                "status": "success"
            }
        ]
    }
    """

    name: str = "update_gns3_node_name"
    description: str = """
    Updates the name of one or multiple nodes in a GNS3 project.
    Input: JSON with project_id and nodes array.
    Each node must have node_id and new_name.
    Returns: A dictionary with all nodes' update results
        including success/failure status.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        try:
            # Parse input JSON
            input_data = json.loads(tool_input)
            project_id = input_data.get("project_id")
            nodes = input_data.get("nodes", [])

            # Validate input
            if not project_id:
                logger.error("Missing required field: project_id.")
                return {"error": "Missing required field: project_id."}

            if not isinstance(nodes, list) or len(nodes) == 0:
                logger.error("nodes must be a non-empty list.")
                return {"error": "nodes must be a non-empty list."}

            # Validate each node entry
            for i, node_data in enumerate(nodes):
                if not isinstance(node_data, dict):
                    logger.error("Node %d must be a dictionary.", i + 1)
                    return {"error": f"Node {i + 1} must be a dictionary."}
                if "node_id" not in node_data or "new_name" not in node_data:
                    logger.error("Node %d missing node_id or new_name.", i + 1)
                    return {
                        "error": f"Node {i + 1} missing node_id or new_name."
                    }

            # Initialize Gns3Connector
            logger.info("Connecting to GNS3 server...")
            gns3_server = get_gns3_connector()

            if gns3_server is None:
                logger.error("Failed to create GNS3 connector")
                return {
                    "error": "Failed to connect to GNS3 server. "
                    "Please check your configuration."
                }

            # Update node names
            logger.info(
                "Updating names for %d nodes in project %s...",
                len(nodes),
                project_id,
            )
            results = []

            for i, node_data in enumerate(nodes):
                try:
                    node_id = node_data.get("node_id")
                    new_name = node_data.get("new_name")

                    logger.info(
                        "Updating node %d/%d: %s -> %s",
                        i + 1,
                        len(nodes),
                        node_id,
                        new_name,
                    )

                    # Get node to retrieve current name
                    node = Node(
                        project_id=project_id,
                        node_id=node_id,
                        connector=gns3_server,
                    )
                    node.get()
                    old_name = node.name

                    # Update node name
                    node.update(name=new_name)

                    # Verify update
                    node.get()
                    if node.name == new_name:
                        node_info = {
                            "node_id": node_id,
                            "old_name": old_name,
                            "new_name": new_name,
                            "status": "success",
                        }
                        results.append(node_info)
                        logger.info(
                            "Successfully updated node name: %s -> %s",
                            old_name,
                            new_name,
                        )
                    else:
                        error_info = {
                            "node_id": node_id,
                            "old_name": old_name,
                            "new_name": new_name,
                            "current_name": node.name,
                            "status": "failed",
                            "error": "Name verification failed",
                        }
                        results.append(error_info)
                        logger.error(
                            "Failed to update node name for %s", node_id
                        )

                except Exception as e:
                    error_info = {
                        "node_id": node_data.get("node_id"),
                        "new_name": node_data.get("new_name"),
                        "status": "failed",
                        "error": str(e),
                    }
                    results.append(error_info)
                    logger.error("Failed to update node %d: %s", i + 1, e)

            # Analyze results
            successful_nodes = [
                r for r in results if r.get("status") == "success"
            ]
            failed_nodes = [r for r in results if r.get("status") == "failed"]

            # Construct final response
            response = {
                "project_id": project_id,
                "total_nodes": len(nodes),
                "successful": len(successful_nodes),
                "failed": len(failed_nodes),
                "nodes": results,
            }

            logger.info(
                "Name update completed: %d successful, %d failed",
                len(successful_nodes),
                len(failed_nodes),
            )

            return response

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            logger.error("Failed to update node names: %s", e)
            return {"error": f"Failed to update node names: {str(e)}"}


if __name__ == "__main__":
    # Test with single node
    print("=== Testing single node name update ===")
    test_input_single = json.dumps(
        {
            # Replace with actual project UUID
            "project_id": "your-project-uuid",
            "nodes": [
                {
                    # Replace with actual node UUID
                    "node_id": "your-node-uuid",
                    "new_name": "Router1",
                }
            ],
        }
    )
    tool = GNS3UpdateNodeNameTool()
    result_single = tool._run(test_input_single)
    pprint(result_single)

    # Test with multiple nodes
    print("\n=== Testing multiple nodes name update ===")
    test_input_multiple = json.dumps(
        {
            # Replace with actual project UUID
            "project_id": "your-project-uuid",
            "nodes": [
                {"node_id": "node-uuid-1", "new_name": "Router1"},
                {"node_id": "node-uuid-2", "new_name": "Switch1"},
                {"node_id": "node-uuid-3", "new_name": "PC1"},
            ],
        }
    )
    result_multiple = tool._run(test_input_multiple)
    pprint(result_multiple)
