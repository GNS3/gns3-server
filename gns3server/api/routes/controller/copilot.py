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
API routes for GNS3 Copilot global operations (non-project).
"""

import logging

from fastapi import APIRouter, Depends
from .dependencies.authentication import get_current_active_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/reload/skills",
    dependencies=[Depends(get_current_active_user)],
)
async def reload_skills() -> dict:
    """
    Hot reload skills and prompts from the external GNS3-Skills repository.

    Reloads injection skills, system prompts, and forbidden commands
    from the skills repository without restarting the server.
    """
    try:
        from gns3server.agent.gns3_copilot.skills.registry import (
            reload_skills_repository,
        )

        result = reload_skills_repository()
    except ImportError:
        return {"error": "AI Copilot is not available"}

    return result
