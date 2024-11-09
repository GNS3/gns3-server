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
import uuid
import socket
import shutil
import aiohttp

try:
    import importlib_resources
except ImportError:
    from importlib import resources as importlib_resources

from ..config import Config
from ..utils import parse_version, md5sum
from ..utils.images import default_images_directory

from .project import Project
from .template import Template
from .appliance import Appliance
from .appliance_manager import ApplianceManager
from .template_manager import TemplateManager
from .compute import Compute, ComputeError
from .notification import Notification
from .symbols import Symbols
from ..version import __version__
from .topology import load_topology
from .gns3vm import GNS3VM
from .gns3vm.gns3_vm_error import GNS3VMError

import logging
log = logging.getLogger(__name__)


class Controller:
    """
    The controller is responsible to manage one or more computes.
    """

    def __init__(self):
        self._computes = {}
        self._projects = {}
        self._notification = Notification(self)
        self.gns3vm = GNS3VM(self)
        self.symbols = Symbols()
        self._ssl_context = None
        self._appliance_manager = ApplianceManager()
        self._template_manager = TemplateManager()
        self._iou_license_settings = {"iourc_content": "",
                                      "license_check": True}
        self._config_loaded = False
        self._config_file = Config.instance().controller_config
        log.info("Load controller configuration file {}".format(self._config_file))

    async def start(self):

        log.info("Controller is starting")
        self._install_base_configs()
        self._install_builtin_disks()
        server_config = Config.instance().get_section_config("Server")
        Config.instance().listen_for_config_changes(self._update_config)
        host = server_config.get("host", "localhost")
        port = server_config.getint("port", 3080)

        # clients will use the IP they use to connect to
        # the controller if console_host is 0.0.0.0
        console_host = host
        if host == "0.0.0.0":
            host = "127.0.0.1"

        name = socket.gethostname()
        if name == "gns3vm":
            name = "Main server"

        computes = self._load_controller_settings()
        from gns3server.web.web_server import WebServer
        self._ssl_context = WebServer.instance(host=host, port=port).ssl_context()
        protocol = server_config.get("protocol", "http")
        if self._ssl_context and protocol != "https":
            log.warning("Protocol changed to 'https' for local compute because SSL is enabled".format(port))
            protocol = "https"
        try:
            self._local_server = await self.add_compute(compute_id="local",
                                                        name=name,
                                                        protocol=protocol,
                                                        host=host,
                                                        console_host=console_host,
                                                        port=port,
                                                        user=server_config.get("user", ""),
                                                        password=server_config.get("password", ""),
                                                        force=True,
                                                        ssl_context=self._ssl_context)
        except aiohttp.web.HTTPConflict:
            log.fatal("Cannot access to the local server, make sure something else is not running on the TCP port {}".format(port))
            sys.exit(1)
        for c in computes:
            try:
                await self.add_compute(**c)
            except (aiohttp.web.HTTPError, KeyError):
                pass  # Skip not available servers at loading

        try:
            await self.gns3vm.auto_start_vm()
        except GNS3VMError as e:
            log.warning(str(e))

        await self.load_projects()
        await self._project_auto_open()

    def ssl_context(self):
        """
        Returns the SSL context for the server.
        """

        return self._ssl_context

    def _update_config(self):
        """
        Call this when the server configuration file changes.
        """

        if self._local_server:
            server_config = Config.instance().get_section_config("Server")
            self._local_server.user = server_config.get("user")
            self._local_server.password = server_config.get("password")

    async def stop(self):

        log.info("Controller is stopping")
        for project in self._projects.values():
            await project.close()
        for compute in self._computes.values():
            try:
                await compute.close()
            # We don't care if a compute is down at this step
            except (ComputeError, aiohttp.web.HTTPError, OSError):
                pass
        await self.gns3vm.exit_vm()
        #self.save()
        self._computes = {}
        self._projects = {}

    async def reload(self):

        log.info("Controller is reloading")
        self._load_controller_settings()

        # remove all projects deleted from disk.
        for project in self._projects.copy().values():
            if not os.path.exists(project.path) or not os.listdir(project.path):
                log.info(f"Project '{project.name}' doesn't exist on the disk anymore, closing...")
                await project.close()
                self.remove_project(project)

        await self.load_projects()
        await self._project_auto_open()

    def check_can_write_config(self):
        """
        Check if the controller configuration can be written on disk

        :returns: boolean
        """

        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            if not os.access(self._config_file, os.W_OK):
                raise aiohttp.web.HTTPConflict(text="Change rejected, cannot write to controller configuration file '{}'".format(self._config_file))
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text="Change rejected: {}".format(e))

    def save(self):
        """
        Save the controller configuration on disk
        """

        controller_settings = dict()
        if self._config_loaded:
            controller_settings = {"computes": [],
                                   "templates": [],
                                   "gns3vm": self.gns3vm.__json__(),
                                   "iou_license": self._iou_license_settings,
                                   "appliances_etag": self._appliance_manager.appliances_etag,
                                   "version": __version__}

            for template in self._template_manager.templates.values():
                if not template.builtin:
                    controller_settings["templates"].append(template.__json__())

            for compute in self._computes.values():
                if compute.id != "local" and compute.id != "vm":
                    controller_settings["computes"].append({"host": compute.host,
                                                            "name": compute.name,
                                                            "port": compute.port,
                                                            "protocol": compute.protocol,
                                                            "user": compute.user,
                                                            "password": compute.password,
                                                            "compute_id": compute.id})

        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, 'w+') as f:
                json.dump(controller_settings, f, indent=4)
        except OSError as e:
            log.error("Cannot write controller configuration file '{}': {}".format(self._config_file, e))

    def _load_controller_settings(self):
        """
        Reload the controller configuration from disk
        """

        try:
            if not os.path.exists(self._config_file):
                self.save()  # this will create the config file
            with open(self._config_file) as f:
                controller_settings = json.load(f)
        except (OSError, ValueError) as e:
            log.critical("Cannot load configuration file '{}': {}".format(self._config_file, e))
            return []

        # load GNS3 VM settings
        if "gns3vm" in controller_settings:
            gns3_vm_settings = controller_settings["gns3vm"]
            if "port" not in gns3_vm_settings:
                # port setting was added in version 2.2.8
                # the default port was 3080 before this
                gns3_vm_settings["port"] = 3080
            self.gns3vm.settings = gns3_vm_settings

        # load the IOU license settings
        if "iou_license" in controller_settings:
            self._iou_license_settings = controller_settings["iou_license"]

        # install the built-in appliances if needed
        server_config = Config.instance().get_section_config("Server")
        if server_config.getboolean("install_builtin_appliances", True):
            previous_version = controller_settings.get("version")
            log.info("Comparing controller version {} with config version {}".format(__version__, previous_version))
            builtin_appliances_path = self._appliance_manager.builtin_appliances_path()
            if not previous_version or \
                    parse_version(__version__.split("+")[0]) > parse_version(previous_version.split("+")[0]):
                self._appliance_manager.install_builtin_appliances()
            elif not os.listdir(builtin_appliances_path):
                self._appliance_manager.install_builtin_appliances()
            else:
                log.info("Built-in appliances are installed in '{}'".format(builtin_appliances_path))

        self._appliance_manager.appliances_etag = controller_settings.get("appliances_etag")
        self._appliance_manager.load_appliances()
        self._template_manager.load_templates(controller_settings.get("templates"))
        self._config_loaded = True
        return controller_settings.get("computes", [])

    async def load_projects(self):
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
                                await self.load_project(os.path.join(project_dir, file), load=False)
                            except (aiohttp.web.HTTPConflict, aiohttp.web.HTTPNotFound, NotImplementedError):
                                pass  # Skip not compatible projects
        except OSError as e:
            log.error(str(e))


    @staticmethod
    def install_resource_files(dst_path, resource_name, upgrade_resources=True):
        """
        Install files from resources to user's file system
        """

        def should_copy(src, dst, upgrade_resources):
            if not os.path.exists(dst):
                return True
            if upgrade_resources is False:
                return False
            # copy the resource if it is different
            return md5sum(src) != md5sum(dst)

        if hasattr(sys, "frozen") and sys.platform.startswith("win"):
            resource_path = os.path.normpath(os.path.join(os.path.dirname(sys.executable), resource_name))
            for filename in os.listdir(resource_path):
                if not os.path.exists(os.path.join(dst_path, filename)):
                    shutil.copy(os.path.join(resource_path, filename), os.path.join(dst_path, filename))
        else:
            for entry in importlib_resources.files('gns3server').joinpath(resource_name).iterdir():
                full_path = os.path.join(dst_path, entry.name)
                if entry.is_file() and should_copy(str(entry), full_path, upgrade_resources):
                    log.debug(f'Installing {resource_name} resource file "{entry.name}" to "{full_path}"')
                    shutil.copy(str(entry), os.path.join(dst_path, entry.name))
                elif entry.is_dir():
                    os.makedirs(full_path, exist_ok=True)
                    Controller.install_resource_files(full_path, os.path.join(resource_name, entry.name))

    def _install_base_configs(self):
        """
        At startup we copy base configs to the user location to allow
        them to customize it
        """

        dst_path = self.configs_path()
        log.info(f"Installing base configs in '{dst_path}'")
        try:
            Controller.install_resource_files(dst_path, "configs", upgrade_resources=False)
        except OSError as e:
            log.error(f"Could not install base config files to {dst_path}: {e}")

    def _install_builtin_disks(self):
        """
        At startup we copy built-in Qemu disks to the user location to allow
        them to use with appliances
        """

        dst_path = self.disks_path()
        log.info(f"Installing built-in disks in '{dst_path}'")
        try:
            Controller.install_resource_files(dst_path, "disks", upgrade_resources=False)
        except OSError as e:
            log.error(f"Could not install disk files to {dst_path}: {e}")

    def images_path(self):
        """
        Get the image storage directory
        """

        server_config = Config.instance().get_section_config("Server")
        images_path = os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))
        os.makedirs(images_path, exist_ok=True)
        return images_path

    def configs_path(self):
        """
        Get the configs storage directory
        """

        server_config = Config.instance().get_section_config("Server")
        configs_path = os.path.expanduser(server_config.get("configs_path", "~/GNS3/configs"))
        os.makedirs(configs_path, exist_ok=True)
        return configs_path

    def disks_path(self, emulator_type="qemu"):
        """
        Get the disks storage directory
        """

        disks_path = default_images_directory(emulator_type)
        os.makedirs(disks_path, exist_ok=True)
        return disks_path

    async def add_compute(self, compute_id=None, name=None, force=False, connect=True, **kwargs):
        """
        Add a server to the dictionary of computes controlled by this controller

        :param compute_id: Compute identifier
        :param name: Compute name
        :param force: True skip security check
        :param connect: True connect to the compute immediately
        :param kwargs: See the documentation of Compute
        """

        if compute_id not in self._computes:

            # We disallow to create from the outside the local and VM server
            if (compute_id == 'local' or compute_id == 'vm') and not force:
                return None

            # It seem we have error with a gns3vm imported as a remote server and conflict
            # with GNS3 VM settings. That's why we ignore server name gns3vm
            if name == 'gns3vm':
                return None

            for compute in self._computes.values():
                if name and compute.name == name and not force:
                    raise aiohttp.web.HTTPConflict(text='Compute name "{}" already exists'.format(name))

            compute = Compute(compute_id=compute_id, controller=self, name=name, **kwargs)
            self._computes[compute.id] = compute
            self.save()
            if connect:
                await compute.connect()
            self.notification.controller_emit("compute.created", compute.__json__())
            return compute
        else:
            if connect:
                await self._computes[compute_id].connect()
            self.notification.controller_emit("compute.updated", self._computes[compute_id].__json__())
            return self._computes[compute_id]

    async def close_compute_projects(self, compute):
        """
        Close projects running on a compute
        """

        for project in self._projects.values():
            if compute in project.computes:
                await project.close()

    def compute_has_open_project(self, compute):
        """
        Check is compute has a project opened.

        :returns: True if a project is open
        """

        for project in self._projects.values():
            if compute in project.computes and project.status == "opened":
                return True
        return False

    async def delete_compute(self, compute_id):
        """
        Delete a compute node. Project using this compute will be close

        :param compute_id: Compute identifier
        """

        try:
            compute = self.get_compute(compute_id)
        except aiohttp.web.HTTPNotFound:
            return
        await self.close_compute_projects(compute)
        await compute.close()
        del self._computes[compute_id]
        self.save()
        self.notification.controller_emit("compute.deleted", compute.__json__())

    @property
    def notification(self):
        """
        The notification system
        """

        return self._notification

    @property
    def computes(self):
        """
        :returns: The dictionary of computes managed by this controller
        """

        return self._computes

    def get_compute(self, compute_id):
        """
        Returns a compute or raise a 404 error.
        """

        try:
            return self._computes[compute_id]
        except KeyError:
            if compute_id == "vm":
                raise aiohttp.web.HTTPNotFound(text="Cannot use a node on the GNS3 VM server with the GNS3 VM not configured")
            raise aiohttp.web.HTTPNotFound(text="Compute ID {} doesn't exist".format(compute_id))

    def has_compute(self, compute_id):
        """
        Return True if the compute exist in the controller
        """

        return compute_id in self._computes

    async def add_project(self, project_id=None, name=None, path=None, **kwargs):
        """
        Creates a project or returns an existing project

        :param project_id: Project ID
        :param name: Project name
        :param kwargs: See the documentation of Project
        """

        if project_id not in self._projects:
            for project in self._projects.values():
                if name and project.name == name:
                    if path and path == project.path:
                        raise aiohttp.web.HTTPConflict(text='Project "{}" already exists in location "{}"'.format(name, path))
                    else:
                        raise aiohttp.web.HTTPConflict(text='Project "{}" already exists'.format(name))
            project = Project(project_id=project_id, controller=self, name=name, path=path, **kwargs)
            self._projects[project.id] = project
            return self._projects[project.id]
        return self._projects[project_id]

    def get_project(self, project_id):
        """
        Returns a project or raise a 404 error.
        """

        try:
            return self._projects[project_id]
        except KeyError:
            raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't exist".format(project_id))

    async def get_loaded_project(self, project_id):
        """
        Returns a project or raise a 404 error.

        If project is not finished to load wait for it
        """

        project = self.get_project(project_id)
        await project.wait_loaded()
        return project

    def remove_project(self, project):

        if project.id in self._projects:
            del self._projects[project.id]

    async def load_project(self, path, load=True):
        """
        Load a project from a .gns3

        :param path: Path of the .gns3
        :param load: Load the topology
        """

        topo_data = load_topology(path)
        topo_data.pop("topology")
        topo_data.pop("version")
        topo_data.pop("revision")
        topo_data.pop("type")

        if topo_data["project_id"] in self._projects:
            project = self._projects[topo_data["project_id"]]
        else:
            project = await self.add_project(path=os.path.dirname(path), status="closed", filename=os.path.basename(path), **topo_data)
        if load or project.auto_open:
            await project.open()
        return project

    async def _project_auto_open(self):
        """
        Auto open the project with auto open enable
        """

        for project in self._projects.values():
            if project.auto_open:
                await project.open()

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
        :returns: The dictionary of projects managed by the controller
        """

        return self._projects

    @property
    def appliance_manager(self):
        """
        :returns: Appliance Manager instance
        """

        return self._appliance_manager

    @property
    def template_manager(self):
        """
        :returns: Template Manager instance
        """

        return self._template_manager

    @property
    def iou_license(self):
        """
        :returns: The dictionary of IOU license settings
        """

        return self._iou_license_settings

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

    async def autoidlepc(self, compute_id, platform, image, ram):
        """
        Compute and IDLE PC value for an image

        :param compute_id: ID of the compute where the idlepc operation need to run
        :param platform: Platform type
        :param image: Image to use
        :param ram: amount of RAM to use
        """

        compute = self.get_compute(compute_id)
        for project in list(self._projects.values()):
            if project.name == "AUTOIDLEPC":
                await project.delete()
                self.remove_project(project)
        project = await self.add_project(name="AUTOIDLEPC")
        node = await project.add_node(compute, "AUTOIDLEPC", str(uuid.uuid4()), node_type="dynamips", platform=platform, image=image, ram=ram)
        res = await node.dynamips_auto_idlepc()
        await project.delete()
        self.remove_project(project)
        return res

    async def compute_ports(self, compute_id):
        """
        Get the ports used by a compute.

        :param compute_id: ID of the compute
        """

        compute = self.get_compute(compute_id)
        response = await compute.get("/network/ports")
        return response.json
