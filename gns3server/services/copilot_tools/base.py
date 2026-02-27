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
Base class for GNS3 Copilot tools.

Provides a common interface for tools that need to interact with GNS3 controller.
"""

import json
from typing import Any, Optional
from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field

from gns3server.controller import Controller
import logging

log = logging.getLogger(__name__)


class GNS3ToolBase(BaseTool):
    """
    Base class for GNS3 Copilot tools.

    Provides access to the GNS3 controller and common utility methods.
    """

    controller: Controller = Field(description="GNS3 controller instance")

    def __init__(self, controller: Controller, **kwargs):
        """
        Initialize the tool with a GNS3 controller.

        :param controller: GNS3 controller instance
        """
        kwargs["controller"] = controller
        super().__init__(**kwargs)
        log.debug(f"Initialized tool: {self.name}")

    def _get_project(self, project_id: str):
        """
        Get a project by ID.

        :param project_id: Project ID
        :return: Project instance
        :raises: ValueError if project not found
        """
        log.debug(f"Getting project: {project_id}")
        # Import here to avoid circular dependencies
        from gns3server.controller.project import Project
        import asyncio

        try:
            # Get the project from controller
            project = self.controller.get_project(project_id)
            if project is None:
                log.error(f"Project {project_id} not found")
                raise ValueError(f"Project {project_id} not found")
            log.debug(f"Found project: {project.name} ({project.id})")
            return project
        except Exception as e:
            log.error(f"Error getting project {project_id}: {e}", exc_info=True)
            raise

    def _parse_json_input(self, tool_input: str) -> dict:
        """
        Parse JSON input string.

        :param tool_input: JSON string
        :return: Parsed dictionary
        :raises: ValueError if JSON is invalid
        """
        log.debug(f"Parsing JSON input: {tool_input[:100]}...")
        try:
            data = json.loads(tool_input)
            log.debug(f"Parsed JSON successfully, keys: {list(data.keys())}")
            return data
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON input: {e}")
            raise ValueError(f"Invalid JSON input: {e}")

    def _format_success_response(self, data: dict) -> str:
        """
        Format a successful response as JSON string.

        :param data: Response data
        :return: JSON string
        """
        response = json.dumps(data, indent=2, ensure_ascii=False)
        log.debug(f"Formatted success response: {response[:100]}...")
        return response

    def _format_error_response(self, message: str) -> str:
        """
        Format an error response.

        :param message: Error message
        :return: JSON string with error
        """
        log.error(f"Formatting error response: {message}")
        return json.dumps({"error": message}, ensure_ascii=False)

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Run the tool (synchronous).

        This method should be overridden by subclasses.

        :param tool_input: Tool input (JSON string)
        :param run_manager: Callback manager
        :return: Tool output (JSON string)
        """
        log.info(f"Running tool: {self.name}")
        raise NotImplementedError("Subclasses must implement _run method")

    async def _arun(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Run the tool (asynchronous).

        Default implementation calls _run synchronously.
        Subclasses can override for true async behavior.

        :param tool_input: Tool input (JSON string)
        :param run_manager: Callback manager
        :return: Tool output (JSON string)
        """
        log.debug(f"Running tool async: {self.name}")
        return self._run(tool_input, run_manager, **kwargs)
