# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import aiohttp
import asyncio
import psutil
import platform
from .project import Project
from uuid import UUID

import logging
log = logging.getLogger(__name__)


class ProjectManager:

    """
    This singleton keeps track of available projects.
    """

    def __init__(self):

        self._projects = {}

    @classmethod
    def instance(cls):
        """
        Singleton to return only one instance of ProjectManager.

        :returns: instance of ProjectManager
        """

        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    @property
    def projects(self):
        """
        Returns all projects.

        :returns: Project instances
        """

        return self._projects.values()

    def get_project(self, project_id):
        """
        Returns a Project instance.

        :param project_id: Project identifier

        :returns: Project instance
        """

        try:
            UUID(project_id, version=4)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(text="Project ID {} is not a valid UUID".format(project_id))

        if project_id not in self._projects:
            raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't exist".format(project_id))
        return self._projects[project_id]

    def _check_available_disk_space(self, project):
        """
        Sends a warning notification if disk space is getting low.

        :param project: project instance
        """

        try:
            used_disk_space = psutil.disk_usage(project.path).percent
        except FileNotFoundError:
            log.warning('Could not find "{}" when checking for used disk space'.format(project.path))
            return
        # send a warning if used disk space is >= 90%
        if used_disk_space >= 90:
            message = 'Only {:.2f}% or less of free disk space detected in "{}" on "{}"'.format(100 - used_disk_space,
                                                                                                project.path,
                                                                                                platform.node())
            log.warning(message)
            project.emit("log.warning", {"message": message})

    def create_project(self, name=None, project_id=None, path=None, variables=None):
        """
        Create a project and keep a references to it in project manager.

        See documentation of Project for arguments
        """
        if project_id is not None and project_id in self._projects:
            return self._projects[project_id]
        project = Project(name=name, project_id=project_id,
                          path=path, variables=variables)
        self._check_available_disk_space(project)
        self._projects[project.id] = project
        return project

    def remove_project(self, project_id):
        """
        Removes a Project instance from the list of projects in use.

        :param project_id: Project identifier
        """

        if project_id not in self._projects:
            raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't exist".format(project_id))
        del self._projects[project_id]

    def check_hardware_virtualization(self, source_node):
        """
        Checks if hardware virtualization can be used.

        :returns: boolean
        """

        for project in self._projects.values():
            for node in project.nodes:
                if node == source_node:
                    continue
                if node.hw_virtualization and node.__class__.__name__ != source_node.__class__.__name__:
                    return False
        return True
