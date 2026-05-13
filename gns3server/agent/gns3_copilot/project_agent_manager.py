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

Project Agent Manager

Manages AgentService instances for GNS3 projects using a singleton pattern.
Each project has its own AgentService with a dedicated SQLite checkpoint
database.
"""

import asyncio
import logging
from typing import Dict
from typing import Optional

from gns3server.agent.gns3_copilot.agent_service import AgentService

log = logging.getLogger(__name__)


class ProjectAgentManager:
    """
    Singleton manager for project-level Agent services.

    Manages the lifecycle of AgentService instances, ensuring that each project
    has exactly one AgentService instance. Handles cleanup of resources when
    projects are closed.
    """

    _instance: Optional["ProjectAgentManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _agents: Dict[str, AgentService] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def get_agent(
        self, project_id: str, project_path: str
    ) -> AgentService:
        """
        Get or create an AgentService for a project.

        Args:
            project_id: GNS3 project ID
            project_path: Path to the GNS3 project directory

        Returns:
            AgentService instance for the project
        """
        async with self._lock:
            if project_id not in self._agents:
                log.info(
                    "Creating new AgentService for project: %s at %s",
                    project_id,
                    project_path,
                )
                self._agents[project_id] = AgentService(project_path)
            return self._agents[project_id]

    async def remove_agent(self, project_id: str):
        """
        Remove and cleanup an AgentService for a project.

        Should be called when a project is closed to free resources.

        Args:
            project_id: GNS3 project ID
        """
        async with self._lock:
            if project_id in self._agents:
                log.info("Removing AgentService for project: %s", project_id)
                agent = self._agents.pop(project_id)
                await agent.close()

    async def close_all(self):
        """
        Close all AgentService instances and cleanup resources.

        Should be called on server shutdown.
        """
        async with self._lock:
            log.info(
                "Closing all AgentService instances (%d projects)",
                len(self._agents),
            )
            for project_id, agent in self._agents.items():
                log.debug("Closing AgentService for project: %s", project_id)
                await agent.close()
            self._agents.clear()

    def has_agent(self, project_id: str) -> bool:
        """
        Check if an AgentService exists for a project.

        Args:
            project_id: GNS3 project ID

        Returns:
            True if AgentService exists, False otherwise
        """
        return project_id in self._agents

    @property
    def active_projects(self) -> list[str]:
        """
        Get list of project IDs with active AgentService instances.

        Returns:
            List of project IDs
        """
        return list(self._agents.keys())


# Global singleton instance
_project_agent_manager: Optional[ProjectAgentManager] = None
_manager_lock = asyncio.Lock()


async def get_project_agent_manager() -> ProjectAgentManager:
    """
    Get the global ProjectAgentManager singleton instance.

    Returns:
        ProjectAgentManager instance
    """
    global _project_agent_manager
    async with _manager_lock:
        if _project_agent_manager is None:
            _project_agent_manager = ProjectAgentManager()
            log.info("ProjectAgentManager singleton created")
        return _project_agent_manager
