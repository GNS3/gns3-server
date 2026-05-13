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

GNS3 template retrieval tool for device discovery.

Provides functionality to retrieve all available device templates
from a GNS3 server, including template names, IDs, and types.
Filters out built-in utility templates that are not useful for network labs.
"""

import json
import logging
from pprint import pprint
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client import get_gns3_connector

# Configure logging
logger = logging.getLogger(__name__)

# Built-in templates to filter out (utility templates, not actual network devices)
FILTERED_TEMPLATES = {
    "atm_switch",          # ATM switch
    "cloud",               # Cloud
    "ethernet_hub",        # Ethernet hub
    "ethernet_switch",     # Ethernet switch (built-in)
    "frame_relay_switch",  # Frame Relay switch
    "nat",                 # NAT device
}


def should_filter_template(template: dict[str, Any]) -> bool:
    """
    Determine whether a template should be filtered out.

    Filter condition:
    1. Template type is in the filter list (exact match)

    Args:
        template: Template dictionary

    Returns:
        True if template should be filtered, False if it should be kept
    """
    template_type = template.get("template_type", "")

    # Check if template_type is in filter list
    # This is the most reliable way to identify built-in utility templates
    return template_type in FILTERED_TEMPLATES


class GNS3TemplateTool(BaseTool):
    """
    LangChain tool to retrieve available device templates from GNS3 server.
    Connects to GNS3 server and extracts name, template_id, and template_type.
    Filters out built-in utility templates that are not useful for network labs.

    **Input:**
    No input required. Connects to GNS3 server at default URL.

    **Output:**
    Dict with list of dicts (name, template_id, template_type).
    If error, returns dict with error message.

    **Filtered Templates:**
    The following built-in utility templates are excluded:
    - ATM switch
    - Cloud
    - Ethernet hub
    - Ethernet switch (built-in)
    - Frame Relay switch
    - NAT
    """

    name: str = "get_gns3_templates"
    description: str = """
    Retrieves available device templates from GNS3 server for network labs.
    Returns dict with list of dicts (name, template_id, template_type).
    Filters out built-in utility templates (ATM switch, Cloud, Ethernet hub,
    Ethernet switch, Frame Relay switch, NAT) as they are not useful for
    network device configuration.
    No input required.
    If connection fails, returns dict with error message.
    """

    def _run(
        self,
        tool_input: str = "",
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        """
        Connects to GNS3 server and retrieves available device templates.

        Args:
            tool_input: Optional input (not used).
            run_manager: LangChain run manager (unused).

        Returns:
            dict: Dict with templates list or error message.
        """
        try:
            # Initialize Gns3Connector using factory function
            logger.info("Connecting to GNS3 server...")
            gns3_server = get_gns3_connector()

            if gns3_server is None:
                logger.error("Failed to create GNS3 connector")
                return {
                    "error": (
                        "Failed to connect to GNS3 server. "
                        "Please check your configuration."
                    )
                }

            # Retrieve all available templates
            templates = gns3_server.get_templates()

            # Filter out utility templates and extract relevant info
            template_info = []
            filtered_count = 0
            for template in templates:
                # Check if template should be filtered
                if should_filter_template(template):
                    filtered_count += 1
                    logger.debug("Filtered out template: %s", template.get("name"))
                    continue

                # Extract name, template_id, and template_type
                template_info.append({
                    "name": template.get("name", "N/A"),
                    "template_id": template.get("template_id", "N/A"),
                    "template_type": template.get("template_type", "N/A"),
                })

            # Return JSON-formatted result with full logging
            result = {"templates": template_info}
            logger.info(
                "Template retrieval completed. Total: %d, Filtered: %d, Remaining: %d",
                len(templates),
                filtered_count,
                len(template_info),
            )
            logger.debug("Result: %s", json.dumps(result, indent=2, ensure_ascii=False))
            return result

        except Exception as e:
            logger.error(
                "Failed to connect to GNS3 server or retrieve templates: %s", e
            )
            return {"error": f"Failed to retrieve templates: {str(e)}"}


if __name__ == "__main__":
    # Test's tool locally
    tool = GNS3TemplateTool()
    result = tool._run("")
    pprint(result)
