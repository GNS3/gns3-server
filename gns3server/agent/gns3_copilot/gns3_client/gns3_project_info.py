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
GNS3 Project Info Tool

This module provides a LangChain BaseTool to retrieve basic information of a
specific GNS3 project by project ID. Returns project name, status, node count,
and link count.

"""

import logging
from pprint import pprint
from typing import Any

from langchain.tools import BaseTool

from gns3server.agent.gns3_copilot.gns3_client import Project
from gns3server.agent.gns3_copilot.gns3_client import get_gns3_connector

# Configure logging
logger = logging.getLogger(__name__)


class GNS3ProjectInfoTool(BaseTool):
    """LangChain tool for retrieving GNS3 project basic information."""

    name: str = "gns3_project_info"
    description: str = """
    Retrieves basic information of a GNS3 project including name, status,
    node count and link count.

    Input: `project_id` (str, required): UUID of the GNS3 project.

    Output: Dictionary with:
    - `project_id`: Project UUID
    - `name`: Project name
    - `status`: Project status (opened/closed)
    - `node_count`: Number of nodes in the project
    - `link_count`: Number of links in the project

    Returns a tuple format: (name, project_id, node_count, link_count, status)
    """

    def _run(
        self,
        tool_input: Any = None,
        run_manager: Any = None,
        project_id: str | None = None,
    ) -> dict:
        """
        Synchronous method to retrieve basic information of a specific GNS3 project.

        Args:
            tool_input : Input parameters, typically a dict or Pydantic model.
            run_manager : Callback manager for tool run.
            project_id : The UUID of the specific GNS3 project.

        Returns:
            dict: A dictionary containing project info (name, project_id, node_count,
                  link_count, status), or an error dictionary if an exception occurs
                  or project_id is not provided.
        """

        # Log received input
        logger.info(
            "Received tool_input: %s, project_id: %s", tool_input, project_id
        )

        try:
            # Validate project_id parameter
            if not project_id:
                logger.error("project_id parameter is required.")
                return {
                    "error": (
                        "project_id parameter is required. Please provide a valid "
                        "project UUID."
                    )
                }

            # Initialize Gns3Connector using factory function
            logger.debug("Connecting to GNS3 server...")
            server = get_gns3_connector()

            if server is None:
                logger.error("Failed to create GNS3 connector")
                return {
                    "error": (
                        "Failed to connect to GNS3 server. Please check your "
                        "configuration."
                    )
                }

            # Use the provided project_id directly
            logger.info(
                f"Retrieving project info for project_id: {project_id}"
            )
            project = Project(project_id=project_id, connector=server)
            project.get()  # Load project details

            # Get node and link counts
            nodes_inventory = project.nodes_inventory()
            links_summary = project.links_summary(is_print=False)

            node_count = len(nodes_inventory) if nodes_inventory else 0
            link_count = len(links_summary) if links_summary else 0

            # Build result in tuple format consistent with GNS3ProjectList
            result = {
                "project_id": project.project_id,
                "name": project.name,
                "status": project.status,
                "node_count": node_count,
                "link_count": link_count,
                "tuple": (
                    project.name,
                    project.project_id,
                    node_count,
                    link_count,
                    project.status,
                ),
            }

            # Log result
            logger.info(
                "Project info retrieved: name=%s, status=%s, nodes=%d, links=%d",
                project.name,
                project.status,
                node_count,
                link_count,
            )

            return result

        except Exception as e:
            logger.error("Error retrieving GNS3 project info: %s", str(e))
            return {"error": f"Failed to retrieve project info: {str(e)}"}


if __name__ == "__main__":
    # Test the tool
    tool = GNS3ProjectInfoTool()

    # Example usage with project_id
    # Replace with an actual project UUID from your GNS3 server
    example_project_id = "0c0fde25-6ead-4413-a283-ea8fd2324291"

    print("Testing GNS3ProjectInfoTool with project_id...")
    result = tool._run(project_id=example_project_id)
    pprint(result)

    # Test without project_id (should return error)
    print("\nTesting without project_id (should return error)...")
    error_result = tool._run()
    pprint(error_result)
