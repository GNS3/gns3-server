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

from ..config import Config
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
from ..utils.get_resource import get_resource
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
        self._appliance_manager = ApplianceManager()
        self._template_manager = TemplateManager()
        self._iou_license_settings = {"iourc_content": "",
                                      "license_check": True}
        self._config_loaded = False
        self._config_file = Config.instance().controller_config
        log.info("Load controller configuration file {}".format(self._config_file))

    async def start(self):

        log.info("Controller is starting")
        self.load_base_files()
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

        computes = await self._load_controller_settings()
        try:
            self._local_server = await self.add_compute(compute_id="local",
                                                        name=name,
                                                        protocol=server_config.get("protocol", "http"),
                                                        host=host,
                                                        console_host=console_host,
                                                        port=port,
                                                        user=server_config.get("user", ""),
                                                        password=server_config.get("password", ""),
                                                        force=True)
        except aiohttp.web.HTTPConflict:
            log.fatal("Cannot access to the local server, make sure something else is not running on the TCP port {}".format(port))
            sys.exit(1)
        for c in computes:
            try:
                await self.add_compute(**c)
            except (aiohttp.web.HTTPError, KeyError):
                pass  # Skip not available servers at loading
        await self.load_projects()
        try:
            await self.gns3vm.auto_start_vm()
        except GNS3VMError as e:
            log.warning(str(e))
        await self._project_auto_open()

    def _update_config(self):
        """
        Call this when the server configuration file changes.
        """

        if self._local_server:
            server_config = Config.instance().get_section_config("Server")
            self._local_server.user = server_config.get("user")
            self._local_server.password = server_config.get("password")

    async def stop(self):

        log.info("Controller is Stopping")
        for project in self._projects.values():
            await project.close()
        for compute in self._computes.values():
            try:
                await compute.close()
            # We don't care if a compute is down at this step
            except (ComputeError, aiohttp.web.HTTPError, OSError):
                pass
        await self.gns3vm.exit_vm()
        self._computes = {}
        self._projects = {}

    def save(self):
        """
        Save the controller configuration on disk
        """

        if self._config_loaded is False:
            return

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

    async def _load_controller_settings(self):
        """
        Reload the controller configuration from disk
        """

        try:
            if not os.path.exists(self._config_file):
                await self._import_gns3_gui_conf()
                self._config_loaded = True
                self.save()
            with open(self._config_file) as f:
                controller_settings = json.load(f)
        except (OSError, ValueError) as e:
            log.critical("Cannot load configuration file '{}': {}".format(self._config_file, e))
            return []

        # load GNS3 VM settings
        if "gns3vm" in controller_settings:
            self.gns3vm.settings = controller_settings["gns3vm"]

        # load the IOU license settings
        if "iou_license" in controller_settings:
            self._iou_license_settings = controller_settings["iou_license"]

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
                            except (aiohttp.web.HTTPConflict, NotImplementedError):
                                pass  # Skip not compatible projects
        except OSError as e:
            log.error(str(e))

    def load_base_files(self):
        """
        At startup we copy base file to the user location to allow
        them to customize it
        """

        dst_path = self.configs_path()
        src_path = get_resource('configs')
        try:
            for file in os.listdir(src_path):
                if not os.path.exists(os.path.join(dst_path, file)):
                    shutil.copy(os.path.join(src_path, file), os.path.join(dst_path, file))
        except OSError:
            pass

    def images_path(self):
        """
        Get the image storage directory
        """

        server_config = Config.instance().get_section_config("Server")
        images_path = os.path.expanduser(server_config.get("images_path", "~/GNS3/projects"))
        os.makedirs(images_path, exist_ok=True)
        return images_path

    def configs_path(self):
        """
        Get the configs storage directory
        """

        server_config = Config.instance().get_section_config("Server")
        images_path = os.path.expanduser(server_config.get("configs_path", "~/GNS3/projects"))
        os.makedirs(images_path, exist_ok=True)
        return images_path

    async def _import_gns3_gui_conf(self):
        """
        Import old config from GNS3 GUI
        """

        config_file = os.path.join(os.path.dirname(self._config_file), "gns3_gui.conf")
        if os.path.exists(config_file):
            with open(config_file) as f:
                settings = json.load(f)
                server_settings = settings.get("Servers", {})
                for remote in server_settings.get("remote_servers", []):
                    try:
                        await self.add_compute(host=remote.get("host", "localhost"),
                                               port=remote.get("port", 3080),
                                               protocol=remote.get("protocol", "http"),
                                               name=remote.get("url"),
                                               user=remote.get("user"),
                                               password=remote.get("password"))
                    except aiohttp.web.HTTPConflict:
                        pass  # if the server is broken we skip it
                if "vm" in server_settings:
                    vmname = None
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

                vms = []
                for vm in settings.get("Qemu", {}).get("vms", []):
                    vm["template_type"] = "qemu"
                    vms.append(vm)
                for vm in settings.get("IOU", {}).get("devices", []):
                    vm["template_type"] = "iou"
                    vms.append(vm)
                for vm in settings.get("Docker", {}).get("containers", []):
                    vm["template_type"] = "docker"
                    vms.append(vm)
                for vm in settings.get("Builtin", {}).get("cloud_nodes", []):
                    vm["template_type"] = "cloud"
                    vms.append(vm)
                for vm in settings.get("Builtin", {}).get("ethernet_switches", []):
                    vm["template_type"] = "ethernet_switch"
                    vms.append(vm)
                for vm in settings.get("Builtin", {}).get("ethernet_hubs", []):
                    vm["template_type"] = "ethernet_hub"
                    vms.append(vm)
                for vm in settings.get("Dynamips", {}).get("routers", []):
                    vm["template_type"] = "dynamips"
                    vms.append(vm)
                for vm in settings.get("VMware", {}).get("vms", []):
                    vm["template_type"] = "vmware"
                    vms.append(vm)
                for vm in settings.get("VirtualBox", {}).get("vms", []):
                    vm["template_type"] = "virtualbox"
                    vms.append(vm)
                for vm in settings.get("VPCS", {}).get("nodes", []):
                    vm["template_type"] = "vpcs"
                    vms.append(vm)
                for vm in settings.get("TraceNG", {}).get("nodes", []):
                    vm["template_type"] = "traceng"
                    vms.append(vm)

                for vm in vms:
                    # remove deprecated properties
                    for prop in vm.copy():
                        if prop in ["enable_remote_console", "use_ubridge", "acpi_shutdown"]:
                            del vm[prop]

                    # remove deprecated default_symbol and hover_symbol
                    # and set symbol if not present
                    deprecated = ["default_symbol", "hover_symbol"]
                    if len([prop for prop in vm.keys() if prop in deprecated]) > 0:
                        if "default_symbol" in vm.keys():
                            del vm["default_symbol"]
                        if "hover_symbol" in vm.keys():
                            del vm["hover_symbol"]

                        if "symbol" not in vm.keys():
                            vm["symbol"] = ":/symbols/computer.svg"

                    vm.setdefault("template_id", str(uuid.uuid4()))
                    try:
                        template = Template(vm["template_id"], vm)
                        template.__json__()  # Check if loaded without error
                        self.template_manager.templates[template.id] = template
                    except KeyError as e:
                        # template data is not complete (missing name or type)
                        log.warning("Cannot load template {} ('{}'): missing key {}".format(vm["template_id"], vm.get("name", "unknown"), e))
                        continue

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
        :returns: The dictionary of projects managed by GNS3
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
