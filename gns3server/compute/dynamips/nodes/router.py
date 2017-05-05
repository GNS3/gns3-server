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
Interface for Dynamips virtual Machine module ("vm")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L77
"""

import asyncio
import time
import sys
import os
import re
import glob
import shlex
import base64
import shutil
import binascii
import logging

log = logging.getLogger(__name__)

from ...base_node import BaseNode
from ..dynamips_error import DynamipsError
from ..nios.nio_udp import NIOUDP


from gns3server.utils.file_watcher import FileWatcher
from gns3server.utils.asyncio import wait_run_in_executor, monitor_process
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
    :param aux: auxiliary console port
    :param platform: Platform of this router
    """

    _status = {0: "inactive",
               1: "shutting down",
               2: "running",
               3: "suspended"}

    def __init__(self, name, node_id, project, manager, dynamips_id=None, console=None, aux=None, platform="c7200", hypervisor=None, ghost_flag=False):

        allocate_aux = manager.config.get_section_config("Dynamips").getboolean("allocate_aux_console_ports", False)

        super().__init__(name, node_id, project, manager, console=console, aux=aux, allocate_aux=aux)

        self._working_directory = os.path.join(self.project.module_working_directory(self.manager.module_name.lower()), self.id)
        try:
            os.makedirs(os.path.join(self._working_directory, "configs"), exist_ok=True)
        except OSError as e:
            raise DynamipsError("Can't create the dynamips config directory: {}".format(str(e)))
        if dynamips_id:
            self._convert_before_2_0_0_b3(dynamips_id)

        self._hypervisor = hypervisor
        self._dynamips_id = dynamips_id
        self._platform = platform
        self._image = ""
        self._startup_config = ""
        self._private_config = ""
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
        if sys.platform.startswith("win"):
            self._exec_area = 16  # 16 MB by default on Windows (Cygwin)
        else:
            self._exec_area = 64  # 64 MB on other systems
        self._disk0 = 0  # Megabytes
        self._disk1 = 0  # Megabytes
        self._auto_delete_disks = False
        self._mac_addr = ""
        self._system_id = "FTX0945W0MY"  # processor board ID in IOS
        self._slots = []
        self._ghost_flag = ghost_flag
        self._memory_watcher = None
        self._startup_config_content = ""
        self._private_config_content = ""

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
        for path in glob.glob(os.path.join(glob.escape(dynamips_dir), "configs", "i{}_*".format(dynamips_id))):
            dst = os.path.join(self._working_directory, "configs", os.path.basename(path))
            if not os.path.exists(dst):
                try:
                    shutil.move(path, dst)
                except OSError as e:
                    raise DynamipsError("Can't move {}: {}".format(path, str(e)))
        for path in glob.glob(os.path.join(glob.escape(dynamips_dir), "*_i{}_*".format(dynamips_id))):
            dst = os.path.join(self._working_directory, os.path.basename(path))
            if not os.path.exists(dst):
                try:
                    shutil.move(path, dst)
                except OSError as e:
                    raise DynamipsError("Can't move {}: {}".format(path, str(e)))

    def __json__(self):

        router_info = {"name": self.name,
                       "node_id": self.id,
                       "node_directory": os.path.join(self._working_directory),
                       "project_id": self.project.id,
                       "dynamips_id": self._dynamips_id,
                       "platform": self._platform,
                       "image": self._image,
                       "image_md5sum": md5sum(self._image),
                       "startup_config": self._startup_config,
                       "private_config": self._private_config,
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
                       "console_type": "telnet",
                       "aux": self.aux,
                       "mac_addr": self._mac_addr,
                       "system_id": self._system_id,
                       "startup_config_content": self._startup_config_content,
                       "private_config_content": self._private_config_content}

        # return the relative path if the IOS image is in the images_path directory
        router_info["image"] = self.manager.get_relative_image_path(self._image)

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
        asyncio.async(self.save_configs())

    @property
    def dynamips_id(self):
        """
        Returns the Dynamips VM ID.

        :return: Dynamips VM identifier
        """

        return self._dynamips_id

    @asyncio.coroutine
    def create(self):

        if not self._hypervisor:
            # We start the hypervisor is the dynamips folder and next we change to node dir
            # this allow the creation of common files in the dynamips folder
            self._hypervisor = yield from self.manager.start_new_hypervisor(working_dir=self.project.module_working_directory(self.manager.module_name.lower()))
            yield from self._hypervisor.set_working_dir(self._working_directory)

        yield from self._hypervisor.send('vm create "{name}" {id} {platform}'.format(name=self._name,
                                                                                     id=self._dynamips_id,
                                                                                     platform=self._platform))

        if not self._ghost_flag:

            log.info('Router {platform} "{name}" [{id}] has been created'.format(name=self._name,
                                                                                 platform=self._platform,
                                                                                 id=self._id))

            yield from self._hypervisor.send('vm set_con_tcp_port "{name}" {console}'.format(name=self._name, console=self._console))

            if self.aux is not None:
                yield from self._hypervisor.send('vm set_aux_tcp_port "{name}" {aux}'.format(name=self._name, aux=self.aux))

            # get the default base MAC address
            mac_addr = yield from self._hypervisor.send('{platform} get_mac_addr "{name}"'.format(platform=self._platform,
                                                                                                  name=self._name))
            self._mac_addr = mac_addr[0]

        self._hypervisor.devices.append(self)

    @asyncio.coroutine
    def get_status(self):
        """
        Returns the status of this router

        :returns: inactive, shutting down, running or suspended.
        """

        status = yield from self._hypervisor.send('vm get_status "{name}"'.format(name=self._name))
        if len(status) == 0:
            raise DynamipsError("Can't get vm {name} status".format(name=self._name))
        return self._status[int(status[0])]

    @asyncio.coroutine
    def start(self):
        """
        Starts this router.
        At least the IOS image must be set before it can start.
        """

        status = yield from self.get_status()
        if status == "suspended":
            yield from self.resume()
        elif status == "inactive":

            if not os.path.isfile(self._image) or not os.path.exists(self._image):
                if os.path.islink(self._image):
                    raise DynamipsError('IOS image "{}" linked to "{}" is not accessible'.format(self._image, os.path.realpath(self._image)))
                else:
                    raise DynamipsError('IOS image "{}" is not accessible'.format(self._image))

            try:
                with open(self._image, "rb") as f:
                    # read the first 7 bytes of the file.
                    elf_header_start = f.read(7)
            except OSError as e:
                raise DynamipsError('Cannot read ELF header for IOS image "{}": {}'.format(self._image, e))

            # IOS images must start with the ELF magic number, be 32-bit, big endian and have an ELF version of 1
            if elf_header_start != b'\x7fELF\x01\x02\x01':
                raise DynamipsError('"{}" is not a valid IOS image'.format(self._image))

            # check if there is enough RAM to run
            if not self._ghost_flag:
                self.check_available_ram(self.ram)

            yield from self._hypervisor.send('vm start "{name}"'.format(name=self._name))
            self.status = "started"
            log.info('router "{name}" [{id}] has been started'.format(name=self._name, id=self._id))

            self._memory_watcher = FileWatcher(self._memory_files(), self._memory_changed, strategy='hash', delay=30)
            monitor_process(self._hypervisor.process, self._termination_callback)

    @asyncio.coroutine
    def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self.status == "started":
            self.status = "stopped"
            log.info("Dynamips hypervisor process has stopped, return code: %d", returncode)
            if returncode != 0:
                self.project.emit("log.error", {"message": "Dynamips hypervisor process has stopped, return code: {}\n{}".format(returncode, self._hypervisor.read_stdout())})

    @asyncio.coroutine
    def stop(self):
        """
        Stops this router.
        """

        status = yield from self.get_status()
        if status != "inactive":
            try:
                yield from self._hypervisor.send('vm stop "{name}"'.format(name=self._name))
            except DynamipsError as e:
                log.warn("Could not stop {}: {}".format(self._name, e))
            self.status = "stopped"
            log.info('Router "{name}" [{id}] has been stopped'.format(name=self._name, id=self._id))
        if self._memory_watcher:
            self._memory_watcher.close()
            self._memory_watcher = None
        yield from self.save_configs()

    @asyncio.coroutine
    def reload(self):
        """
        Reload this router.
        """

        yield from self.stop()
        yield from self.start()

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this router.
        """

        status = yield from self.get_status()
        if status == "running":
            yield from self._hypervisor.send('vm suspend "{name}"'.format(name=self._name))
            self.status = "suspended"
            log.info('Router "{name}" [{id}] has been suspended'.format(name=self._name, id=self._id))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this suspended router
        """

        status = yield from self.get_status()
        if status == "suspended":
            yield from self._hypervisor.send('vm resume "{name}"'.format(name=self._name))
            self.status = "started"
        log.info('Router "{name}" [{id}] has been resumed'.format(name=self._name, id=self._id))

    @asyncio.coroutine
    def is_running(self):
        """
        Checks if this router is running.

        :returns: True if running, False otherwise
        """

        status = yield from self.get_status()
        if status == "running":
            return True
        return False

    @asyncio.coroutine
    def close(self):

        if not (yield from super().close()):
            return False

        for adapter in self._slots:
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)

        if self in self._hypervisor.devices:
            self._hypervisor.devices.remove(self)
        if self._hypervisor and not self._hypervisor.devices:
            try:
                yield from self.stop()
                yield from self._hypervisor.send('vm delete "{}"'.format(self._name))
            except DynamipsError as e:
                log.warn("Could not stop and delete {}: {}".format(self._name, e))
            yield from self.hypervisor.stop()

        if self._auto_delete_disks:
            # delete nvram and disk files
            files = glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_disk[0-1]".format(self.platform, self.dynamips_id)))
            files += glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_slot[0-1]".format(self.platform, self.dynamips_id)))
            files += glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_nvram".format(self.platform, self.dynamips_id)))
            files += glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_flash[0-1]".format(self.platform, self.dynamips_id)))
            files += glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_rom".format(self.platform, self.dynamips_id)))
            files += glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_bootflash".format(self.platform, self.dynamips_id)))
            files += glob.glob(os.path.join(glob.escape(self._working_directory), "{}_i{}_ssa".format(self.platform, self.dynamips_id)))
            for file in files:
                try:
                    log.debug("Deleting file {}".format(file))
                    yield from wait_run_in_executor(os.remove, file)
                except OSError as e:
                    log.warn("Could not delete file {}: {}".format(file, e))
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

    @asyncio.coroutine
    def list(self):
        """
        Returns all VM instances

        :returns: list of all VM instances
        """

        vm_list = yield from self._hypervisor.send("vm list")
        return vm_list

    @asyncio.coroutine
    def list_con_ports(self):
        """
        Returns all VM console TCP ports

        :returns: list of port numbers
        """

        port_list = yield from self._hypervisor.send("vm list_con_ports")
        return port_list

    @asyncio.coroutine
    def set_debug_level(self, level):
        """
        Sets the debug level for this router (default is 0).

        :param level: level number
        """

        yield from self._hypervisor.send('vm set_debug_level "{name}" {level}'.format(name=self._name, level=level))

    @property
    def image(self):
        """
        Returns this IOS image for this router.

        :returns: path to IOS image file
        """

        return self._image

    @asyncio.coroutine
    def set_image(self, image):
        """
        Sets the IOS image for this router.
        There is no default.

        :param image: path to IOS image file
        """

        image = self.manager.get_abs_image_path(image)

        yield from self._hypervisor.send('vm set_ios "{name}" "{image}"'.format(name=self._name, image=image))

        log.info('Router "{name}" [{id}]: has a new IOS image set: "{image}"'.format(name=self._name,
                                                                                     id=self._id,
                                                                                     image=image))

        self._image = image

    @property
    def ram(self):
        """
        Returns the amount of RAM allocated to this router.

        :returns: amount of RAM in Mbytes (integer)
        """

        return self._ram

    @asyncio.coroutine
    def set_ram(self, ram):
        """
        Sets amount of RAM allocated to this router

        :param ram: amount of RAM in Mbytes (integer)
        """

        if self._ram == ram:
            return

        yield from self._hypervisor.send('vm set_ram "{name}" {ram}'.format(name=self._name, ram=ram))
        log.info('Router "{name}" [{id}]: RAM updated from {old_ram}MB to {new_ram}MB'.format(name=self._name,
                                                                                              id=self._id,
                                                                                              old_ram=self._ram,
                                                                                              new_ram=ram))
        self._ram = ram

    @property
    def nvram(self):
        """
        Returns the mount of NVRAM allocated to this router.

        :returns: amount of NVRAM in Kbytes (integer)
        """

        return self._nvram

    @asyncio.coroutine
    def set_nvram(self, nvram):
        """
        Sets amount of NVRAM allocated to this router

        :param nvram: amount of NVRAM in Kbytes (integer)
        """

        if self._nvram == nvram:
            return

        yield from self._hypervisor.send('vm set_nvram "{name}" {nvram}'.format(name=self._name, nvram=nvram))
        log.info('Router "{name}" [{id}]: NVRAM updated from {old_nvram}KB to {new_nvram}KB'.format(name=self._name,
                                                                                                    id=self._id,
                                                                                                    old_nvram=self._nvram,
                                                                                                    new_nvram=nvram))
        self._nvram = nvram

    @property
    def mmap(self):
        """
        Returns True if a mapped file is used to simulate this router memory.

        :returns: boolean either mmap is activated or not
        """

        return self._mmap

    @asyncio.coroutine
    def set_mmap(self, mmap):
        """
        Enable/Disable use of a mapped file to simulate router memory.
        By default, a mapped file is used. This is a bit slower, but requires less memory.

        :param mmap: activate/deactivate mmap (boolean)
        """

        if mmap:
            flag = 1
        else:
            flag = 0

        yield from self._hypervisor.send('vm set_ram_mmap "{name}" {mmap}'.format(name=self._name, mmap=flag))

        if mmap:
            log.info('Router "{name}" [{id}]: mmap enabled'.format(name=self._name, id=self._id))
        else:
            log.info('Router "{name}" [{id}]: mmap disabled'.format(name=self._name, id=self._id))
        self._mmap = mmap

    @property
    def sparsemem(self):
        """
        Returns True if sparse memory is used on this router.

        :returns: boolean either mmap is activated or not
        """

        return self._sparsemem

    @asyncio.coroutine
    def set_sparsemem(self, sparsemem):
        """
        Enable/disable use of sparse memory

        :param sparsemem: activate/deactivate sparsemem (boolean)
        """

        if sparsemem:
            flag = 1
        else:
            flag = 0
        yield from self._hypervisor.send('vm set_sparse_mem "{name}" {sparsemem}'.format(name=self._name, sparsemem=flag))

        if sparsemem:
            log.info('Router "{name}" [{id}]: sparse memory enabled'.format(name=self._name, id=self._id))
        else:
            log.info('Router "{name}" [{id}]: sparse memory disabled'.format(name=self._name, id=self._id))
        self._sparsemem = sparsemem

    @property
    def clock_divisor(self):
        """
        Returns the clock divisor value for this router.

        :returns: clock divisor value (integer)
        """

        return self._clock_divisor

    @asyncio.coroutine
    def set_clock_divisor(self, clock_divisor):
        """
        Sets the clock divisor value. The higher is the value, the faster is the clock in the
        virtual machine. The default is 4, but it is often required to adjust it.

        :param clock_divisor: clock divisor value (integer)
        """

        yield from self._hypervisor.send('vm set_clock_divisor "{name}" {clock}'.format(name=self._name, clock=clock_divisor))
        log.info('Router "{name}" [{id}]: clock divisor updated from {old_clock} to {new_clock}'.format(name=self._name,
                                                                                                        id=self._id,
                                                                                                        old_clock=self._clock_divisor,
                                                                                                        new_clock=clock_divisor))
        self._clock_divisor = clock_divisor

    @property
    def idlepc(self):
        """
        Returns the idle Pointer Counter (PC).

        :returns: idlepc value (string)
        """

        return self._idlepc

    @asyncio.coroutine
    def set_idlepc(self, idlepc):
        """
        Sets the idle Pointer Counter (PC)

        :param idlepc: idlepc value (string)
        """

        if not idlepc:
            idlepc = "0x0"

        is_running = yield from self.is_running()
        if not is_running:
            # router is not running
            yield from self._hypervisor.send('vm set_idle_pc "{name}" {idlepc}'.format(name=self._name, idlepc=idlepc))
        else:
            yield from self._hypervisor.send('vm set_idle_pc_online "{name}" 0 {idlepc}'.format(name=self._name, idlepc=idlepc))

        log.info('Router "{name}" [{id}]: idle-PC set to {idlepc}'.format(name=self._name, id=self._id, idlepc=idlepc))
        self._idlepc = idlepc

    @asyncio.coroutine
    def get_idle_pc_prop(self):
        """
        Gets the idle PC proposals.
        Takes 1000 measurements and records up to 10 idle PC proposals.
        There is a 10ms wait between each measurement.

        :returns: list of idle PC proposal
        """

        is_running = yield from self.is_running()
        was_auto_started = False
        if not is_running:
            yield from self.start()
            was_auto_started = True
            yield from asyncio.sleep(20)  # leave time to the router to boot

        log.info('Router "{name}" [{id}] has started calculating Idle-PC values'.format(name=self._name, id=self._id))
        begin = time.time()
        idlepcs = yield from self._hypervisor.send('vm get_idle_pc_prop "{}" 0'.format(self._name))
        log.info('Router "{name}" [{id}] has finished calculating Idle-PC values after {time:.4f} seconds'.format(name=self._name,
                                                                                                                  id=self._id,
                                                                                                                  time=time.time() - begin))
        if was_auto_started:
            yield from self.stop()
        return idlepcs

    @asyncio.coroutine
    def show_idle_pc_prop(self):
        """
        Dumps the idle PC proposals (previously generated).

        :returns: list of idle PC proposal
        """

        is_running = yield from self.is_running()
        if not is_running:
            # router is not running
            raise DynamipsError('Router "{name}" is not running'.format(name=self._name))

        proposals = yield from self._hypervisor.send('vm show_idle_pc_prop "{}" 0'.format(self._name))
        return proposals

    @property
    def idlemax(self):
        """
        Returns CPU idle max value.

        :returns: idle max (integer)
        """

        return self._idlemax

    @asyncio.coroutine
    def set_idlemax(self, idlemax):
        """
        Sets CPU idle max value

        :param idlemax: idle max value (integer)
        """

        is_running = yield from self.is_running()
        if is_running:  # router is running
            yield from self._hypervisor.send('vm set_idle_max "{name}" 0 {idlemax}'.format(name=self._name, idlemax=idlemax))

        log.info('Router "{name}" [{id}]: idlemax updated from {old_idlemax} to {new_idlemax}'.format(name=self._name,
                                                                                                      id=self._id,
                                                                                                      old_idlemax=self._idlemax,
                                                                                                      new_idlemax=idlemax))

        self._idlemax = idlemax

    @property
    def idlesleep(self):
        """
        Returns CPU idle sleep time value.

        :returns: idle sleep (integer)
        """

        return self._idlesleep

    @asyncio.coroutine
    def set_idlesleep(self, idlesleep):
        """
        Sets CPU idle sleep time value.

        :param idlesleep: idle sleep value (integer)
        """

        is_running = yield from self.is_running()
        if is_running:  # router is running
            yield from self._hypervisor.send('vm set_idle_sleep_time "{name}" 0 {idlesleep}'.format(name=self._name,
                                                                                                    idlesleep=idlesleep))

        log.info('Router "{name}" [{id}]: idlesleep updated from {old_idlesleep} to {new_idlesleep}'.format(name=self._name,
                                                                                                            id=self._id,
                                                                                                            old_idlesleep=self._idlesleep,
                                                                                                            new_idlesleep=idlesleep))

        self._idlesleep = idlesleep

    @property
    def ghost_file(self):
        """
        Returns ghost RAM file.

        :returns: path to ghost file
        """

        return self._ghost_file

    @asyncio.coroutine
    def set_ghost_file(self, ghost_file):
        """
        Sets ghost RAM file

        :ghost_file: path to ghost file
        """

        yield from self._hypervisor.send('vm set_ghost_file "{name}" {ghost_file}'.format(name=self._name,
                                                                                          ghost_file=shlex.quote(ghost_file)))

        log.info('Router "{name}" [{id}]: ghost file set to {ghost_file}'.format(name=self._name,
                                                                                 id=self._id,
                                                                                 ghost_file=ghost_file))

        self._ghost_file = ghost_file

    def formatted_ghost_file(self):
        """
        Returns a properly formatted ghost file name.

        :returns: formatted ghost_file name (string)
        """

        # replace specials characters in 'drive:\filename' in Linux and Dynamips in MS Windows or viceversa.
        ghost_file = "{}-{}.ghost".format(os.path.basename(self._image), self._ram)
        ghost_file = ghost_file.replace('\\', '-').replace('/', '-').replace(':', '-')
        return ghost_file

    @property
    def ghost_status(self):
        """Returns ghost RAM status

        :returns: ghost status (integer)
        """

        return self._ghost_status

    @asyncio.coroutine
    def set_ghost_status(self, ghost_status):
        """
        Sets ghost RAM status

        :param ghost_status: state flag indicating status
        0 => Do not use IOS ghosting
        1 => This is a ghost instance
        2 => Use an existing ghost instance
        """

        yield from self._hypervisor.send('vm set_ghost_status "{name}" {ghost_status}'.format(name=self._name,
                                                                                              ghost_status=ghost_status))

        log.info('Router "{name}" [{id}]: ghost status set to {ghost_status}'.format(name=self._name,
                                                                                     id=self._id,
                                                                                     ghost_status=ghost_status))
        self._ghost_status = ghost_status

    @property
    def exec_area(self):
        """
        Returns the exec area value.

        :returns: exec area value (integer)
        """

        return self._exec_area

    @asyncio.coroutine
    def set_exec_area(self, exec_area):
        """
        Sets the exec area value.
        The exec area is a pool of host memory used to store pages
        translated by the JIT (they contain the native code
        corresponding to MIPS code pages).

        :param exec_area: exec area value (integer)
        """

        yield from self._hypervisor.send('vm set_exec_area "{name}" {exec_area}'.format(name=self._name,
                                                                                        exec_area=exec_area))

        log.info('Router "{name}" [{id}]: exec area updated from {old_exec}MB to {new_exec}MB'.format(name=self._name,
                                                                                                      id=self._id,
                                                                                                      old_exec=self._exec_area,
                                                                                                      new_exec=exec_area))
        self._exec_area = exec_area

    @property
    def disk0(self):
        """
        Returns the size (MB) for PCMCIA disk0.

        :returns: disk0 size (integer)
        """

        return self._disk0

    @asyncio.coroutine
    def set_disk0(self, disk0):
        """
        Sets the size (MB) for PCMCIA disk0.

        :param disk0: disk0 size (integer)
        """

        yield from self._hypervisor.send('vm set_disk0 "{name}" {disk0}'.format(name=self._name, disk0=disk0))

        log.info('Router "{name}" [{id}]: disk0 updated from {old_disk0}MB to {new_disk0}MB'.format(name=self._name,
                                                                                                    id=self._id,
                                                                                                    old_disk0=self._disk0,
                                                                                                    new_disk0=disk0))
        self._disk0 = disk0

    @property
    def disk1(self):
        """
        Returns the size (MB) for PCMCIA disk1.

        :returns: disk1 size (integer)
        """

        return self._disk1

    @asyncio.coroutine
    def set_disk1(self, disk1):
        """
        Sets the size (MB) for PCMCIA disk1.

        :param disk1: disk1 size (integer)
        """

        yield from self._hypervisor.send('vm set_disk1 "{name}" {disk1}'.format(name=self._name, disk1=disk1))

        log.info('Router "{name}" [{id}]: disk1 updated from {old_disk1}MB to {new_disk1}MB'.format(name=self._name,
                                                                                                    id=self._id,
                                                                                                    old_disk1=self._disk1,
                                                                                                    new_disk1=disk1))
        self._disk1 = disk1

    @property
    def auto_delete_disks(self):
        """
        Returns True if auto delete disks is enabled on this router.

        :returns: boolean either auto delete disks is activated or not
        """

        return self._auto_delete_disks

    @asyncio.coroutine
    def set_auto_delete_disks(self, auto_delete_disks):
        """
        Enable/disable use of auto delete disks

        :param auto_delete_disks: activate/deactivate auto delete disks (boolean)
        """

        if auto_delete_disks:
            log.info('Router "{name}" [{id}]: auto delete disks enabled'.format(name=self._name, id=self._id))
        else:
            log.info('Router "{name}" [{id}]: auto delete disks disabled'.format(name=self._name, id=self._id))
        self._auto_delete_disks = auto_delete_disks

    @asyncio.coroutine
    def set_console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        self.console = console
        yield from self._hypervisor.send('vm set_con_tcp_port "{name}" {console}'.format(name=self._name, console=self.console))

    @asyncio.coroutine
    def set_aux(self, aux):
        """
        Sets the TCP auxiliary port.

        :param aux: console auxiliary port (integer)
        """

        self.aux = aux
        yield from self._hypervisor.send('vm set_aux_tcp_port "{name}" {aux}'.format(name=self._name, aux=aux))

    @asyncio.coroutine
    def get_cpu_usage(self, cpu_id=0):
        """
        Shows cpu usage in seconds, "cpu_id" is ignored.

        :returns: cpu usage in seconds
        """

        cpu_usage = yield from self._hypervisor.send('vm cpu_usage "{name}" {cpu_id}'.format(name=self._name, cpu_id=cpu_id))
        return int(cpu_usage[0])

    @property
    def mac_addr(self):
        """
        Returns the MAC address.

        :returns: the MAC address (hexadecimal format: hh:hh:hh:hh:hh:hh)
        """

        return self._mac_addr

    @asyncio.coroutine
    def set_mac_addr(self, mac_addr):
        """
        Sets the MAC address.

        :param mac_addr: a MAC address (hexadecimal format: hh:hh:hh:hh:hh:hh)
        """

        yield from self._hypervisor.send('{platform} set_mac_addr "{name}" {mac_addr}'.format(platform=self._platform,
                                                                                              name=self._name,
                                                                                              mac_addr=mac_addr))

        log.info('Router "{name}" [{id}]: MAC address updated from {old_mac} to {new_mac}'.format(name=self._name,
                                                                                                  id=self._id,
                                                                                                  old_mac=self._mac_addr,
                                                                                                  new_mac=mac_addr))
        self._mac_addr = mac_addr

    @property
    def system_id(self):
        """
        Returns the system ID.

        :returns: the system ID (also called board processor ID)
        """

        return self._system_id

    @asyncio.coroutine
    def set_system_id(self, system_id):
        """
        Sets the system ID.

        :param system_id: a system ID (also called board processor ID)
        """

        yield from self._hypervisor.send('{platform} set_system_id "{name}" {system_id}'.format(platform=self._platform,
                                                                                                name=self._name,
                                                                                                system_id=system_id))

        log.info('Router "{name}" [{id}]: system ID updated from {old_id} to {new_id}'.format(name=self._name,
                                                                                              id=self._id,
                                                                                              old_id=self._system_id,
                                                                                              new_id=system_id))
        self._system_id = system_id

    @asyncio.coroutine
    def get_slot_bindings(self):
        """
        Returns slot bindings.

        :returns: slot bindings (adapter names) list
        """

        slot_bindings = yield from self._hypervisor.send('vm slot_bindings "{}"'.format(self._name))
        return slot_bindings

    @asyncio.coroutine
    def slot_add_binding(self, slot_number, adapter):
        """
        Adds a slot binding (a module into a slot).

        :param slot_number: slot number
        :param adapter: device to add in the corresponding slot
        """

        try:
            slot = self._slots[slot_number]
        except IndexError:
            raise DynamipsError('Slot {slot_number} does not exist on router "{name}"'.format(name=self._name, slot_number=slot_number))

        if slot is not None:
            current_adapter = slot
            raise DynamipsError('Slot {slot_number} is already occupied by adapter {adapter} on router "{name}"'.format(name=self._name,
                                                                                                                        slot_number=slot_number,
                                                                                                                        adapter=current_adapter))

        is_running = yield from self.is_running()

        # Only c7200, c3600 and c3745 (NM-4T only) support new adapter while running
        if is_running and not ((self._platform == 'c7200' and not str(adapter).startswith('C7200'))
                               and not (self._platform == 'c3600' and self.chassis == '3660')
                               and not (self._platform == 'c3745' and adapter == 'NM-4T')):
            raise DynamipsError('Adapter {adapter} cannot be added while router "{name}" is running'.format(adapter=adapter,
                                                                                                            name=self._name))

        yield from self._hypervisor.send('vm slot_add_binding "{name}" {slot_number} 0 {adapter}'.format(name=self._name,
                                                                                                         slot_number=slot_number,
                                                                                                         adapter=adapter))

        log.info('Router "{name}" [{id}]: adapter {adapter} inserted into slot {slot_number}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     adapter=adapter,
                                                                                                     slot_number=slot_number))

        self._slots[slot_number] = adapter

        # Generate an OIR event if the router is running
        if is_running:

            yield from self._hypervisor.send('vm slot_oir_start "{name}" {slot_number} 0'.format(name=self._name,
                                                                                                 slot_number=slot_number))

            log.info('Router "{name}" [{id}]: OIR start event sent to slot {slot_number}'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 slot_number=slot_number))

    @asyncio.coroutine
    def slot_remove_binding(self, slot_number):
        """
        Removes a slot binding (a module from a slot).

        :param slot_number: slot number
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError('Slot {slot_number} does not exist on router "{name}"'.format(name=self._name,
                                                                                              slot_number=slot_number))

        if adapter is None:
            raise DynamipsError('No adapter in slot {slot_number} on router "{name}"'.format(name=self._name,
                                                                                             slot_number=slot_number))

        is_running = yield from self.is_running()

        # Only c7200, c3600 and c3745 (NM-4T only) support to remove adapter while running
        if is_running and not ((self._platform == 'c7200' and not str(adapter).startswith('C7200'))
                               and not (self._platform == 'c3600' and self.chassis == '3660')
                               and not (self._platform == 'c3745' and adapter == 'NM-4T')):
            raise DynamipsError('Adapter {adapter} cannot be removed while router "{name}" is running'.format(adapter=adapter,
                                                                                                              name=self._name))

        # Generate an OIR event if the router is running
        if is_running:

            yield from self._hypervisor.send('vm slot_oir_stop "{name}" {slot_number} 0'.format(name=self._name,
                                                                                                slot_number=slot_number))

            log.info('Router "{name}" [{id}]: OIR stop event sent to slot {slot_number}'.format(name=self._name,
                                                                                                id=self._id,
                                                                                                slot_number=slot_number))

        yield from self._hypervisor.send('vm slot_remove_binding "{name}" {slot_number} 0'.format(name=self._name,
                                                                                                  slot_number=slot_number))

        log.info('Router "{name}" [{id}]: adapter {adapter} removed from slot {slot_number}'.format(name=self._name,
                                                                                                    id=self._id,
                                                                                                    adapter=adapter,
                                                                                                    slot_number=slot_number))
        self._slots[slot_number] = None

    @asyncio.coroutine
    def install_wic(self, wic_slot_number, wic):
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
            raise DynamipsError("WIC slot {wic_slot_number} doesn't exist".format(wic_slot_number=wic_slot_number))

        if not adapter.wic_slot_available(wic_slot_number):
            raise DynamipsError("WIC slot {wic_slot_number} is already occupied by another WIC".format(wic_slot_number=wic_slot_number))

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_number = 16 * (wic_slot_number + 1)
        yield from self._hypervisor.send('vm slot_add_binding "{name}" {slot_number} {wic_slot_number} {wic}'.format(name=self._name,
                                                                                                                     slot_number=slot_number,
                                                                                                                     wic_slot_number=internal_wic_slot_number,
                                                                                                                     wic=wic))

        log.info('Router "{name}" [{id}]: {wic} inserted into WIC slot {wic_slot_number}'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 wic=wic,
                                                                                                 wic_slot_number=wic_slot_number))

        adapter.install_wic(wic_slot_number, wic)

    @asyncio.coroutine
    def uninstall_wic(self, wic_slot_number):
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
            raise DynamipsError("WIC slot {wic_slot_number} doesn't exist".format(wic_slot_number=wic_slot_number))

        if adapter.wic_slot_available(wic_slot_number):
            raise DynamipsError("No WIC is installed in WIC slot {wic_slot_number}".format(wic_slot_number=wic_slot_number))

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_number = 16 * (wic_slot_number + 1)
        yield from self._hypervisor.send('vm slot_remove_binding "{name}" {slot_number} {wic_slot_number}'.format(name=self._name,
                                                                                                                  slot_number=slot_number,
                                                                                                                  wic_slot_number=internal_wic_slot_number))

        log.info('Router "{name}" [{id}]: {wic} removed from WIC slot {wic_slot_number}'.format(name=self._name,
                                                                                                id=self._id,
                                                                                                wic=adapter.wics[wic_slot_number],
                                                                                                wic_slot_number=wic_slot_number))
        adapter.uninstall_wic(wic_slot_number)

    @asyncio.coroutine
    def get_slot_nio_bindings(self, slot_number):
        """
        Returns slot NIO bindings.

        :param slot_number: slot number

        :returns: list of NIO bindings
        """

        nio_bindings = yield from self._hypervisor.send('vm slot_nio_bindings "{name}" {slot_number}'.format(name=self._name,
                                                                                                             slot_number=slot_number))
        return nio_bindings

    @asyncio.coroutine
    def slot_add_nio_binding(self, slot_number, port_number, nio):
        """
        Adds a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError('Slot {slot_number} does not exist on router "{name}"'.format(name=self._name,
                                                                                              slot_number=slot_number))

        if adapter is None:
            raise DynamipsError("Adapter is missing in slot {slot_number}".format(slot_number=slot_number))

        if not adapter.port_exists(port_number):
            raise DynamipsError("Port {port_number} does not exist in adapter {adapter}".format(adapter=adapter,
                                                                                                port_number=port_number))

        try:
            yield from self._hypervisor.send('vm slot_add_nio_binding "{name}" {slot_number} {port_number} {nio}'.format(name=self._name,
                                                                                                                         slot_number=slot_number,
                                                                                                                         port_number=port_number,
                                                                                                                         nio=nio))
        except DynamipsError:
            # in case of error try to remove and add the nio binding
            yield from self._hypervisor.send('vm slot_remove_nio_binding "{name}" {slot_number} {port_number}'.format(name=self._name,
                                                                                                                      slot_number=slot_number,
                                                                                                                      port_number=port_number))
            yield from self._hypervisor.send('vm slot_add_nio_binding "{name}" {slot_number} {port_number} {nio}'.format(name=self._name,
                                                                                                                         slot_number=slot_number,
                                                                                                                         port_number=port_number,
                                                                                                                         nio=nio))

        log.info('Router "{name}" [{id}]: NIO {nio_name} bound to port {slot_number}/{port_number}'.format(name=self._name,
                                                                                                           id=self._id,
                                                                                                           nio_name=nio.name,
                                                                                                           slot_number=slot_number,
                                                                                                           port_number=port_number))

        yield from self.slot_enable_nio(slot_number, port_number)
        adapter.add_nio(port_number, nio)

    @asyncio.coroutine
    def slot_remove_nio_binding(self, slot_number, port_number):
        """
        Removes a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number

        :returns: removed NIO instance
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError('Slot {slot_number} does not exist on router "{name}"'.format(name=self._name,
                                                                                              slot_number=slot_number))

        if adapter is None:
            raise DynamipsError("Adapter is missing in slot {slot_number}".format(slot_number=slot_number))

        if not adapter.port_exists(port_number):
            raise DynamipsError("Port {port_number} does not exist in adapter {adapter}".format(adapter=adapter,
                                                                                                port_number=port_number))

        yield from self.slot_disable_nio(slot_number, port_number)
        yield from self._hypervisor.send('vm slot_remove_nio_binding "{name}" {slot_number} {port_number}'.format(name=self._name,
                                                                                                                  slot_number=slot_number,
                                                                                                                  port_number=port_number))

        nio = adapter.get_nio(port_number)
        if nio is None:
            return
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(port_number)

        log.info('Router "{name}" [{id}]: NIO {nio_name} removed from port {slot_number}/{port_number}'.format(name=self._name,
                                                                                                               id=self._id,
                                                                                                               nio_name=nio.name,
                                                                                                               slot_number=slot_number,
                                                                                                               port_number=port_number))

        return nio

    @asyncio.coroutine
    def slot_enable_nio(self, slot_number, port_number):
        """
        Enables a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        """

        is_running = yield from self.is_running()
        if is_running:  # running router
            yield from self._hypervisor.send('vm slot_enable_nio "{name}" {slot_number} {port_number}'.format(name=self._name,
                                                                                                              slot_number=slot_number,
                                                                                                              port_number=port_number))

            log.info('Router "{name}" [{id}]: NIO enabled on port {slot_number}/{port_number}'.format(name=self._name,
                                                                                                      id=self._id,
                                                                                                      slot_number=slot_number,
                                                                                                      port_number=port_number))

    @asyncio.coroutine
    def slot_disable_nio(self, slot_number, port_number):
        """
        Disables a slot NIO binding.

        :param slot_number: slot number
        :param port_number: port number
        """

        is_running = yield from self.is_running()
        if is_running:  # running router
            yield from self._hypervisor.send('vm slot_disable_nio "{name}" {slot_number} {port_number}'.format(name=self._name,
                                                                                                               slot_number=slot_number,
                                                                                                               port_number=port_number))

            log.info('Router "{name}" [{id}]: NIO disabled on port {slot_number}/{port_number}'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       slot_number=slot_number,
                                                                                                       port_number=port_number))

    @asyncio.coroutine
    def start_capture(self, slot_number, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param slot_number: slot number
        :param port_number: port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        try:
            open(output_file, 'w+').close()
        except OSError as e:
            raise DynamipsError('Can not write capture to "{}": {}'.format(output_file, str(e)))

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError('Slot {slot_number} does not exist on router "{name}"'.format(name=self._name,
                                                                                              slot_number=slot_number))
        if not adapter.port_exists(port_number):
            raise DynamipsError("Port {port_number} does not exist in adapter {adapter}".format(adapter=adapter,
                                                                                                port_number=port_number))

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError("Port {slot_number}/{port_number} is not connected".format(slot_number=slot_number,
                                                                                           port_number=port_number))

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {port_number} has already a filter applied on {adapter}".format(adapter=adapter,
                                                                                                      port_number=port_number))

        yield from nio.bind_filter("both", "capture")
        yield from nio.setup_filter("both", '{} "{}"'.format(data_link_type, output_file))

        log.info('Router "{name}" [{id}]: starting packet capture on port {slot_number}/{port_number}'.format(name=self._name,
                                                                                                              id=self._id,
                                                                                                              nio_name=nio.name,
                                                                                                              slot_number=slot_number,
                                                                                                              port_number=port_number))

    @asyncio.coroutine
    def stop_capture(self, slot_number, port_number):
        """
        Stops a packet capture.

        :param slot_number: slot number
        :param port_number: port number
        """

        try:
            adapter = self._slots[slot_number]
        except IndexError:
            raise DynamipsError('Slot {slot_number} does not exist on router "{name}"'.format(name=self._name,
                                                                                              slot_number=slot_number))
        if not adapter.port_exists(port_number):
            raise DynamipsError("Port {port_number} does not exist in adapter {adapter}".format(adapter=adapter,
                                                                                                port_number=port_number))

        nio = adapter.get_nio(port_number)

        if not nio:
            raise DynamipsError("Port {slot_number}/{port_number} is not connected".format(slot_number=slot_number,
                                                                                           port_number=port_number))

        yield from nio.unbind_filter("both")

        log.info('Router "{name}" [{id}]: stopping packet capture on port {slot_number}/{port_number}'.format(name=self._name,
                                                                                                              id=self._id,
                                                                                                              nio_name=nio.name,
                                                                                                              slot_number=slot_number,
                                                                                                              port_number=port_number))

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
    def startup_config(self):
        """
        Returns the startup-config for this router.

        :returns: path to startup-config file
        """

        return self._startup_config

    @property
    def private_config(self):
        """
        Returns the private-config for this router.

        :returns: path to private-config file
        """

        return self._private_config

    @asyncio.coroutine
    def set_name(self, new_name):
        """
        Renames this router.

        :param new_name: new name string
        """

        if self._startup_config:
            # change the hostname in the startup-config
            startup_config_path = os.path.join(self._working_directory, "configs", "i{}_startup-config.cfg".format(self._dynamips_id))
            if os.path.isfile(startup_config_path):
                try:
                    with open(startup_config_path, "r+", encoding="utf-8", errors="replace") as f:
                        old_config = f.read()
                        new_config = re.sub(r"^hostname .+$", "hostname " + new_name, old_config, flags=re.MULTILINE)
                        f.seek(0)
                        self._startup_config_content = new_config
                        f.write(new_config)
                except OSError as e:
                    raise DynamipsError("Could not amend the configuration {}: {}".format(startup_config_path, e))

        if self._private_config:
            # change the hostname in the private-config
            private_config_path = os.path.join(self._working_directory, "configs", "i{}_private-config.cfg".format(self._dynamips_id))
            if os.path.isfile(private_config_path):
                try:
                    with open(private_config_path, "r+", encoding="utf-8", errors="replace") as f:
                        old_config = f.read()
                        new_config = old_config.replace(self.name, new_name)
                        f.seek(0)
                        self._private_config_content = new_config
                        f.write(new_config)
                except OSError as e:
                    raise DynamipsError("Could not amend the configuration {}: {}".format(private_config_path, e))

        yield from self._hypervisor.send('vm rename "{name}" "{new_name}"'.format(name=self._name, new_name=new_name))
        log.info('Router "{name}" [{id}]: renamed to "{new_name}"'.format(name=self._name, id=self._id, new_name=new_name))
        self._name = new_name

    @asyncio.coroutine
    def set_configs(self, startup_config, private_config=''):
        """
        Sets the config files that are pushed to startup-config and
        private-config in NVRAM when the instance is started.

        :param startup_config: path to statup-config file
        :param private_config: path to private-config file
        (keep existing data when if an empty string)
        """

        startup_config = startup_config.replace("\\", '/')
        private_config = private_config.replace("\\", '/')

        if self._startup_config != startup_config or self._private_config != private_config:
            self._startup_config = startup_config
            self._private_config = private_config

            if private_config:
                private_config_path = os.path.join(self._working_directory, private_config)
                try:
                    if not os.path.getsize(private_config_path):
                        # an empty private-config can prevent a router to boot.
                        private_config = ''
                        self._private_config_content = ""
                    else:
                        with open(private_config_path) as f:
                            self._private_config_content = f.read()
                except OSError as e:
                    raise DynamipsError("Cannot access the private-config {}: {}".format(private_config_path, e))

            try:
                startup_config_path = os.path.join(self._working_directory, startup_config)
                if os.path.exists(startup_config_path):
                    with open(startup_config_path, encoding="utf-8") as f:
                        self._startup_config_content = f.read()
                else:
                    self._startup_config_content = ''
            except OSError as e:
                raise DynamipsError("Cannot access the startup-config {}: {}".format(startup_config_path, e))

            yield from self._hypervisor.send('vm set_config "{name}" "{startup}" "{private}"'.format(name=self._name,
                                                                                                     startup=startup_config,
                                                                                                     private=private_config))

            log.info('Router "{name}" [{id}]: has a new startup-config set: "{startup}"'.format(name=self._name,
                                                                                                id=self._id,
                                                                                                startup=startup_config))

            if private_config:
                log.info('Router "{name}" [{id}]: has a new private-config set: "{private}"'.format(name=self._name,
                                                                                                    id=self._id,
                                                                                                    private=private_config))

    @asyncio.coroutine
    def extract_config(self):
        """
        Gets the contents of the config files
        startup-config and private-config from NVRAM.

        :returns: tuple (startup-config, private-config) base64 encoded
        """

        try:
            reply = yield from self._hypervisor.send('vm extract_config "{}"'.format(self._name))
        except DynamipsError:
            # for some reason Dynamips gets frozen when it does not find the magic number in the NVRAM file.
            return None, None
        reply = reply[0].rsplit(' ', 2)[-2:]
        startup_config = reply[0][1:-1]  # get statup-config and remove single quotes
        private_config = reply[1][1:-1]  # get private-config and remove single quotes
        return startup_config, private_config

    @asyncio.coroutine
    def save_configs(self):
        """
        Saves the startup-config and private-config to files.
        """

        if self.startup_config or self.private_config:

            try:
                config_path = os.path.join(self._working_directory, "configs")
                os.makedirs(config_path, exist_ok=True)
            except OSError as e:
                raise DynamipsError("Could could not create configuration directory {}: {}".format(config_path, e))

            startup_config_base64, private_config_base64 = yield from self.extract_config()
            if startup_config_base64:
                if not self.startup_config:
                    self._startup_config = os.path.join("configs", "i{}_startup-config.cfg".format(self._dynamips_id))
                try:
                    config = base64.b64decode(startup_config_base64).decode("utf-8", errors="replace")
                    config = "!\n" + config.replace("\r", "")
                    config_path = os.path.join(self._working_directory, self.startup_config)
                    with open(config_path, "wb") as f:
                        log.info("saving startup-config to {}".format(self.startup_config))
                        self._startup_config_content = config
                        f.write(config.encode("utf-8"))
                except (binascii.Error, OSError) as e:
                    raise DynamipsError("Could not save the startup configuration {}: {}".format(config_path, e))

            if private_config_base64 and base64.b64decode(private_config_base64) != b'\nkerberos password \nend\n':
                if not self.private_config:
                    self._private_config = os.path.join("configs", "i{}_private-config.cfg".format(self._dynamips_id))
                try:
                    config = base64.b64decode(private_config_base64).decode("utf-8", errors="replace")
                    config_path = os.path.join(self._working_directory, self.private_config)
                    with open(config_path, "wb") as f:
                        log.info("saving private-config to {}".format(self.private_config))
                        self._private_config_content = config
                        f.write(config.encode("utf-8"))
                except (binascii.Error, OSError) as e:
                    raise DynamipsError("Could not save the private configuration {}: {}".format(config_path, e))

    def delete(self):
        """
        Delete this VM (including all its files).
        """
        try:
            yield from wait_run_in_executor(shutil.rmtree, self._working_directory)
        except OSError as e:
            log.warn("Could not delete file {}".format(e))

        self.manager.release_dynamips_id(self._project.id, self._dynamips_id)

    @asyncio.coroutine
    def clean_delete(self):
        """
        Deletes this router & associated files (nvram, disks etc.)
        """

        yield from self._hypervisor.send('vm clean_delete "{}"'.format(self._name))
        self._hypervisor.devices.remove(self)
        try:
            yield from wait_run_in_executor(shutil.rmtree, self._working_directory)
        except OSError as e:
            log.warn("Could not delete file {}".format(e))
        log.info('Router "{name}" [{id}] has been deleted (including associated files)'.format(name=self._name, id=self._id))

    def _memory_files(self):
        return [
            os.path.join(self._working_directory, "{}_i{}_rom".format(self.platform, self.dynamips_id)),
            os.path.join(self._working_directory, "{}_i{}_nvram".format(self.platform, self.dynamips_id))
        ]
