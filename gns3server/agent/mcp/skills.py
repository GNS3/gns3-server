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
device_skill_get — the MCP surface of the GNS3-Skills repository.

The copilot's DeviceSkillsTool already proved the access pattern
(list -> topic index -> single topic; bodies load ONLY on an explicit
topic request). This handler reuses the same framework-free core —
get_skill() / list_available_skills() over SKILLS_REGISTRY — instead of
the LangChain tool shell, so both surfaces stay in step by construction
and share the SkillsManager hot reload.

The protocol is multi-call by design: list -> a device's topic index ->
one topic body. The caller picks the key from the list and passes it
back unchanged; there is no name guessing in this layer.
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

    action = params.get("action")
    if not action:
        # No explicit action: list when nothing to get, get otherwise.
        action = "list" if not params.get("device_type") else "get"
    if action == "list":
        skills = registry.list_available_skills()
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
        detail=params.get("detail", "full"),
        issue=params.get("issue"),
        topic=params.get("topic"),
    )
    if "error" in result:
        return {"status": "failed", **result}
    return {"status": "ok", "skill": result}
