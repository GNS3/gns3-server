#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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
#

"""
MCP surface of the GNS3-Skills repository: device_skill_get and
injection_skill_get.

Both reuse the copilot's framework-free core instead of the LangChain
tool shell, so the access protocols stay in step by construction:

- device_skill_get: list -> device topic index -> one topic body
  (get_skill / list_available_skills over SKILLS_REGISTRY).
- injection_skill_get: topology context -> fault category -> one fault
  (get_injection_skill / list_available_injection_skills over
  INJECTION_SKILLS_REGISTRY).

The caller picks each key from the previous call and passes it back
unchanged; there is no name guessing in this layer.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def device_skills_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """List or fetch skills from the GNS3-Skills repository.

    action "list" -> every loaded skill (device_type, name, topic_count).
    Otherwise one skill by the key the list returned.
    """
    try:
        from gns3server.agent.gns3_copilot.skills import registry
    except Exception as e:
        log.debug("device_skill_get: skills registry unavailable: %s", e)
        return {"status": "failed", "error": f"Skills subsystem unavailable: {e}"}

    # First call on a fresh server may race the background repository
    # load; triggering the (idempotent, retryable) init avoids returning
    # an empty list just because the clone has not finished yet.
    if not registry.SKILLS_REGISTRY and registry.get_skills_manager() is None:
        return {
            "status": "failed",
            "error": "Skills repository is not initialized. Configure the GNS3-Skills repository "
            "(skills_repo_url) and retry — the initial clone may still be running.",
        }

    action = params.get("action")
    if not action:
        # No explicit action: list when nothing to get, get otherwise.
        action = "list" if not params.get("device_type") else "get"
    if action == "list":
        skills = registry.list_available_skills(params.get("category"))
        return {"status": "ok", "count": len(skills), "skills": skills}

    device_type = params.get("device_type")
    if not device_type:
        return {
            "status": "failed",
            "error": "Provide device_type (the skill key)",
            "hint": "device_skill_get(action='list') enumerates what is loaded",
        }

    result = registry.get_skill(
        device_type,
        category=params.get("category"),
        detail=params.get("detail", "full"),
        issue=params.get("issue"),
        topic=params.get("topic"),
    )
    if "error" in result:
        return {"status": "failed", **result}
    return {"status": "ok", "skill": result}


def injection_skills_handler(params: dict[str, Any], gns3_ctx: dict[str, Any]) -> dict[str, Any]:
    """List or fetch fault-injection skills from the GNS3-Skills repository.

    action "list" requires ``context`` — the protocols/services found in
    the topology — and returns only the matching fault categories.
    Otherwise one category (detail index/summary/full) or a single issue.
    """
    try:
        from gns3server.agent.gns3_copilot.skills import registry
    except Exception as e:
        log.debug("injection_skill_get: skills registry unavailable: %s", e)
        return {"status": "failed", "error": f"Skills subsystem unavailable: {e}"}

    if not registry.INJECTION_SKILLS_REGISTRY and registry.get_skills_manager() is None:
        return {
            "status": "failed",
            "error": "Skills repository is not initialized. Configure the GNS3-Skills repository "
            "(skills_repo_url) and retry — the initial clone may still be running.",
        }

    action = params.get("action")
    if not action:
        # No explicit action: list when there is no category to fetch.
        action = "list" if not params.get("device_type") else "get"

    if action == "list":
        context = params.get("context")
        if not isinstance(context, list) or not context:
            return {
                "status": "failed",
                "error": "context is required when action='list'",
                "hint": 'Pass the protocols/services found in the topology, e.g. {"context": ["ospf", "bgp"]}',
                "total_available": len(registry.INJECTION_SKILLS_REGISTRY),
            }
        skills = registry.list_available_injection_skills(context=context)
        return {
            "status": "ok",
            "count": len(skills),
            "total_available": len(registry.INJECTION_SKILLS_REGISTRY),
            "context": context,
            "fault_types": skills,
        }

    device_type = params.get("device_type")
    if not device_type:
        return {
            "status": "failed",
            "error": "Provide device_type (the fault category key from the list), e.g. 'injection_ospf_issues'",
            "hint": "injection_skill_get(action='list', context=[...]) enumerates the matching categories",
        }

    result = registry.get_injection_skill(
        device_type,
        detail=params.get("detail", "full"),
        issue=params.get("issue"),
    )
    if "error" in result:
        return {"status": "failed", **result}
    return {"status": "ok", "skill": result}
