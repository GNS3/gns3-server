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
import socket
import asyncio
import aiohttp

from ..config import Config
from .project import Project
from .compute import Compute
from .notification import Notification
from .symbols import Symbols
from ..version import __version__
from .topology import load_topology
from .gns3vm import GNS3VM


import logging
log = logging.getLogger(__name__)


class Controller:
    """The controller is responsible to manage one or more compute servers"""

    def __init__(self):
        self._computes = {}
        self._projects = {}
        self._notification = Notification(self)
        self.gns3vm = GNS3VM(self)
        self.symbols = Symbols()
        # Store settings shared by the different GUI will be replace by dedicated API later
        self._settings = {}

        self._config_file = os.path.join(Config.instance().config_dir, "gns3_controller.conf")
        log.info("Load controller configuration file {}".format(self._config_file))

    @asyncio.coroutine
    def start(self):
        log.info("Start controller")
        yield from self.load()
        server_config = Config.instance().get_section_config("Server")
        host = server_config.get("host", "localhost")
        if host == "0.0.0.0":
            host = "127.0.0.1"
        yield from self.add_compute(compute_id="local",
                                    name=socket.gethostname(),
                                    protocol=server_config.get("protocol", "http"),
                                    host=host,
                                    port=server_config.getint("port", 3080),
                                    user=server_config.get("user", ""),
                                    password=server_config.get("password", ""),
                                    force=True)
        yield from self.load_projects()
        yield from self.gns3vm.auto_start_vm()
        yield from self._project_auto_open()

    @asyncio.coroutine
    def stop(self):
        log.info("Stop controller")
        for project in self._projects.values():
            yield from project.close()
        for compute in self._computes.values():
            try:
                yield from compute.close()
            # We don't care if a compute is down at this step
            except (aiohttp.errors.ClientOSError, aiohttp.web_exceptions.HTTPError):
                pass
        yield from self.gns3vm.exit_vm()
        self._computes = {}
        self._projects = {}

    def save(self):
        """
        Save the controller configuration on disk
        """
        data = {
            "computes": [],
            "settings": self._settings,
            "gns3vm": self.gns3vm.__json__(),
            "version": __version__
        }

        for c in self._computes.values():
            if c.id != "local" and c.id != "vm":
                data["computes"].append({
                    "host": c.host,
                    "name": c.name,
                    "port": c.port,
                    "protocol": c.protocol,
                    "user": c.user,
                    "password": c.password,
                    "compute_id": c.id
                })
        os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
        with open(self._config_file, 'w+') as f:
            json.dump(data, f, indent=4)

    @asyncio.coroutine
    def load(self):
        """
        Reload the controller configuration from disk
        """

        if not os.path.exists(self._config_file):
            yield from self._import_gns3_gui_conf()
            self.save()
        try:
            with open(self._config_file) as f:
                data = json.load(f)
        except OSError as e:
            log.critical("Cannot load %s: %s", self._config_file, str(e))
            return
        if "settings" in data:
            self._settings = data["settings"]
        if "gns3vm" in data:
            self.gns3vm.settings = data["gns3vm"]

        for c in data["computes"]:
            yield from self.add_compute(**c)

    @asyncio.coroutine
    def load_projects(self):
        """
        Preload the list of projects from disk
        """
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

    def images_path(self):
        """
        Get the image storage directory
        """
        server_config = Config.instance().get_section_config("Server")
        images_path = os.path.expanduser(server_config.get("images_path", "~/GNS3/projects"))
        os.makedirs(images_path, exist_ok=True)
        return images_path

    @asyncio.coroutine
    def _import_gns3_gui_conf(self):
        """
        Import old config from GNS3 GUI
        """
        config_file = os.path.join(os.path.dirname(self._config_file), "gns3_gui.conf")
        if os.path.exists(config_file):
            with open(config_file) as f:
                data = json.load(f)
                server_settings = data.get("Servers", {})
                for remote in server_settings.get("remote_servers", []):
                    yield from self.add_compute(
                        host=remote.get("host", "localhost"),
                        port=remote.get("port", 3080),
                        protocol=remote.get("protocol", "http"),
                        name=remote.get("url"),
                        user=remote.get("user"),
                        password=remote.get("password")
                    )
                if "vm" in server_settings:
                    vm_settings = server_settings["vm"]
                    if vm_settings["virtualization"] == "VMware":
                        engine = "vmware"
                        vmname = vm_settings.get("vmname", "")
                    elif vm_settings["virtualization"] == "VirtualBox":
                        engine = "virtualbox"
                        vmname = vm_settings.get("vmname", "")
                    else:
                        engine = "remote"
                        # In case of remote server we match the compute with url parameter
                        for compute in self._computes.values():
                            if compute.host == vm_settings.get("remote_vm_host") and compute.port == vm_settings.get("remote_vm_port"):
                                vmname = compute.name

                    if vm_settings.get("auto_stop", True):
                        when_exit = "stop"
                    else:
                        when_exit = "keep"

                    self.gns3vm.settings = {
                        "engine": engine,
                        "enable": vm_settings.get("auto_start", False),
                        "when_exit": when_exit,
                        "headless": vm_settings.get("headless", False),
                        "vmname": vmname
                    }

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

    @asyncio.coroutine
    def add_compute(self, compute_id=None, name=None, force=False, connect=True, **kwargs):
        """
        Add a server to the dictionary of compute servers controlled by this controller

        :param compute_id: Compute server identifier
        :param name: Compute name
        :param force: True skip security check
        :param connect: True connect to the compute immediately
        :param kwargs: See the documentation of Compute
        """
        if compute_id not in self._computes:

            # We disallow to create from the outside the local and VM server
            if (compute_id == 'local' or compute_id == 'vm') and not force:
                return None

            for compute in self._computes.values():
                if name and compute.name == name:
                    raise aiohttp.web.HTTPConflict(text='Compute name "{}" already exists'.format(name))

            compute = Compute(compute_id=compute_id, controller=self, name=name, **kwargs)
            self._computes[compute.id] = compute
            self.save()
            if connect:
                yield from compute.connect()
            self.notification.emit("compute.created", compute.__json__())
            return compute
        else:
            if connect:
                yield from self._computes[compute_id].connect()
            self.notification.emit("compute.updated", self._computes[compute_id].__json__())
            return self._computes[compute_id]

    @asyncio.coroutine
    def delete_compute(self, compute_id):
        """
        Delete a compute node. Project using this compute will be close

        :param compute_id: Compute server identifier
        """
        compute = self.get_compute(compute_id)

        for project in self._projects.values():
            if compute in project.computes:
                yield from project.close()

        yield from compute.close()
        del self._computes[compute_id]
        self.save()
        self.notification.emit("compute.deleted", compute.__json__())

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
            server_config = Config.instance().get_section_config("Server")
            if compute_id == "vm":
                raise aiohttp.web.HTTPNotFound(text="You try to use a node on the GNS3 VM server but the GNS3 is not configured")
            raise aiohttp.web.HTTPNotFound(text="Compute ID {} doesn't exist".format(compute_id))

    def has_compute(self, compute_id):
        """
        Return True if the compute exist in the controller
        """
        return compute_id in self._computes

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
                    raise aiohttp.web.HTTPConflict(text='Project name "{}" already exists'.format(name))
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
            self.remove_project(self._projects[topo_data["project_id"]])

        project = yield from self.add_project(path=os.path.dirname(path), status="closed", filename=os.path.basename(path), **topo_data)
        if load or project.auto_open:
            yield from project.open()
        return project

    @asyncio.coroutine
    def _project_auto_open(self):
        """
        Auto open the project with auto open enable
        """
        for project in self._projects.values():
            if project.auto_open:
                yield from project.open()

    def get_free_project_name(self, base_name):
        """
        Generate a free project name base on the base name
        """
        names = [p.name for p in self._projects.values()]
        if base_name not in names:
            return base_name
        i = 1

        projects_path = self.projects_directory()

        while True:
            new_name = "{}-{}".format(base_name, i)
            if new_name not in names and not os.path.exists(os.path.join(projects_path, new_name)):
                break
            i += 1
            if i > 1000000:
                raise aiohttp.web.HTTPConflict(text="A project name could not be allocated (node limit reached?)")
        return new_name

    @property
    def projects(self):
        """
        :returns: The dictionary of computes managed by GNS3
        """
        return self._projects

    def projects_directory(self):
        server_config = Config.instance().get_section_config("Server")
        return os.path.expanduser(server_config.get("projects_path", "~/GNS3/projects"))

    @staticmethod
    def instance():
        """
        Singleton to return only on instance of Controller.

        :returns: instance of Controller
        """

        if not hasattr(Controller, '_instance') or Controller._instance is None:
            Controller._instance = Controller()
        return Controller._instance
