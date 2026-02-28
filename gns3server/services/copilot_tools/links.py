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
GNS3 Link Tool

Provides tool for creating links between GNS3 nodes.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain.tools import BaseTool
from pydantic import Field

from gns3server.controller import Controller

log = logging.getLogger(__name__)


class GNS3LinkTool(BaseTool):
    controller: Controller = Field(description="GNS3 controller instance")

    def __init__(self, controller: Controller, **kwargs):
        kwargs["controller"] = controller
        super().__init__(**kwargs)

    """
    A LangChain tool to create links between GNS3 nodes.

    **Input:**
    A JSON object containing the project_id and two node endpoints.

    Example input:
        {
            "project_id": "uuid-of-project",
            "node_a": "uuid-of-node-a",
            "node_b": "uuid-of-node-b",
            "port_a": 0,
            "port_b": 0
        }
    """

    name: str = "create_gns3_link"
    description: str = """
    Creates a link between two nodes in a GNS3 project.

    Input: A JSON string with:
    - `project_id` (str): The UUID of the GNS3 project.
    - `node_a` (str): UUID of the first node (IMPORTANT: Use node_id from topology, NOT the node name).
    - `node_b` (str): UUID of the second node (IMPORTANT: Use node_id from topology, NOT the node name).
    - `port_a` (int, optional): Adapter/port number for node_a (default: 0).
    - `port_b` (int, optional): Adapter/port number for node_b (default: 0).

    Note: Node IDs must be UUIDs from get_gns3_topology tool, not node names.

    Example Input:
    {
        "project_id": "uuid-of-project",
        "node_a": "uuid-of-node1",
        "node_b": "uuid-of-node2",
        "port_a": 0,
        "port_b": 0
    }

    Output: Created link information with link_id, node names, and port numbers.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict:
        """
        Create a GNS3 link.

        Args:
            tool_input: JSON string with project_id, node_a, node_b, port_a, port_b
            run_manager: LangChain run manager

        Returns:
            dict: Created link info or error dict
        """
        log.info("create_gns3_link called with input: %s...", tool_input[:200])
        try:
            # Parse input JSON
            input_data = json.loads(tool_input)
            project_id = input_data.get("project_id")
            node_a_id = input_data.get("node_a")
            node_b_id = input_data.get("node_b")
            port_a = input_data.get("port_a", 0)
            port_b = input_data.get("port_b", 0)

            # Validate required fields
            if not all([project_id, node_a_id, node_b_id]):
                return {"error": "Missing required fields: project_id, node_a, node_b"}

            # Get project
            project = self.controller.get_project(project_id)

            # Get nodes
            node_a = project.get_node(node_a_id)
            node_b = project.get_node(node_b_id)

            if not node_a:
                return {"error": f"Node A ({node_a_id}) not found in project"}
            if not node_b:
                return {"error": f"Node B ({node_b_id}) not found in project"}

            # Create link using the correct API
            log.info("Creating link between %s and %s", node_a.name, node_b.name)

            # Step 1: Create an empty link
            link = asyncio.run(project.add_link())

            # Step 2: Add nodes to the link
            asyncio.run(link.add_node(node_a, port_a, 0))
            asyncio.run(link.add_node(node_b, port_b, 0))

            # Step 3: Create the link on the nodes
            asyncio.run(link.create())

            link_info = {
                "link_id": link.id,
                "node_a": {
                    "node_id": node_a.id,
                    "name": node_a.name,
                    "port": port_a,
                },
                "node_b": {
                    "node_id": node_b.id,
                    "name": node_b.name,
                    "port": port_b,
                },
                "active": link.created,
            }

            log.info("Successfully created link between %s and %s", node_a.name, node_b.name)
            return link_info

        except json.JSONDecodeError as e:
            log.error("Invalid JSON input: %s", e)
            return {"error": "Invalid JSON input: %s" % str(e)}
        except Exception as e:
            log.error("Error in create link tool: %s", e, exc_info=True)
            return {"error": "Failed to create link: %s" % str(e)}
