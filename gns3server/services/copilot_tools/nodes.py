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
GNS3 Node Tools

Provides tools for creating and managing GNS3 nodes.
"""

from typing import Any, Optional
from langchain_core.callbacks import CallbackManagerForToolRun

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class GNS3CreateNodeTool(GNS3ToolBase):
    """
    A LangChain tool to create nodes in a GNS3 project.

    **Input:**
    A JSON object containing the project_id, template_id, and optional parameters.

    Example input:
        {
            "project_id": "uuid-of-project",
            "template_id": "uuid-of-template",
            "x": 100,
            "y": -200,
            "name": "R1"
        }

    **Output:**
    A dictionary containing the created node information.
    Example output:
        {
            "node_id": "uuid",
            "name": "R1",
            "node_type": "vpcs",
            "status": "stopped",
            "x": 100,
            "y": -200
        }
    """

    name: str = "create_gns3_node"
    description: str = """
    Creates a new node in a GNS3 project using a template.
    Input is a JSON object with project_id, template_id, x, y coordinates.
    Optional: name (auto-generated if not provided).
    Example input: {"project_id": "uuid", "template_id": "uuid", "x": 100, "y": -200, "name": "R1"}
    IMPORTANT: Ensure the distance between any two nodes is greater than 250 pixels for better visualization.
    Returns the created node information including node_id, name, and status.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Create a GNS3 node.

        :param tool_input: JSON string with node creation parameters
        :param run_manager: Callback manager
        :return: JSON string with created node information
        """
        log.info(f"create_gns3_node called with input: {tool_input[:200]}...")
        try:
            # Parse input
            input_data = self._parse_json_input(tool_input)
            project_id = input_data.get("project_id")
            template_id = input_data.get("template_id")
            x = input_data.get("x")
            y = input_data.get("y")
            name = input_data.get("name")

            log.debug(f"Parsed parameters: project_id={project_id}, template_id={template_id}, x={x}, y={y}, name={name}")

            # Validate required fields
            if not all([project_id, template_id, x is not None, y is not None]):
                log.error("Missing required fields")
                return self._format_error_response(
                    "Missing required fields: project_id, template_id, x, y"
                )

            # Get project
            log.debug(f"Getting project {project_id}")
            project = self._get_project(project_id)

            # Get template
            log.debug(f"Getting template {template_id}")
            template = self.controller.template.get_template(template_id)
            if not template:
                log.error(f"Template {template_id} not found")
                return self._format_error_response(f"Template {template_id} not found")

            log.debug(f"Template found: {template.name}, type: {template.template_type}")

            # Get compute for template
            compute_id = template.compute_id
            compute = self.controller.get_compute(compute_id)
            if not compute:
                log.error(f"Compute {compute_id} not found")
                return self._format_error_response(f"Compute {compute_id} not found")

            log.debug(f"Compute found: {compute_id}")

            # Prepare node data
            node_data = {
                "name": name,
                "node_type": template.template_type,
                "template_id": template_id,
                "x": x,
                "y": y,
                "properties": {},
            }

            # Create node
            log.info(f"Creating node in project {project_id} at ({x}, {y})")
            node = await project.add_node(compute, name=name, node_id=None, **node_data)

            node_info = {
                "node_id": node.id,
                "name": node.name,
                "node_type": node.node_type,
                "status": node.status,
                "x": node.x,
                "y": node.y,
                "console_type": node.console_type,
                "console_port": node.console_port,
            }

            log.info(f"Successfully created node {node.name} ({node.id})")
            return self._format_success_response(node_info)

        except ValueError as e:
            log.error(f"Error in create node tool: {e}", exc_info=True)
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in create node tool: {e}", exc_info=True)
            return self._format_error_response(f"Failed to create node: {str(e)}")


class GNS3StartNodeTool(GNS3ToolBase):
    """
    A LangChain tool to start a GNS3 node.

    **Input:**
    A JSON object containing the project_id and node_id.

    Example input:
        {
            "project_id": "uuid-of-project",
            "node_id": "uuid-of-node"
        }

    **Output:**
    A dictionary containing the result of the start operation.
    Example output:
        {
            "node_id": "uuid",
            "name": "R1",
            "status": "started"
        }
    """

    name: str = "start_gns3_node"
    description: str = """
    Starts a GNS3 node.
    Input is a JSON object with project_id and node_id.
    Example input: {"project_id": "uuid", "node_id": "uuid"}
    Returns the node status after starting.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Start a GNS3 node.

        :param tool_input: JSON string with project_id and node_id
        :param run_manager: Callback manager
        :return: JSON string with node status
        """
        log.info(f"start_gns3_node called with input: {tool_input[:200]}...")
        try:
            # Parse input
            input_data = self._parse_json_input(tool_input)
            project_id = input_data.get("project_id")
            node_id = input_data.get("node_id")

            log.debug(f"Parsed parameters: project_id={project_id}, node_id={node_id}")

            # Validate required fields
            if not all([project_id, node_id]):
                log.error("Missing required fields")
                return self._format_error_response("Missing required fields: project_id, node_id")

            # Get project
            log.debug(f"Getting project {project_id}")
            project = self._get_project(project_id)

            # Get node
            log.debug(f"Getting node {node_id}")
            node = project.get_node(node_id)
            if not node:
                log.error(f"Node {node_id} not found in project")
                return self._format_error_response(f"Node {node_id} not found in project")

            log.debug(f"Node found: {node.name}, current status: {node.status}")

            # Start node
            log.info(f"Starting node {node.name} ({node_id})")
            await node.start()

            node_info = {
                "node_id": node.id,
                "name": node.name,
                "status": node.status,
            }

            log.info(f"Successfully started node {node.name}, new status: {node.status}")
            return self._format_success_response(node_info)

        except ValueError as e:
            log.error(f"Error in start node tool: {e}", exc_info=True)
            return self._format_error_response(str(e))
        except Exception as e:
            log.error(f"Unexpected error in start node tool: {e}", exc_info=True)
            return self._format_error_response(f"Failed to start node: {str(e)}")
