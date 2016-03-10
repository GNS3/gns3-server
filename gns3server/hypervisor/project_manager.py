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
from .project import Project
from uuid import UUID


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

    def create_project(self, name=None, project_id=None, path=None, temporary=False):
        """
        Create a project and keep a references to it in project manager.

        See documentation of Project for arguments
        """

        if project_id is not None and project_id in self._projects:
            return self._projects[project_id]
        project = Project(name=name, project_id=project_id, path=path, temporary=temporary)
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

    def check_hardware_virtualization(self, source_vm):
        """
        Checks if hardware virtualization can be used.

        :returns: boolean
        """

        for project in self._projects.values():
            for vm in project.vms:
                if vm == source_vm:
                    continue
                if vm.hw_virtualization and vm.__class__.__name__ != source_vm.__class__.__name__:
                    return False
        return True
