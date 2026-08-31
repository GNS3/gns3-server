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
Agent module with optional AI Copilot and MCP support.

This module provides the AI Copilot and MCP (Model Context Protocol)
functionality as optional features. If the respective dependencies are
not installed, the affected features will be disabled but will not
prevent the server from starting.

Installation:
    pip install gns3-server[ai-features]         # Install all AI features
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

    # Start skills repository initialization in background.
    # Clones/pulls GNS3-Skills during server startup.
    # Git network timeouts are configured in SkillsManager (_GIT_TIMEOUT_ENV).
    # The daemon thread auto-terminates when the process exits.
    from gns3server.agent.gns3_copilot.skills.registry import _ensure_skills_manager

    threading.Thread(target=_ensure_skills_manager, daemon=True).start()

except ImportError as e:
    # AI dependencies not installed, disable AI Copilot feature
    logging.warning(
        f"AI Copilot dependencies not installed: {e}. "
        "AI features will be disabled. "
        "Install with: pip install gns3-server[ai-features]"
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
            "Install AI dependencies with: pip install gns3-server[ai-features]"
        )

    class ProjectAgentManager:
        """
        Stub class for ProjectAgentManager when AI dependencies are not installed.
        """

        def __init__(self):
            raise RuntimeError(
                "AI Copilot is not available. "
                "Install AI dependencies with: pip install gns3-server[ai-features]"
            )


# Feature flag: MCP (Model Context Protocol) is available
MCP_AVAILABLE = False

# Try to import MCP dependencies
try:
    # Use importlib so the top-level SDK name "mcp" is not bound in this
    # namespace — it would shadow the gns3server.agent.mcp subpackage.
    import importlib
    importlib.import_module("mcp.server.fastmcp")
    MCP_AVAILABLE = True
except ImportError:
    # MCP dependencies not installed, disable MCP feature
    logging.warning(
        "MCP dependencies not installed. "
        "MCP features will be disabled. "
        "Install with: pip install gns3-server[ai-features]"
    )
    MCP_AVAILABLE = False


__all__ = [
    "AI_COPILOT_AVAILABLE",
    "MCP_AVAILABLE",
    "get_project_agent_manager",
    "ProjectAgentManager",
]
