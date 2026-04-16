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
# Copyright (C) 2025 Yue Guobin
# Author: Yue Guobin
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Skill Registry and DeviceSkillsTool

This module provides:
- SKILLS_REGISTRY: A dictionary mapping device_type to skill definitions
- get_skill(): Function to retrieve skill for a device_type
- DeviceSkillsTool: LangChain tool for LLM to query skills
"""

import json
import logging
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

logger = logging.getLogger(__name__)

# Import all skill modules to register them
from gns3server.agent.gns3_copilot.skills.vpcs import VPCS_SKILL
from gns3server.agent.gns3_copilot.skills.topology import TOPOLOGY_PLANNER_SKILL

# Global skill registry - maps device_type to skill definition
SKILLS_REGISTRY: dict[str, dict[str, Any]] = {
    "gns3_vpcs_telnet": VPCS_SKILL,
    "topology_planner": TOPOLOGY_PLANNER_SKILL,
    # Add more skills here as they are implemented
    # "huawei_telnet": HUAWEI_SKILL,
    # "ruijie_telnet": RUIJIE_SKILL,
    # Protocol/Feature skills:
    # "ospf": OSPF_SKILL,
    # "bgp": BGP_SKILL,
    # "mpls": MPLS_SKILL,
}


def get_skill(
    device_type: str,
    category: str | None = None,
    operation: str = "all"
) -> dict[str, Any]:
    """
    Get skill by device_type, optionally filtered by category.

    Args:
        device_type: The device type identifier (e.g., "gns3_vpcs_telnet", "huawei_telnet")
        category: Optional category filter - "device", "protocol", "feature"
        operation: Filter by operation type - "config", "diagnosis", or "all" (default)

    Returns:
        Skill dictionary containing commands, notes, and troubleshooting info,
        or error dict if device_type not found
    """
    skill = SKILLS_REGISTRY.get(device_type, {})

    if not skill:
        # Try to find by name if not found by device_type
        for did, s in SKILLS_REGISTRY.items():
            if s.get("name", "").lower() == device_type.lower():
                skill = s
                break

    if not skill:
        return {
            "error": f"Unknown device_type: {device_type}",
            "available_device_types": list(SKILLS_REGISTRY.keys()),
        }

    # Filter by category if specified
    if category:
        skill_category = skill.get("category", "")
        if category.lower() != skill_category.lower():
            return {
                "error": f"device_type '{device_type}' is not in category '{category}'",
                "device_category": skill.get("category"),
                "available_in_category": [
                    did for did, s in SKILLS_REGISTRY.items()
                    if s.get("category", "").lower() == category.lower()
                ],
            }

    if operation == "config":
        return {
            "device_type": device_type,
            "name": skill.get("name"),
            "category": skill.get("category"),
            "description": skill.get("description"),
            "config_commands": skill.get("config_commands", {}),
        }
    elif operation == "diagnosis":
        return {
            "device_type": device_type,
            "name": skill.get("name"),
            "category": skill.get("category"),
            "display_commands": skill.get("display_commands", {}),
            "troubleshooting": skill.get("troubleshooting", {}),
        }
    else:
        # Return full skill
        result = dict(skill)
        result["device_type"] = device_type
        return result


def list_available_skills(category: str | None = None) -> list[dict[str, str]]:
    """
    List all available skills, optionally filtered by category.

    Args:
        category: Optional category filter - "device", "protocol", "feature"

    Returns:
        List of dicts with device_type, name, and category
    """
    skills = []
    for did, skill in SKILLS_REGISTRY.items():
        if category:
            if skill.get("category", "").lower() == category.lower():
                skills.append({
                    "device_type": did,
                    "name": skill.get("name", did),
                    "category": skill.get("category"),
                })
        else:
            skills.append({
                "device_type": did,
                "name": skill.get("name", did),
                "category": skill.get("category"),
            })
    return skills


class DeviceSkillsTool(BaseTool):
    """
    LangChain tool for querying device-specific skills.

    Use this tool to get device-specific command syntax, examples,
    and troubleshooting guidance before executing commands.

    Example:
        # Get VPCS skill by device_type
        tool.run('{"device_type": "gns3_vpcs_telnet"}')

        # Get OSPF protocol skill
        tool.run('{"device_type": "ospf", "category": "protocol"}')

        # Get only config commands
        tool.run('{"device_type": "gns3_vpcs_telnet", "operation": "config"}')

        # Get only diagnosis commands
        tool.run('{"device_type": "gns3_vpcs_telnet", "operation": "diagnosis"}')

        # List all available skills
        tool.run('{"action": "list"}')

        # List skills by category
        tool.run('{"action": "list", "category": "device"}')
    """

    name: str = "device_skills"
    description: str = """
    Get or list device/ protocol/ feature specific skills and command knowledge.

    Use this tool BEFORE executing device commands to understand:
    - Command syntax for the specific device type
    - Configuration command examples
    - Display/diagnostic command syntax
    - Troubleshooting guidance

    INPUT FORMAT (JSON string):
    {
        "action": "get",  # Optional: "get" (default) or "list"
        "device_type": "gns3_vpcs_telnet",  # Required for action="get": device type identifier
        "category": "device",  # Optional: "device", "protocol", "feature"
        "operation": "all"  # Optional: "config", "diagnosis", or "all" (default)
    }

    For action="list":
    {
        "action": "list",
        "category": "device"  # Optional: filter by category
    }

    OUTPUT:
    - Skill name and description
    - Command syntax with parameters
    - Usage examples
    - Troubleshooting tips
    - Important notes

    Available categories:
    - "device": Device-specific skills (VPCS, routers, switches)
    - "protocol": Network protocol skills (OSPF, BGP, MPLS)
    - "feature": Feature skills (ACL, QoS, NAT)
    """

    def _run(
        self,
        tool_input: str | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Execute the device skills lookup.

        Args:
            tool_input: JSON string or dict with device_type and optional operation/category

        Returns:
            JSON string with skill information or skill list
        """
        logger.info("DeviceSkillsTool invoked with input: %s", tool_input)

        # Parse input
        if isinstance(tool_input, str):
            try:
                params = json.loads(tool_input)
            except json.JSONDecodeError as e:
                return json.dumps({
                    "error": f"Invalid JSON input: {e}",
                    "hint": 'Expected format: {"device_type": "xxx"} or {"action": "list"}'
                }, ensure_ascii=False, indent=2)
        else:
            params = tool_input

        action = params.get("action", "get")

        if action == "list":
            category = params.get("category")
            skills = list_available_skills(category)
            return json.dumps({
                "category": category or "all",
                "skills": skills
            }, ensure_ascii=False, indent=2)

        # Default action: "get"
        device_type = params.get("device_type")
        if not device_type:
            return json.dumps({
                "error": "Missing required field: device_type",
                "available_device_types": list(SKILLS_REGISTRY.keys()),
                "hint": 'Use {"action": "list"} to see all available device types'
            }, ensure_ascii=False, indent=2)

        category = params.get("category")
        operation = params.get("operation", "all")

        # Get skill
        skill = get_skill(device_type, category, operation)

        return json.dumps(skill, ensure_ascii=False, indent=2)
