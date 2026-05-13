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
Skill Registry and Tools

This module provides:
- SKILLS_REGISTRY: Device/feature skills (VPCS, topology, etc.)
- INJECTION_SKILLS_REGISTRY: Fault injection skills only
- get_skill(): Function to retrieve device/feature skills
- get_injection_skill(): Function to retrieve injection skills
- DeviceSkillsTool: LangChain tool for device/feature skills
- InjectionSkillsTool: LangChain tool for injection skills
"""

import json
import logging
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

# command_filter imports are done locally in functions
# to avoid circular import (command_filter also imports from registry)

logger = logging.getLogger(__name__)

# Device/Feature skills registry - loaded from external repository
SKILLS_REGISTRY: dict[str, dict[str, Any]] = {}

# Injection skills registry - fault injection skills only
# This registry can be hot-reloaded via SkillsManager
INJECTION_SKILLS_REGISTRY: dict[str, dict[str, Any]] = {}

# Packet analysis protocols registry - loaded from external repository
# Contains protocol definitions for tshark-based packet analysis
PACKET_ANALYSIS_REGISTRY: dict[str, dict[str, Any]] = {}

# Global skills manager instance for hot reload
_skills_manager = None
_init_in_progress = False


def set_skills_manager(manager):
    """
    Set the global skills manager instance.

    The skills manager handles Git operations and hot reload of skills.

    Args:
        manager: SkillsManager instance
    """
    global _skills_manager
    _skills_manager = manager


def _ensure_skills_manager():
    """
    Initialize the SkillsManager (idempotent, retryable on failure).

    Reads config, creates SkillsManager, clones/pulls repo,
    and loads skills/prompts into memory. Safe to call from
    background threads - uses _init_in_progress to prevent
    concurrent initialization.

    On failure, resets _init_in_progress so future calls
    (e.g., /reload/skills API) can retry. On success, the
    manager is stored in _skills_manager and subsequent
    calls return immediately.
    """
    global _skills_manager, _init_in_progress

    if _skills_manager is not None:
        return

    if _init_in_progress:
        return

    _init_in_progress = True

    try:
        from gns3server.agent.gns3_copilot.configs.skills_config import get_skills_config
        from gns3server.agent.gns3_copilot.skills.manager import SkillsManager

        config = get_skills_config()

        if not config.get("enabled", False):
            logger.info("External skills repository is disabled")
            return

        logger.info("Initializing SkillsManager")

        manager = SkillsManager(
            repo_url=config.get("repo_url"),
            branch=config.get("branch", "main"),
            auto_update=config.get("auto_update", False)
        )

        if not manager.initialize():
            logger.error("Failed to initialize skills repository")
            return

        if manager.reload_skills():
            logger.debug(f"Loaded {manager.get_skill_count()} injection skills")
        else:
            logger.warning("Failed to reload injection skills")

        if manager.reload_prompts():
            logger.debug(f"Loaded {manager.get_prompt_count()} prompts")
        else:
            logger.warning("Failed to reload prompts")

        if manager.reload_packet_analysis_protocols():
            logger.debug(f"Loaded {len(PACKET_ANALYSIS_REGISTRY)} packet analysis protocols")
        else:
            logger.warning("Failed to reload packet analysis protocols")

        _skills_manager = manager
        logger.debug("SkillsManager initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing skills manager: {e}", exc_info=True)
    finally:
        _init_in_progress = False


def get_skills_manager():
    """
    Get the global skills manager instance, initializing on first access.

    Returns:
        SkillsManager instance or None
    """
    _ensure_skills_manager()
    return _skills_manager


def reload_skills_repository() -> dict[str, Any]:
    """
    Reload the entire skills repository.

    Performs one git update check, then reloads all skills, prompts,
    and forbidden commands from local files.

    Returns:
        Dictionary with combined reload results.
    """
    manager = get_skills_manager()
    if manager is None:
        return {
            "success": False,
            "message": "Skills manager not initialized",
        }

    # One git update for the entire repository
    manager._update_if_needed()

    # Reload everything from local files
    skills_ok = manager.reload_skills()
    prompts_ok = manager.reload_prompts()
    protocols_ok = manager.reload_packet_analysis_protocols()

    # Reload forbidden commands (local import to avoid circular dependency)
    from gns3server.agent.gns3_copilot.utils.command_filter import reload_forbidden_commands as _reload_fc
    from gns3server.agent.gns3_copilot.utils.command_filter import get_forbidden_commands

    _reload_fc()
    forbidden_commands = get_forbidden_commands()

    return {
        "success": skills_ok or prompts_ok or protocols_ok,
        "skills": skills_ok,
        "skill_count": manager.get_skill_count(),
        "prompts": prompts_ok,
        "prompt_count": manager.get_prompt_count(),
        "protocols": protocols_ok,
        "protocol_count": len(PACKET_ANALYSIS_REGISTRY),
        "forbidden_commands": len(forbidden_commands),
        "version": manager.get_current_version(),
    }


def reload_injection_skills() -> dict[str, Any]:
    """
    Trigger hot reload of injection skills.

    This function uses the global skills manager to pull latest changes
    from the skills repository and reload the INJECTION_SKILLS_REGISTRY.

    Returns:
        Dictionary with status information:
        {
            "success": bool,
            "message": str,
            "skill_count": int,
            "version": str
        }
    """
    manager = get_skills_manager()
    if manager is None:
        return {
            "success": False,
            "message": "Skills manager not initialized",
            "skill_count": len(INJECTION_SKILLS_REGISTRY),
            "version": ""
        }

    try:
        success = manager.reload_skills()
        return {
            "success": success,
            "message": "Skills reloaded successfully" if success else "Failed to reload skills",
            "skill_count": manager.get_skill_count(),
            "version": manager.get_current_version()
        }
    except Exception as e:
        logger.error(f"Error during skills reload: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "skill_count": len(INJECTION_SKILLS_REGISTRY),
            "version": ""
        }


def reload_prompts() -> dict[str, Any]:
    """
    Trigger hot reload of system prompts.

    This function uses the global skills manager to pull latest changes
    from the skills repository and reload prompts from disk.

    Returns:
        Dictionary with status information:
        {
            "success": bool,
            "message": str,
            "prompt_count": int,
            "version": str
        }
    """
    manager = get_skills_manager()
    if manager is None:
        return {
            "success": False,
            "message": "Skills manager not initialized",
            "prompt_count": 0,
            "version": ""
        }

    try:
        success = manager.reload_prompts()
        return {
            "success": success,
            "message": "Prompts reloaded successfully" if success else "Failed to reload prompts",
            "prompt_count": manager.get_prompt_count(),
            "version": manager.get_current_version()
        }
    except Exception as e:
        logger.error(f"Error during prompts reload: {e}")
        manager = get_skills_manager()
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "prompt_count": manager.get_prompt_count() if manager else 0,
            "version": ""
        }


def reload_forbidden_commands() -> dict[str, Any]:
    """
    Hot reload forbidden commands from the skills repository.

    Directly loads and caches commands from the skills repository.

    Returns:
        Dictionary with status information:
        {
            "success": bool,
            "message": str,
            "command_count": int,
            "version": str
        }
    """
    try:
        from gns3server.agent.gns3_copilot.utils.command_filter import reload_forbidden_commands as _reload
        from gns3server.agent.gns3_copilot.utils.command_filter import get_forbidden_commands

        _reload()
        commands = get_forbidden_commands()
        manager = get_skills_manager()
        return {
            "success": True,
            "message": "Forbidden commands reloaded",
            "command_count": len(commands),
            "version": manager.get_current_version() if manager else ""
        }
    except Exception as e:
        logger.error(f"Error during forbidden commands reload: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "command_count": 0,
            "version": ""
        }


def get_prompt(prompt_name: str) -> str:
    """
    Get a system prompt by name, always loading from disk.

    Args:
        prompt_name: Name of the prompt (e.g., "teaching_assistant")

    Returns:
        Prompt content as string, or empty string if not found
    """
    # Always load from skills manager (no cache), triggers lazy init
    manager = get_skills_manager()
    if manager:
        try:
            prompt = manager.load_prompt(prompt_name)
            if prompt:
                return prompt
        except Exception as e:
            logger.error(f"Error loading prompt '{prompt_name}': {e}")

    logger.warning(f"Prompt not found: {prompt_name}")
    return ""


def get_skills_repository_info() -> dict[str, Any]:
    """
    Get information about the skills repository.

    Returns:
        Dictionary with repository information
    """
    manager = get_skills_manager()
    if manager is None:
        return {
            "initialized": False,
            "message": "Skills manager not initialized"
        }

    return manager.get_repository_info()


def get_skill(
    device_type: str,
    category: str | None = None,
    detail: str = "full",
    issue: str | None = None,
) -> dict[str, Any]:
    """
    Get skill by device_type, with configurable detail level.

    Args:
        device_type: The device type identifier
        category: Optional category filter
        detail: Detail level - "index" (names only), "summary" (+desc/sev/diff), "full" (all)
        issue: Optional specific issue key to retrieve

    Returns:
        Skill dictionary (detail varies by level), or error dict
    """
    skill = SKILLS_REGISTRY.get(device_type, {})

    if not skill:
        for did, s in SKILLS_REGISTRY.items():
            if s.get("name", "").lower() == device_type.lower():
                skill = s
                break

    if not skill:
        return {
            "error": f"Unknown device_type: {device_type}",
            "available_device_types": list(SKILLS_REGISTRY.keys()),
        }

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

    issues = skill.get("issues", {})

    # Single issue lookup (most token-efficient)
    if issue:
        issue_def = issues.get(issue)
        if not issue_def:
            return {
                "error": f"Unknown issue '{issue}' in {device_type}",
                "available_issues": list(issues.keys()),
            }
        return {
            "device_type": device_type,
            "skill_name": skill.get("name"),
            "issue": {issue: issue_def},
        }

    if detail == "index":
        # Minimal: only issue keys and names (90%+ token savings)
        return {
            "device_type": device_type,
            "name": skill.get("name"),
            "description": skill.get("description"),
            "issues": {k: v["name"] for k, v in issues.items()},
        }

    if detail == "summary":
        # Moderate: names + description + severity + difficulty
        return {
            "device_type": device_type,
            "name": skill.get("name"),
            "description": skill.get("description"),
            "issues": {
                k: {
                    "name": v["name"],
                    "description": v.get("description", ""),
                    "severity": v.get("severity", ""),
                    "difficulty": v.get("difficulty", ""),
                }
                for k, v in issues.items()
            },
        }

    # Full detail (original behavior)
    result = dict(skill)
    result["device_type"] = device_type
    return result


def list_available_skills(category: str | None = None) -> list[dict[str, str]]:
    """List all available device/feature skills, optionally filtered by category."""
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


def get_injection_skill(
    device_type: str,
    detail: str = "full",
    issue: str | None = None,
) -> dict[str, Any]:
    """
    Get injection fault skill by device_type, with configurable detail level.

    Args:
        device_type: The injection fault type (e.g., "injection_ospf")
        detail: Detail level - "index" (names only), "summary" (+desc/sev/diff), "full" (all)
        issue: Optional specific issue key to retrieve

    Returns:
        Skill dictionary (detail varies by level), or error dict
    """
    skill = INJECTION_SKILLS_REGISTRY.get(device_type, {})

    if not skill:
        return {
            "error": f"Unknown injection fault type: {device_type}",
            "available_fault_types": list(INJECTION_SKILLS_REGISTRY.keys()),
            "hint": "Use {'action': 'list'} to see all available fault types"
        }

    issues = skill.get("issues", {})

    # Single issue lookup (most token-efficient)
    if issue:
        issue_def = issues.get(issue)
        if not issue_def:
            return {
                "error": f"Unknown issue '{issue}' in {device_type}",
                "available_issues": list(issues.keys()),
            }
        return {
            "device_type": device_type,
            "skill_name": skill.get("name"),
            "issue": {issue: issue_def},
        }

    if detail == "index":
        # Minimal: only issue keys and names (90%+ token savings)
        return {
            "device_type": device_type,
            "name": skill.get("name"),
            "description": skill.get("description"),
            "issues": {k: v["name"] for k, v in issues.items()},
        }

    if detail == "summary":
        # Moderate: names + description + severity + difficulty
        return {
            "device_type": device_type,
            "name": skill.get("name"),
            "description": skill.get("description"),
            "issues": {
                k: {
                    "name": v["name"],
                    "description": v.get("description", ""),
                    "severity": v.get("severity", ""),
                    "difficulty": v.get("difficulty", ""),
                }
                for k, v in issues.items()
            },
        }

    # Full detail (original behavior)
    result = dict(skill)
    result["device_type"] = device_type
    return result


def list_available_injection_skills(context: list[str] | None = None) -> list[dict[str, str]]:
    """
    List available injection fault skills, optionally filtered by context.

    Args:
        context: List of protocol/service keywords (e.g., ["ospf", "bgp", "vlan"]).
                 Only returns skills whose category matches any keyword.

    Returns:
        List of skill info dicts with device_type, name, and category.
    """
    skills = []
    for did, skill in INJECTION_SKILLS_REGISTRY.items():
        category = skill.get("category", "")
        if context:
            # Match if skill category contains any context keyword
            category_lower = category.lower()
            if not any(kw.lower() in category_lower or kw.lower() in did.lower() for kw in context):
                continue
        skills.append({
            "device_type": did,
            "name": skill.get("name", did),
            "category": category,
        })
    return skills


def get_packet_analysis_protocol(protocol: str) -> dict[str, Any]:
    """
    Get a packet analysis protocol definition.

    Args:
        protocol: The protocol key (e.g., "ospf", "bgp", "icmp")

    Returns:
        Protocol definition dictionary with available_fields, base_filter, etc.
        Returns error dict if protocol not found.
    """
    protocol_data = PACKET_ANALYSIS_REGISTRY.get(protocol)

    if not protocol_data:
        # Try case-insensitive match
        for key, data in PACKET_ANALYSIS_REGISTRY.items():
            if key.lower() == protocol.lower():
                protocol_data = data
                protocol = key
                break

    if not protocol_data:
        return {
            "error": f"Unknown protocol: {protocol}",
            "available_protocols": list(PACKET_ANALYSIS_REGISTRY.keys()),
        }

    return protocol_data


def list_available_packet_analysis_protocols() -> list[dict[str, str]]:
    """
    List all available packet analysis protocols.

    Returns:
        List of protocol info dicts with protocol, name, and description.
    """
    protocols = []
    for key, data in PACKET_ANALYSIS_REGISTRY.items():
        protocols.append({
            "protocol": key,
            "name": data.get("name", key),
            "description": data.get("description", ""),
        })
    return protocols


class DeviceSkillsTool(BaseTool):
    """
    LangChain tool for querying device/feature skills.

    Use this tool to get device command knowledge, topology planning skills, etc.
    For fault injection skills, use InjectionSkillsTool instead.
    """

    name: str = "device_skills"
    description: str = """
    Get or list device and feature specific skills.

    Provides access to device command knowledge (VPCS), topology planning, etc.
    For fault injection skills, use the injection_skills tool.

    INPUT FORMAT (JSON string):
    {
        "action": "get",  # "get" (default) or "list"
        "device_type": "gns3_vpcs_telnet",  # Required for action="get"
        "detail": "full"  # "full" (default) for complete skill information
    }

    For action="list":
    {"action": "list"}  # Lists all available device/feature skills
    """

    def _run(
        self,
        tool_input: str | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute the device skills lookup."""
        logger.debug("DeviceSkillsTool invoked with input: %s", tool_input)

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
            skills = list_available_skills()
            return json.dumps({
                "count": len(skills),
                "skills": skills
            }, ensure_ascii=False, indent=2)

        device_type = params.get("device_type")
        if not device_type:
            return json.dumps({
                "error": "Missing required field: device_type",
                "available_device_types": list(SKILLS_REGISTRY.keys()),
                "hint": 'Use {"action": "list"} to see all available device types'
            }, ensure_ascii=False, indent=2)

        category = params.get("category")
        detail = params.get("detail", "full")
        issue = params.get("issue")

        skill = get_skill(device_type, category, detail=detail, issue=issue)

        return json.dumps(skill, ensure_ascii=False, indent=2)


class InjectionSkillsTool(BaseTool):
    """
    LangChain tool for querying fault injection skills.

    Use this tool to list available injection fault types and get fault details.
    """

    name: str = "injection_skills"
    description: str = """
    Get or list network fault injection skills for troubleshooting practice.

    REQUIRED: When action="list", you MUST always pass "context" with the
    protocols/services found in your topology analysis.
    Example: {"action": "list", "context": ["ospf", "bgp", "mpls", "vlan", "stp"]}

    TOKEN-EFFICIENT USAGE:
    1. List faults for YOUR topology protocols (REQUIRED):
       {"action": "list", "context": ["ospf", "bgp"]}
    2. Get specific fault details:
       {"device_type": "injection_ospf", "issue": "ospf_hello_dead_mismatch"}
       {"device_type": "injection_ospf", "detail": "index"}

    PARAMETERS:
    - action: "list" or "get"
    - context: [str] - REQUIRED for action="list". Protocols from your topology.
    - device_type: Required for action="get" (e.g., "injection_ospf")
    - detail: "index" | "summary" | "full"
    - issue: Get single fault detail by key
    """

    def _run(
        self,
        tool_input: str | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute the injection skills lookup."""
        logger.debug("InjectionSkillsTool invoked with input: %s", tool_input)

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
            context = params.get("context")
            if not context or not isinstance(context, list) or len(context) == 0:
                return json.dumps({
                    "error": "context parameter is required when action='list'",
                    "hint": "Analyze the topology and device configurations first, "
                            "then pass the protocols/services you found as context. "
                            'Example: {"action": "list", "context": ["ospf", "bgp", "vlan"]}',
                    "available_categories": sorted(set(
                        skill.get("category", "")
                        for skill in INJECTION_SKILLS_REGISTRY.values()
                    ))
                }, ensure_ascii=False, indent=2)

            skills = list_available_injection_skills(context=context)
            logger.debug(f"Injection skills filtered by context={context}: {len(skills)} matching")
            return json.dumps({
                "count": len(skills),
                "total_available": len(INJECTION_SKILLS_REGISTRY),
                "context": context,
                "fault_types": skills
            }, ensure_ascii=False, indent=2)

        device_type = params.get("device_type")
        if not device_type:
            return json.dumps({
                "error": "Missing required field: device_type",
                "available_fault_types": list(INJECTION_SKILLS_REGISTRY.keys()),
                "hint": 'Use {"action": "list"} to see all available fault types'
            }, ensure_ascii=False, indent=2)

        detail = params.get("detail", "full")
        issue = params.get("issue")

        skill = get_injection_skill(device_type, detail=detail, issue=issue)

        return json.dumps(skill, ensure_ascii=False, indent=2)


class PacketAnalysisSkillsTool(BaseTool):
    """
    LangChain tool for querying packet analysis protocol definitions.

    Use this tool to list available protocols and get protocol-specific
    tshark fields, display filters, and check rules.
    """

    name: str = "packet_analysis_skills"
    description: str = """
    Get or list packet analysis protocol definitions.

    Before calling packet_analysis tool, use this to query the protocol's
    available tshark fields, display filters, and check rules.

    USAGE:
    - List available protocols:
      {"action": "list"}

    - Get protocol definition with fields:
      {"action": "get", "protocol": "ospf"}

    PARAMETERS:
    - action: "list" or "get" (required)
    - protocol: Protocol key for action="get" (e.g., "ospf", "bgp", "arp", "icmp")
    """

    def _run(
        self,
        tool_input: str | dict[str, Any],
        run_manager: CallbackManagerForToolRun | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute the packet analysis skills lookup."""
        logger.debug("PacketAnalysisSkillsTool invoked with input: %s", tool_input)

        if isinstance(tool_input, str):
            try:
                params = json.loads(tool_input)
            except json.JSONDecodeError as e:
                return json.dumps({
                    "error": f"Invalid JSON input: {e}",
                    "hint": 'Expected format: {"action": "get", "protocol": "ospf"}'
                }, ensure_ascii=False, indent=2)
        else:
            params = tool_input

        action = params.get("action", "get")

        if action == "list":
            protocols = list_available_packet_analysis_protocols()
            return json.dumps({
                "count": len(protocols),
                "protocols": protocols
            }, ensure_ascii=False, indent=2)

        protocol = params.get("protocol")
        if not protocol:
            return json.dumps({
                "error": "Missing required field: protocol",
                "available_protocols": list(PACKET_ANALYSIS_REGISTRY.keys()),
            }, ensure_ascii=False, indent=2)

        result = get_packet_analysis_protocol(protocol)
        return json.dumps(result, ensure_ascii=False, indent=2)
