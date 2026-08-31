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

GNS3 node stop tool for network device shutdown.

Provides functionality to stop one or multiple nodes in GNS3 projects.
"""

import json
import logging
from pprint import pprint
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client.api_handlers import (
    build_gns3_ctx,
    get_nodes_handler,
    stop_node_handler,
)

# Configure logging
logger = logging.getLogger(__name__)


class GNS3StopNodeTool(BaseTool):
    """
    A LangChain tool to stop one or multiple nodes in a GNS3 project.

    **Input**:
    A JSON object with project_id and node_ids (list of node IDs).
    Example:
        {
            "project_id": "uuid-of-project",
            "node_ids": ["uuid-of-node-1", "uuid-of-node-2"]
        }

    **Output**:
    A dictionary with all nodes' details:
    {
        "project_id": "...",
        "total_nodes": 2,
        "successful": 2,
        "failed": 0,
        "nodes": [
            {"node_id": "...", "name": "...", "status": "stopped"},
            {"node_id": "...", "name": "...", "status": "stopped"}
        ]
    }
    """

    name: str = "stop_gns3_node"
    description: str = """
    Stops one or multiple nodes in a GNS3 project.
    Input: JSON with project_id and node_ids (list of node IDs).
    Returns: A dict with all nodes' details (success/failure status).
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
            node_ids = input_data.get("node_ids")

            # Validate input
            if not project_id or not node_ids:
                logger.error(
                    "Missing required fields: project_id or node_ids."
                )
                return {
                    "error": "Missing required fields: "
                    "project_id and node_ids."
                }

            if not isinstance(node_ids, list):
                logger.error("node_ids must be a list.")
                return {"error": "node_ids must be a list."}

            # Build handler context (JWT + server URL from request context)
            logger.info("Connecting to GNS3 server...")
            gns3_ctx = build_gns3_ctx()

            if gns3_ctx is None:
                logger.error("Failed to create GNS3 connector")
                return {
                    "error": "Failed to connect to GNS3 server. "
                    "Please check your configuration."
                }

            # Verify nodes exist and capture names (one call)
            listing = get_nodes_handler({"project_id": project_id}, gns3_ctx)
            if "error" in listing:
                return {"error": listing["error"]}
            nodes_by_id = {n["node_id"]: n for n in listing["nodes"]}

            # Stop all nodes (parallel batch) and collect results
            logger.info(
                "Stopping %d nodes in project %s...",
                len(node_ids),
                project_id,
            )
            results = []
            known_ids = [nid for nid in node_ids if nid in nodes_by_id]
            stop_results = stop_node_handler(
                {"project_id": project_id, "node_ids": known_ids}, gns3_ctx
            )
            stop_errors = {
                r["node_id"]: r.get("error")
                for r in stop_results
                if r.get("status") == "error"
            }

            # Get updated status — one call
            listing = get_nodes_handler({"project_id": project_id}, gns3_ctx)
            if "error" in listing:
                return {"error": listing["error"]}
            after_by_id = {n["node_id"]: n for n in listing["nodes"]}

            for node_id in node_ids:
                if node_id not in nodes_by_id:
                    logger.error(
                        "Node %s not found in project %s", node_id, project_id
                    )
                    results.append(
                        {
                            "node_id": node_id,
                            "name": "N/A",
                            "status": "error",
                            "error": "Node not found",
                        }
                    )
                elif node_id in stop_errors:
                    logger.error(
                        "Failed to stop node %s: %s", node_id, stop_errors[node_id]
                    )
                    results.append(
                        {
                            "node_id": node_id,
                            "name": nodes_by_id[node_id].get("name") or "N/A",
                            "status": "error",
                            "error": stop_errors[node_id],
                        }
                    )
                else:
                    logger.info(
                        "Stop command sent for node %s (%s)",
                        node_id,
                        nodes_by_id[node_id].get("name"),
                    )
                    current = after_by_id.get(node_id, nodes_by_id[node_id])
                    results.append(
                        {
                            "node_id": node_id,
                            "name": current.get("name") or "N/A",
                            "status": current.get("status") or "unknown",
                        }
                    )

            # Analyze results
            successful_nodes = [
                r for r in results if r.get("status") != "error"
            ]
            failed_nodes = [r for r in results if r.get("status") == "error"]

            # Construct final response
            response = {
                "project_id": project_id,
                "total_nodes": len(node_ids),
                "successful": len(successful_nodes),
                "failed": len(failed_nodes),
                "nodes": results,
            }

            logger.info(
                "Stop operation completed: %d successful, %d failed",
                len(successful_nodes),
                len(failed_nodes),
            )

            return response

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            logger.error("Failed to stop nodes: %s", e)
            return {"error": f"Failed to stop nodes: {str(e)}"}


if __name__ == "__main__":
    # Test with single node
    print("=== Testing single node stop ===")
    test_input_single = json.dumps(
        {
            "project_id": "<PROJECT_UUID>",  # Replace with actual project UUID
            "node_ids": [
                "fbeda109-9a74-4d8c-a749-cc3847911a90"
            ],  # Replace with actual node UUID
        }
    )
    tool = GNS3StopNodeTool()
    result_single = tool._run(test_input_single)
    pprint(result_single)

    # Test with multiple nodes
    print("\n=== Testing multiple nodes stop ===")
    test_input_multiple = json.dumps(
        {
            "project_id": "<PROJECT_UUID>",  # Replace with actual project UUID
            "node_ids": [
                "fbeda109-9a74-4d8c-a749-cc3847911a90",
                # Replace with actual node UUIDs
                "another-node-uuid-here",
                "third-node-uuid-here",
            ],
        }
    )
    result_multiple = tool._run(test_input_multiple)
    pprint(result_multiple)
