#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import asyncio
import aiohttp

from ..config import Config
from .project import Project
from .compute import Compute


class Controller:
    """The controller manage multiple gns3 computes"""

    def __init__(self):
        self._computes = {}
        self._projects = {}

    def isEnabled(self):
        """
        :returns: True if current instance is the controller
        of our GNS3 infrastructure.
        """
        return Config.instance().get_section_config("Server").getboolean("controller")

    @asyncio.coroutine
    def addCompute(self, compute_id, **kwargs):
        """
        Add a server to the dictionnary of computes controlled by GNS3

        :param kwargs: See the documentation of Compute
        """
        if compute_id not in self._computes:
            compute = Compute(compute_id=compute_id, controller=self, **kwargs)
            self._computes[compute_id] = compute
        return self._computes[compute_id]

    @property
    def computes(self):
        """
        :returns: The dictionnary of computes managed by GNS3
        """
        return self._computes

    def getCompute(self, compute_id):
        """
        Return an compute or raise a 404
        """
        try:
            return self._computes[compute_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Compute ID {} doesn't exist".format(compute_id))

    @asyncio.coroutine
    def addProject(self, project_id=None, **kwargs):
        """
        Create a project or return an existing project

        :param kwargs: See the documentation of Project
        """
        if project_id not in self._projects:
            project = Project(project_id=project_id, **kwargs)
            self._projects[project.id] = project
            for compute in self._computes.values():
                yield from project.addCompute(compute)
            return self._projects[project.id]
        return self._projects[project_id]

    def getProject(self, project_id):
        """
        Return a project or raise a 404
        """
        try:
            return self._projects[project_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't exist".format(project_id))

    def removeProject(self, project):
        del self._projects[project.id]

    @property
    def projects(self):
        """
        :returns: The dictionnary of computes managed by GNS3
        """
        return self._projects

    @staticmethod
    def instance():
        """
        Singleton to return only on instance of Controller.
        :returns: instance of Controller
        """

        if not hasattr(Controller, '_instance') or Controller._instance is None:
            Controller._instance = Controller()
        return Controller._instance

    def emit(self, action, event, **kwargs):
        """
        Send a notification to clients scoped by projects
        """

        if "project_id" in kwargs:
            try:
                project_id = kwargs.pop("project_id")
                self._projects[project_id].emit(action, event, **kwargs)
            except KeyError:
                pass
        else:
            for project in self._projects.values():
                project.emit(action, event, **kwargs)
