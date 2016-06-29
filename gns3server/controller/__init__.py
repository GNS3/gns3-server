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

import os
import sys
import json
import asyncio
import aiohttp

from ..config import Config
from .project import Project
from .compute import Compute
from .notification import Notification
from .symbols import Symbols
from ..version import __version__
from .topology import load_topology

import logging
log = logging.getLogger(__name__)


class Controller:
    """The controller is responsible to manage one or more compute servers"""

    def __init__(self):
        self._computes = {}
        self._projects = {}
        self._notification = Notification(self)
        self.symbols = Symbols()
        # Store settings shared by the different GUI will be replace by dedicated API later
        self._settings = {}

        if sys.platform.startswith("win"):
            config_path = os.path.join(os.path.expandvars("%APPDATA%"), "GNS3")
        else:
            config_path = os.path.join(os.path.expanduser("~"), ".config", "GNS3")
        self._config_file = os.path.join(config_path, "gns3_controller.conf")

        server_config = Config.instance().get_section_config("Server")
        if server_config.getboolean("local", False) is True:
            self._computes["local"] = Compute(compute_id="local",
                                              controller=self,
                                              protocol=server_config.get("protocol", "http"),
                                              host=server_config.get("host", "localhost"),
                                              port=server_config.getint("port", 3080),
                                              user=server_config.get("user", ""),
                                              password=server_config.get("password", ""))

    def save(self):
        """
        Save the controller configuration on disk
        """
        data = {"computes": [{"host": c.host,
                              "name": c.name,
                              "port": c.port,
                              "protocol": c.protocol,
                              "user": c.user,
                              "password": c.password,
                              "compute_id": c.id
                              } for c in self._computes.values()],
                "settings": self._settings,
                "version": __version__}
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        with open(self._config_file, 'w+') as f:
            json.dump(data, f, indent=4)

    @asyncio.coroutine
    def load(self):
        """
        Reload the controller configuration from disk
        """

        if not os.path.exists(self._config_file):
            self.save()
        try:
            with open(self._config_file) as f:
                data = json.load(f)
        except OSError as e:
            log.critical("Cannot load %s: %s", self._config_file, str(e))
            return
        if "settings" in data:
            self._settings = data["settings"]

        for c in data["computes"]:
            yield from self.add_compute(**c)

        # Preload the list of projects from disk
        server_config = Config.instance().get_section_config("Server")
        projects_path = os.path.expanduser(server_config.get("projects_path", "~/GNS3/projects"))
        os.makedirs(projects_path, exist_ok=True)
        try:
            for project_path in os.listdir(projects_path):
                project_dir = os.path.join(projects_path, project_path)
                if os.path.isdir(project_dir):
                    for file in os.listdir(project_dir):
                        if file.endswith(".gns3"):
                            try:
                                yield from self.load_project(os.path.join(project_dir, file), load=False)
                            except aiohttp.web_exceptions.HTTPConflict:
                                pass  # Skip not compatible projects
        except OSError as e:
            log.error(str(e))

    @property
    def settings(self):
        """
        Store settings shared by the different GUI will be replace by dedicated API later. Dictionnary
        """
        return self._settings

    @settings.setter
    def settings(self, val):
        self._settings = val
        self.notification.emit("settings.updated", val)

    def is_enabled(self):
        """
        :returns: whether the current instance is the controller
        of our GNS3 infrastructure.
        """
        return Config.instance().get_section_config("Server").getboolean("controller")

    @asyncio.coroutine
    def add_compute(self, compute_id=None, name=None, **kwargs):
        """
        Add a server to the dictionary of compute servers controlled by this controller

        :param compute_id: Compute server identifier
        :param name: Compute name
        :param kwargs: See the documentation of Compute
        """
        if compute_id not in self._computes:

            # We disallow to create from the outside the
            if compute_id == 'local':
                return None

            for compute in self._computes.values():
                if name and compute.name == name:
                    raise aiohttp.web.HTTPConflict(text="Compute name {} is duplicate".format(name))

            compute = Compute(compute_id=compute_id, controller=self, name=name, **kwargs)
            self._computes[compute.id] = compute
            self.save()
            self.notification.emit("compute.created", compute.__json__())
            return compute
        else:
            self.notification.emit("compute.updated", self._computes[compute_id].__json__())
            return self._computes[compute_id]

    @asyncio.coroutine
    def delete_compute(self, compute_id):
        """
        Delete a compute node
        :param compute_id: Compute server identifier
        """
        compute = self.get_compute(compute_id)
        yield from compute.close()
        del self._computes[compute_id]
        self.save()
        self.notification.emit("compute.deleted", compute.__json__())

    @asyncio.coroutine
    def close(self):
        log.info("Close controller")
        for compute in self._computes.values():
            yield from compute.close()

    @property
    def notification(self):
        """
        The notification system
        """
        return self._notification

    @property
    def computes(self):
        """
        :returns: The dictionary of compute server managed by this controller
        """
        return self._computes

    def get_compute(self, compute_id):
        """
        Returns a compute server or raise a 404 error.
        """
        try:
            return self._computes[compute_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Compute ID {} doesn't exist".format(compute_id))

    @asyncio.coroutine
    def add_project(self, project_id=None, name=None, **kwargs):
        """
        Creates a project or returns an existing project

        :param project_id: Project ID
        :param name: Project name
        :param kwargs: See the documentation of Project
        """
        if project_id not in self._projects:

            for project in self._projects.values():
                if name and project.name == name:
                    raise aiohttp.web.HTTPConflict(text="Project name {} is duplicate".format(name))
            project = Project(project_id=project_id, controller=self, name=name, **kwargs)
            self._projects[project.id] = project
            return self._projects[project.id]
        return self._projects[project_id]

    def get_project(self, project_id):
        """
        Returns a compute server or raise a 404 error.
        """
        try:
            return self._projects[project_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't exist".format(project_id))

    def remove_project(self, project):
        del self._projects[project.id]

    @asyncio.coroutine
    def load_project(self, path, load=True):
        """
        Load a project from a .gns3

        :param path: Path of the .gns3
        :param load: Load the topology
        """
        topo_data = load_topology(path)
        topology = topo_data.pop("topology")
        topo_data.pop("version")
        topo_data.pop("revision")
        topo_data.pop("type")

        if topo_data["project_id"] in self._projects:
            project = self._projects[topo_data["project_id"]]
        else:
            project = yield from self.add_project(path=os.path.dirname(path), status="closed", filename=os.path.basename(path), **topo_data)
        if load:
            yield from project.open()
        return project

    @property
    def projects(self):
        """
        :returns: The dictionary of computes managed by GNS3
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
