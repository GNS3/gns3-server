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
GNS3 Topology Tool

Reads and analyzes GNS3 project topology information.
Reference implementation from gns3-copilot's links_summary method.
"""

import logging
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from .base import GNS3ToolBase

log = logging.getLogger(__name__)


class GetGNS3TopologyInput(BaseModel):
    """Input schema for get_gns3_topology tool."""

    project_id: str = Field(description="GNS3 project UUID")


class GNS3TopologyTool(GNS3ToolBase):
    """
    A LangChain tool to read GNS3 project topology information.

    Reference: gns3-copilot's links_summary and GNS3TopologyTool implementations.

    **Input:**
    A JSON object containing the project_id.

    Example input:
        {
            "project_id": "uuid-of-project"
        }

    **Output:**
    A dictionary containing project topology information including nodes and links.
    Example output:
        {
            "project_id": "uuid",
            "name": "My Project",
            "status": "opened",
            "nodes_count": 2,
            "links_count": 1,
            "nodes": {
                "node-id-1": {
                    "name": "R1",
                    "node_id": "node-id-1",
                    "node_type": "vpcs",
                    "status": "started",
                    "ports": [{"name": "Ethernet0", "short_name": "e0"}]
                }
            },
            "links": [
                {
                    "node_a": "R1",
                    "port_a": "e0",
                    "node_b": "R2",
                    "port_b": "e0",
                    "link_id": "link-uuid"
                }
            ]
        }
    """

    name: str = "get_gns3_topology"
    description: str = """
    Retrieves the topology of a GNS3 project including nodes and links.

    Input: `project_id` (str, required): UUID of the GNS3 project.

    Output: Dictionary with:
    - `project_id`, `name`, `status`: Project metadata
    - `nodes`: Dict of node details (node_id, name, ports, type, etc.)
    - `links`: List of link connections

    Use this to understand network structure before making changes.
    """
    args_schema: type[BaseModel] = GetGNS3TopologyInput

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> dict:
        """
        Read GNS3 project topology (sync wrapper).

        Following FlowNet-Lab's approach: returns dict directly.

        :param tool_input: JSON string with project_id (or dict with project_id)
        :param run_manager: Callback manager
        :return: Dict with topology information (or dict with error key)
        """
        import asyncio

        log.info("get_gns3_topology called (sync) with input: %s...", tool_input[:100])
        try:
            # Parse input - handle both string and dict
            if isinstance(tool_input, dict):
                input_data = tool_input
            else:
                input_data = self._parse_json_input(tool_input)

            project_id = input_data.get("project_id")

            if not project_id:
                return {"error": "Missing project_id"}

            # Get project (sync - this may block)
            try:
                project = self.controller.get_project(project_id)
            except Exception as e:
                return {"error": f"Project {project_id} not found: {e}"}

            # Build topology using sync helper
            topology = asyncio.run(self._build_topology(project))

            log.info("Retrieved topology for project %s: %d nodes, %d links",
                     project_id, topology['nodes_count'], topology['links_count'])

            return topology

        except ValueError as e:
            log.error("Error in topology tool: %s", e, exc_info=True)
            return {"error": str(e)}
        except Exception as e:
            log.error("Unexpected error in topology tool: %s", e, exc_info=True)
            return {"error": "Failed to read topology: %s" % str(e)}

    async def _arun(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Read GNS3 project topology (async implementation).

        :param tool_input: JSON string with project_id
        :param run_manager: Callback manager
        :return: JSON string with topology information
        """
        log.info("get_gns3_topology called with input: %s...", tool_input[:100])
        try:
            # Parse input
            input_data = self._parse_json_input(tool_input)
            project_id = input_data.get("project_id")

            if not project_id:
                return self._format_error_response("Missing project_id")

            # Get project (async)
            project = await self.controller.get_loaded_project(project_id)
            if not project:
                return self._format_error_response("Project %s not found" % project_id)

            # Build topology using helper methods
            topology = await self._build_topology(project)

            log.info("Retrieved topology for project %s: %d nodes, %d links",
                     project_id, topology['nodes_count'], topology['links_count'])

            return self._format_success_response(topology)

        except ValueError as e:
            log.error("Error in topology tool: %s", e, exc_info=True)
            return self._format_error_response(str(e))
        except Exception as e:
            log.error("Unexpected error in topology tool: %s", e, exc_info=True)
            return self._format_error_response("Failed to read topology: %s" % str(e))

    async def _build_topology(self, project) -> dict:
        """
        Build structured topology data from project.

        Reference: gns3-copilot's links_summary and nodes_inventory methods.

        :param project: GNS3 project instance
        :return: Topology data dictionary
        """
        # Build nodes inventory
        nodes_data = {}
        for node_id, node in project.nodes.items():
            node_info = {
                "name": node.name,
                "node_id": node.id,
                "node_type": node.node_type,
                "status": node.status,
                "x": node.x if hasattr(node, 'x') else 0,
                "y": node.y if hasattr(node, 'y') else 0,
            }

            # Add ports if available
            if hasattr(node, "ports") and node.ports:
                node_info["ports"] = await self._get_ports_data(node)
            else:
                node_info["ports"] = []

            nodes_data[node_id] = node_info

        # Build links summary
        links_data = await self._get_links_data(project)

        # Return structured topology
        return {
            "project_id": project.id,
            "name": project.name,
            "status": project.status if hasattr(project, 'status') else "opened",
            "nodes_count": len(nodes_data),
            "links_count": len(links_data),
            "nodes": nodes_data,
            "links": links_data
        }

    async def _get_ports_data(self, node) -> list:
        """
        Extract port information from a node.

        :param node: GNS3 node instance
        :return: List of port data dictionaries
        """
        ports_data = []
        for port in node.ports:
            try:
                # Try using asdict() method first
                if hasattr(port, 'asdict'):
                    port_dict = port.asdict()
                    port_name = port_dict.get("name", "unknown")
                    port_short_name = port_dict.get("short_name", "unknown")
                else:
                    # Direct attribute access with fallback
                    port_name = getattr(port, "_name", None) or getattr(port, "name", None)
                    port_short_name = getattr(port, "_short_name", None) or getattr(port, "short_name", None)
                    port_number = getattr(port, "_port_number", getattr(port, "port_number", 0))

                    if not port_name:
                        port_name = "port%s" % port_number
                    if not port_short_name:
                        port_short_name = "p%s" % port_number

                    # Convert to string
                    port_name = str(port_name)
                    port_short_name = str(port_short_name)

                ports_data.append({
                    "name": port_name,
                    "short_name": port_short_name
                })
            except Exception as e:
                log.warning("Error accessing port attributes: %s", e)
                port_number = getattr(port, "_port_number", getattr(port, "port_number", 0))
                ports_data.append({
                    "name": "port%s" % port_number,
                    "short_name": "p%s" % port_number
                })

        return ports_data

    async def _get_links_data(self, project) -> list:
        """
        Extract link information from a project.

        Reference: gns3-copilot's links_summary implementation.
        Use link._nodes (internal storage) not link.nodes (property returns Node objects only).

        :param project: GNS3 project instance
        :return: List of link data dictionaries
        """
        links_data = []

        for link in project.links.values():
            # Skip if link has no nodes
            # Use _nodes (internal storage): [{"node": obj, "adapter_number": 0, "port_number": 0}, ...]
            if not link._nodes or len(link._nodes) < 2:
                log.debug("Skipping link with insufficient nodes")
                continue

            # Get both sides of the link
            side_a = link._nodes[0]
            side_b = link._nodes[1]

            # Extract node objects
            node_a = side_a.get("node")
            node_b = side_b.get("node")

            if not node_a or not node_b:
                log.debug("Skipping link with missing nodes")
                continue

            # Get adapter and port numbers
            adapter_a = side_a.get("adapter_number", 0)
            port_a_num = side_a.get("port_number", 0)
            adapter_b = side_b.get("adapter_number", 0)
            port_b_num = side_b.get("port_number", 0)

            # Get port names
            port_a_name = self._get_port_name(node_a, adapter_a, port_a_num)
            port_b_name = self._get_port_name(node_b, adapter_b, port_b_num)

            links_data.append({
                "node_a": node_a.name,
                "port_a": port_a_name,
                "node_b": node_b.name,
                "port_b": port_b_name,
                "link_id": link.id if hasattr(link, 'id') else None
            })

        return links_data

    def _get_port_name(self, node, adapter_number: int, port_number: int) -> str:
        """
        Get port name from node by adapter and port number.

        Reference: gns3-copilot's port lookup logic.

        :param node: GNS3 node object
        :param adapter_number: Adapter number
        :param port_number: Port number
        :return: Port name or placeholder
        """
        if not hasattr(node, "ports") or not node.ports:
            return "adp%s/prt%s" % (adapter_number, port_number)

        for port in node.ports:
            # Access port object attributes directly
            port_adapter_num = getattr(port, "adapter_number", None)
            port_port_num = getattr(port, "port_number", None)

            if port_adapter_num == adapter_number and port_port_num == port_number:
                return getattr(port, "short_name", "adp%s/prt%s" % (adapter_number, port_number))

        return "adp%s/prt%s" % (adapter_number, port_number)
