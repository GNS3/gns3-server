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
Interface for Dynamips virtual Machine module ("vm")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L77
"""

import asyncio
import base64
import binascii
import contextlib
import glob
import logging
import os
import re
import shutil
import time

log = logging.getLogger(__name__)

from gns3server.utils.asyncio import monitor_process, wait_run_in_executor
from gns3server.utils.file_watcher import FileWatcher
from gns3server.utils.hostname import is_ios_hostname_valid
from gns3server.utils.images import md5sum
from gns3server.utils.kernel_anchor import kernel_anchor_name

from ...base_node import BaseNode
from ...error import NodeError
from ...kernel_datapath import KernelDatapathMixin
from ...nios.nio_bridge import NIOBridge
from ...ubridge.ubridge_error import UbridgeError
from ..adapters.adapter import ETHERNET_ADAPTERS, ETHERNET_WICS
from ..dynamips_error import DynamipsError
from ..nios.nio_tap import NIOTAP


class Router(KernelDatapathMixin, BaseNode):
    """
    Dynamips router implementation.

    :param name: The name of this router
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param dynamips_id: ID to use with Dynamips
    :param console: console port
    :param console_type: console type
    :param aux: auxiliary console port
    :param aux_type: auxiliary console type
    :param platform: Platform of this router
    """

    _status = {0: "inactive", 1: "shutting down", 2: "running", 3: "suspended"}

    def __init__(
        self,
        name,
        node_id,
        project,
        manager,
        dynamips_id=None,
        console=None,
        console_type="telnet",
        aux=None,
        aux_type="none",
        platform="c7200",
        hypervisor=None,
        ghost_flag=False,
    ):

        if not ghost_flag and not is_ios_hostname_valid(name):
            raise DynamipsError(f"{name} is an invalid name to create a Dynamips node")

        super().__init__(
            name,
            node_id,
            project,
            manager,
            console=console,
            console_type=console_type,
            aux=aux,
            aux_type=aux_type,
            wrap_console=(console_type == "ssh"),
            wrap_aux=(aux_type == "ssh"),
        )

        self._working_directory = os.path.join(
            self.project.module_working_directory(self.manager.module_name.lower()), self.id
        )
        try:
            os.makedirs(os.path.join(self._working_directory, "configs"), exist_ok=True)
        except OSError as e:
            raise DynamipsError(f"Can't create the dynamips config directory: {e!s}")
        if dynamips_id:
            self._convert_before_2_0_0_b3(dynamips_id)

        self._hypervisor = hypervisor
        self._dynamips_id = dynamips_id
        self._platform = platform
        self._image = ""
        self._ram = 128  # Megabytes
        self._nvram = 128  # Kilobytes
        self._mmap = True
        self._sparsemem = True
        self._clock_divisor = 8
        self._idlepc = ""
        self._idlemax = 500
        self._idlesleep = 30
        self._ghost_file = ""
        self._ghost_status = 0
        self._exec_area = 64
        self._disk0 = 0  # Megabytes
        self._disk1 = 0  # Megabytes
        self._auto_delete_disks = False
        self._mac_addr = ""
        self._system_id = "FTX0945W0MY"  # processor board ID in IOS
        self._slots = []
        self._ghost_flag = ghost_flag
        self._memory_watcher = None
        # Kernel datapath: the persistent anchor TAP per Ethernet slot/port
        # (in _kernel_taps) and the hypervisor TAP NIO holding each anchor
        # open while a kernel link binds the port (in _tap_nios).
        self._kernel_taps = {}
        self._tap_nios = {}
        self._tap_datapath = False
        self._ubridge_tc_caps = None

        if not ghost_flag:
            if not dynamips_id:
                self._dynamips_id = manager.get_dynamips_id(project.id)
            else:
                self._dynamips_id = dynamips_id
                manager.take_dynamips_id(project.id, dynamips_id)
        else:
            log.debug("Creating a new ghost IOS instance")
            if self._console:
                # Ghost VMs do not need a console port.
                self.console = None

            self._dynamips_id = 0
            self._name = "Ghost"

    def _convert_before_2_0_0_b3(self, dynamips_id):
        """
        Before 2.0.0 beta3 the node didn't have a folder by node
        when we start we move the file, we can't do it in the topology
        conversion due to case of remote servers
        """
        dynamips_dir = self.project.module_working_directory(self.manager.module_name.lower())
        for path in glob.glob(os.path.join(glob.escape(dynamips_dir), "configs", f"i{dynamips_id}_*")):
            dst = os.path.join(self._working_directory, "configs", os.path.basename(path))
            if not os.path.exists(dst):
                try:
                    shutil.move(path, dst)
                except OSError as e:
                    log.error(f"Can't move {path}: {e!s}")
                    continue
        for path in glob.glob(os.path.join(glob.escape(dynamips_dir), f"*_i{dynamips_id}_*")):
            dst = os.path.join(self._working_directory, os.path.basename(path))
            if not os.path.exists(dst):
                try:
                    shutil.move(path, dst)
                except OSError as e:
                    log.error(f"Can't move {path}: {e!s}")
                    continue

    def asdict(self):

        router_info = {
            "name": self.name,
            "usage": self.usage,
            "node_id": self.id,
            "node_directory": os.path.join(self._working_directory),
            "project_id": self.project.id,
            "dynamips_id": self._dynamips_id,
            "platform": self._platform,
            "image": self._image,
            "image_md5sum": md5sum(self._image, self._working_directory),
            "ram": self._ram,
            "nvram": self._nvram,
            "mmap": self._mmap,
            "sparsemem": self._sparsemem,
            "clock_divisor": self._clock_divisor,
            "idlepc": self._idlepc,
            "idlemax": self._idlemax,
            "idlesleep": self._idlesleep,
            "exec_area": self._exec_area,
            "disk0": self._disk0,
            "disk1": self._disk1,
            "auto_delete_disks": self._auto_delete_disks,
            "status": self.status,
            "console": self.console,
            "console_type": self.console_type,
            "aux": self.aux,
            "aux_type": self.aux_type,
            "mac_addr": self._mac_addr,
            "system_id": self._system_id,
        }

        router_info["image"] = self.manager.get_relative_image_path(self._image, self.project.path)

        # add the slots
        slot_number = 0
        for slot in self._slots:
            if slot:
                slot = str(slot)
            router_info["slot" + str(slot_number)] = slot
            slot_number += 1

        # add the wics
        if len(self._slots) > 0 and self._slots[0] and self._slots[0].wics:
            for wic_slot_number in range(0, len(self._slots[0].wics)):
                if self._slots[0].wics[wic_slot_number]:
                    router_info["wic" + str(wic_slot_number)] = str(self._slots[0].wics[wic_slot_number])
                else:
                    router_info["wic" + str(wic_slot_number)] = None

        return router_info

    def _memory_changed(self, path):
        """
        Called when the NVRAM file has changed
        """
        asyncio.ensure_future(self.save_configs())

    @property
    def dynamips_id(self):
        """
        Returns the Dynamips VM ID.

        :return: Dynamips VM identifier
        """

        return self._dynamips_id

    async def create(self):

        if not self._hypervisor:
            # We start the hypervisor is the dynamips folder and next we change to node dir
            # this allow the creation of common files in the dynamips folder
            self._hypervisor = await self.manager.start_new_hypervisor(
                working_dir=self.project.module_working_directory(self.manager.module_name.lower())
            )
            await self._hypervisor.set_working_dir(self._working_directory)

        await self._hypervisor.send(f'vm create "{self._name}" {self._dynamips_id} {self._platform}')

        if not self._ghost_flag:
            log.debug(f'Router {self._platform} "{self._name}" [{self._id}] has been created')

            if self._console is not None:
                # For SSH console, tell Dynamips to listen on the internal port so that
                # the AsyncioSSHServer proxy can wrap it on the external console port.
                con_port = (
                    self._internal_console_port if self._wrap_console and self._internal_console_port else self._console
                )
                await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {con_port}')

            if self.aux is not None:
                aux_port = self._internal_aux_port if self._wrap_aux and self._internal_aux_port else self.aux
                await self._hypervisor.send(f'vm set_aux_tcp_port "{self._name}" {aux_port}')

            # get the default base MAC address
            mac_addr = await self._hypervisor.send(f'{self._platform} get_mac_addr "{self._name}"')
            self._mac_addr = mac_addr[0]

        self._hypervisor.devices.append(self)

    async def get_status(self):
        """
        Returns the status of this router

        :returns: inactive, shutting down, running or suspended.
        """

        status = await self._hypervisor.send(f'vm get_status "{self._name}"')
        if len(status) == 0:
            raise DynamipsError(f"Can't get vm {self._name} status")
        return self._status[int(status[0])]

    async def start(self):
        """
        Starts this router.
        At least the IOS image must be set before it can start.
        """

        status = await self.get_status()
        if status == "suspended":
            await self.resume()
        elif status == "inactive":
            if not os.path.isfile(self._image) or not os.path.exists(self._image):
                if os.path.islink(self._image):
                    raise DynamipsError(
                        f'IOS image "{self._image}" linked to "{os.path.realpath(self._image)}" is not accessible'
                    )
                else:
                    raise DynamipsError(f'IOS image "{self._image}" is not accessible')

            try:
                with open(self._image, "rb") as f:
                    # read the first 7 bytes of the file.
                    elf_header_start = f.read(7)
            except OSError as e:
                raise DynamipsError(f'Cannot read ELF header for IOS image "{self._image}": {e}')

            # IOS images must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
            if elf_header_start != b"\x7fELF\x01\x02\x01":
                raise DynamipsError(f'"{self._image}" is not a valid IOS image')

            # check if there is enough RAM to run
            if not self._ghost_flag:
                self.check_available_ram(self.ram)

            # config paths are relative to the working directory configured on Dynamips hypervisor
            startup_config_path = os.path.join("configs", f"i{self._dynamips_id}_startup-config.cfg")
            private_config_path = os.path.join("configs", f"i{self._dynamips_id}_private-config.cfg")

            if not os.path.exists(os.path.join(self._working_directory, private_config_path)) or not os.path.getsize(
                os.path.join(self._working_directory, private_config_path)
            ):
                # an empty private-config can prevent a router to boot.
                private_config_path = ""

            # uBridge owns the kernel datapath's anchor TAPs; start it and
            # create them before the VM boots, so kernel links bound while
            # the node was stopped wire themselves as IOS comes up.
            await self._prepare_tap_datapath()

            await self._hypervisor.send(f'vm set_config "{self._name}" "{startup_config_path}" "{private_config_path}"')
            await self._hypervisor.send(f'vm start "{self._name}"')
            self.status = "started"
            log.debug(f'router "{self._name}" [{self._id}] has been started')

            self._memory_watcher = FileWatcher(self._memory_files(), self._memory_changed, strategy="hash", delay=30)
            monitor_process(self._hypervisor.process, self._termination_callback)

        if self._wrap_console or self._wrap_aux:
            try:
                await self.start_wrap_console()
            except OSError as e:
                raise DynamipsError(f"Could not start Dynamips console wrapper: {e}")

    async def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self.status == "started":
            self.status = "stopped"
            log.debug("Dynamips hypervisor process has stopped, return code: %d", returncode)
            if returncode != 0:
                self.project.emit(
                    "log.error",
                    {
                        "message": f"Dynamips hypervisor process has stopped, return code: {returncode}\n{self._hypervisor.read_stdout()}"
                    },
                )

    async def stop(self):
        """
        Stops this router.
        """

        status = await self.get_status()
        if status != "inactive":
            try:
                await self._hypervisor.send(f'vm stop "{self._name}"')
            except DynamipsError as e:
                log.warning(f"Could not stop {self._name}: {e}")
            self.status = "stopped"
            log.debug(f'Router "{self._name}" [{self._id}] has been stopped')
        if self._memory_watcher:
            self._memory_watcher.close()
            self._memory_watcher = None
        await self.save_configs()
        await self.stop_wrap_console()

    async def reload(self):
        """
        Reload this router.
        """

        await self.stop()
        await self.start()

    async def suspend(self):
        """
        Suspends this router.
        """

        status = await self.get_status()
        if status == "running":
            await self._hypervisor.send(f'vm suspend "{self._name}"')
            self.status = "suspended"
            log.debug(f'Router "{self._name}" [{self._id}] has been suspended')

    async def resume(self):
        """
        Resumes this suspended router
        """

        status = await self.get_status()
        if status == "suspended":
            await self._hypervisor.send(f'vm resume "{self._name}"')
            self.status = "started"
        log.debug(f'Router "{self._name}" [{self._id}] has been resumed')

    async def is_running(self):
        """
        Checks if this router is running.

        :returns: True if running, False otherwise
        """

        status = await self.get_status()
        if status == "running":
            return True
        return False

    async def close(self):

        if not (await super().close()):
            return False

        for adapter in self._slots:
            if adapter is not None:
                for nio in adapter.ports.values():
                    # NIOBridge has no hypervisor side to close here — its
                    # release runs in _stop_ubridge below.
                    if nio and not isinstance(nio, NIOBridge):
                        await nio.close()

        await self._stop_ubridge()

        if self in self._hypervisor.devices:
            self._hypervisor.devices.remove(self)
        if self._hypervisor and not self._hypervisor.devices:
            try:
                await self.stop()
                await self._hypervisor.send(f'vm delete "{self._name}"')
            except DynamipsError as e:
                log.warning(f"Could not stop and delete {self._name}: {e}")
            await self.hypervisor.stop()

        if self._auto_delete_disks:
            # delete nvram and disk files
            files = glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_disk[0-1]")
            )
            files += glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_slot[0-1]")
            )
            files += glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_nvram")
            )
            files += glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_flash[0-1]")
            )
            files += glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_rom")
            )
            files += glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_bootflash")
            )
            files += glob.glob(
                os.path.join(glob.escape(self._working_directory), f"{self.platform}_i{self.dynamips_id}_ssa")
            )
            for file in files:
                try:
                    log.debug(f"Deleting file {file}")
                    await wait_run_in_executor(os.remove, file)
                except OSError as e:
                    log.warning(f"Could not delete file {file}: {e}")
                    continue
        self.manager.release_dynamips_id(self.project.id, self.dynamips_id)

    @property
    def platform(self):
        """
        Returns the platform of this router.

        :returns: platform name (string):
        c7200, c3745, c3725, c3600, c2691, c2600 or c1700
        """

        return self._platform

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor instance
        """

        return self._hypervisor

    async def list(self):
        """
        Returns all VM instances

        :returns: list of all VM instances
        """

        vm_list = await self._hypervisor.send("vm list")
        return vm_list

    async def list_con_ports(self):
        """
        Returns all VM console TCP ports

        :returns: list of port numbers
        """

        port_list = await self._hypervisor.send("vm list_con_ports")
        return port_list

    async def set_debug_level(self, level):
        """
        Sets the debug level for this router (default is 0).

        :param level: level number
        """

        await self._hypervisor.send(f'vm set_debug_level "{self._name}" {level}')

    @property
    def image(self):
        """
        Returns this IOS image for this router.

        :returns: path to IOS image file
        """

        return self._image

    async def set_image(self, image):
        """
        Sets the IOS image for this router.
        There is no default.

        :param image: path to IOS image file
        """

        image = self.manager.get_abs_image_path(image, self.project.path)

        await self._hypervisor.send(f'vm set_ios "{self._name}" "{image}"')

        log.debug(f'Router "{self._name}" [{self._id}]: has a new IOS image set: "{image}"')

        self._image = image

    @property
    def ram(self):
        """
        Returns the amount of RAM allocated to this router.

        :returns: amount of RAM in Mbytes (integer)
        """

        return self._ram

    async def set_ram(self, ram):
        """
        Sets amount of RAM allocated to this router

        :param ram: amount of RAM in Mbytes (integer)
        """

        if self._ram == ram:
            return

        await self._hypervisor.send(f'vm set_ram "{self._name}" {ram}')
        log.debug(f'Router "{self._name}" [{self._id}]: RAM updated from {self._ram}MB to {ram}MB')
        self._ram = ram

    @property
    def nvram(self):
        """
        Returns the mount of NVRAM allocated to this router.

        :returns: amount of NVRAM in Kbytes (integer)
        """

        return self._nvram

    async def set_nvram(self, nvram):
        """
        Sets amount of NVRAM allocated to this router

        :param nvram: amount of NVRAM in Kbytes (integer)
        """

        if self._nvram == nvram:
            return

        await self._hypervisor.send(f'vm set_nvram "{self._name}" {nvram}')
        log.debug(f'Router "{self._name}" [{self._id}]: NVRAM updated from {self._nvram}KB to {nvram}KB')
        self._nvram = nvram

    @property
    def mmap(self):
        """
        Returns True if a mapped file is used to simulate this router memory.

        :returns: boolean either mmap is activated or not
        """

        return self._mmap

    async def set_mmap(self, mmap):
        """
        Enable/Disable use of a mapped file to simulate router memory.
        By default, a mapped file is used. This is a bit slower, but requires less memory.

        :param mmap: activate/deactivate mmap (boolean)
        """

        if mmap:
            flag = 1
        else:
            flag = 0

        await self._hypervisor.send(f'vm set_ram_mmap "{self._name}" {flag}')

        if mmap:
            log.debug(f'Router "{self._name}" [{self._id}]: mmap enabled')
        else:
            log.debug(f'Router "{self._name}" [{self._id}]: mmap disabled')
        self._mmap = mmap

    @property
    def sparsemem(self):
        """
        Returns True if sparse memory is used on this router.

        :returns: boolean either mmap is activated or not
        """

        return self._sparsemem

    async def set_sparsemem(self, sparsemem):
        """
        Enable/disable use of sparse memory

        :param sparsemem: activate/deactivate sparsemem (boolean)
        """

        if sparsemem:
            flag = 1
        else:
            flag = 0
        await self._hypervisor.send(f'vm set_sparse_mem "{self._name}" {flag}')

        if sparsemem:
            log.debug(f'Router "{self._name}" [{self._id}]: sparse memory enabled')
        else:
            log.debug(f'Router "{self._name}" [{self._id}]: sparse memory disabled')
        self._sparsemem = sparsemem

    @property
    def clock_divisor(self):
        """
        Returns the clock divisor value for this router.

        :returns: clock divisor value (integer)
        """

        return self._clock_divisor

    async def set_clock_divisor(self, clock_divisor):
        """
        Sets the clock divisor value. The higher is the value, the faster is the clock in the
        virtual machine. The default is 4, but it is often required to adjust it.

        :param clock_divisor: clock divisor value (integer)
        """

        await self._hypervisor.send(f'vm set_clock_divisor "{self._name}" {clock_divisor}')
        log.debug(
            f'Router "{self._name}" [{self._id}]: clock divisor updated from {self._clock_divisor} to {clock_divisor}'
        )
        self._clock_divisor = clock_divisor

    @property
    def idlepc(self):
        """
        Returns the idle Pointer Counter (PC).

        :returns: idlepc value (string)
        """

        return self._idlepc

    async def set_idlepc(self, idlepc):
        """
        Sets the idle Pointer Counter (PC)

        :param idlepc: idlepc value (string)
        """

        if not idlepc:
            idlepc = "0x0"

        is_running = await self.is_running()
        if not is_running:
            # router is not running
            await self._hypervisor.send(f'vm set_idle_pc "{self._name}" {idlepc}')
        else:
            await self._hypervisor.send(f'vm set_idle_pc_online "{self._name}" 0 {idlepc}')

        log.debug(f'Router "{self._name}" [{self._id}]: idle-PC set to {idlepc}')
        self._idlepc = idlepc

    async def get_idle_pc_prop(self):
        """
        Gets the idle PC proposals.
        Takes 1000 measurements and records up to 10 idle PC proposals.
        There is a 10ms wait between each measurement.

        :returns: list of idle PC proposal
        """

        is_running = await self.is_running()
        was_auto_started = False
        if not is_running:
            await self.start()
            was_auto_started = True
            await asyncio.sleep(20)  # leave time to the router to boot

        log.debug(f'Router "{self._name}" [{self._id}] has started calculating Idle-PC values')
        begin = time.time()
        idlepcs = await self._hypervisor.send(f'vm get_idle_pc_prop "{self._name}" 0')
        log.debug(
            f'Router "{self._name}" [{self._id}] has finished calculating Idle-PC values after {time.time() - begin:.4f} seconds'
        )
        if was_auto_started:
            await self.stop()
        return idlepcs

    async def show_idle_pc_prop(self):
        """
        Dumps the idle PC proposals (previously generated).

        :returns: list of idle PC proposal
        """

        is_running = await self.is_running()
        if not is_running:
            # router is not running
            raise DynamipsError(f'Router "{self._name}" is not running')

        proposals = await self._hypervisor.send(f'vm show_idle_pc_prop "{self._name}" 0')
        return proposals

    @property
    def idlemax(self):
        """
        Returns CPU idle max value.

        :returns: idle max (integer)
        """

        return self._idlemax

    async def set_idlemax(self, idlemax):
        """
        Sets CPU idle max value

        :param idlemax: idle max value (integer)
        """

        is_running = await self.is_running()
        if is_running:  # router is running
            await self._hypervisor.send(f'vm set_idle_max "{self._name}" 0 {idlemax}')

        log.debug(f'Router "{self._name}" [{self._id}]: idlemax updated from {self._idlemax} to {idlemax}')

        self._idlemax = idlemax

    @property
    def idlesleep(self):
        """
        Returns CPU idle sleep time value.

        :returns: idle sleep (integer)
        """

        return self._idlesleep

    async def set_idlesleep(self, idlesleep):
        """
        Sets CPU idle sleep time value.

        :param idlesleep: idle sleep value (integer)
        """

        is_running = await self.is_running()
        if is_running:  # router is running
            await self._hypervisor.send(f'vm set_idle_sleep_time "{self._name}" 0 {idlesleep}')

        log.debug(f'Router "{self._name}" [{self._id}]: idlesleep updated from {self._idlesleep} to {idlesleep}')

        self._idlesleep = idlesleep

    @property
    def ghost_file(self):
        """
        Returns ghost RAM file.

        :returns: path to ghost file
        """

        return self._ghost_file

    async def set_ghost_file(self, ghost_file):
        """
        Sets ghost RAM file

        :ghost_file: path to ghost file
        """

        await self._hypervisor.send(f'vm set_ghost_file "{self._name}" "{ghost_file}"')

        log.debug(f'Router "{self._name}" [{self._id}]: ghost file set to "{ghost_file}"')

        self._ghost_file = ghost_file

    def formatted_ghost_file(self):
        """
        Returns a properly formatted ghost file name.

        :returns: formatted ghost_file name (string)
        """

        # replace specials characters in 'drive:\filename' in Linux and Dynamips in MS Windows or viceversa.
        ghost_file = f"{os.path.basename(self._image)}-{self._ram}.ghost"
        ghost_file = ghost_file.replace("\\", "-").replace("/", "-").replace(":", "-")
        return ghost_file

    @property
    def ghost_status(self):
        """Returns ghost RAM status

        :returns: ghost status (integer)
        """

        return self._ghost_status

    async def set_ghost_status(self, ghost_status):
        """
        Sets ghost RAM status

        :param ghost_status: state flag indicating status
        0 => Do not use IOS ghosting
        1 => This is a ghost instance
        2 => Use an existing ghost instance
        """

        await self._hypervisor.send(f'vm set_ghost_status "{self._name}" {ghost_status}')

        log.debug(f'Router "{self._name}" [{self._id}]: ghost status set to {ghost_status}')
        self._ghost_status = ghost_status

    @property
    def exec_area(self):
        """
        Returns the exec area value.

        :returns: exec area value (integer)
        """

        return self._exec_area

    async def set_exec_area(self, exec_area):
        """
        Sets the exec area value.
        The exec area is a pool of host memory used to store pages
        translated by the JIT (they contain the native code
        corresponding to MIPS code pages).

        :param exec_area: exec area value (integer)
        """

        await self._hypervisor.send(f'vm set_exec_area "{self._name}" {exec_area}')

        log.debug(f'Router "{self._name}" [{self._id}]: exec area updated from {self._exec_area}MB to {exec_area}MB')
        self._exec_area = exec_area

    @property
    def disk0(self):
        """
        Returns the size (MB) for PCMCIA disk0.

        :returns: disk0 size (integer)
        """

        return self._disk0

    async def set_disk0(self, disk0):
        """
        Sets the size (MB) for PCMCIA disk0.

        :param disk0: disk0 size (integer)
        """

        await self._hypervisor.send(f'vm set_disk0 "{self._name}" {disk0}')

        log.debug(f'Router "{self._name}" [{self._id}]: disk0 updated from {self._disk0}MB to {disk0}MB')
        self._disk0 = disk0

    @property
    def disk1(self):
        """
        Returns the size (MB) for PCMCIA disk1.

        :returns: disk1 size (integer)
        """

        return self._disk1

    async def set_disk1(self, disk1):
        """
        Sets the size (MB) for PCMCIA disk1.

        :param disk1: disk1 size (integer)
        """

        await self._hypervisor.send(f'vm set_disk1 "{self._name}" {disk1}')

        log.debug(f'Router "{self._name}" [{self._id}]: disk1 updated from {self._disk1}MB to {disk1}MB')
        self._disk1 = disk1

    @property
    def auto_delete_disks(self):
        """
        Returns True if auto delete disks is enabled on this router.

        :returns: boolean either auto delete disks is activated or not
        """

        return self._auto_delete_disks

    async def set_auto_delete_disks(self, auto_delete_disks):
        """
        Enable/disable use of auto delete disks

        :param auto_delete_disks: activate/deactivate auto delete disks (boolean)
        """

        if auto_delete_disks:
            log.debug(f'Router "{self._name}" [{self._id}]: auto delete disks enabled')
        else:
            log.debug(f'Router "{self._name}" [{self._id}]: auto delete disks disabled')
        self._auto_delete_disks = auto_delete_disks

    async def set_console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        self.console = console
        con_port = self._internal_console_port if self._wrap_console and self._internal_console_port else self.console
        await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {con_port}')

    async def set_console_type(self, console_type):
        """
        Sets the console type.

        :param console_type: console type
        """

        if self.console_type != console_type:
            status = await self.get_status()
            if status == "running":
                raise DynamipsError(f'"{self._name}" must be stopped to change the console type to {console_type}')

        self.console_type = console_type

        if self._console:
            if console_type == "ssh":
                # Switching to SSH: ensure an internal port is allocated and redirect Dynamips to it.
                self._wrap_console = True
                if self._internal_console_port is None:
                    self._internal_console_port = self._manager.port_manager.get_free_tcp_port(self._project)
                await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {self._internal_console_port}')
            elif console_type == "telnet":
                # Switching to telnet: stop SSH wrapper if running and redirect Dynamips to external port.
                await self.stop_wrap_console()
                self._wrap_console = False
                if self._internal_console_port is not None:
                    self._manager.port_manager.release_tcp_port(self._internal_console_port, self._project)
                    self._internal_console_port = None
                await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {self._console}')

    async def set_aux(self, aux):
        """
        Sets the TCP auxiliary port.

        :param aux: console auxiliary port (integer)
        """

        self.aux = aux
        aux_port = self._internal_aux_port if self._wrap_aux and self._internal_aux_port else self.aux
        await self._hypervisor.send(f'vm set_aux_tcp_port "{self._name}" {aux_port}')

    async def set_aux_type(self, aux_type):
        """
        Sets the aux type.

        :param aux_type: auxiliary console type
        """

        if self.aux_type != aux_type:
            status = await self.get_status()
            if status == "running":
                raise DynamipsError(
                    f'"{self._name}" must be stopped to change the auxiliary console type to {aux_type}'
                )

        self.aux_type = aux_type

        if self._aux:
            if aux_type == "ssh":
                # Switching to SSH: ensure an internal aux port is allocated and redirect Dynamips to it.
                self._wrap_aux = True
                if self._internal_aux_port is None:
                    self._internal_aux_port = self._manager.port_manager.get_free_tcp_port(self._project)
                await self._hypervisor.send(f'vm set_aux_tcp_port "{self._name}" {self._internal_aux_port}')
            elif aux_type == "telnet":
                # Switching to telnet: clear SSH wrapper state and redirect Dynamips to external port.
                self._wrap_aux = False
                if self._internal_aux_port is not None:
                    self._manager.port_manager.release_tcp_port(self._internal_aux_port, self._project)
                    self._internal_aux_port = None
                await self._hypervisor.send(f'vm set_aux_tcp_port "{self._name}" {self._aux}')

    async def reset_console(self):
        """
        Reset console
        """

        pass  # reset console is not supported with Dynamips

    async def get_cpu_usage(self, cpu_id=0):
        """
        Shows cpu usage in seconds, "cpu_id" is ignored.

        :returns: cpu usage in seconds
        """

        cpu_usage = await self._hypervisor.send(f'vm cpu_usage "{self._name}" {cpu_id}')
        return int(cpu_usage[0])

    @property
    def mac_addr(self):
        """
        Returns the MAC address.

        :returns: the MAC address (hexadecimal format: hh:hh:hh:hh:hh:hh)
        """

        return self._mac_addr

    async def set_mac_addr(self, mac_addr):
        """
        Sets the MAC address.

        :param mac_addr: a MAC address (hexadecimal format: hh:hh:hh:hh:hh:hh)
        """

        await self._hypervisor.send(f'{self._platform} set_mac_addr "{self._name}" {mac_addr}')

        log.debug(f'Router "{self._name}" [{self._id}]: MAC address updated from {self._mac_addr} to {mac_addr}')
        self._mac_addr = mac_addr

    @property
    def system_id(self):
        """
        Returns the system ID.

        :returns: the system ID (also called board processor ID)
        """

        return self._system_id

    async def set_system_id(self, system_id):
        """
        Sets the system ID.

        :param system_id: a system ID (also called board processor ID)
        """

        await self._hypervisor.send(f'{self._platform} set_system_id "{self._name}" {system_id}')

        log.debug(f'Router "{self._name}" [{self._id}]: system ID updated from {self._system_id} to {system_id}')
        self._system_id = system_id

    async def get_slot_bindings(self):
        """
        Returns slot bindings.

        :returns: slot bindings (adapter names) list
        """

        slot_bindings = await self._hypervisor.send(f'vm slot_bindings "{self._name}"')
        return slot_bindings

    async def slot_add_binding(self, slot_number, adapter):
        """
        Adds a slot binding (a module into a slot).

        :param slot_number: slot number
        :param adapter: device to add in the corresponding slot
        """

        try:
            slot = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')

        if slot is not None:
            current_adapter = slot
            raise DynamipsError(
                f'Slot {slot_number} is already occupied by adapter {current_adapter} on router "{self._name}"'
            )

        is_running = await self.is_running()

        # Only c7200, c3600 and c3745 (NM-4T only) support new adapter while running
        if is_running and not (
            (self._platform == "c7200" and not str(adapter).startswith("C7200"))
            and not (self._platform == "c3600" and self.chassis == "3660")
            and not (self._platform == "c3745" and adapter == "NM-4T")
        ):
            raise DynamipsError(f'Adapter {adapter} cannot be added while router "{self._name}" is running')

        await self._hypervisor.send(f'vm slot_add_binding "{self._name}" {slot_number} 0 {adapter}')

        log.debug(f'Router "{self._name}" [{self._id}]: adapter {adapter} inserted into slot {slot_number}')

        self._slots[slot_number] = adapter

        # Generate an OIR event if the router is running
        if is_running:
            await self._hypervisor.send(f'vm slot_oir_start "{self._name}" {slot_number} 0')

            log.debug(f'Router "{self._name}" [{self._id}]: OIR start event sent to slot {slot_number}')

            if self._tap_datapath:
                # The new adapter's Ethernet ports need their anchor TAPs now
                # (not at next start) for kernel links to attach at once.
                await self._create_taps()

    async def slot_remove_binding(self, slot_number):
        """
        Removes a slot binding (a module from a slot).

        :param slot_number: slot number
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')

        if adapter is None:
            raise DynamipsError(f'No adapter in slot {slot_number} on router "{self._name}"')

        is_running = await self.is_running()

        # Only c7200, c3600 and c3745 (NM-4T only) support to remove adapter while running
        if is_running and not (
            (self._platform == "c7200" and not str(adapter).startswith("C7200"))
            and not (self._platform == "c3600" and self.chassis == "3660")
            and not (self._platform == "c3745" and adapter == "NM-4T")
        ):
            raise DynamipsError(f'Adapter {adapter} cannot be removed while router "{self._name}" is running')

        # Generate an OIR event if the router is running
        if is_running:
            await self._hypervisor.send(f'vm slot_oir_stop "{self._name}" {slot_number} 0')

            log.debug(f'Router "{self._name}" [{self._id}]: OIR stop event sent to slot {slot_number}')

        await self._hypervisor.send(f'vm slot_remove_binding "{self._name}" {slot_number} 0')

        log.debug(f'Router "{self._name}" [{self._id}]: adapter {adapter} removed from slot {slot_number}')
        self._slots[slot_number] = None

    async def install_wic(self, wic_slot_number, wic):
        """
        Installs a WIC adapter into this router.

        :param wic_slot_number: WIC slot number
        :param wic: WIC to be installed
        """

        # WICs are always installed on adapters in slot 0
        slot_number = 0

        # Do not check if slot has an adapter because adapters with WICs interfaces
        # must be inserted by default in the router and cannot be removed.
        adapter = self._slots[slot_number]

        if wic_slot_number > len(adapter.wics) - 1:
            raise DynamipsError(f"WIC slot {wic_slot_number} doesn't exist")

        if not adapter.wic_slot_available(wic_slot_number):
            raise DynamipsError(f"WIC slot {wic_slot_number} is already occupied by another WIC")

        if await self.is_running():
            raise DynamipsError(f'WIC "{wic}" cannot be added while router "{self._name}" is running')

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_number = 16 * (wic_slot_number + 1)
        await self._hypervisor.send(
            f'vm slot_add_binding "{self._name}" {slot_number} {internal_wic_slot_number} {wic}'
        )

        log.debug(f'Router "{self._name}" [{self._id}]: {wic} inserted into WIC slot {wic_slot_number}')

        adapter.install_wic(wic_slot_number, wic)

    async def uninstall_wic(self, wic_slot_number):
        """
        Uninstalls a WIC adapter from this router.

        :param wic_slot_number: WIC slot number
        """

        # WICs are always installed on adapters in slot 0
        slot_number = 0

        # Do not check if slot has an adapter because adapters with WICs interfaces
        # must be inserted by default in the router and cannot be removed.
        adapter = self._slots[slot_number]

        if wic_slot_number > len(adapter.wics) - 1:
            raise DynamipsError(f"WIC slot {wic_slot_number} doesn't exist")

        if adapter.wic_slot_available(wic_slot_number):
            raise DynamipsError(f"No WIC is installed in WIC slot {wic_slot_number}")

        if await self.is_running():
            raise DynamipsError(
                f'WIC cannot be removed from slot {wic_slot_number} while router "{self._name}" is running'
            )

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_number = 16 * (wic_slot_number + 1)
        await self._hypervisor.send(f'vm slot_remove_binding "{self._name}" {slot_number} {internal_wic_slot_number}')

        log.debug(
            f'Router "{self._name}" [{self._id}]: {adapter.wics[wic_slot_number]} removed from WIC slot {wic_slot_number}'
        )
        adapter.uninstall_wic(wic_slot_number)

    async def get_slot_nio_bindings(self, slot_number):
        """
        Returns slot NIO bindings.

        :param slot_number: slot number

        :returns: list of NIO bindings
        """

        nio_bindings = await self._hypervisor.send(f'vm slot_nio_bindings "{self._name}" {slot_number}')
        return nio_bindings

    async def slot_add_nio_binding(self, slot_number, port_number, nio):
        """
        Adds a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')

        if adapter is None:
            raise DynamipsError(f"Adapter is missing in slot {slot_number}")

        if not adapter.port_exists(port_number):
            raise DynamipsError(f"Port {port_number} does not exist on adapter {adapter}")

        # The compute-side backstop of the controller's duplicate-port guard:
        # a port carries at most one NIO, and overwriting the one a link
        # still owns orphans that link's teardown (its host state leaks).
        # Refusing also keeps the kernel wiring's own idempotence check from
        # silently skipping the attach while rebinding the bookkeeping.
        if adapter.get_nio(port_number) is not None:
            raise DynamipsError(f"Port {port_number} on slot {slot_number} of router '{self._name}' already has a link")

        if isinstance(nio, NIOBridge):
            # Kernel datapath: the port's anchor TAP is opened in the
            # hypervisor and enslaved into the NIO's per-link bridge (the
            # wiring is deferred to the node's start when no anchors exist).
            # Wire before bookkeeping: an attach that fails mid-way leaves
            # the port unbound instead of half-wired.
            await self._attach_kernel_nio(slot_number, port_number, nio)
            adapter.add_nio(port_number, nio)
            log.debug(f'Router "{self._name}" [{self._id}]: {nio} bound to port {slot_number}/{port_number}')
            return

        try:
            await self._hypervisor.send(f'vm slot_add_nio_binding "{self._name}" {slot_number} {port_number} {nio}')
        except DynamipsError:
            # in case of error try to remove and add the nio binding
            await self._hypervisor.send(f'vm slot_remove_nio_binding "{self._name}" {slot_number} {port_number}')
            await self._hypervisor.send(f'vm slot_add_nio_binding "{self._name}" {slot_number} {port_number} {nio}')

        log.debug(f'Router "{self._name}" [{self._id}]: NIO {nio.name} bound to port {slot_number}/{port_number}')

        await self.slot_enable_nio(slot_number, port_number)
        adapter.add_nio(port_number, nio)

    async def slot_update_nio_binding(self, slot_number, port_number, nio):
        """
        Update a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        :param nio: NIO instance to add to the slot/port
        """

        if isinstance(nio, NIOBridge):
            # Filters, markers or suspend changed on a kernel link: re-apply
            # on the anchor, no re-binding and no re-enslaving. A NIO bound
            # while the node was stopped carries its state; start applies it.
            anchor = self._kernel_host_ifc(slot_number, port_number)
            if anchor is not None and self.ubridge:
                await self._kernel_update(anchor, nio)
                await self._set_adapter_carrier(slot_number, not nio.suspend, port_number)
            return
        await nio.update()

    async def slot_remove_nio_binding(self, slot_number, port_number):
        """
        Removes a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number

        :returns: removed NIO instance
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')

        if adapter is None:
            raise DynamipsError(f"Adapter is missing in slot {slot_number}")

        if not adapter.port_exists(port_number):
            raise DynamipsError(f"Port {port_number} does not exist on adapter {adapter}")

        await self.stop_capture(slot_number, port_number)

        nio = adapter.get_nio(port_number)
        if nio is None:
            return

        if isinstance(nio, NIOBridge):
            await self._remove_kernel_nio_binding(slot_number, port_number, nio)
            adapter.remove_nio(port_number)
            log.debug(f'Router "{self._name}" [{self._id}]: {nio} removed from port {slot_number}/{port_number}')
            return nio

        await self.slot_disable_nio(slot_number, port_number)
        await self._hypervisor.send(f'vm slot_remove_nio_binding "{self._name}" {slot_number} {port_number}')
        await nio.close()
        adapter.remove_nio(port_number)

        log.debug(f'Router "{self._name}" [{self._id}]: NIO {nio.name} removed from port {slot_number}/{port_number}')

        return nio

    async def slot_enable_nio(self, slot_number, port_number):
        """
        Enables a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        """

        is_running = await self.is_running()
        if is_running:  # running router
            await self._hypervisor.send(f'vm slot_enable_nio "{self._name}" {slot_number} {port_number}')

            log.debug(f'Router "{self._name}" [{self._id}]: NIO enabled on port {slot_number}/{port_number}')

    def get_nio(self, slot_number, port_number):
        """
        Gets an slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number

        :returns: NIO instance
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')
        if not adapter.port_exists(port_number):
            raise DynamipsError(f"Port {port_number} does not exist on adapter {adapter}")

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError(f"Port {slot_number}/{port_number} is not connected")
        return nio

    async def slot_disable_nio(self, slot_number, port_number):
        """
        Disables a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        """

        is_running = await self.is_running()
        if is_running:  # running router
            await self._hypervisor.send(f'vm slot_disable_nio "{self._name}" {slot_number} {port_number}')

            log.debug(f'Router "{self._name}" [{self._id}]: NIO disabled on port {slot_number}/{port_number}')

    async def start_capture(self, slot_number, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param slot_number: slot number
        :param port_number: port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        try:
            open(output_file, "w+").close()
        except OSError as e:
            raise DynamipsError(f'Can not write capture to "{output_file}": {e!s}')

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')
        if not adapter.port_exists(port_number):
            raise DynamipsError(f"Port {port_number} does not exist on adapter {adapter}")

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError(f"Port {slot_number}/{port_number} is not connected")

        if isinstance(nio, NIOBridge):
            # Kernel link: capture on the port's TAP anchor (AF_PACKET),
            # not in the Dynamips NIO (this link has no Dynamips NIO).
            nio.start_packet_capture(output_file, data_link_type)
            if self.ubridge:
                anchor = self._kernel_host_ifc(slot_number, port_number)
                if anchor is not None:
                    await self._ubridge_send(f'capture start_kernel {anchor} "{output_file}"')
            log.debug(
                f'Router "{self._name}" [{self._id}]: starting packet capture on port {slot_number}/{port_number}'
            )
            return

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError(f"Port {port_number} has already a filter applied on {adapter}")
        await nio.start_packet_capture(output_file, data_link_type)
        log.debug(f'Router "{self._name}" [{self._id}]: starting packet capture on port {slot_number}/{port_number}')

    async def stop_capture(self, slot_number, port_number):
        """
        Stops a packet capture.

        :param slot_number: slot number
        :param port_number: port number
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(f'Slot {slot_number} does not exist on router "{self._name}"')
        if not adapter.port_exists(port_number):
            raise DynamipsError(f"Port {port_number} does not exist on adapter {adapter}")

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError(f"Port {slot_number}/{port_number} is not connected")

        if not nio.capturing:
            return

        if isinstance(nio, NIOBridge):
            nio.stop_packet_capture()
            if self.ubridge and self._kernel_host_ifc(slot_number, port_number) is not None:
                await self._ubridge_send("capture stop_kernel")
            return
        await nio.stop_packet_capture()

        log.debug(f'Router "{self._name}" [{self._id}]: stopping packet capture on port {slot_number}/{port_number}')

    # ------------------------------------------------------------------
    # Kernel datapath: the port anchor is a persistent TAP held by the
    # Dynamips hypervisor (nio create_tap) — QEMU's shape, not IOU's
    # ------------------------------------------------------------------

    def _tap_name(self, slot_number, port_number):
        """
        Deterministic anchor TAP name for a slot/port (the shared
        utils.kernel_anchor naming contract — the controller names a peer's
        anchor with the same function when an Ethernet switch absorbs it;
        fits IFNAMSIZ even for WIC port numbers 16/32/48).
        """

        return kernel_anchor_name("dynamips", self._id, slot_number, port_number)

    def _kernel_host_ifc(self, slot_number, port_number=0):
        """
        The persistent TAP this Ethernet slot/port owns, or None for serial,
        ATM or POS ports (never anchored) and before the router started.
        """

        return self._kernel_taps.get((slot_number, port_number))

    def _kernel_anchors(self):
        """
        Every anchor TAP this router currently owns.
        """

        return set(self._kernel_taps.values())

    def _kernel_error(self, message):
        return DynamipsError(message)

    def _ethernet_slot_ports(self):
        """
        Every (slot, port) that can carry Ethernet frames: slot adapters
        whose model is Ethernet, plus WIC-1ENET ports (numbered from 16 per
        WIC slot, the Dynamips convention) in any motherboard.
        """

        ports = []
        for slot_number, adapter in enumerate(self._slots):
            if adapter is None:
                continue
            if str(adapter) in ETHERNET_ADAPTERS:
                ports.extend((slot_number, port_number) for port_number in adapter.ports)
            for wic_slot_number, wic in enumerate(adapter.wics or []):
                if wic is not None and str(wic) in ETHERNET_WICS:
                    ports.append((slot_number, 16 * (wic_slot_number + 1)))
        return ports

    @property
    def _ethernet_adapters(self):
        """
        Slot adapters owning at least one anchor — the mixin's per-link
        bridge sweep walks them. Dynamips ports live in slot adapters (WIC
        ports included), so this derives from the anchor map rather than
        the slot list.
        """

        adapters = []
        for slot_number, _port_number in self._kernel_taps:
            if slot_number < len(self._slots):
                adapter = self._slots[slot_number]
                if adapter is not None and adapter not in adapters:
                    adapters.append(adapter)
        return adapters

    async def _prepare_tap_datapath(self):
        """
        Start uBridge and create the persistent TAP every Ethernet slot/port
        owns — the anchor role QEMU's TAPs and Docker's veth host ends play.
        The Dynamips hypervisor opens the device (ownership handed to this
        user by _create_taps), so it needs no privileges of its own to hold
        the fd. A uBridge without the tap module keeps this router on the
        relay datapath: every link rides the NIOUDP tunnel, exactly as
        before.

        Nothing here is undone at node stop — the hypervisor, its NIO
        bindings and the per-link kernel bridges all outlive ``vm stop``,
        which is what makes a stopped router's links self-heal on the next
        start. The anchors are only retired when the node closes.
        """

        if self._ghost_flag:
            # Ghost IOS images share RAM with a real router and never link.
            return

        try:
            await self._start_ubridge()
        except NodeError as e:
            # A Dynamips router without links never needed uBridge; keep the
            # node bootable and let the relay raise at link time (as before).
            log.warning("Router '%s': %s", self._name, e)
            return

        # uBridge (re)started: the tc capabilities must be probed again.
        self._ubridge_tc_caps = None
        if not self._tap_datapath:
            probe = f"gd{self._id.replace('-', '')[:8]}prob"
            try:
                await self._ubridge_send(f'tap create "{probe}"')
            except UbridgeError as e:
                message = (
                    f"Router '{self._name}': uBridge cannot create persistent TAPs ({e}); "
                    "this node runs on the relay datapath and cannot carry kernel links"
                )
                log.warning(message)
                self.project.emit("log.warning", {"message": message})
                return
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'tap delete "{probe}"')
            self._tap_datapath = True

        await self._create_taps()
        # Kernel links bound while the router was stopped could not wire (no
        # anchors existed); wire them now, before IOS comes up.
        for slot_number, adapter in enumerate(self._slots):
            if adapter is None:
                continue
            for port_number, nio in list(adapter.ports.items()):
                if isinstance(nio, NIOBridge):
                    await self._attach_kernel_nio(slot_number, port_number, nio)

    async def _create_taps(self):
        """
        Create the persistent TAP every Ethernet slot/port owns. Each TAP
        starts DOWN (carrier off until a kernel link attaches); uBridge
        creates the device and hands ownership to this user, so the
        unprivileged Dynamips hypervisor can open it. A port whose anchor
        already exists (a restart, or an adapter hot-added to a running
        router) keeps it — an anchor is never recreated under a live link.
        A persistent TAP outlives its creator, so a leftover from a previous
        run (crash, kill) is swept first.
        """

        for slot_number, port_number in self._ethernet_slot_ports():
            if (slot_number, port_number) in self._kernel_taps:
                continue
            tap = self._tap_name(slot_number, port_number)
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'tap delete "{tap}"')
            await self._ubridge_send(f'tap create "{tap}"')
            try:
                await self._ubridge_send(f"tap set_owner {tap} {os.getuid()}")
            except UbridgeError as e:
                # Only root could open the TAP now: the hypervisor would fail
                # to bind its NIO, which is worth surfacing at that point.
                log.warning("Router '%s': could not hand TAP %s to uid %s: %s", self._name, tap, os.getuid(), e)
            await self._ubridge_send(f'link set "{tap}" down')
            self._kernel_taps[(slot_number, port_number)] = tap

    async def _attach_kernel_nio(self, slot_number, port_number, nio):
        """
        Wire a kernel link's NIO (NIOBridge) on a port: open the port's
        anchor TAP in the Dynamips hypervisor (``nio create_tap`` — the
        hypervisor, not uBridge, holds the fd, the same shape as QEMU), bind
        it to the slot/port, then enslave the anchor into the per-link
        kernel bridge — the shared mixin flow. On a router that is not
        running the wiring is deferred to its start (no anchors exist yet).
        A port whose wiring survived a stop (nothing is torn down there) is
        left alone: re-binding would collide on both hypervisor and bridge.
        """

        if (slot_number, port_number) in self._tap_nios:
            return
        anchor = self._kernel_host_ifc(slot_number, port_number)
        if anchor is None:
            if self.status != "started":
                return
            raise self._kernel_error(
                f"Port {slot_number}/{port_number} of router '{self._name}' runs on the relay datapath "
                "(this uBridge cannot create persistent TAPs) and cannot carry a kernel link"
            )

        tap_nio = NIOTAP(self._hypervisor, anchor)
        await tap_nio.create()
        try:
            await self._hypervisor.send(
                f'vm slot_add_nio_binding "{self._name}" {slot_number} {port_number} {tap_nio.name}'
            )
        except DynamipsError:
            with contextlib.suppress(DynamipsError):
                await tap_nio.delete()
            raise
        await self.slot_enable_nio(slot_number, port_number)
        self._tap_nios[(slot_number, port_number)] = tap_nio
        await self._kernel_attach(anchor, nio)
        await self._set_adapter_carrier(slot_number, not nio.suspend, port_number)

    async def _remove_kernel_nio_binding(self, slot_number, port_number, nio):
        """
        Release a kernel link's NIO: tear the anchor out of the per-link
        kernel bridge (markers, tc, delif — the shared mixin flow), then
        unbind the port and delete the hypervisor's TAP NIO, releasing the
        anchor fd. The anchor device itself survives for the next link.
        """

        if self.ubridge and self._kernel_host_ifc(slot_number, port_number) is not None:
            await self._remove_kernel_nio(nio, slot_number, port_number)
        tap_nio = self._tap_nios.pop((slot_number, port_number), None)
        if tap_nio is not None:
            with contextlib.suppress(DynamipsError, OSError):
                await self.slot_disable_nio(slot_number, port_number)
            with contextlib.suppress(DynamipsError, OSError):
                await self._hypervisor.send(f'vm slot_remove_nio_binding "{self._name}" {slot_number} {port_number}')
            with contextlib.suppress(DynamipsError, OSError):
                await tap_nio.delete()

    async def _stop_ubridge(self):
        """
        Stops uBridge, retiring the kernel datapath's host state first — in
        the QEMU order, since here it is the Dynamips hypervisor (not
        uBridge) that holds the anchor fds: the per-link kernel bridges need
        the control channel, and the anchor TAPs (persistent devices) must
        be deleted through it after the hypervisor's TAP NIOs are gone, or a
        device Dynamips still holds open would outlive its retirement. The
        next start spawns a fresh uBridge, so the tc capabilities must be
        probed again.
        """

        if self.ubridge:
            for (slot_number, port_number), tap_nio in list(self._tap_nios.items()):
                with contextlib.suppress(DynamipsError, OSError):
                    await self._hypervisor.send(
                        f'vm slot_remove_nio_binding "{self._name}" {slot_number} {port_number}'
                    )
                with contextlib.suppress(DynamipsError, OSError):
                    await tap_nio.delete()
            self._tap_nios.clear()
            for tap in self._kernel_taps.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'tap delete "{tap}"')
            await self._remove_kernel_bridges()
        self._kernel_taps.clear()
        self._ubridge_tc_caps = None
        await super()._stop_ubridge()

    def _create_slots(self, numslots):
        """
        Creates the appropriate number of slots for this router.

        :param numslots: number of slots to create
        """

        self._slots = numslots * [None]

    @property
    def slots(self):
        """
        Returns the slots for this router.

        :return: slot list
        """

        return self._slots

    @property
    def startup_config_path(self):
        """
        :returns: Path of the startup config
        """
        return os.path.join(self._working_directory, "configs", f"i{self._dynamips_id}_startup-config.cfg")

    @property
    def private_config_path(self):
        """
        :returns: Path of the private config
        """
        return os.path.join(self._working_directory, "configs", f"i{self._dynamips_id}_private-config.cfg")

    async def set_name(self, new_name):
        """
        Renames this router.

        :param new_name: new name string
        """

        if not is_ios_hostname_valid(new_name):
            raise DynamipsError(
                f"{new_name} is an invalid name to rename router '{self._name}'. Allowed characters: letters (a-z, A-Z), digits (0-9), and hyphens (-). The name must start with a letter, end with a letter or digit, and be 63 characters or fewer."
            )

        await self._hypervisor.send(f'vm rename "{self._name}" "{new_name}"')

        # change the hostname in the startup-config
        if os.path.isfile(self.startup_config_path):
            try:
                with open(self.startup_config_path, "r+", encoding="utf-8", errors="replace") as f:
                    old_config = f.read()
                    new_config = re.sub(r"hostname .+$", "hostname " + new_name, old_config, flags=re.MULTILINE)
                    f.seek(0)
                    f.write(new_config)
            except OSError as e:
                raise DynamipsError(f"Could not amend the configuration {self.startup_config_path}: {e}")

        # change the hostname in the private-config
        if os.path.isfile(self.private_config_path):
            try:
                with open(self.private_config_path, "r+", encoding="utf-8", errors="replace") as f:
                    old_config = f.read()
                    new_config = old_config.replace(self.name, new_name)
                    f.seek(0)
                    f.write(new_config)
            except OSError as e:
                raise DynamipsError(f"Could not amend the configuration {self.private_config_path}: {e}")

        log.debug(f'Router "{self._name}" [{self._id}]: renamed to "{new_name}"')
        self._name = new_name

    async def extract_config(self):
        """
        Gets the contents of the config files
        startup-config and private-config from NVRAM.

        :returns: tuple (startup-config, private-config) base64 encoded
        """

        try:
            reply = await self._hypervisor.send(f'vm extract_config "{self._name}"')
        except DynamipsError:
            # for some reason Dynamips gets frozen when it does not find the magic number in the NVRAM file.
            return None, None
        reply = reply[0].rsplit(" ", 2)[-2:]
        startup_config = reply[0][1:-1]  # get statup-config and remove single quotes
        private_config = reply[1][1:-1]  # get private-config and remove single quotes
        return startup_config, private_config

    async def save_configs(self):
        """
        Saves the startup-config and private-config to files.
        """

        try:
            config_path = os.path.join(self._working_directory, "configs")
            os.makedirs(config_path, exist_ok=True)
        except OSError as e:
            raise DynamipsError(f"Could could not create configuration directory {config_path}: {e}")

        startup_config_base64, private_config_base64 = await self.extract_config()
        if startup_config_base64:
            startup_config = self.startup_config_path
            try:
                config = base64.b64decode(startup_config_base64).decode("utf-8", errors="replace")
                config = "!\n" + config.replace("\r", "")
                config_path = os.path.join(self._working_directory, startup_config)
                with open(config_path, "wb") as f:
                    log.debug(f"saving startup-config to {startup_config}")
                    f.write(config.encode("utf-8"))
            except (binascii.Error, OSError) as e:
                raise DynamipsError(f"Could not save the startup configuration {config_path}: {e}")

        if private_config_base64 and base64.b64decode(private_config_base64) != b"\nkerberos password \nend\n":
            private_config = self.private_config_path
            try:
                config = base64.b64decode(private_config_base64).decode("utf-8", errors="replace")
                config_path = os.path.join(self._working_directory, private_config)
                with open(config_path, "wb") as f:
                    log.debug(f"saving private-config to {private_config}")
                    f.write(config.encode("utf-8"))
            except (binascii.Error, OSError) as e:
                raise DynamipsError(f"Could not save the private configuration {config_path}: {e}")

    async def delete(self):
        """
        Deletes this VM (including all its files).
        """

        try:
            await wait_run_in_executor(shutil.rmtree, self._working_directory)
        except OSError as e:
            log.warning(f"Could not delete file {e}")

        self.manager.release_dynamips_id(self._project.id, self._dynamips_id)

    async def clean_delete(self):
        """
        Deletes this router & associated files (nvram, disks etc.)
        """

        await self._hypervisor.send(f'vm clean_delete "{self._name}"')
        self._hypervisor.devices.remove(self)
        try:
            await wait_run_in_executor(shutil.rmtree, self._working_directory)
        except OSError as e:
            log.warning(f"Could not delete file {e}")
        log.debug(f'Router "{self._name}" [{self._id}] has been deleted (including associated files)')

    def _memory_files(self):

        return [
            os.path.join(self._working_directory, f"{self.platform}_i{self.dynamips_id}_rom"),
            os.path.join(self._working_directory, f"{self.platform}_i{self.dynamips_id}_nvram"),
        ]
