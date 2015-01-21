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

    def get_project(self, project_uuid):
        """
        Returns a Project instance.

        :param project_uuid: Project UUID

        :returns: Project instance
        """

        try:
            UUID(project_uuid, version=4)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(text="{} is not a valid UUID".format(project_uuid))

        if project_uuid not in self._projects:
            raise aiohttp.web.HTTPNotFound(text="Project UUID {} doesn't exist".format(project_uuid))
        return self._projects[project_uuid]

    def create_project(self, **kwargs):
        """
        Create a project and keep a references to it in project manager.

        See documentation of Project for arguments
        """

        project = Project(**kwargs)
        self._projects[project.uuid] = project
        return project
