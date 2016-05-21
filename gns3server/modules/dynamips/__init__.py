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
import logging
import glob

log = logging.getLogger(__name__)

from gns3server.utils.interfaces import interfaces, is_interface_up
from gns3server.utils.asyncio import wait_run_in_executor
from gns3server.utils import parse_version
from uuid import UUID, uuid4
from ..base_manager import BaseManager
from ..project_manager import ProjectManager
from ..port_manager import PortManager
from .dynamips_error import DynamipsError
from .hypervisor import Hypervisor
from .nodes.router import Router
from .dynamips_vm import DynamipsVM
from .dynamips_device import DynamipsDevice

# NIOs
from .nios.nio_udp import NIOUDP
from .nios.nio_unix import NIOUNIX
from .nios.nio_vde import NIOVDE
from .nios.nio_tap import NIOTAP
from .nios.nio_generic_ethernet import NIOGenericEthernet
from .nios.nio_linux_ethernet import NIOLinuxEthernet
from .nios.nio_null import NIONull

# Adapters
from .adapters.c7200_io_2fe import C7200_IO_2FE
from .adapters.c7200_io_fe import C7200_IO_FE
from .adapters.c7200_io_ge_e import C7200_IO_GE_E
from .adapters.nm_16esw import NM_16ESW
from .adapters.nm_1e import NM_1E
from .adapters.nm_1fe_tx import NM_1FE_TX
from .adapters.nm_4e import NM_4E
from .adapters.nm_4t import NM_4T
from .adapters.pa_2fe_tx import PA_2FE_TX
from .adapters.pa_4e import PA_4E
from .adapters.pa_4t import PA_4T
from .adapters.pa_8e import PA_8E
from .adapters.pa_8t import PA_8T
from .adapters.pa_a1 import PA_A1
from .adapters.pa_fe_tx import PA_FE_TX
from .adapters.pa_ge import PA_GE
from .adapters.pa_pos_oc3 import PA_POS_OC3
from .adapters.wic_1enet import WIC_1ENET
from .adapters.wic_1t import WIC_1T
from .adapters.wic_2t import WIC_2T


ADAPTER_MATRIX = {"C7200-IO-2FE": C7200_IO_2FE,
                  "C7200-IO-FE": C7200_IO_FE,
                  "C7200-IO-GE-E": C7200_IO_GE_E,
                  "NM-16ESW": NM_16ESW,
                  "NM-1E": NM_1E,
                  "NM-1FE-TX": NM_1FE_TX,
                  "NM-4E": NM_4E,
                  "NM-4T": NM_4T,
                  "PA-2FE-TX": PA_2FE_TX,
                  "PA-4E": PA_4E,
                  "PA-4T+": PA_4T,
                  "PA-8E": PA_8E,
                  "PA-8T": PA_8T,
                  "PA-A1": PA_A1,
                  "PA-FE-TX": PA_FE_TX,
                  "PA-GE": PA_GE,
                  "PA-POS-OC3": PA_POS_OC3}

WIC_MATRIX = {"WIC-1ENET": WIC_1ENET,
              "WIC-1T": WIC_1T,
              "WIC-2T": WIC_2T}


class Dynamips(BaseManager):

    _VM_CLASS = DynamipsVM
    _DEVICE_CLASS = DynamipsDevice
    _ghost_ios_lock = None

    def __init__(self):

        super().__init__()
        Dynamips._ghost_ios_lock = asyncio.Lock()
        self._devices = {}
        self._ghost_files = set()
        self._dynamips_path = None
        self._dynamips_ids = {}

    def get_dynamips_id(self, project_id):
        """
        :param project_id: UUID of the project
        :returns: a free dynamips id
        """
        self._dynamips_ids.setdefault(project_id, set())
        dynamips_id = 0
        for dynamips_id in range(1, 4097):
            if dynamips_id not in self._dynamips_ids[project_id]:
                self._dynamips_ids[project_id].add(dynamips_id)
                return dynamips_id
        raise DynamipsError("Maximum number of Dynamips instances reached")

    def take_dynamips_id(self, project_id, dynamips_id):
        """
        Reserve a dynamips id or raise an error

        :param project_id: UUID of the project
        :param dynamips_id: Asked id
        """
        self._dynamips_ids.setdefault(project_id, set())
        if dynamips_id in self._dynamips_ids[project_id]:
            raise DynamipsError("Dynamips identifier {} is already used by another router".format(dynamips_id))
        self._dynamips_ids[project_id].add(dynamips_id)

    def release_dynamips_id(self, project_id, dynamips_id):
        """
        A dynamips id can be reused by another vm

        :param project_id: UUID of the project
        :param dynamips_id: Asked id
        """
        self._dynamips_ids.setdefault(project_id, set())
        if dynamips_id in self._dynamips_ids[project_id]:
            self._dynamips_ids[project_id].remove(dynamips_id)

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
                except (Exception, GeneratorExit) as e:
                    log.error("Could not stop device hypervisor {}".format(e), exc_info=1)
                    continue

    @asyncio.coroutine
    def project_closing(self, project):
        """
        Called when a project is about to be closed.

        :param project: Project instance
        """

        yield from super().project_closing(project)
        # delete the Dynamips devices corresponding to the project
        tasks = []
        for device in self._devices.values():
            if device.project.id == project.id:
                tasks.append(asyncio.async(device.delete()))

        if tasks:
            done, _ = yield from asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except (Exception, GeneratorExit) as e:
                    log.error("Could not delete device {}".format(e), exc_info=1)

    @asyncio.coroutine
    def project_closed(self, project):
        """
        Called when a project is closed.

        :param project: Project instance
        """
        yield from super().project_closed(project)
        # delete useless Dynamips files
        project_dir = project.module_working_path(self.module_name.lower())

        files = glob.glob(os.path.join(glob.escape(project_dir), "*.ghost"))
        files += glob.glob(os.path.join(glob.escape(project_dir), "*_lock"))
        files += glob.glob(os.path.join(glob.escape(project_dir), "ilt_*"))
        files += glob.glob(os.path.join(glob.escape(project_dir), "c[0-9][0-9][0-9][0-9]_i[0-9]*_rommon_vars"))
        files += glob.glob(os.path.join(glob.escape(project_dir), "c[0-9][0-9][0-9][0-9]_i[0-9]*_log.txt"))
        for file in files:
            try:
                log.debug("Deleting file {}".format(file))
                if file in self._ghost_files:
                    self._ghost_files.remove(file)
                yield from wait_run_in_executor(os.remove, file)
            except OSError as e:
                log.warn("Could not delete file {}: {}".format(file, e))
                continue

        # Release the dynamips ids if we want to reload the same project
        # later
        if project.id in self._dynamips_ids:
            del self._dynamips_ids[project.id]

    @asyncio.coroutine
    def project_moved(self, project):
        """
        Called when a project is moved.

        :param project: Project instance
        """

        for vm in self._vms.values():
            if vm.project.id == project.id:
                yield from vm.hypervisor.set_working_dir(project.module_working_directory(self.module_name.lower()))

        for device in self._devices.values():
            if device.project.id == project.id:
                yield from device.hypervisor.set_working_dir(project.module_working_directory(self.module_name.lower()))

    @asyncio.coroutine
    def project_committed(self, project):
        """
        Called when a project has been committed.

        :param project: Project instance
        """

        # save the configs when the project is committed
        for vm in self._vms.copy().values():
            if vm.project.id == project.id:
                try:
                    yield from vm.save_configs()
                except DynamipsError as e:
                    log.warning(e)
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
        if device_id and isinstance(device_id, int):
            with (yield from BaseManager._convert_lock):
                device_id = yield from self.convert_old_project(project, device_id, name)

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

        # FIXME: hypervisor should always listen to 127.0.0.1
        # See https://github.com/GNS3/dynamips/issues/62
        server_config = self.config.get_section_config("Server")
        server_host = server_config.get("host")

        try:
            info = socket.getaddrinfo(server_host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
            if not info:
                raise DynamipsError("getaddrinfo returns an empty list on {}".format(server_host))
            for res in info:
                af, socktype, proto, _, sa = res
                # let the OS find an unused port for the Dynamips hypervisor
                with socket.socket(af, socktype, proto) as sock:
                    sock.bind(sa)
                    port = sock.getsockname()[1]
                    break
        except OSError as e:
            raise DynamipsError("Could not find free port for the Dynamips hypervisor: {}".format(e))

        port_manager = PortManager.instance()
        hypervisor = Hypervisor(self._dynamips_path, working_dir, server_host, port, port_manager.console_host)

        log.info("Creating new hypervisor {}:{} with working directory {}".format(hypervisor.host, hypervisor.port, working_dir))
        yield from hypervisor.start()
        log.info("Hypervisor {}:{} has successfully started".format(hypervisor.host, hypervisor.port))
        yield from hypervisor.connect()
        if parse_version(hypervisor.version) < parse_version('0.2.11'):
            raise DynamipsError("Dynamips version must be >= 0.2.11, detected version is {}".format(hypervisor.version))

        return hypervisor

    @asyncio.coroutine
    def ghost_ios_support(self, vm):

        ghost_ios_support = self.config.get_section_config("Dynamips").getboolean("ghost_ios_support", True)
        if ghost_ios_support:
            with (yield from Dynamips._ghost_ios_lock):
                try:
                    yield from self._set_ghost_ios(vm)
                except GeneratorExit:
                    log.warning("Could not create ghost IOS image {} (GeneratorExit)".format(vm.name))

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
                info = socket.getaddrinfo(rhost, rport, socket.AF_UNSPEC, socket.SOCK_DGRAM, 0, socket.AI_PASSIVE)
                if not info:
                    raise DynamipsError("getaddrinfo returns an empty list on {}:{}".format(rhost, rport))
                for res in info:
                    af, socktype, proto, _, sa = res
                    with socket.socket(af, socktype, proto) as sock:
                        sock.connect(sa)
            except OSError as e:
                raise DynamipsError("Could not create an UDP connection to {}:{}: {}".format(rhost, rport, e))
            nio = NIOUDP(node.hypervisor, lport, rhost, rport)
        elif nio_settings["type"] == "nio_generic_ethernet":
            ethernet_device = nio_settings["ethernet_device"]
            if sys.platform.startswith("win"):
                # replace the interface name by the GUID on Windows
                windows_interfaces = interfaces()
                npf_interface = None
                for interface in windows_interfaces:
                    if interface["name"] == ethernet_device:
                        npf_interface = interface["id"]
                if not npf_interface:
                    raise DynamipsError("Could not find interface {} on this host".format(ethernet_device))
                else:
                    ethernet_device = npf_interface
            if not is_interface_up(ethernet_device):
                raise aiohttp.web.HTTPConflict(text="Ethernet interface {} is down".format(ethernet_device))
            nio = NIOGenericEthernet(node.hypervisor, ethernet_device)
        elif nio_settings["type"] == "nio_linux_ethernet":
            if sys.platform.startswith("win"):
                raise DynamipsError("This NIO type is not supported on Windows")
            ethernet_device = nio_settings["ethernet_device"]
            nio = NIOLinuxEthernet(node.hypervisor, ethernet_device)
        elif nio_settings["type"] == "nio_tap":
            tap_device = nio_settings["tap_device"]
            nio = NIOTAP(node.hypervisor, tap_device)
            if not is_interface_up(tap_device):
                # test after the TAP interface has been created (if it doesn't exist yet)
                raise aiohttp.web.HTTPConflict(text="TAP interface {} is down".format(tap_device))
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
        else:
            raise aiohttp.web.HTTPConflict(text="NIO of type {} is not supported".format(nio_settings["type"]))

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

        if vm.platform == "c7200" and vm.npe == "npe-g2":
            log.warning("Ghost IOS is not supported for c7200 with NPE-G2")
            return

        ghost_file = vm.formatted_ghost_file()
        ghost_file_path = os.path.join(vm.hypervisor.working_dir, ghost_file)
        if ghost_file_path not in self._ghost_files:
            # create a new ghost IOS instance
            ghost_id = str(uuid4())
            ghost = Router("ghost-" + ghost_file, ghost_id, vm.project, vm.manager, platform=vm.platform, hypervisor=vm.hypervisor, ghost_flag=True)
            try:
                yield from ghost.create()
                yield from ghost.set_image(vm.image)
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
            except DynamipsError as e:
                log.warn("Could not create ghost instance: {}".format(e))

        if vm.ghost_file != ghost_file and os.path.isfile(ghost_file_path):
            # set the ghost file to the router
            yield from vm.set_ghost_status(2)
            yield from vm.set_ghost_file(ghost_file)

    @asyncio.coroutine
    def update_vm_settings(self, vm, settings):
        """
        Updates the VM settings.

        :param vm: VM instance
        :param settings: settings to update (dict)
        """

        for name, value in settings.items():
            if hasattr(vm, name) and getattr(vm, name) != value:
                if hasattr(vm, "set_{}".format(name)):
                    setter = getattr(vm, "set_{}".format(name))
                    yield from setter(value)
            elif name.startswith("slot") and value in ADAPTER_MATRIX:
                slot_id = int(name[-1])
                adapter_name = value
                adapter = ADAPTER_MATRIX[adapter_name]()
                try:
                    if vm.slots[slot_id] and not isinstance(vm.slots[slot_id], type(adapter)):
                        yield from vm.slot_remove_binding(slot_id)
                    if not isinstance(vm.slots[slot_id], type(adapter)):
                        yield from vm.slot_add_binding(slot_id, adapter)
                except IndexError:
                    raise DynamipsError("Slot {} doesn't exist on this router".format(slot_id))
            elif name.startswith("slot") and value is None:
                slot_id = int(name[-1])
                try:
                    if vm.slots[slot_id]:
                        yield from vm.slot_remove_binding(slot_id)
                except IndexError:
                    raise DynamipsError("Slot {} doesn't exist on this router".format(slot_id))
            elif name.startswith("wic") and value in WIC_MATRIX:
                wic_slot_id = int(name[-1])
                wic_name = value
                wic = WIC_MATRIX[wic_name]()
                try:
                    if vm.slots[0].wics[wic_slot_id] and not isinstance(vm.slots[0].wics[wic_slot_id], type(wic)):
                        yield from vm.uninstall_wic(wic_slot_id)
                    if not isinstance(vm.slots[0].wics[wic_slot_id], type(wic)):
                        yield from vm.install_wic(wic_slot_id, wic)
                except IndexError:
                    raise DynamipsError("WIC slot {} doesn't exist on this router".format(wic_slot_id))
            elif name.startswith("wic") and value is None:
                wic_slot_id = int(name[-1])
                try:
                    if vm.slots[0].wics and vm.slots[0].wics[wic_slot_id]:
                        yield from vm.uninstall_wic(wic_slot_id)
                except IndexError:
                    raise DynamipsError("WIC slot {} doesn't exist on this router".format(wic_slot_id))

        mmap_support = self.config.get_section_config("Dynamips").getboolean("mmap_support", True)
        if mmap_support is False:
            yield from vm.set_mmap(False)

        sparse_memory_support = self.config.get_section_config("Dynamips").getboolean("sparse_memory_support", True)
        if sparse_memory_support is False:
            yield from vm.set_sparsemem(False)

        # update the configs if needed
        yield from self.set_vm_configs(vm, settings)

    @asyncio.coroutine
    def set_vm_configs(self, vm, settings):
        """
        Set VM configs from pushed content or existing config files.

        :param vm: VM instance
        :param settings: VM settings
        """

        module_workdir = vm.project.module_working_directory(self.module_name.lower())
        default_startup_config_path = os.path.join(module_workdir, "configs", "i{}_startup-config.cfg".format(vm.dynamips_id))
        default_private_config_path = os.path.join(module_workdir, "configs", "i{}_private-config.cfg".format(vm.dynamips_id))

        startup_config_path = settings.get("startup_config")
        startup_config_content = settings.get("startup_config_content")
        if startup_config_path:
            yield from vm.set_configs(startup_config_path)
        elif startup_config_content:
            startup_config_path = self._create_config(vm, default_startup_config_path, startup_config_content)
            yield from vm.set_configs(startup_config_path)
        elif os.path.isfile(default_startup_config_path) and os.path.getsize(default_startup_config_path) == 0:
            # An empty startup-config may crash Dynamips
            startup_config_path = self._create_config(vm, default_startup_config_path, "!\n")
            yield from vm.set_configs(startup_config_path)

        private_config_path = settings.get("private_config")
        private_config_content = settings.get("private_config_content")
        if private_config_path:
            yield from vm.set_configs(vm.startup_config, private_config_path)
        elif private_config_content:
            private_config_path = self._create_config(vm, default_private_config_path, private_config_content)
            yield from vm.set_configs(vm.startup_config, private_config_path)

    def _create_config(self, vm, path, content=None):
        """
        Creates a config file.

        :param vm: VM instance
        :param path: path to the destination config file
        :param content: config content

        :returns: relative path to the created config file
        """

        log.info("Creating config file {}".format(path))
        config_dir = os.path.dirname(path)
        try:
            os.makedirs(config_dir, exist_ok=True)
        except OSError as e:
            raise DynamipsError("Could not create Dynamips configs directory: {}".format(e))

        try:
            with open(path, "wb") as f:
                if content:
                    content = "!\n" + content.replace("\r", "")
                    content = content.replace('%h', vm.name)
                    f.write(content.encode("utf-8"))
        except OSError as e:
            raise DynamipsError("Could not create config file {}: {}".format(path, e))

        return os.path.join("configs", os.path.basename(path))

    @asyncio.coroutine
    def auto_idlepc(self, vm):
        """
        Try to find the best possible idle-pc value.

        :param vm: VM instance
        """

        yield from vm.set_idlepc("0x0")
        was_auto_started = False
        try:
            status = yield from vm.get_status()
            if status != "running":
                yield from vm.start()
                was_auto_started = True
                yield from asyncio.sleep(20)  # leave time to the router to boot
            validated_idlepc = None
            idlepcs = yield from vm.get_idle_pc_prop()
            if not idlepcs:
                raise DynamipsError("No Idle-PC values found")

            for idlepc in idlepcs:
                yield from vm.set_idlepc(idlepc.split()[0])
                log.debug("Auto Idle-PC: trying idle-PC value {}".format(vm.idlepc))
                start_time = time.time()
                initial_cpu_usage = yield from vm.get_cpu_usage()
                log.debug("Auto Idle-PC: initial CPU usage is {}%".format(initial_cpu_usage))
                yield from asyncio.sleep(3)  # wait 3 seconds to probe the cpu again
                elapsed_time = time.time() - start_time
                cpu_usage = yield from vm.get_cpu_usage()
                cpu_elapsed_usage = cpu_usage - initial_cpu_usage
                cpu_usage = abs(cpu_elapsed_usage * 100.0 / elapsed_time)
                if cpu_usage > 100:
                    cpu_usage = 100
                log.debug("Auto Idle-PC: CPU usage is {}% after {:.2} seconds".format(cpu_usage, elapsed_time))
                if cpu_usage < 70:
                    validated_idlepc = vm.idlepc
                    log.debug("Auto Idle-PC: idle-PC value {} has been validated".format(validated_idlepc))
                    break

            if validated_idlepc is None:
                raise DynamipsError("Sorry, no idle-pc value was suitable")

        except DynamipsError:
            raise
        finally:
            if was_auto_started:
                yield from vm.stop()
        return validated_idlepc

    def get_images_directory(self):
        """
        Return the full path of the images directory on disk
        """
        return os.path.join(os.path.expanduser(self.config.get_section_config("Server").get("images_path", "~/GNS3/images")), "IOS")

    @asyncio.coroutine
    def list_images(self):
        """
        Return the list of available IOS images.

        :returns: Array of hash
        """

        image_dir = self.get_images_directory()
        if not os.path.exists(image_dir):
            return []
        try:
            files = os.listdir(image_dir)
        except OSError as e:
            raise DynamipsError("Can not list {}: {}".format(image_dir, str(e)))
        files.sort()
        images = []
        for filename in files:
            if filename[0] != "." and not filename.endswith(".md5sum"):
                try:
                    path = os.path.join(image_dir, filename)
                    with open(path, "rb") as f:
                        # read the first 7 bytes of the file.
                        elf_header_start = f.read(7)
                except OSError as e:
                    continue
                # valid IOS images must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
                if elf_header_start == b'\x7fELF\x01\x02\x01':
                    path = os.path.relpath(path, image_dir)
                    images.append({"filename": filename, "path": path})
        return images
