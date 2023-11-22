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
import time
import sys
import os
import re
import glob
import base64
import shutil
import binascii
import logging

log = logging.getLogger(__name__)

from ...base_node import BaseNode
from ..dynamips_error import DynamipsError

from gns3server.utils.file_watcher import FileWatcher
from gns3server.utils.asyncio import wait_run_in_executor, monitor_process
from gns3server.utils.hostname import is_ios_hostname_valid
from gns3server.utils.images import md5sum


class Router(BaseNode):

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
            name, node_id, project, manager, console=console, console_type=console_type, aux=aux, aux_type=aux_type
        )

        self._working_directory = os.path.join(
            self.project.module_working_directory(self.manager.module_name.lower()), self.id
        )
        try:
            os.makedirs(os.path.join(self._working_directory, "configs"), exist_ok=True)
        except OSError as e:
            raise DynamipsError(f"Can't create the dynamips config directory: {str(e)}")
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

        if not ghost_flag:
            if not dynamips_id:
                self._dynamips_id = manager.get_dynamips_id(project.id)
            else:
                self._dynamips_id = dynamips_id
                manager.take_dynamips_id(project.id, dynamips_id)
        else:
            log.info("Creating a new ghost IOS instance")
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
                    log.error(f"Can't move {path}: {str(e)}")
                    continue
        for path in glob.glob(os.path.join(glob.escape(dynamips_dir), f"*_i{dynamips_id}_*")):
            dst = os.path.join(self._working_directory, os.path.basename(path))
            if not os.path.exists(dst):
                try:
                    shutil.move(path, dst)
                except OSError as e:
                    log.error(f"Can't move {path}: {str(e)}")
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

        await self._hypervisor.send(
            'vm create "{name}" {id} {platform}'.format(name=self._name, id=self._dynamips_id, platform=self._platform)
        )

        if not self._ghost_flag:

            log.info(
                'Router {platform} "{name}" [{id}] has been created'.format(
                    name=self._name, platform=self._platform, id=self._id
                )
            )

            if self._console is not None:
                await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {self._console}')

            if self.aux is not None:
                await self._hypervisor.send(f'vm set_aux_tcp_port "{self._name}" {self.aux}')

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

            await self._hypervisor.send(
                'vm set_config "{name}" "{startup}" "{private}"'.format(
                    name=self._name, startup=startup_config_path, private=private_config_path
                )
            )
            await self._hypervisor.send(f'vm start "{self._name}"')
            self.status = "started"
            log.info(f'router "{self._name}" [{self._id}] has been started')

            self._memory_watcher = FileWatcher(self._memory_files(), self._memory_changed, strategy="hash", delay=30)
            monitor_process(self._hypervisor.process, self._termination_callback)

    async def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self.status == "started":
            self.status = "stopped"
            log.info("Dynamips hypervisor process has stopped, return code: %d", returncode)
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
            log.info(f'Router "{self._name}" [{self._id}] has been stopped')
        if self._memory_watcher:
            self._memory_watcher.close()
            self._memory_watcher = None
        await self.save_configs()

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
            log.info(f'Router "{self._name}" [{self._id}] has been suspended')

    async def resume(self):
        """
        Resumes this suspended router
        """

        status = await self.get_status()
        if status == "suspended":
            await self._hypervisor.send(f'vm resume "{self._name}"')
            self.status = "started"
        log.info(f'Router "{self._name}" [{self._id}] has been resumed')

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
                    if nio:
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

        log.info(
            'Router "{name}" [{id}]: has a new IOS image set: "{image}"'.format(
                name=self._name, id=self._id, image=image
            )
        )

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
        log.info(
            'Router "{name}" [{id}]: RAM updated from {old_ram}MB to {new_ram}MB'.format(
                name=self._name, id=self._id, old_ram=self._ram, new_ram=ram
            )
        )
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
        log.info(
            'Router "{name}" [{id}]: NVRAM updated from {old_nvram}KB to {new_nvram}KB'.format(
                name=self._name, id=self._id, old_nvram=self._nvram, new_nvram=nvram
            )
        )
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
            log.info(f'Router "{self._name}" [{self._id}]: mmap enabled')
        else:
            log.info(f'Router "{self._name}" [{self._id}]: mmap disabled')
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
            log.info(f'Router "{self._name}" [{self._id}]: sparse memory enabled')
        else:
            log.info(f'Router "{self._name}" [{self._id}]: sparse memory disabled')
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
        log.info(
            'Router "{name}" [{id}]: clock divisor updated from {old_clock} to {new_clock}'.format(
                name=self._name, id=self._id, old_clock=self._clock_divisor, new_clock=clock_divisor
            )
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

        log.info(f'Router "{self._name}" [{self._id}]: idle-PC set to {idlepc}')
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

        log.info(f'Router "{self._name}" [{self._id}] has started calculating Idle-PC values')
        begin = time.time()
        idlepcs = await self._hypervisor.send(f'vm get_idle_pc_prop "{self._name}" 0')
        log.info(
            'Router "{name}" [{id}] has finished calculating Idle-PC values after {time:.4f} seconds'.format(
                name=self._name, id=self._id, time=time.time() - begin
            )
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

        log.info(
            'Router "{name}" [{id}]: idlemax updated from {old_idlemax} to {new_idlemax}'.format(
                name=self._name, id=self._id, old_idlemax=self._idlemax, new_idlemax=idlemax
            )
        )

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
            await self._hypervisor.send(
                'vm set_idle_sleep_time "{name}" 0 {idlesleep}'.format(name=self._name, idlesleep=idlesleep)
            )

        log.info(
            'Router "{name}" [{id}]: idlesleep updated from {old_idlesleep} to {new_idlesleep}'.format(
                name=self._name, id=self._id, old_idlesleep=self._idlesleep, new_idlesleep=idlesleep
            )
        )

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

        await self._hypervisor.send(
            'vm set_ghost_file "{name}" "{ghost_file}"'.format(name=self._name, ghost_file=ghost_file)
        )

        log.info(
            'Router "{name}" [{id}]: ghost file set to "{ghost_file}"'.format(
                name=self._name, id=self._id, ghost_file=ghost_file
            )
        )

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

        await self._hypervisor.send(
            'vm set_ghost_status "{name}" {ghost_status}'.format(name=self._name, ghost_status=ghost_status)
        )

        log.info(
            'Router "{name}" [{id}]: ghost status set to {ghost_status}'.format(
                name=self._name, id=self._id, ghost_status=ghost_status
            )
        )
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

        await self._hypervisor.send(
            'vm set_exec_area "{name}" {exec_area}'.format(name=self._name, exec_area=exec_area)
        )

        log.info(
            'Router "{name}" [{id}]: exec area updated from {old_exec}MB to {new_exec}MB'.format(
                name=self._name, id=self._id, old_exec=self._exec_area, new_exec=exec_area
            )
        )
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

        log.info(
            'Router "{name}" [{id}]: disk0 updated from {old_disk0}MB to {new_disk0}MB'.format(
                name=self._name, id=self._id, old_disk0=self._disk0, new_disk0=disk0
            )
        )
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

        log.info(
            'Router "{name}" [{id}]: disk1 updated from {old_disk1}MB to {new_disk1}MB'.format(
                name=self._name, id=self._id, old_disk1=self._disk1, new_disk1=disk1
            )
        )
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
            log.info(f'Router "{self._name}" [{self._id}]: auto delete disks enabled')
        else:
            log.info(f'Router "{self._name}" [{self._id}]: auto delete disks disabled')
        self._auto_delete_disks = auto_delete_disks

    async def set_console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        self.console = console
        await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {self.console}')

    async def set_console_type(self, console_type):
        """
        Sets the console type.

        :param console_type: console type
        """

        if self.console_type != console_type:
            status = await self.get_status()
            if status == "running":
                raise DynamipsError('"{name}" must be stopped to change the console type to {console_type}'.format(name=self._name,
                                                                                                                   console_type=console_type))

        self.console_type = console_type

        if self._console and console_type == "telnet":
            await self._hypervisor.send(f'vm set_con_tcp_port "{self._name}" {self._console}')

    async def set_aux(self, aux):
        """
        Sets the TCP auxiliary port.

        :param aux: console auxiliary port (integer)
        """

        self.aux = aux
        await self._hypervisor.send(f'vm set_aux_tcp_port "{self._name}" {aux}')

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

        await self._hypervisor.send(
            '{platform} set_mac_addr "{name}" {mac_addr}'.format(
                platform=self._platform, name=self._name, mac_addr=mac_addr
            )
        )

        log.info(
            'Router "{name}" [{id}]: MAC address updated from {old_mac} to {new_mac}'.format(
                name=self._name, id=self._id, old_mac=self._mac_addr, new_mac=mac_addr
            )
        )
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

        await self._hypervisor.send(
            '{platform} set_system_id "{name}" {system_id}'.format(
                platform=self._platform, name=self._name, system_id=system_id
            )
        )

        log.info(
            'Router "{name}" [{id}]: system ID updated from {old_id} to {new_id}'.format(
                name=self._name, id=self._id, old_id=self._system_id, new_id=system_id
            )
        )
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
                'Slot {slot_number} is already occupied by adapter {adapter} on router "{name}"'.format(
                    name=self._name, slot_number=slot_number, adapter=current_adapter
                )
            )

        is_running = await self.is_running()

        # Only c7200, c3600 and c3745 (NM-4T only) support new adapter while running
        if is_running and not (
            (self._platform == "c7200" and not str(adapter).startswith("C7200"))
            and not (self._platform == "c3600" and self.chassis == "3660")
            and not (self._platform == "c3745" and adapter == "NM-4T")
        ):
            raise DynamipsError(
                'Adapter {adapter} cannot be added while router "{name}" is running'.format(
                    adapter=adapter, name=self._name
                )
            )

        await self._hypervisor.send(
            'vm slot_add_binding "{name}" {slot_number} 0 {adapter}'.format(
                name=self._name, slot_number=slot_number, adapter=adapter
            )
        )

        log.info(
            'Router "{name}" [{id}]: adapter {adapter} inserted into slot {slot_number}'.format(
                name=self._name, id=self._id, adapter=adapter, slot_number=slot_number
            )
        )

        self._slots[slot_number] = adapter

        # Generate an OIR event if the router is running
        if is_running:

            await self._hypervisor.send(
                'vm slot_oir_start "{name}" {slot_number} 0'.format(name=self._name, slot_number=slot_number)
            )

            log.info(
                'Router "{name}" [{id}]: OIR start event sent to slot {slot_number}'.format(
                    name=self._name, id=self._id, slot_number=slot_number
                )
            )

    async def slot_remove_binding(self, slot_number):
        """
        Removes a slot binding (a module from a slot).

        :param slot_number: slot number
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(
                'Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )

        if adapter is None:
            raise DynamipsError(
                'No adapter in slot {slot_number} on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )

        is_running = await self.is_running()

        # Only c7200, c3600 and c3745 (NM-4T only) support to remove adapter while running
        if is_running and not (
            (self._platform == "c7200" and not str(adapter).startswith("C7200"))
            and not (self._platform == "c3600" and self.chassis == "3660")
            and not (self._platform == "c3745" and adapter == "NM-4T")
        ):
            raise DynamipsError(
                'Adapter {adapter} cannot be removed while router "{name}" is running'.format(
                    adapter=adapter, name=self._name
                )
            )

        # Generate an OIR event if the router is running
        if is_running:

            await self._hypervisor.send(
                'vm slot_oir_stop "{name}" {slot_number} 0'.format(name=self._name, slot_number=slot_number)
            )

            log.info(
                'Router "{name}" [{id}]: OIR stop event sent to slot {slot_number}'.format(
                    name=self._name, id=self._id, slot_number=slot_number
                )
            )

        await self._hypervisor.send(
            'vm slot_remove_binding "{name}" {slot_number} 0'.format(name=self._name, slot_number=slot_number)
        )

        log.info(
            'Router "{name}" [{id}]: adapter {adapter} removed from slot {slot_number}'.format(
                name=self._name, id=self._id, adapter=adapter, slot_number=slot_number
            )
        )
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
            raise DynamipsError(
                'WIC "{wic}" cannot be added while router "{name}" is running'.format(wic=wic, name=self._name)
            )

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_number = 16 * (wic_slot_number + 1)
        await self._hypervisor.send(
            'vm slot_add_binding "{name}" {slot_number} {wic_slot_number} {wic}'.format(
                name=self._name, slot_number=slot_number, wic_slot_number=internal_wic_slot_number, wic=wic
            )
        )

        log.info(
            'Router "{name}" [{id}]: {wic} inserted into WIC slot {wic_slot_number}'.format(
                name=self._name, id=self._id, wic=wic, wic_slot_number=wic_slot_number
            )
        )

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
                'WIC cannot be removed from slot {wic_slot_number} while router "{name}" is running'.format(
                    wic_slot_number=wic_slot_number, name=self._name
                )
            )

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_number = 16 * (wic_slot_number + 1)
        await self._hypervisor.send(
            'vm slot_remove_binding "{name}" {slot_number} {wic_slot_number}'.format(
                name=self._name, slot_number=slot_number, wic_slot_number=internal_wic_slot_number
            )
        )

        log.info(
            'Router "{name}" [{id}]: {wic} removed from WIC slot {wic_slot_number}'.format(
                name=self._name, id=self._id, wic=adapter.wics[wic_slot_number], wic_slot_number=wic_slot_number
            )
        )
        adapter.uninstall_wic(wic_slot_number)

    async def get_slot_nio_bindings(self, slot_number):
        """
        Returns slot NIO bindings.

        :param slot_number: slot number

        :returns: list of NIO bindings
        """

        nio_bindings = await self._hypervisor.send(
            'vm slot_nio_bindings "{name}" {slot_number}'.format(name=self._name, slot_number=slot_number)
        )
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
            raise DynamipsError(
                'Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )

        if adapter is None:
            raise DynamipsError(f"Adapter is missing in slot {slot_number}")

        if not adapter.port_exists(port_number):
            raise DynamipsError(
                "Port {port_number} does not exist on adapter {adapter}".format(
                    adapter=adapter, port_number=port_number
                )
            )

        try:
            await self._hypervisor.send(
                'vm slot_add_nio_binding "{name}" {slot_number} {port_number} {nio}'.format(
                    name=self._name, slot_number=slot_number, port_number=port_number, nio=nio
                )
            )
        except DynamipsError:
            # in case of error try to remove and add the nio binding
            await self._hypervisor.send(
                'vm slot_remove_nio_binding "{name}" {slot_number} {port_number}'.format(
                    name=self._name, slot_number=slot_number, port_number=port_number
                )
            )
            await self._hypervisor.send(
                'vm slot_add_nio_binding "{name}" {slot_number} {port_number} {nio}'.format(
                    name=self._name, slot_number=slot_number, port_number=port_number, nio=nio
                )
            )

        log.info(
            'Router "{name}" [{id}]: NIO {nio_name} bound to port {slot_number}/{port_number}'.format(
                name=self._name, id=self._id, nio_name=nio.name, slot_number=slot_number, port_number=port_number
            )
        )

        await self.slot_enable_nio(slot_number, port_number)
        adapter.add_nio(port_number, nio)

    async def slot_update_nio_binding(self, slot_number, port_number, nio):
        """
        Update a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        :param nio: NIO instance to add to the slot/port
        """

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
            raise DynamipsError(
                'Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )

        if adapter is None:
            raise DynamipsError(f"Adapter is missing in slot {slot_number}")

        if not adapter.port_exists(port_number):
            raise DynamipsError(
                "Port {port_number} does not exist on adapter {adapter}".format(
                    adapter=adapter, port_number=port_number
                )
            )

        await self.stop_capture(slot_number, port_number)
        await self.slot_disable_nio(slot_number, port_number)
        await self._hypervisor.send(
            'vm slot_remove_nio_binding "{name}" {slot_number} {port_number}'.format(
                name=self._name, slot_number=slot_number, port_number=port_number
            )
        )

        nio = adapter.get_nio(port_number)
        if nio is None:
            return
        await nio.close()
        adapter.remove_nio(port_number)

        log.info(
            'Router "{name}" [{id}]: NIO {nio_name} removed from port {slot_number}/{port_number}'.format(
                name=self._name, id=self._id, nio_name=nio.name, slot_number=slot_number, port_number=port_number
            )
        )

        return nio

    async def slot_enable_nio(self, slot_number, port_number):
        """
        Enables a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        """

        is_running = await self.is_running()
        if is_running:  # running router
            await self._hypervisor.send(
                'vm slot_enable_nio "{name}" {slot_number} {port_number}'.format(
                    name=self._name, slot_number=slot_number, port_number=port_number
                )
            )

            log.info(
                'Router "{name}" [{id}]: NIO enabled on port {slot_number}/{port_number}'.format(
                    name=self._name, id=self._id, slot_number=slot_number, port_number=port_number
                )
            )

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
            raise DynamipsError(
                'Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )
        if not adapter.port_exists(port_number):
            raise DynamipsError(
                "Port {port_number} does not exist on adapter {adapter}".format(
                    adapter=adapter, port_number=port_number
                )
            )

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError(
                "Port {slot_number}/{port_number} is not connected".format(
                    slot_number=slot_number, port_number=port_number
                )
            )
        return nio

    async def slot_disable_nio(self, slot_number, port_number):
        """
        Disables a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        """

        is_running = await self.is_running()
        if is_running:  # running router
            await self._hypervisor.send(
                'vm slot_disable_nio "{name}" {slot_number} {port_number}'.format(
                    name=self._name, slot_number=slot_number, port_number=port_number
                )
            )

            log.info(
                'Router "{name}" [{id}]: NIO disabled on port {slot_number}/{port_number}'.format(
                    name=self._name, id=self._id, slot_number=slot_number, port_number=port_number
                )
            )

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
            raise DynamipsError(f'Can not write capture to "{output_file}": {str(e)}')

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(
                'Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )
        if not adapter.port_exists(port_number):
            raise DynamipsError(
                "Port {port_number} does not exist on adapter {adapter}".format(
                    adapter=adapter, port_number=port_number
                )
            )

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError(
                "Port {slot_number}/{port_number} is not connected".format(
                    slot_number=slot_number, port_number=port_number
                )
            )

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError(
                "Port {port_number} has already a filter applied on {adapter}".format(
                    adapter=adapter, port_number=port_number
                )
            )
        await nio.start_packet_capture(output_file, data_link_type)
        log.info(
            'Router "{name}" [{id}]: starting packet capture on port {slot_number}/{port_number}'.format(
                name=self._name, id=self._id, nio_name=nio.name, slot_number=slot_number, port_number=port_number
            )
        )

    async def stop_capture(self, slot_number, port_number):
        """
        Stops a packet capture.

        :param slot_number: slot number
        :param port_number: port number
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError(
                'Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number)
            )
        if not adapter.port_exists(port_number):
            raise DynamipsError(
                "Port {port_number} does not exist on adapter {adapter}".format(
                    adapter=adapter, port_number=port_number
                )
            )

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError(
                "Port {slot_number}/{port_number} is not connected".format(
                    slot_number=slot_number, port_number=port_number
                )
            )

        if not nio.capturing:
            return
        await nio.stop_packet_capture()

        log.info(
            'Router "{name}" [{id}]: stopping packet capture on port {slot_number}/{port_number}'.format(
                name=self._name, id=self._id, nio_name=nio.name, slot_number=slot_number, port_number=port_number
            )
        )

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
            raise DynamipsError(f"{new_name} is an invalid name to rename router '{self._name}'")

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

        log.info(f'Router "{self._name}" [{self._id}]: renamed to "{new_name}"')
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
                    log.info(f"saving startup-config to {startup_config}")
                    f.write(config.encode("utf-8"))
            except (binascii.Error, OSError) as e:
                raise DynamipsError(f"Could not save the startup configuration {config_path}: {e}")

        if private_config_base64 and base64.b64decode(private_config_base64) != b"\nkerberos password \nend\n":
            private_config = self.private_config_path
            try:
                config = base64.b64decode(private_config_base64).decode("utf-8", errors="replace")
                config_path = os.path.join(self._working_directory, private_config)
                with open(config_path, "wb") as f:
                    log.info(f"saving private-config to {private_config}")
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
        log.info(f'Router "{self._name}" [{self._id}] has been deleted (including associated files)')

    def _memory_files(self):

        return [
            os.path.join(self._working_directory, f"{self.platform}_i{self.dynamips_id}_rom"),
            os.path.join(self._working_directory, f"{self.platform}_i{self.dynamips_id}_nvram"),
        ]
