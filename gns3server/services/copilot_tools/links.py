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

from typing import Any, Optional
from langchain_core.callbacks import CallbackManagerForToolRun

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class GNS3LinkTool(GNS3ToolBase):
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

    **Output:**
    A dictionary containing the created link information.
    Example output:
        {
            "link_id": "uuid",
            "node_a": "R1",
            "node_b": "R2",
            "port_a": 0,
            "port_b": 0,
            "status": "active"
        }
    """

    name: str = "create_gns3_link"
    description: str = """
    Creates a link between two nodes in a GNS3 project.
    Input is a JSON object with project_id, node_a, node_b, and optional port numbers.
    Example input: {"project_id": "uuid", "node_a": "uuid1", "node_b": "uuid2", "port_a": 0, "port_b": 0}
    If port numbers are not specified, the first available port on each node will be used.
    Returns the created link information including link_id and connected nodes.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Create a GNS3 link (sync wrapper - must use async version).

        :param tool_input: JSON string with link creation parameters
        :param run_manager: Callback manager
        :return: JSON string with created link information
        """
        return self._format_error_response("This tool requires async execution. Use _arun instead.")

    async def _arun(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Create a GNS3 link (async implementation).

        :param tool_input: JSON string with link creation parameters
        :param run_manager: Callback manager
        :return: JSON string with created link information
        """
        try:
            # Parse input
            input_data = self._parse_json_input(tool_input)
            project_id = input_data.get("project_id")
            node_a_id = input_data.get("node_a")
            node_b_id = input_data.get("node_b")
            port_a = input_data.get("port_a", 0)
            port_b = input_data.get("port_b", 0)

            # Validate required fields
            if not all([project_id, node_a_id, node_b_id]):
                return self._format_error_response(
                    "Missing required fields: project_id, node_a, node_b"
                )

            # Get project
            project = self._get_project(project_id)

            # Get nodes
            node_a = project.get_node(node_a_id)
            node_b = project.get_node(node_b_id)

            if not node_a:
                return self._format_error_response(f"Node A ({node_a_id}) not found in project")
            if not node_b:
                return self._format_error_response(f"Node B ({node_b_id}) not found in project")

            # Create link
            log.info(f"Creating link between {node_a.name} and {node_b.name}")

            link_data = {
                "nodes": [
                    {"node_id": node_a_id, "adapter_number": port_a, "port_number": 0},
                    {"node_id": node_b_id, "adapter_number": port_b, "port_number": 0},
                ]
            }

            link = await project.create_link(link_data)

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
                "active": link.active,
            }

            log.info(f"Successfully created link between {node_a.name} and {node_b.name}")
            return self._format_success_response(link_info)

        except ValueError as e:
            log.error(f"Error in create link tool: {e}")
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in create link tool: {e}")
            return self._format_error_response(f"Failed to create link: {str(e)}")
