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


class Controller:
    """The controller manage multiple gns3 hypervisors"""

    def __init__(self):
        self._hypervisors = {}
        self._projects = {}

    def isEnabled(self):
        """
        :returns: True if current instance is the controller
        of our GNS3 infrastructure.
        """
        return Config.instance().get_section_config("Server").getboolean("controller")

    def addHypervisor(self, hypervisor):
        """
        Add a server to the dictionnary of hypervisors controlled by GNS3
        """
        if hypervisor.id not in self._hypervisors:
            self._hypervisors[hypervisor.id] = hypervisor

    @property
    def hypervisors(self):
        """
        :returns: The dictionnary of hypervisors managed by GNS3
        """
        return self._hypervisors

    @asyncio.coroutine
    def addProject(self, project):
        """
        Add a server to the dictionnary of projects controlled by GNS3
        """
        if project.id not in self._projects:
            self._projects[project.id] = project
            for hypervisor in self._hypervisors.values():
                yield from project.addHypervisor(hypervisor)

    def getProject(self, project_id):
        """
        Return a server or raise a 404
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
        :returns: The dictionnary of hypervisors managed by GNS3
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
