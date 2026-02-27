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
"""

from typing import Any, Optional
from langchain_core.callbacks import CallbackManagerForToolRun

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class GNS3TopologyTool(GNS3ToolBase):
    """
    A LangChain tool to read GNS3 project topology information.

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
            "project_name": "My Project",
            "nodes": [
                {
                    "node_id": "uuid",
                    "name": "R1",
                    "node_type": "vpcs",
                    "status": "started",
                    "console_port": 5000
                }
            ],
            "links": [
                {
                    "link_id": "uuid",
                    "node_a": "R1",
                    "node_b": "R2",
                    "port_a": "Ethernet0",
                    "port_b": "Ethernet0"
                }
            ]
        }
    """

    name: str = "get_gns3_topology"
    description: str = """
    Reads and analyzes GNS3 project topology information.
    Input is a JSON object with project_id.
    Example input: {"project_id": "uuid-of-project"}
    Returns detailed information about all nodes and links in the project.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Read GNS3 project topology.

        :param tool_input: JSON string with project_id
        :param run_manager: Callback manager
        :return: JSON string with topology information
        """
        try:
            # Parse input
            input_data = self._parse_json_input(tool_input)
            project_id = input_data.get("project_id")

            if not project_id:
                return self._format_error_response("Missing project_id")

            # Get project
            project = self._get_project(project_id)

            # Build topology information
            topology = {
                "project_id": project.id,
                "project_name": project.name,
                "nodes": [],
                "links": [],
                "drawings": [],
                "statistics": {
                    "total_nodes": len(project.nodes),
                    "total_links": len(project.links),
                    "total_drawings": len(project.drawings),
                },
            }

            # Add node information
            for node in project.nodes:
                node_info = {
                    "node_id": node.id,
                    "name": node.name,
                    "node_type": node.node_type,
                    "status": node.status,
                    "console_type": node.console_type,
                    "console": node.console,
                    "console_port": node.console_port,
                    "properties": node.properties,
                }
                topology["nodes"].append(node_info)

            # Add link information
            for link in project.links:
                link_info = {
                    "link_id": link.id,
                    "node_a": {
                        "node_id": link.node_a.id,
                        "name": link.node_a.name,
                        "port": link.port_a,
                        "adapter": link.adapter_a,
                    },
                    "node_b": {
                        "node_id": link.node_b.id,
                        "name": link.node_b.name,
                        "port": link.port_b,
                        "adapter": link.adapter_b,
                    },
                    "capturing": link.capturing,
                    "capture_file_name": link.capture_file_name,
                }
                topology["links"].append(link_info)

            # Add drawing information
            for drawing in project.drawings:
                drawing_info = {
                    "drawing_id": drawing.id,
                    "type": drawing.drawing_type,
                    "x": drawing.x,
                    "y": drawing.y,
                    "z": drawing.z,
                    "rotation": drawing.rotation,
                    "svg": drawing.svg,
                }
                topology["drawings"].append(drawing_info)

            log.info(f"Retrieved topology for project {project_id}: "
                     f"{len(topology['nodes'])} nodes, {len(topology['links'])} links")

            return self._format_success_response(topology)

        except ValueError as e:
            log.error(f"Error in topology tool: {e}")
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in topology tool: {e}")
            return self._format_error_response(f"Failed to read topology: {str(e)}")
