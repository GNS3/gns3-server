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
# You should have received copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Agent module with optional AI Copilot support.

This module provides the AI Copilot functionality as an optional feature.
If the AI dependencies are not installed, the module will be disabled but
will not prevent the server from starting.

Installation:
    pip install gns3-server[ai-copilot]
"""

import logging
import threading

# Feature flag: AI Copilot is available
AI_COPILOT_AVAILABLE = False

# Try to import AI Copilot components
try:
    from .gns3_copilot.project_agent_manager import get_project_agent_manager
    from .gns3_copilot.project_agent_manager import ProjectAgentManager
    AI_COPILOT_AVAILABLE = True

    # Start skills repository initialization in background with 5s timeout.
    # This clones/pulls GNS3-Skills during server startup.
    # If GitHub is unreachable (common in some regions), the timeout
    # ensures the server starts without delay, using fallback defaults.
    def _init_skills_background():
        """Initialize skills repo - called from background thread."""
        from gns3server.agent.gns3_copilot.skills.registry import _ensure_skills_manager

        t = threading.Thread(target=_ensure_skills_manager, daemon=True)
        t.start()
        t.join(5)
        if t.is_alive():
            log = logging.getLogger(__name__)
            log.warning(
                "Skills repository initialization timed out (5s). "
                "Will use fallback defaults. "
                "The background thread will complete when network is available."
            )

    threading.Thread(target=_init_skills_background, daemon=True).start()

except ImportError as e:
    # AI dependencies not installed, disable AI Copilot feature
    logging.warning(
        f"AI Copilot dependencies not installed: {e}. "
        "AI features will be disabled. Install with: pip install gns3-server[ai-copilot]"
    )
    AI_COPILOT_AVAILABLE = False

    # Provide stub functions that raise helpful errors
    async def get_project_agent_manager():
        """
        Get the global ProjectAgentManager singleton instance.

        Raises:
            RuntimeError: If AI Copilot dependencies are not installed
        """
        raise RuntimeError(
            "AI Copilot is not available. "
            "Install AI dependencies with: pip install gns3-server[ai-copilot]"
        )

    class ProjectAgentManager:
        """
        Stub class for ProjectAgentManager when AI dependencies are not installed.
        """

        def __init__(self):
            raise RuntimeError(
                "AI Copilot is not available. "
                "Install AI dependencies with: pip install gns3-server[ai-copilot]"
            )


__all__ = [
    "AI_COPILOT_AVAILABLE",
    "get_project_agent_manager",
    "ProjectAgentManager",
]
