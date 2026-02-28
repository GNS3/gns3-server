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

from typing import Any, Optional
from langchain_core.callbacks import CallbackManagerForToolRun

from .base import GNS3ToolBase

import logging

log = logging.getLogger(__name__)


class GNS3TemplateTool(GNS3ToolBase):
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
        **kwargs: Any,
    ) -> str:
        """
        List GNS3 templates.

        :param tool_input: JSON string with optional filter parameters
        :param run_manager: Callback manager
        :return: JSON string with templates list
        """
        try:
            # Parse input (may be empty object)
            try:
                input_data = self._parse_json_input(tool_input)
            except:
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

            info("Retrieved %s templates", len(result['templates'])))
            return self._format_success_response(result)

        except Exception as e:
            error("Error in template tool: %s", e))
            return self._format_error_response(f"Failed to retrieve templates: {str(e)}")
