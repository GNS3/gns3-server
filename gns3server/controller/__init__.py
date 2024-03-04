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
import uuid
import shutil
import asyncio
import random
import json

try:
    import importlib_resources
except ImportError:
    from importlib import resources as importlib_resources


from ..config import Config
from ..utils import parse_version
from ..utils.images import default_images_directory

from .project import Project
from .appliance import Appliance
from .appliance_manager import ApplianceManager
from .compute import Compute, ComputeError
from .notification import Notification
from .symbols import Symbols
from .topology import load_topology
from .gns3vm import GNS3VM
from .gns3vm.gns3_vm_error import GNS3VMError
from .controller_error import ControllerError, ControllerNotFoundError
from ..version import __version__

import logging

log = logging.getLogger(__name__)


class Controller:
    """
    The controller is responsible to manage one or more computes.
    """

    def __init__(self):

        self._computes = {}
        self._projects = {}
        self._ssl_context = None
        self._notification = Notification(self)
        self.gns3vm = GNS3VM(self)
        self.symbols = Symbols()
        self._appliance_manager = ApplianceManager()
        self._iou_license_settings = {"iourc_content": "", "license_check": True}
        self._vars_loaded = False
        self._vars_file = Config.instance().controller_vars
        log.info(f'Loading controller vars file "{self._vars_file}"')

    async def start(self, computes=None):

        log.info("Controller is starting")
        self._install_base_configs()
        self._install_builtin_disks()
        server_config = Config.instance().settings.Server
        Config.instance().listen_for_config_changes(self._update_config)
        name = server_config.name
        host = server_config.host
        port = server_config.port

        # clients will use the IP they use to connect to
        # the controller if console_host is 0.0.0.0
        console_host = host
        if host == "0.0.0.0":
            host = "127.0.0.1"

        self._load_controller_vars()

        if server_config.enable_ssl:
            self._ssl_context = self._create_ssl_context(server_config)

        protocol = server_config.protocol
        if self._ssl_context and protocol != "https":
            log.warning(f"Protocol changed to 'https' for local compute because SSL is enabled")
            protocol = "https"
        try:
            self._local_server = await self.add_compute(
                compute_id="local",
                name=name,
                protocol=protocol,
                host=host,
                console_host=console_host,
                port=port,
                user=server_config.compute_username,
                password=server_config.compute_password,
                force=True,
                connect=True,
                wait_connection=False,
                ssl_context=self._ssl_context,
            )
        except ControllerError:
            log.fatal(
                f"Cannot access to the local server, make sure something else is not running on the TCP port {port}"
            )
            sys.exit(1)

        if computes:
            for c in computes:
                try:
                    #FIXME: Task exception was never retrieved
                    await self.add_compute(
                        compute_id=str(c.compute_id),
                        connect=False,
                        **c.dict(exclude_unset=True, exclude={"compute_id", "created_at", "updated_at"}),
                    )
                except (ControllerError, KeyError):
                    pass  # Skip not available servers at loading

        try:
            await self.gns3vm.auto_start_vm()
        except GNS3VMError as e:
            log.warning(str(e))

        await self.load_projects()
        await self._project_auto_open()

    def _create_ssl_context(self, server_config):

        import ssl

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        certfile = server_config.certfile
        certkey = server_config.certkey
        try:
            ssl_context.load_cert_chain(certfile, certkey)
        except FileNotFoundError:
            log.critical("Could not find the SSL certfile or certkey")
            raise SystemExit
        except ssl.SSLError as e:
            log.critical(f"SSL error: {e}")
            raise SystemExit
        return ssl_context

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
            self._local_server.user = Config.instance().settings.Server.compute_username
            self._local_server.password = Config.instance().settings.Server.compute_password

    async def stop(self):

        log.info("Controller is stopping")
        for project in self._projects.values():
            await project.close()
        for compute in self._computes.values():
            try:
                await compute.close()
            # We don't care if a compute is down at this step
            except (ComputeError, ControllerError, OSError):
                pass
        await self.gns3vm.exit_vm()
        self.save()
        self._computes = {}
        self._projects = {}

    async def reload(self):

        log.info("Controller is reloading")
        self._load_controller_vars()

        # remove all projects deleted from disk.
        for project in self._projects.copy().values():
            if not os.path.exists(project.path) or not os.listdir(project.path):
                log.info(f"Project '{project.name}' doesn't exist on the disk anymore, closing...")
                await project.close()
                self.remove_project(project)

        await self.load_projects()

    def save(self):
        """
        Save the controller vars on disk
        """

        controller_vars = dict()
        if self._vars_loaded:
            controller_vars = {
                "appliances_etag": self._appliance_manager.appliances_etag,
                "version": __version__
            }

            if self._iou_license_settings["iourc_content"]:

                iou_config = Config.instance().settings.IOU
                server_config = Config.instance().settings.Server

                if iou_config.iourc_path:
                    iourc_path = iou_config.iourc_path
                else:
                    os.makedirs(server_config.secrets_dir, exist_ok=True)
                    iourc_path = os.path.join(server_config.secrets_dir, "gns3_iourc_license")

                try:
                    with open(iourc_path, "w+") as f:
                        f.write(self._iou_license_settings["iourc_content"])
                    log.info(f"iourc file '{iourc_path}' saved")
                except OSError as e:
                    log.error(f"Cannot write IOU license file '{iourc_path}': {e}")

        try:
            os.makedirs(os.path.dirname(self._vars_file), exist_ok=True)
            with open(self._vars_file, 'w+') as f:
                json.dump(controller_vars, f, indent=4)
        except OSError as e:
            log.error(f"Cannot write controller vars file '{self._vars_file}': {e}")

    def _load_controller_vars(self):
        """
        Reload the controller vars from disk
        """

        try:
            if not os.path.exists(self._vars_file):
                self.save()  # this will create the vars file
            with open(self._vars_file) as f:
                controller_vars = json.load(f)
        except (OSError, ValueError) as e:
            log.critical(f"Cannot load controller vars file '{self._vars_file}': {e}")
            return []

        # load the IOU license settings
        iou_config = Config.instance().settings.IOU
        server_config = Config.instance().settings.Server

        if iou_config.iourc_path:
            iourc_path = iou_config.iourc_path
        else:
            if not server_config.secrets_dir:
                server_config.secrets_dir = os.path.dirname(Config.instance().server_config)
            iourc_path = os.path.join(server_config.secrets_dir, "gns3_iourc_license")

        if os.path.exists(iourc_path):
            try:
                with open(iourc_path) as f:
                    self._iou_license_settings["iourc_content"] = f.read()
                log.info(f"iourc file '{iourc_path}' loaded")
            except OSError as e:
                log.error(f"Cannot read IOU license file '{iourc_path}': {e}")
        self._iou_license_settings["license_check"] = iou_config.license_check

        previous_version = controller_vars.get("version")
        log.info("Comparing controller version {} with config version {}".format(__version__, previous_version))
        if not previous_version or \
                parse_version(__version__.split("+")[0]) > parse_version(previous_version.split("+")[0]):
            self._appliance_manager.install_builtin_appliances()
        elif not os.listdir(self._appliance_manager.builtin_appliances_path()):
            self._appliance_manager.install_builtin_appliances()

        self._appliance_manager.appliances_etag = controller_vars.get("appliances_etag")
        self._appliance_manager.load_appliances()
        self._vars_loaded = True

    async def load_projects(self):
        """
        Preload the list of projects from disk
        """

        server_config = Config.instance().settings.Server
        projects_path = os.path.expanduser(server_config.projects_path)
        os.makedirs(projects_path, exist_ok=True)
        try:
            for project_path in os.listdir(projects_path):
                project_dir = os.path.join(projects_path, project_path)
                if os.path.isdir(project_dir):
                    for file in os.listdir(project_dir):
                        if file.endswith(".gns3"):
                            try:
                                await self.load_project(os.path.join(project_dir, file), load=False)
                            except (ControllerError, NotImplementedError):
                                pass  # Skip not compatible projects
        except OSError as e:
            log.error(str(e))

    @staticmethod
    def install_resource_files(dst_path, resource_name):
        """
        Install files from resources to user's file system
        """

        if hasattr(sys, "frozen") and sys.platform.startswith("win"):
            resource_path = os.path.normpath(os.path.join(os.path.dirname(sys.executable), resource_name))
            for filename in os.listdir(resource_path):
                if not os.path.exists(os.path.join(dst_path, filename)):
                    shutil.copy(os.path.join(resource_path, filename), os.path.join(dst_path, filename))
        else:
            for entry in importlib_resources.files('gns3server').joinpath(resource_name).iterdir():
                full_path = os.path.join(dst_path, entry.name)
                if entry.is_file() and not os.path.exists(full_path):
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
            Controller.install_resource_files(dst_path, "configs")
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
            Controller.install_resource_files(dst_path, "disks")
        except OSError as e:
            log.error(f"Could not install disk files to {dst_path}: {e}")

    def images_path(self):
        """
        Get the image storage directory
        """

        server_config = Config.instance().settings.Server
        images_path = os.path.expanduser(server_config.images_path)
        os.makedirs(images_path, exist_ok=True)
        return images_path

    def configs_path(self):
        """
        Get the configs storage directory
        """

        server_config = Config.instance().settings.Server
        configs_path = os.path.expanduser(server_config.configs_path)
        os.makedirs(configs_path, exist_ok=True)
        return configs_path

    def disks_path(self, emulator_type="qemu"):
        """
        Get the disks storage directory
        """

        disks_path = default_images_directory(emulator_type)
        os.makedirs(disks_path, exist_ok=True)
        return disks_path

    async def add_compute(self, compute_id=None, name=None, force=False, connect=True, wait_connection=True, **kwargs):
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
            if (compute_id == "local" or compute_id == "vm") and not force:
                return None

            # It seem we have error with a gns3vm imported as a remote server and conflict
            # with GNS3 VM settings. That's why we ignore server name gns3vm
            if name == "gns3vm":
                return None

            for compute in self._computes.values():
                if name and compute.name == name and not force:
                    raise ControllerError(f'Compute name "{name}" already exists')

            compute = Compute(compute_id=compute_id, controller=self, name=name, **kwargs)
            self._computes[compute.id] = compute
            if connect:
                if wait_connection:
                    await compute.connect()
                else:
                    # call compute.connect() later to give time to the controller to be fully started
                    asyncio.get_event_loop().call_later(1, lambda: asyncio.ensure_future(compute.connect()))
            self.notification.controller_emit("compute.created", compute.asdict())
            return compute
        else:
            if connect:
                await self._computes[compute_id].connect()
            self.notification.controller_emit("compute.updated", self._computes[compute_id].asdict())
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
        except ControllerNotFoundError:
            return
        await self.close_compute_projects(compute)
        await compute.close()
        del self._computes[compute_id]
        self.notification.controller_emit("compute.deleted", compute.asdict())

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

        if compute_id is None:
            # get all connected computes
            computes = [compute for compute in self._computes.values() if compute.connected is True]
            if len(computes) == 1:
                # return the only available compute
                return computes[0]
            else:
                # randomly pick a compute until we have proper scalability handling
                # https://github.com/GNS3/gns3-server/issues/1676
                return random.choice(computes)

        try:
            return self._computes[compute_id]
        except KeyError:
            if compute_id == "vm":
                raise ControllerNotFoundError("Cannot use a node on the GNS3 VM server with the GNS3 VM not configured")
            raise ControllerNotFoundError(f"Compute ID {compute_id} doesn't exist")

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
                        raise ControllerError(f'Project "{name}" already exists in location "{path}"')
                    else:
                        raise ControllerError(f'Project "{name}" already exists')
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
            raise ControllerNotFoundError(f"Project ID {project_id} doesn't exist")

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

        if not os.path.exists(path):
            raise ControllerError(f"'{path}' does not exist on the controller")

        topo_data = load_topology(path)
        topo_data.pop("topology")
        topo_data.pop("version")
        topo_data.pop("revision")
        topo_data.pop("type")

        if topo_data["project_id"] in self._projects:
            project = self._projects[topo_data["project_id"]]
        else:
            project = await self.add_project(
                path=os.path.dirname(path),
                status="closed",
                filename=os.path.basename(path),
                **topo_data
            )
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
            new_name = f"{base_name}-{i}"
            if new_name not in names and not os.path.exists(os.path.join(projects_path, new_name)):
                break
            i += 1
            if i > 1000000:
                raise ControllerError("A project name could not be allocated (node limit reached?)")
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
    def iou_license(self):
        """
        :returns: The dictionary of IOU license settings
        """

        return self._iou_license_settings

    def projects_directory(self):

        server_config = Config.instance().settings.Server
        return os.path.expanduser(server_config.projects_path)

    @staticmethod
    def instance():
        """
        Singleton to return only on instance of Controller.

        :returns: instance of Controller
        """

        if not hasattr(Controller, "_instance") or Controller._instance is None:
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
        node = await project.add_node(
            compute, "AUTOIDLEPC", str(uuid.uuid4()), node_type="dynamips", platform=platform, image=image, ram=ram
        )
        res = await node.dynamips_auto_idlepc()
        await project.delete()
        self.remove_project(project)
        return res
