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

"""
Dynamips server module.
"""

import aiohttp
import sys
import os
import shutil
import socket
import time
import asyncio
import tempfile
import glob
import logging

log = logging.getLogger(__name__)

from gns3server.utils.interfaces import get_windows_interfaces
from gns3server.utils.asyncio import wait_run_in_executor
from pkg_resources import parse_version
from uuid import UUID, uuid4
from ..base_manager import BaseManager
from ..project_manager import ProjectManager
from .dynamips_error import DynamipsError
from .hypervisor import Hypervisor
from .nodes.router import Router
from .dynamips_vm import DynamipsVM
from .dynamips_device import DynamipsDevice

# NIOs
from .nios.nio_udp import NIOUDP
from .nios.nio_udp_auto import NIOUDPAuto
from .nios.nio_unix import NIOUNIX
from .nios.nio_vde import NIOVDE
from .nios.nio_tap import NIOTAP
from .nios.nio_generic_ethernet import NIOGenericEthernet
from .nios.nio_linux_ethernet import NIOLinuxEthernet
from .nios.nio_fifo import NIOFIFO
from .nios.nio_mcast import NIOMcast
from .nios.nio_null import NIONull


class Dynamips(BaseManager):

    _VM_CLASS = DynamipsVM
    _DEVICE_CLASS = DynamipsDevice

    def __init__(self):

        super().__init__()
        self._devices = {}
        self._ghost_files = set()
        self._dynamips_path = None

    @asyncio.coroutine
    def unload(self):

        yield from BaseManager.unload(self)

        tasks = []
        for device in self._devices.values():
            tasks.append(asyncio.async(device.hypervisor.stop()))

        if tasks:
            done, _ = yield from asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    log.error("Could not stop device hypervisor {}".format(e), exc_info=1)
                    continue

    @asyncio.coroutine
    def project_closed(self, project_dir):
        """
        Called when a project is closed.

        :param project_dir: project directory
        """

        # delete the Dynamips devices
        tasks = []
        for device in self._devices.values():
            tasks.append(asyncio.async(device.delete()))

        if tasks:
            done, _ = yield from asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    log.error("Could not delete device {}".format(e), exc_info=1)

        # delete useless files
        project_dir = os.path.join(project_dir, 'project-files', self.module_name.lower())
        files = glob.glob(os.path.join(project_dir, "*.ghost"))
        files += glob.glob(os.path.join(project_dir, "*_lock"))
        files += glob.glob(os.path.join(project_dir, "ilt_*"))
        files += glob.glob(os.path.join(project_dir, "c[0-9][0-9][0-9][0-9]_*_rommon_vars"))
        files += glob.glob(os.path.join(project_dir, "c[0-9][0-9][0-9][0-9]_*_ssa"))
        for file in files:
            try:
                log.debug("Deleting file {}".format(file))
                if file in self._ghost_files:
                    self._ghost_files.remove(file)
                yield from wait_run_in_executor(os.remove, file)
            except OSError as e:
                log.warn("Could not delete file {}: {}".format(file, e))
                continue

    @property
    def dynamips_path(self):
        """
        Returns the path to Dynamips.

        :returns: path
        """

        return self._dynamips_path

    @asyncio.coroutine
    def create_device(self, name, project_id, device_id, device_type, *args, **kwargs):
        """
        Create a new Dynamips device.

        :param name: Device name
        :param project_id: Project identifier
        :param vm_id: restore a VM identifier
        """

        project = ProjectManager.instance().get_project(project_id)
        if not device_id:
            device_id = str(uuid4())

        device = self._DEVICE_CLASS(name, device_id, project, self, device_type, *args, **kwargs)
        yield from device.create()
        self._devices[device.id] = device
        return device

    def get_device(self, device_id, project_id=None):
        """
        Returns a device instance.

        :param device_id: Device identifier
        :param project_id: Project identifier

        :returns: Device instance
        """

        if project_id:
            # check the project_id exists
            project = ProjectManager.instance().get_project(project_id)

        try:
            UUID(device_id, version=4)
        except ValueError:
            raise aiohttp.web.HTTPBadRequest(text="Device ID} is not a valid UUID".format(device_id))

        if device_id not in self._devices:
            raise aiohttp.web.HTTPNotFound(text="Device ID {} doesn't exist".format(device_id))

        device = self._devices[device_id]
        if project_id:
            if device.project.id != project.id:
                raise aiohttp.web.HTTPNotFound(text="Project ID {} doesn't belong to device {}".format(project_id, device.name))

        return device

    @asyncio.coroutine
    def delete_device(self, device_id):
        """
        Delete a device

        :param device_id: Device identifier

        :returns: Device instance
        """

        device = self.get_device(device_id)
        yield from device.delete()
        del self._devices[device.id]
        return device

    def find_dynamips(self):

        # look for Dynamips
        dynamips_path = self.config.get_section_config("Dynamips").get("dynamips_path")
        if not dynamips_path:
            dynamips_path = shutil.which("dynamips")

        if not dynamips_path:
            raise DynamipsError("Could not find Dynamips")
        if not os.path.isfile(dynamips_path):
            raise DynamipsError("Dynamips {} is not accessible".format(dynamips_path))
        if not os.access(dynamips_path, os.X_OK):
            raise DynamipsError("Dynamips is not executable")

        self._dynamips_path = dynamips_path
        return dynamips_path

    @asyncio.coroutine
    def _wait_for_hypervisor(self, host, port, timeout=10.0):
        """
        Waits for an hypervisor to be started (accepting a socket connection)

        :param host: host/address to connect to the hypervisor
        :param port: port to connect to the hypervisor
        """

        begin = time.time()
        connection_success = False
        last_exception = None
        while time.time() - begin < timeout:
            yield from asyncio.sleep(0.01)
            try:
                _, writer = yield from asyncio.open_connection(host, port)
                writer.close()
            except OSError as e:
                last_exception = e
                continue
            connection_success = True
            break

        if not connection_success:
            raise DynamipsError("Couldn't connect to hypervisor on {}:{} :{}".format(host, port, last_exception))
        else:
            log.info("Dynamips server ready after {:.4f} seconds".format(time.time() - begin))

    @asyncio.coroutine
    def start_new_hypervisor(self, working_dir=None):
        """
        Creates a new Dynamips process and start it.

        :param working_dir: working directory

        :returns: the new hypervisor instance
        """

        if not self._dynamips_path:
            self.find_dynamips()

        if not working_dir:
            working_dir = tempfile.gettempdir()

        try:
            # let the OS find an unused port for the Dynamips hypervisor
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
        except OSError as e:
            raise DynamipsError("Could not find free port for the Dynamips hypervisor: {}".format(e))

        hypervisor = Hypervisor(self._dynamips_path, working_dir, "127.0.0.1", port)

        log.info("Ceating new hypervisor {}:{} with working directory {}".format(hypervisor.host, hypervisor.port, working_dir))
        yield from hypervisor.start()

        yield from self._wait_for_hypervisor("127.0.0.1", port)
        log.info("Hypervisor {}:{} has successfully started".format(hypervisor.host, hypervisor.port))

        yield from hypervisor.connect()
        if parse_version(hypervisor.version) < parse_version('0.2.11'):
            raise DynamipsError("Dynamips version must be >= 0.2.11, detected version is {}".format(hypervisor.version))

        return hypervisor

    @asyncio.coroutine
    def ghost_ios_support(self, vm):

        ghost_ios_support = self.config.get_section_config("Dynamips").get("ghost_ios_support", True)
        if ghost_ios_support:
            yield from self._set_ghost_ios(vm)

    @asyncio.coroutine
    def create_nio(self, node, nio_settings):
        """
        Creates a new NIO.

        :param node: Dynamips node instance
        :param nio_settings: information to create the NIO

        :returns: a NIO object
        """

        nio = None
        if nio_settings["type"] == "nio_udp":
            lport = nio_settings["lport"]
            rhost = nio_settings["rhost"]
            rport = nio_settings["rport"]
            try:
                # TODO: handle IPv6
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect((rhost, rport))
            except OSError as e:
                raise DynamipsError("Could not create an UDP connection to {}:{}: {}".format(rhost, rport, e))
            # check if we have an allocated NIO UDP auto
            #nio = node.hypervisor.get_nio_udp_auto(lport)
            #if not nio:
            # otherwise create an NIO UDP
            nio = NIOUDP(node.hypervisor, lport, rhost, rport)
            #else:
            #    nio.connect(rhost, rport)
        elif nio_settings["type"] == "nio_generic_ethernet":
            ethernet_device = nio_settings["ethernet_device"]
            if sys.platform.startswith("win"):
                # replace the interface name by the GUID on Windows
                interfaces = get_windows_interfaces()
                npf_interface = None
                for interface in interfaces:
                    if interface["name"] == ethernet_device:
                        npf_interface = interface["id"]
                if not npf_interface:
                    raise DynamipsError("Could not find interface {} on this host".format(ethernet_device))
                else:
                    ethernet_device = npf_interface
            nio = NIOGenericEthernet(node.hypervisor, ethernet_device)
        elif nio_settings["type"] == "nio_linux_ethernet":
            if sys.platform.startswith("win"):
                raise DynamipsError("This NIO type is not supported on Windows")
            ethernet_device = nio_settings["ethernet_device"]
            nio = NIOLinuxEthernet(node.hypervisor, ethernet_device)
        elif nio_settings["type"] == "nio_tap":
            tap_device = nio_settings["tap_device"]
            nio = NIOTAP(node.hypervisor, tap_device)
        elif nio_settings["type"] == "nio_unix":
            local_file = nio_settings["local_file"]
            remote_file = nio_settings["remote_file"]
            nio = NIOUNIX(node.hypervisor, local_file, remote_file)
        elif nio_settings["type"] == "nio_vde":
            control_file = nio_settings["control_file"]
            local_file = nio_settings["local_file"]
            nio = NIOVDE(node.hypervisor, control_file, local_file)
        elif nio_settings["type"] == "nio_null":
            nio = NIONull(node.hypervisor)

        yield from nio.create()
        return nio

    @asyncio.coroutine
    def _set_ghost_ios(self, vm):
        """
        Manages Ghost IOS support.

        :param vm: VM instance
        """

        if not vm.mmap:
            raise DynamipsError("mmap support is required to enable ghost IOS support")

        ghost_file = vm.formatted_ghost_file()
        ghost_file_path = os.path.join(vm.hypervisor.working_dir, ghost_file)
        if ghost_file_path not in self._ghost_files:
            # create a new ghost IOS instance
            ghost_id = str(uuid4())
            ghost = Router("ghost-" + ghost_file, ghost_id, vm.project, vm.manager, platform=vm.platform, hypervisor=vm.hypervisor, ghost_flag=True)
            yield from ghost.create()
            yield from ghost.set_image(vm.image)
            # for 7200s, the NPE must be set when using an NPE-G2.
            if vm.platform == "c7200":
                yield from ghost.set_npe(vm.npe)
            yield from ghost.set_ghost_status(1)
            yield from ghost.set_ghost_file(ghost_file)
            yield from ghost.set_ram(vm.ram)
            try:
                yield from ghost.start()
                yield from ghost.stop()
                self._ghost_files.add(ghost_file_path)
            except DynamipsError:
                raise
            finally:
                yield from ghost.clean_delete()

        if vm.ghost_file != ghost_file:
            # set the ghost file to the router
            yield from vm.set_ghost_status(2)
            yield from vm.set_ghost_file(ghost_file)
#
#     def create_config_from_file(self, local_base_config, router, destination_config_path):
#         """
#         Creates a config file from a local base config
#
#         :param local_base_config: path the a local base config
#         :param router: router instance
#         :param destination_config_path: path to the destination config file
#
#         :returns: relative path to the created config file
#         """
#
#         log.info("creating config file {} from {}".format(destination_config_path, local_base_config))
#         config_path = destination_config_path
#         config_dir = os.path.dirname(destination_config_path)
#         try:
#             os.makedirs(config_dir)
#         except FileExistsError:
#             pass
#         except OSError as e:
#             raise DynamipsError("Could not create configs directory: {}".format(e))
#
#         try:
#             with open(local_base_config, "r", errors="replace") as f:
#                 config = f.read()
#             with open(config_path, "w") as f:
#                 config = "!\n" + config.replace("\r", "")
#                 config = config.replace('%h', router.name)
#                 f.write(config)
#         except OSError as e:
#             raise DynamipsError("Could not save the configuration from {} to {}: {}".format(local_base_config, config_path, e))
#         return "configs" + os.sep + os.path.basename(config_path)
#
#     def create_config_from_base64(self, config_base64, router, destination_config_path):
#         """
#         Creates a config file from a base64 encoded config.
#
#         :param config_base64: base64 encoded config
#         :param router: router instance
#         :param destination_config_path: path to the destination config file
#
#         :returns: relative path to the created config file
#         """
#
#         log.info("creating config file {} from base64".format(destination_config_path))
#         config = base64.decodebytes(config_base64.encode("utf-8")).decode("utf-8")
#         config = "!\n" + config.replace("\r", "")
#         config = config.replace('%h', router.name)
#         config_dir = os.path.dirname(destination_config_path)
#         try:
#             os.makedirs(config_dir)
#         except FileExistsError:
#             pass
#         except OSError as e:
#             raise DynamipsError("Could not create configs directory: {}".format(e))
#
#         config_path = destination_config_path
#         try:
#             with open(config_path, "w") as f:
#                 log.info("saving startup-config to {}".format(config_path))
#                 f.write(config)
#         except OSError as e:
#             raise DynamipsError("Could not save the configuration {}: {}".format(config_path, e))
#         return "configs" + os.sep + os.path.basename(config_path)
