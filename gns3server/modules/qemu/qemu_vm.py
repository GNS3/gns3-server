# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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
QEMU VM management (creates command line, processes, files etc.) in
order to run a QEMU VM.
"""

import sys
import os
import re
import shutil
import subprocess
import shlex
import asyncio
import socket
import gns3server

from pkg_resources import parse_version
from .qemu_error import QemuError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from ..nios.nio_tap import NIOTAP
from ..nios.nio_nat import NIONAT
from ..base_vm import BaseVM
from ...schemas.qemu import QEMU_OBJECT_SCHEMA, QEMU_PLATFORMS
from ...utils.asyncio import monitor_process
from ...utils.images import md5sum

import logging
log = logging.getLogger(__name__)


class QemuVM(BaseVM):
    module_name = 'qemu'

    """
    QEMU VM implementation.

    :param name: Qemu VM name
    :param vm_id: Qemu VM identifier
    :param project: Project instance
    :param manager: Manager instance
    :param qemu_path: path to the QEMU binary
    :param platform: Platform to emulate
    :param console: TCP console port
    """

    def __init__(self, name, vm_id, project, manager, linked_clone=True, qemu_path=None, console_type="telnet", platform=None):

        super().__init__(name, vm_id, project, manager, console_type=console_type)
        server_config = manager.config.get_section_config("Server")
        self._host = server_config.get("host", "127.0.0.1")
        self._monitor_host = server_config.get("monitor_host", "127.0.0.1")
        self._linked_clone = linked_clone
        self._command = []
        self._process = None
        self._cpulimit_process = None
        self._monitor = None
        self._stdout_file = ""
        self._execute_lock = asyncio.Lock()

        # QEMU VM settings
        if qemu_path:
            try:
                self.qemu_path = qemu_path
            except QemuError as e:
                if platform:
                    self.platform = platform
                else:
                    raise e
        else:
            self.platform = platform

        self._hda_disk_image = ""
        self._hdb_disk_image = ""
        self._hdc_disk_image = ""
        self._hdd_disk_image = ""
        self._hda_disk_interface = "ide"
        self._hdb_disk_interface = "ide"
        self._hdc_disk_interface = "ide"
        self._hdd_disk_interface = "ide"
        self._cdrom_image = ""
        self._boot_priority = "c"
        self._mac_address = ""
        self._options = ""
        self._ram = 256
        self._cpus = 1
        self._ethernet_adapters = []
        self._adapter_type = "e1000"
        self._initrd = ""
        self._kernel_image = ""
        self._kernel_command_line = ""
        self._legacy_networking = False
        self._acpi_shutdown = False
        self._cpu_throttling = 0  # means no CPU throttling
        self._process_priority = "low"

        self.mac_address = ""  # this will generate a MAC address
        self.adapters = 1  # creates 1 adapter by default
        log.info('QEMU VM "{name}" [{id}] has been created'.format(name=self._name, id=self._id))

    @property
    def monitor(self):
        """
        Returns the TCP monitor port.

        :returns: monitor port (integer)
        """

        return self._monitor

    @property
    def qemu_path(self):
        """
        Returns the QEMU binary path for this QEMU VM.

        :returns: QEMU path
        """

        return self._qemu_path

    @qemu_path.setter
    def qemu_path(self, qemu_path):
        """
        Sets the QEMU binary path this QEMU VM.

        :param qemu_path: QEMU path
        """

        if qemu_path and os.pathsep not in qemu_path:
            new_qemu_path = shutil.which(qemu_path, path=os.pathsep.join(self._manager.paths_list()))
            if new_qemu_path is None:
                raise QemuError("QEMU binary path {} is not found in the path".format(qemu_path))
            qemu_path = new_qemu_path

        self._check_qemu_path(qemu_path)
        self._qemu_path = qemu_path
        self._platform = os.path.basename(qemu_path)
        if self._platform == "qemu-kvm":
            self._platform = "x86_64"
        else:
            qemu_bin = os.path.basename(qemu_path)
            qemu_bin = re.sub(r'(w)?\.(exe|EXE)$', '', qemu_bin)
            self._platform = re.sub(r'^qemu-system-(.*)$', r'\1', qemu_bin, re.IGNORECASE)
        if self._platform.split(".")[0] not in QEMU_PLATFORMS:
            raise QemuError("Platform {} is unknown".format(self._platform))
        log.info('QEMU VM "{name}" [{id}] has set the QEMU path to {qemu_path}'.format(name=self._name,
                                                                                       id=self._id,
                                                                                       qemu_path=qemu_path))

    def _check_qemu_path(self, qemu_path):
        if qemu_path is None:
            raise QemuError("QEMU binary path is not set")
        if not os.path.exists(qemu_path):
            raise QemuError("QEMU binary '{}' is not accessible".format(qemu_path))
        if not os.access(qemu_path, os.X_OK):
            raise QemuError("QEMU binary '{}' is not executable".format(qemu_path))

    @property
    def platform(self):
        """
        Return the current platform
        """
        return self._platform

    @platform.setter
    def platform(self, platform):
        self._platform = platform
        if sys.platform.startswith("win"):
            self.qemu_path = "qemu-system-{}w.exe".format(platform)
        else:
            self.qemu_path = "qemu-system-{}".format(platform)

    @property
    def hda_disk_image(self):
        """
        Returns the hda disk image path for this QEMU VM.

        :returns: QEMU hda disk image path
        """

        return self._hda_disk_image

    @hda_disk_image.setter
    def hda_disk_image(self, hda_disk_image):
        """
        Sets the hda disk image for this QEMU VM.

        :param hda_disk_image: QEMU hda disk image path
        """
        self._hda_disk_image = self.manager.get_abs_image_path(hda_disk_image)
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hda disk image path to {disk_image}'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       disk_image=self._hda_disk_image))

    @property
    def hdb_disk_image(self):
        """
        Returns the hdb disk image path for this QEMU VM.

        :returns: QEMU hdb disk image path
        """

        return self._hdb_disk_image

    @hdb_disk_image.setter
    def hdb_disk_image(self, hdb_disk_image):
        """
        Sets the hdb disk image for this QEMU VM.

        :param hdb_disk_image: QEMU hdb disk image path
        """

        self._hdb_disk_image = self.manager.get_abs_image_path(hdb_disk_image)
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hdb disk image path to {disk_image}'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       disk_image=self._hdb_disk_image))

    @property
    def hdc_disk_image(self):
        """
        Returns the hdc disk image path for this QEMU VM.

        :returns: QEMU hdc disk image path
        """

        return self._hdc_disk_image

    @hdc_disk_image.setter
    def hdc_disk_image(self, hdc_disk_image):
        """
        Sets the hdc disk image for this QEMU VM.

        :param hdc_disk_image: QEMU hdc disk image path
        """

        self._hdc_disk_image = self.manager.get_abs_image_path(hdc_disk_image)
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hdc disk image path to {disk_image}'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       disk_image=self._hdc_disk_image))

    @property
    def hdd_disk_image(self):
        """
        Returns the hdd disk image path for this QEMU VM.

        :returns: QEMU hdd disk image path
        """

        return self._hdd_disk_image

    @hdd_disk_image.setter
    def hdd_disk_image(self, hdd_disk_image):
        """
        Sets the hdd disk image for this QEMU VM.

        :param hdd_disk_image: QEMU hdd disk image path
        """

        self._hdd_disk_image = hdd_disk_image
        self._hdd_disk_image = self.manager.get_abs_image_path(hdd_disk_image)
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hdd disk image path to {disk_image}'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       disk_image=self._hdd_disk_image))

    @property
    def hda_disk_interface(self):
        """
        Returns the hda disk interface this QEMU VM.

        :returns: QEMU hda disk interface
        """

        return self._hda_disk_interface

    @hda_disk_interface.setter
    def hda_disk_interface(self, hda_disk_interface):
        """
        Sets the hda disk interface for this QEMU VM.

        :param hda_disk_interface: QEMU hda disk interface
        """

        self._hda_disk_interface = hda_disk_interface
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hda disk interface to {interface}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     interface=self._hda_disk_interface))

    @property
    def hdb_disk_interface(self):
        """
        Returns the hdb disk interface this QEMU VM.

        :returns: QEMU hdb disk interface
        """

        return self._hda_disk_interface

    @hdb_disk_interface.setter
    def hdb_disk_interface(self, hdb_disk_interface):
        """
        Sets the hda disk interface for this QEMU VM.

        :param hdb_disk_interface: QEMU hdb disk interface
        """

        self._hdb_disk_interface = hdb_disk_interface
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hdb disk interface to {interface}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     interface=self._hdb_disk_interface))

    @property
    def hdc_disk_interface(self):
        """
        Returns the hdc disk interface this QEMU VM.

        :returns: QEMU hdc disk interface
        """

        return self._hdc_disk_interface

    @hdc_disk_interface.setter
    def hdc_disk_interface(self, hdc_disk_interface):
        """
        Sets the hdc disk interface for this QEMU VM.

        :param hdc_disk_interface: QEMU hdc disk interface
        """

        self._hdc_disk_interface = hdc_disk_interface
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hdc disk interface to {interface}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     interface=self._hdc_disk_interface))

    @property
    def hdd_disk_interface(self):
        """
        Returns the hda disk interface this QEMU VM.

        :returns: QEMU hda disk interface
        """

        return self._hdd_disk_interface

    @hdd_disk_interface.setter
    def hdd_disk_interface(self, hdd_disk_interface):
        """
        Sets the hdd disk interface for this QEMU VM.

        :param hdd_disk_interface: QEMU hdd disk interface
        """

        self._hdd_disk_interface = hdd_disk_interface
        log.info('QEMU VM "{name}" [{id}] has set the QEMU hdd disk interface to {interface}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     interface=self._hdd_disk_interface))

    @property
    def cdrom_image(self):
        """
        Returns the cdrom image path for this QEMU VM.

        :returns: QEMU cdrom image path
        """

        return self._cdrom_image

    @cdrom_image.setter
    def cdrom_image(self, cdrom_image):
        """
        Sets the cdrom image for this QEMU VM.

        :param cdrom_image: QEMU cdrom image path
        """
        self._cdrom_image = self.manager.get_abs_image_path(cdrom_image)
        log.info('QEMU VM "{name}" [{id}] has set the QEMU cdrom image path to {cdrom_image}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     cdrom_image=self._cdrom_image))

    @property
    def boot_priority(self):
        """
        Returns the boot priority for this QEMU VM.

        :returns: QEMU boot priority
        """

        return self._boot_priority

    @boot_priority.setter
    def boot_priority(self, boot_priority):
        """
        Sets the boot priority for this QEMU VM.

        :param boot_priority: QEMU boot priority
        """

        self._boot_priority = boot_priority
        log.info('QEMU VM "{name}" [{id}] has set the boot priority to {boot_priority}'.format(name=self._name,
                                                                                               id=self._id,
                                                                                               boot_priority=self._boot_priority))

    @property
    def adapters(self):
        """
        Returns the number of Ethernet adapters for this QEMU VM.

        :returns: number of adapters
        """

        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this QEMU VM.

        :param adapters: number of adapters
        """

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info('QEMU VM "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     adapters=adapters))

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this QEMU VM.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this QEMU VM.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type

        log.info('QEMU VM "{name}" [{id}]: adapter type changed to {adapter_type}'.format(name=self._name,
                                                                                          id=self._id,
                                                                                          adapter_type=adapter_type))

    @property
    def mac_address(self):
        """
        Returns the MAC address for this QEMU VM.

        :returns: adapter type (string)
        """

        return self._mac_address

    @mac_address.setter
    def mac_address(self, mac_address):
        """
        Sets the MAC address for this QEMU VM.

        :param mac_address: MAC address
        """

        if not mac_address:
            self._mac_address = "00:00:ab:%s:%s:00" % (self.id[-4:-2], self.id[-2:])
        else:
            self._mac_address = mac_address

        log.info('QEMU VM "{name}" [{id}]: MAC address changed to {mac_addr}'.format(name=self._name,
                                                                                     id=self._id,
                                                                                     mac_addr=mac_address))

    @property
    def legacy_networking(self):
        """
        Returns either QEMU legacy networking commands are used.

        :returns: boolean
        """

        return self._legacy_networking

    @legacy_networking.setter
    def legacy_networking(self, legacy_networking):
        """
        Sets either QEMU legacy networking commands are used.

        :param legacy_networking: boolean
        """

        if legacy_networking:
            log.info('QEMU VM "{name}" [{id}] has enabled legacy networking'.format(name=self._name, id=self._id))
        else:
            log.info('QEMU VM "{name}" [{id}] has disabled legacy networking'.format(name=self._name, id=self._id))
        self._legacy_networking = legacy_networking

    @property
    def acpi_shutdown(self):
        """
        Returns either this QEMU VM can be ACPI shutdown.

        :returns: boolean
        """

        return self._acpi_shutdown

    @acpi_shutdown.setter
    def acpi_shutdown(self, acpi_shutdown):
        """
        Sets either this QEMU VM can be ACPI shutdown.

        :param acpi_shutdown: boolean
        """

        if acpi_shutdown:
            log.info('QEMU VM "{name}" [{id}] has enabled ACPI shutdown'.format(name=self._name, id=self._id))
        else:
            log.info('QEMU VM "{name}" [{id}] has disabled ACPI shutdown'.format(name=self._name, id=self._id))
        self._acpi_shutdown = acpi_shutdown

    @property
    def cpu_throttling(self):
        """
        Returns the percentage of CPU allowed.

        :returns: integer
        """

        return self._cpu_throttling

    @cpu_throttling.setter
    def cpu_throttling(self, cpu_throttling):
        """
        Sets the percentage of CPU allowed.

        :param cpu_throttling: integer
        """

        log.info('QEMU VM "{name}" [{id}] has set the percentage of CPU allowed to {cpu}'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 cpu=cpu_throttling))
        self._cpu_throttling = cpu_throttling
        self._stop_cpulimit()
        if cpu_throttling:
            self._set_cpu_throttling()

    @property
    def process_priority(self):
        """
        Returns the process priority.

        :returns: string
        """

        return self._process_priority

    @process_priority.setter
    def process_priority(self, process_priority):
        """
        Sets the process priority.

        :param process_priority: string
        """

        log.info('QEMU VM "{name}" [{id}] has set the process priority to {priority}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             priority=process_priority))
        self._process_priority = process_priority

    @property
    def ram(self):
        """
        Returns the RAM amount for this QEMU VM.

        :returns: RAM amount in MB
        """

        return self._ram

    @ram.setter
    def ram(self, ram):
        """
        Sets the amount of RAM for this QEMU VM.

        :param ram: RAM amount in MB
        """

        log.info('QEMU VM "{name}" [{id}] has set the RAM to {ram}'.format(name=self._name, id=self._id, ram=ram))
        self._ram = ram

    @property
    def cpus(self):
        """
        Returns the number of vCPUs this QEMU VM.

        :returns: number of vCPUs.
        """

        return self._cpus

    @cpus.setter
    def cpus(self, cpus):
        """
        Sets the number of vCPUs this QEMU VM.

        :param cpus: number of vCPUs.
        """

        log.info('QEMU VM "{name}" [{id}] has set the number of vCPUs to {cpus}'.format(name=self._name, id=self._id, cpus=cpus))
        self._cpus = cpus

    @property
    def options(self):
        """
        Returns the options for this QEMU VM.

        :returns: QEMU options
        """

        return self._options

    @options.setter
    def options(self, options):
        """
        Sets the options for this QEMU VM.

        :param options: QEMU options
        """

        log.info('QEMU VM "{name}" [{id}] has set the QEMU options to {options}'.format(name=self._name,
                                                                                        id=self._id,
                                                                                        options=options))

        if not sys.platform.startswith("linux"):
            if "-no-kvm" in options:
                options = options.replace("-no-kvm", "")
            if "-enable-kvm" in options:
                options = options.replace("-enable-kvm", "")
        elif "-icount" in options and ("-no-kvm" not in options):
            # automatically add the -no-kvm option if -icount is detected
            # to help with the migration of ASA VMs created before version 1.4
            options = "-no-kvm " + options
        self._options = options.strip()

    @property
    def initrd(self):
        """
        Returns the initrd path for this QEMU VM.

        :returns: QEMU initrd path
        """

        return self._initrd

    @initrd.setter
    def initrd(self, initrd):
        """
        Sets the initrd path for this QEMU VM.

        :param initrd: QEMU initrd path
        """

        if not os.path.isabs(initrd):
            server_config = self.manager.config.get_section_config("Server")
            initrd = os.path.join(os.path.expanduser(server_config.get("images_path", "~/GNS3/images")), "QEMU", initrd)

        log.info('QEMU VM "{name}" [{id}] has set the QEMU initrd path to {initrd}'.format(name=self._name,
                                                                                           id=self._id,
                                                                                           initrd=initrd))
        self._initrd = initrd

    @property
    def kernel_image(self):
        """
        Returns the kernel image path for this QEMU VM.

        :returns: QEMU kernel image path
        """

        return self._kernel_image

    @kernel_image.setter
    def kernel_image(self, kernel_image):
        """
        Sets the kernel image path for this QEMU VM.

        :param kernel_image: QEMU kernel image path
        """

        if not os.path.isabs(kernel_image):
            server_config = self.manager.config.get_section_config("Server")
            kernel_image = os.path.join(os.path.expanduser(server_config.get("images_path", "~/GNS3/images")), "QEMU", kernel_image)

        log.info('QEMU VM "{name}" [{id}] has set the QEMU kernel image path to {kernel_image}'.format(name=self._name,
                                                                                                       id=self._id,
                                                                                                       kernel_image=kernel_image))
        self._kernel_image = kernel_image

    @property
    def kernel_command_line(self):
        """
        Returns the kernel command line for this QEMU VM.

        :returns: QEMU kernel command line
        """

        return self._kernel_command_line

    @kernel_command_line.setter
    def kernel_command_line(self, kernel_command_line):
        """
        Sets the kernel command line for this QEMU VM.

        :param kernel_command_line: QEMU kernel command line
        """

        log.info('QEMU VM "{name}" [{id}] has set the QEMU kernel command line to {kernel_command_line}'.format(name=self._name,
                                                                                                                id=self._id,
                                                                                                                kernel_command_line=kernel_command_line))
        self._kernel_command_line = kernel_command_line

    @asyncio.coroutine
    def _set_process_priority(self):
        """
        Changes the process priority
        """

        if sys.platform.startswith("win"):
            try:
                import win32api
                import win32con
                import win32process
            except ImportError:
                log.error("pywin32 must be installed to change the priority class for QEMU VM {}".format(self._name))
            else:
                log.info("setting QEMU VM {} priority class to BELOW_NORMAL".format(self._name))
                handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, 0, self._process.pid)
                if self._process_priority == "realtime":
                    priority = win32process.REALTIME_PRIORITY_CLASS
                elif self._process_priority == "very high":
                    priority = win32process.HIGH_PRIORITY_CLASS
                elif self._process_priority == "high":
                    priority = win32process.ABOVE_NORMAL_PRIORITY_CLASS
                elif self._process_priority == "low":
                    priority = win32process.BELOW_NORMAL_PRIORITY_CLASS
                elif self._process_priority == "very low":
                    priority = win32process.IDLE_PRIORITY_CLASS
                else:
                    priority = win32process.NORMAL_PRIORITY_CLASS
                win32process.SetPriorityClass(handle, priority)
        else:
            if self._process_priority == "realtime":
                priority = -20
            elif self._process_priority == "very high":
                priority = -15
            elif self._process_priority == "high":
                priority = -5
            elif self._process_priority == "low":
                priority = 5
            elif self._process_priority == "very low":
                priority = 19
            else:
                priority = 0
            try:
                process = yield from asyncio.create_subprocess_exec('renice', '-n', str(priority), '-p', str(self._process.pid))
                yield from process.wait()
            except (OSError, subprocess.SubprocessError) as e:
                log.error('Could not change process priority for QEMU VM "{}": {}'.format(self._name, e))

    def _stop_cpulimit(self):
        """
        Stops the cpulimit process.
        """

        if self._cpulimit_process and self._cpulimit_process.returncode is None:
            self._cpulimit_process.kill()
            try:
                self._process.wait(3)
            except subprocess.TimeoutExpired:
                log.error("Could not kill cpulimit process {}".format(self._cpulimit_process.pid))

    def _set_cpu_throttling(self):
        """
        Limits the CPU usage for current QEMU process.
        """

        if not self.is_running():
            return

        try:
            if sys.platform.startswith("win") and hasattr(sys, "frozen"):
                cpulimit_exec = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "cpulimit", "cpulimit.exe")
            else:
                cpulimit_exec = "cpulimit"
            subprocess.Popen([cpulimit_exec, "--lazy", "--pid={}".format(self._process.pid), "--limit={}".format(self._cpu_throttling)], cwd=self.working_dir)
            log.info("CPU throttled to {}%".format(self._cpu_throttling))
        except FileNotFoundError:
            raise QemuError("cpulimit could not be found, please install it or deactivate CPU throttling")
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError("Could not throttle CPU: {}".format(e))

    @asyncio.coroutine
    def start(self):
        """
        Starts this QEMU VM.
        """

        with (yield from self._execute_lock):
            if self.is_running():
                # resume the VM if it is paused
                yield from self.resume()
                return

            else:

                if self._manager.config.get_section_config("Qemu").getboolean("monitor", True):
                    try:
                        info = socket.getaddrinfo(self._monitor_host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
                        if not info:
                            raise QemuError("getaddrinfo returns an empty list on {}".format(self._monitor_host))
                        for res in info:
                            af, socktype, proto, _, sa = res
                            # let the OS find an unused port for the Qemu monitor
                            with socket.socket(af, socktype, proto) as sock:
                                sock.bind(sa)
                                self._monitor = sock.getsockname()[1]
                    except OSError as e:
                        raise QemuError("Could not find free port for the Qemu monitor: {}".format(e))

                # check if there is enough RAM to run
                self.check_available_ram(self.ram)

                self._command = yield from self._build_command()
                command_string = " ".join(shlex.quote(s) for s in self._command)
                try:
                    log.info("Starting QEMU with: {}".format(command_string))
                    self._stdout_file = os.path.join(self.working_dir, "qemu.log")
                    log.info("logging to {}".format(self._stdout_file))
                    with open(self._stdout_file, "w", encoding="utf-8") as fd:
                        fd.write("Start QEMU with {}\n\nExecution log:\n".format(command_string))
                        self._process = yield from asyncio.create_subprocess_exec(*self._command,
                                                                                  stdout=fd,
                                                                                  stderr=subprocess.STDOUT,
                                                                                  cwd=self.working_dir)
                    log.info('QEMU VM "{}" started PID={}'.format(self._name, self._process.pid))

                    self.status = "started"
                    monitor_process(self._process, self._termination_callback)
                except (OSError, subprocess.SubprocessError, UnicodeEncodeError) as e:
                    stdout = self.read_stdout()
                    log.error("Could not start QEMU {}: {}\n{}".format(self.qemu_path, e, stdout))
                    raise QemuError("Could not start QEMU {}: {}\n{}".format(self.qemu_path, e, stdout))

                yield from self._set_process_priority()
                if self._cpu_throttling:
                    self._set_cpu_throttling()

                if "-enable-kvm" in command_string:
                    self._hw_virtualization = True

    def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self.started:
            log.info("QEMU process has stopped, return code: %d", returncode)
            self.status = "stopped"
            self._hw_virtualization = False
            self._process = None
            if returncode != 0:
                self.project.emit("log.error", {"message": "QEMU process has stopped, return code: {}\n{}".format(returncode, self.read_stdout())})

    @asyncio.coroutine
    def stop(self):
        """
        Stops this QEMU VM.
        """

        with (yield from self._execute_lock):
            # stop the QEMU process
            self._hw_virtualization = False
            if self.is_running():
                log.info('Stopping QEMU VM "{}" PID={}'.format(self._name, self._process.pid))
                self.status = "stopped"
                try:
                    if self.acpi_shutdown:
                        yield from self._control_vm("system_powerdown")
                        yield from gns3server.utils.asyncio.wait_for_process_termination(self._process, timeout=30)
                    else:
                        self._process.terminate()
                        yield from gns3server.utils.asyncio.wait_for_process_termination(self._process, timeout=3)
                except ProcessLookupError:
                    pass
                except asyncio.TimeoutError:
                    try:
                        self._process.kill()
                    except ProcessLookupError:
                        pass
                    if self._process.returncode is None:
                        log.warn('QEMU VM "{}" PID={} is still running'.format(self._name, self._process.pid))
            self._process = None
            self._stop_cpulimit()

    @asyncio.coroutine
    def _control_vm(self, command, expected=None):
        """
        Executes a command with QEMU monitor when this VM is running.

        :param command: QEMU monitor command (e.g. info status, stop etc.)
        :param expected: An array of expected strings

        :returns: result of the command (matched object or None)
        """

        result = None
        if self.is_running() and self._monitor:
            log.debug("Execute QEMU monitor command: {}".format(command))
            try:
                log.info("Connecting to Qemu monitor on {}:{}".format(self._monitor_host, self._monitor))
                reader, writer = yield from asyncio.open_connection(self._monitor_host, self._monitor)
            except OSError as e:
                log.warn("Could not connect to QEMU monitor: {}".format(e))
                return result
            try:
                writer.write(command.encode('ascii') + b"\n")
            except OSError as e:
                log.warn("Could not write to QEMU monitor: {}".format(e))
                writer.close()
                return result
            if expected:
                try:
                    while result is None:
                        line = yield from reader.readline()
                        if not line:
                            break
                        for expect in expected:
                            if expect in line:
                                result = line.decode("utf-8").strip()
                                break
                except EOFError as e:
                    log.warn("Could not read from QEMU monitor: {}".format(e))
            writer.close()
        return result

    @asyncio.coroutine
    def close(self):
        """
        Closes this QEMU VM.
        """

        log.debug('QEMU VM "{name}" [{id}] is closing'.format(name=self._name, id=self._id))
        super().close()

        self.acpi_shutdown = False
        yield from self.stop()

        for adapter in self._ethernet_adapters:
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)

        yield from self.stop()

    @asyncio.coroutine
    def _get_vm_status(self):
        """
        Returns this VM suspend status.

        Status are extracted from:
          https://github.com/qemu/qemu/blob/master/qapi-schema.json#L152

        :returns: status (string)
        """

        result = yield from self._control_vm("info status", [
            b"debug", b"inmigrate", b"internal-error", b"io-error",
            b"paused", b"postmigrate", b"prelaunch", b"finish-migrate",
            b"restore-vm", b"running", b"save-vm", b"shutdown", b"suspended",
            b"watchdog", b"guest-panicked"
        ])
        if result is None:
            return result
        return result.rsplit(' ', 1)[1]

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this QEMU VM.
        """

        if self.is_running():
            vm_status = yield from self._get_vm_status()
            if vm_status is None:
                raise QemuError("Suspending a QEMU VM is not supported")
            elif vm_status == "running":
                yield from self._control_vm("stop")
                log.debug("QEMU VM has been suspended")
            else:
                log.info("QEMU VM is not running to be suspended, current status is {}".format(vm_status))

    @asyncio.coroutine
    def reload(self):
        """
        Reloads this QEMU VM.
        """

        yield from self._control_vm("system_reset")
        log.debug("QEMU VM has been reset")

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this QEMU VM.
        """

        vm_status = yield from self._get_vm_status()
        if vm_status is None:
            raise QemuError("Resuming a QEMU VM is not supported")
        elif vm_status == "paused":
            yield from self._control_vm("cont")
            log.debug("QEMU VM has been resumed")
        else:
            log.info("QEMU VM is not paused to be resumed, current status is {}".format(vm_status))

    @asyncio.coroutine
    def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds a port NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the adapter
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise QemuError('Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(name=self._name,
                                                                                                 adapter_number=adapter_number))

        if self.is_running():
            raise QemuError("Sorry, adding a link to a started Qemu VM is not supported.")
            # FIXME: does the code below work? very undocumented feature...
            # dynamically configure an UDP tunnel on the QEMU VM adapter
            if nio and isinstance(nio, NIOUDP):
                if self._legacy_networking:
                    yield from self._control_vm("host_net_remove {} gns3-{}".format(adapter_number, adapter_number))
                    yield from self._control_vm("host_net_add udp vlan={},name=gns3-{},sport={},dport={},daddr={}".format(adapter_number,
                                                                                                                          adapter_number,
                                                                                                                          nio.lport,
                                                                                                                          nio.rport,
                                                                                                                          nio.rhost))
                else:
                    # Apparently there is a bug in Qemu...
                    # netdev_add [user|tap|socket|hubport|netmap],id=str[,prop=value][,...] -- add host network device
                    # netdev_del id -- remove host network device
                    yield from self._control_vm("netdev_del gns3-{}".format(adapter_number))
                    yield from self._control_vm("netdev_add socket,id=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_number,
                                                                                                                nio.rhost,
                                                                                                                nio.rport,
                                                                                                                self._host,
                                                                                                                nio.lport))

        adapter.add_nio(0, nio)
        log.info('QEMU VM "{name}" [{id}]: {nio} added to adapter {adapter_number}'.format(name=self._name,
                                                                                           id=self._id,
                                                                                           nio=nio,
                                                                                           adapter_number=adapter_number))

    @asyncio.coroutine
    def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes a port NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise QemuError('Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(name=self._name,
                                                                                                 adapter_number=adapter_number))

        if self.is_running():
            # FIXME: does the code below work? very undocumented feature...
            # dynamically disable the QEMU VM adapter
            yield from self._control_vm("host_net_remove {} gns3-{}".format(adapter_number, adapter_number))
            yield from self._control_vm("host_net_add user vlan={},name=gns3-{}".format(adapter_number, adapter_number))

        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(0)
        log.info('QEMU VM "{name}" [{id}]: {nio} removed from adapter {adapter_number}'.format(name=self._name,
                                                                                               id=self._id,
                                                                                               nio=nio,
                                                                                               adapter_number=adapter_number))
        return nio

    @property
    def started(self):
        """
        Returns either this QEMU VM has been started or not.

        :returns: boolean
        """

        return self.status == "started"

    def read_stdout(self):
        """
        Reads the standard output of the QEMU process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stdout_file:
            try:
                with open(self._stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warn("Could not read {}: {}".format(self._stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the QEMU process is running

        :returns: True or False
        """

        if self._process:
            if self._process.returncode is None:
                return True
            else:
                self._process = None
        return False

    def command(self):
        """
        Returns the QEMU command line.

        :returns: QEMU command line (string)
        """

        return " ".join(self._build_command())

    def _serial_options(self):

        if self._console:
            return ["-serial", "telnet:{}:{},server,nowait".format(self._manager.port_manager.console_host, self._console)]
        else:
            return []

    def _vnc_options(self):

        if self._console:
            vnc_port = self._console - 5900  # subtract by 5900 to get the display number
            return ["-vnc", "{}:{}".format(self._manager.port_manager.console_host, vnc_port)]
        else:
            return []

    def _monitor_options(self):

        if self._monitor:
            return ["-monitor", "tcp:{}:{},server,nowait".format(self._monitor_host, self._monitor)]
        else:
            return []

    def _get_qemu_img(self):
        """
        Search the qemu-img binary in the same binary of the qemu binary
        for avoiding version incompatibily.

        :returns: qemu-img path or raise an error
        """
        qemu_img_path = ""
        qemu_path_dir = os.path.dirname(self.qemu_path)
        try:
            for f in os.listdir(qemu_path_dir):
                if f.startswith("qemu-img"):
                    qemu_img_path = os.path.join(qemu_path_dir, f)
        except OSError as e:
            raise QemuError("Error while looking for qemu-img in {}: {}".format(qemu_path_dir, e))

        if not qemu_img_path:
            raise QemuError("Could not find qemu-img in {}".format(qemu_path_dir))

        return qemu_img_path

    @asyncio.coroutine
    def _disk_options(self):
        options = []
        qemu_img_path = self._get_qemu_img()

        if self._hda_disk_image:
            if not os.path.isfile(self._hda_disk_image) or not os.path.exists(self._hda_disk_image):
                if os.path.islink(self._hda_disk_image):
                    raise QemuError("hda disk image '{}' linked to '{}' is not accessible".format(self._hda_disk_image, os.path.realpath(self._hda_disk_image)))
                else:
                    raise QemuError("hda disk image '{}' is not accessible".format(self._hda_disk_image))
            if self._linked_clone:
                hda_disk = os.path.join(self.working_dir, "hda_disk.qcow2")
                if not os.path.exists(hda_disk):
                    # create the disk
                    try:
                        process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-o",
                                                                            "backing_file={}".format(self._hda_disk_image),
                                                                            "-f", "qcow2", hda_disk)
                        retcode = yield from process.wait()
                        log.info("{} returned with {}".format(qemu_img_path, retcode))
                    except (OSError, subprocess.SubprocessError) as e:
                        raise QemuError("Could not create hda disk image {}".format(e))
            else:
                hda_disk = self._hda_disk_image
            options.extend(["-drive", 'file={},if={},index=0,media=disk'.format(hda_disk, self.hda_disk_interface)])

        if self._hdb_disk_image:
            if not os.path.isfile(self._hdb_disk_image) or not os.path.exists(self._hdb_disk_image):
                if os.path.islink(self._hdb_disk_image):
                    raise QemuError("hdb disk image '{}' linked to '{}' is not accessible".format(self._hdb_disk_image, os.path.realpath(self._hdb_disk_image)))
                else:
                    raise QemuError("hdb disk image '{}' is not accessible".format(self._hdb_disk_image))
            if self._linked_clone:
                hdb_disk = os.path.join(self.working_dir, "hdb_disk.qcow2")
                if not os.path.exists(hdb_disk):
                    try:
                        process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-o",
                                                                            "backing_file={}".format(self._hdb_disk_image),
                                                                            "-f", "qcow2", hdb_disk)
                        retcode = yield from process.wait()
                        log.info("{} returned with {}".format(qemu_img_path, retcode))
                    except (OSError, subprocess.SubprocessError) as e:
                        raise QemuError("Could not create hdb disk image {}".format(e))
            else:
                hdb_disk = self._hdb_disk_image
            options.extend(["-drive", 'file={},if={},index=1,media=disk'.format(hdb_disk, self.hdb_disk_interface)])

        if self._hdc_disk_image:
            if not os.path.isfile(self._hdc_disk_image) or not os.path.exists(self._hdc_disk_image):
                if os.path.islink(self._hdc_disk_image):
                    raise QemuError("hdc disk image '{}' linked to '{}' is not accessible".format(self._hdc_disk_image, os.path.realpath(self._hdc_disk_image)))
                else:
                    raise QemuError("hdc disk image '{}' is not accessible".format(self._hdc_disk_image))
            if self._linked_clone:
                hdc_disk = os.path.join(self.working_dir, "hdc_disk.qcow2")
                if not os.path.exists(hdc_disk):
                    try:
                        process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-o",
                                                                            "backing_file={}".format(self._hdc_disk_image),
                                                                            "-f", "qcow2", hdc_disk)
                        retcode = yield from process.wait()
                        log.info("{} returned with {}".format(qemu_img_path, retcode))
                    except (OSError, subprocess.SubprocessError) as e:
                        raise QemuError("Could not create hdc disk image {}".format(e))
            else:
                hdc_disk = self._hdc_disk_image
            options.extend(["-drive", 'file={},if={},index=2,media=disk'.format(hdc_disk, self.hdc_disk_interface)])

        if self._hdd_disk_image:
            if not os.path.isfile(self._hdd_disk_image) or not os.path.exists(self._hdd_disk_image):
                if os.path.islink(self._hdd_disk_image):
                    raise QemuError("hdd disk image '{}' linked to '{}' is not accessible".format(self._hdd_disk_image, os.path.realpath(self._hdd_disk_image)))
                else:
                    raise QemuError("hdd disk image '{}' is not accessible".format(self._hdd_disk_image))
            if self._linked_clone:
                hdd_disk = os.path.join(self.working_dir, "hdd_disk.qcow2")
                if not os.path.exists(hdd_disk):
                    try:
                        process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-o",
                                                                            "backing_file={}".format(self._hdd_disk_image),
                                                                            "-f", "qcow2", hdd_disk)
                        retcode = yield from process.wait()
                        log.info("{} returned with {}".format(qemu_img_path, retcode))
                    except (OSError, subprocess.SubprocessError) as e:
                        raise QemuError("Could not create hdd disk image {}".format(e))
            else:
                hdd_disk = self._hdd_disk_image
            options.extend(["-drive", 'file={},if={},index=3,media=disk'.format(hdd_disk, self.hdd_disk_interface)])

        return options

    def _cdrom_option(self):

        options = []
        if self._cdrom_image:
            if not os.path.isfile(self._cdrom_image) or not os.path.exists(self._cdrom_image):
                if os.path.islink(self._cdrom_image):
                    raise QemuError("cdrom image '{}' linked to '{}' is not accessible".format(self._cdrom_image, os.path.realpath(self._cdrom_image)))
                else:
                    raise QemuError("cdrom image '{}' is not accessible".format(self._cdrom_image))
            if self._hdc_disk_image:
                raise QemuError("You cannot use a disk image on hdc disk and a CDROM image at the same time")
            options.extend(["-cdrom", self._cdrom_image])
        return options

    def _linux_boot_options(self):

        options = []
        if self._initrd:
            if not os.path.isfile(self._initrd) or not os.path.exists(self._initrd):
                if os.path.islink(self._initrd):
                    raise QemuError("initrd file '{}' linked to '{}' is not accessible".format(self._initrd, os.path.realpath(self._initrd)))
                else:
                    raise QemuError("initrd file '{}' is not accessible".format(self._initrd))
            options.extend(["-initrd", self._initrd])
        if self._kernel_image:
            if not os.path.isfile(self._kernel_image) or not os.path.exists(self._kernel_image):
                if os.path.islink(self._kernel_image):
                    raise QemuError("kernel image '{}' linked to '{}' is not accessible".format(self._kernel_image, os.path.realpath(self._kernel_image)))
                else:
                    raise QemuError("kernel image '{}' is not accessible".format(self._kernel_image))
            options.extend(["-kernel", self._kernel_image])
        if self._kernel_command_line:
            options.extend(["-append", self._kernel_command_line])

        return options

    @asyncio.coroutine
    def _network_options(self):

        network_options = []
        network_options.extend(["-net", "none"])  # we do not want any user networking back-end if no adapter is connected.

        patched_qemu = False
        if self._legacy_networking:
            version = yield from self.manager.get_qemu_version(self.qemu_path)
            if version and parse_version(version) < parse_version("1.1.0"):
                # this is a patched Qemu if version is below 1.1.0
                patched_qemu = True

        for adapter_number, adapter in enumerate(self._ethernet_adapters):
            mac = "%s%02x" % (self._mac_address[:-2], (int(self._mac_address[-2:]) + adapter_number) % 255)
            nio = adapter.get_nio(0)
            if self._legacy_networking:
                # legacy QEMU networking syntax (-net)
                if nio:
                    network_options.extend(["-net", "nic,vlan={},macaddr={},model={}".format(adapter_number, mac, self._adapter_type)])
                    if isinstance(nio, NIOUDP):
                        if patched_qemu:
                            # use patched Qemu syntax
                            network_options.extend(["-net", "udp,vlan={},name=gns3-{},sport={},dport={},daddr={}".format(adapter_number,
                                                                                                                         adapter_number,
                                                                                                                         nio.lport,
                                                                                                                         nio.rport,
                                                                                                                         nio.rhost)])
                        else:
                            # use UDP tunnel support added in Qemu 1.1.0
                            network_options.extend(["-net", "socket,vlan={},name=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_number,
                                                                                                                           adapter_number,
                                                                                                                           nio.rhost,
                                                                                                                           nio.rport,
                                                                                                                           self._host,
                                                                                                                           nio.lport)])
                    elif isinstance(nio, NIOTAP):
                        network_options.extend(["-net", "tap,name=gns3-{},ifname={}".format(adapter_number, nio.tap_device)])
                    elif isinstance(nio, NIONAT):
                        network_options.extend(["-net", "user,vlan={},name=gns3-{}".format(adapter_number, adapter_number)])
                else:
                    network_options.extend(["-net", "nic,vlan={},macaddr={},model={}".format(adapter_number, mac, self._adapter_type)])

            else:
                # newer QEMU networking syntax
                if nio:
                    network_options.extend(["-device", "{},mac={},netdev=gns3-{}".format(self._adapter_type, mac, adapter_number)])
                    if isinstance(nio, NIOUDP):
                        network_options.extend(["-netdev", "socket,id=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_number,
                                                                                                                nio.rhost,
                                                                                                                nio.rport,
                                                                                                                self._host,
                                                                                                                nio.lport)])
                    elif isinstance(nio, NIOTAP):
                        network_options.extend(["-netdev", "tap,id=gns3-{},ifname={},script=no,downscript=no".format(adapter_number, nio.tap_device)])
                    elif isinstance(nio, NIONAT):
                        network_options.extend(["-netdev", "user,id=gns3-{}".format(adapter_number)])
                else:
                    network_options.extend(["-device", "{},mac={}".format(self._adapter_type, mac)])

        return network_options

    def _graphic(self):
        """
        Adds the correct graphic options depending of the OS
        """

        if sys.platform.startswith("win"):
            return []
        if len(os.environ.get("DISPLAY", "")) > 0:
            return []
        return ["-nographic"]

    def _run_with_kvm(self, qemu_path, options):
        """
        Check if we could run qemu with KVM

        :param qemu_path: Path to qemu
        :param options: String of qemu user options
        :returns: Boolean True if we need to enable KVM
        """

        if sys.platform.startswith("linux") and self.manager.config.get_section_config("Qemu").getboolean("enable_kvm", True) \
                and "-no-kvm" not in options:

            # Turn OFF kvm for non x86 architectures
            if os.path.basename(qemu_path) not in ["qemu-system-x86_64", "qemu-system-i386", "qemu-kvm"]:
                return False

            if not os.path.exists("/dev/kvm"):
                raise QemuError("KVM acceleration cannot be used (/dev/kvm doesn't exist). You can turn off KVM support in the gns3_server.conf by adding enable_kvm = false to the [Qemu] section.")
            return True
        return False

    @asyncio.coroutine
    def _build_command(self):
        """
        Command to start the QEMU process.
        (to be passed to subprocess.Popen())
        """

        command = [self.qemu_path]
        command.extend(["-name", self._name])
        command.extend(["-m", "{}M".format(self._ram)])
        command.extend(["-smp", "cpus={}".format(self._cpus)])
        if self._run_with_kvm(self.qemu_path, self._options):
            command.extend(["-enable-kvm"])
        command.extend(["-boot", "order={}".format(self._boot_priority)])
        cdrom_option = self._cdrom_option()
        command.extend(cdrom_option)
        command.extend((yield from self._disk_options()))
        command.extend(self._linux_boot_options())
        if self._console_type == "telnet":
            command.extend(self._serial_options())
        elif self._console_type == "vnc":
            command.extend(self._vnc_options())
        else:
            raise QemuError("Console type {} is unknown".format(self._console_type))
        command.extend(self._monitor_options())
        command.extend((yield from self._network_options()))
        command.extend(self._graphic())
        additional_options = self._options.strip()
        if additional_options:
            try:
                command.extend(shlex.split(additional_options))
            except ValueError as e:
                raise QemuError("Invalid additional options: {} error {}".format(additional_options, e))
        return command

    def __json__(self):
        answer = {
            "project_id": self.project.id,
            "vm_id": self.id,
            "vm_directory": self.working_dir
        }
        # Qemu has a long list of options. The JSON schema is the single source of information
        for field in QEMU_OBJECT_SCHEMA["required"]:
            if field not in answer:
                try:
                    answer[field] = getattr(self, field)
                except AttributeError:
                    pass

        answer["hda_disk_image"] = self.manager.get_relative_image_path(self._hda_disk_image)
        answer["hda_disk_image_md5sum"] = md5sum(self._hda_disk_image)
        answer["hdb_disk_image"] = self.manager.get_relative_image_path(self._hdb_disk_image)
        answer["hdb_disk_image_md5sum"] = md5sum(self._hdb_disk_image)
        answer["hdc_disk_image"] = self.manager.get_relative_image_path(self._hdc_disk_image)
        answer["hdc_disk_image_md5sum"] = md5sum(self._hdc_disk_image)
        answer["hdd_disk_image"] = self.manager.get_relative_image_path(self._hdd_disk_image)
        answer["hdd_disk_image_md5sum"] = md5sum(self._hdd_disk_image)
        answer["cdrom_image"] = self.manager.get_relative_image_path(self._cdrom_image)
        answer["cdrom_image_md5sum"] = md5sum(self._cdrom_image)
        answer["initrd"] = self.manager.get_relative_image_path(self._initrd)
        answer["initrd_md5sum"] = md5sum(self._initrd)

        answer["kernel_image"] = self.manager.get_relative_image_path(self._kernel_image)
        answer["kernel_image_md5sum"] = md5sum(self._kernel_image)

        return answer
