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
GNS3 Template Tool

Provides tool for listing GNS3 node templates.
"""

import json
import logging
from typing import Any, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from langchain.tools import BaseTool
from pydantic import Field

from gns3server.controller import Controller

log = logging.getLogger(__name__)


class GNS3TemplateTool(BaseTool):
    controller: Controller = Field(description="GNS3 controller instance")

    def __init__(self, controller: Controller, **kwargs):
        kwargs["controller"] = controller
        super().__init__(**kwargs)

    """
    A LangChain tool to list available GNS3 node templates.

    **Input:**
    An optional JSON object to filter templates by type.

    Example input:
        {
            "template_type": "vpcs"
        }

    Or empty object for all templates:
        {}

    **Output:**
    A dictionary containing available templates.
    Example output:
        {
            "templates": [
                {
                    "template_id": "uuid",
                    "name": "VPCS",
                    "template_type": "vpcs",
                    "category": "guest",
                    "symbol": "vpcs.svg",
                    "default_name_format": "PC{0}"
                },
                ...
            ]
        }
    """

    name: str = "list_gns3_templates"
    description: str = """
    Lists available GNS3 node templates.
    Input is an optional JSON object with template_type to filter by type.
    Example input: {} or {"template_type": "vpcs"}
    Returns a list of available templates with their IDs, names, and types.
    Use this tool to find template_id before creating nodes.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict:
        """
        List GNS3 templates.

        Args:
            tool_input: JSON string with optional filter parameters
            run_manager: LangChain run manager

        Returns:
            dict: Templates list or error dict
        """
        try:
            # Parse input (may be empty object)
            try:
                input_data = json.loads(tool_input)
            except (json.JSONDecodeError, TypeError):
                input_data = {}

            template_type = input_data.get("template_type")

            # Get templates
            templates = self.controller.template.templates

            result = {"templates": []}

            for template_id, template in templates.items():
                # Filter by type if specified
                if template_type and template.template_type != template_type:
                    continue

                template_info = {
                    "template_id": template_id,
                    "name": template.name,
                    "template_type": template.template_type,
                    "category": template.category,
                    "symbol": template.symbol,
                    "default_name_format": template.default_name_format,
                    "compute_id": template.compute_id,
                }

                result["templates"].append(template_info)

            log.info("Retrieved %s templates", len(result['templates']))
            return result

        except Exception as e:
            log.error("Error in template tool: %s", e)
            return {"error": "Failed to retrieve templates: %s" % str(e)}
