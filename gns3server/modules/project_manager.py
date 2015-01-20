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

    def get_project(self, project_id):
        """
        Returns a Project instance.

        :param project_id: Project identifier

        :returns: Project instance
        """

        assert len(project_id) == 36

        if project_id not in self._projects:
            raise aiohttp.web.HTTPNotFound(text="Project UUID {} doesn't exist".format(project_id))
        return self._projects[project_id]

    def create_project(self, **kwargs):
        """
        Create a project and keep a references to it in project manager.

        See documentation of Project for arguments
        """

        project = Project(**kwargs)
        self._projects[project.uuid] = project
        return project
