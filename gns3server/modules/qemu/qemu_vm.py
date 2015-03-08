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
QEMU VM instance.
"""

import sys
import os
import shutil
import random
import subprocess
import shlex
import asyncio

from .qemu_error import QemuError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from ..base_vm import BaseVM
from ...schemas.qemu import QEMU_OBJECT_SCHEMA
from ...config import Config

import logging
log = logging.getLogger(__name__)


class QemuVM(BaseVM):
    module_name = 'qemu'

    """
    QEMU VM implementation.

    :param name: name of this Qemu vm
    :param vm_id: IOU instance identifier
    :param project: Project instance
    :param manager: parent VM Manager
    :param console: TCP console port
    :param qemu_path: path to the QEMU binary
    :param host: host/address to bind for console and UDP connections
    :param qemu_id: QEMU VM instance ID
    :param console: TCP console port
    :param monitor: TCP monitor port
    :param monitor_host: IP address to bind for monitor connections
    """

    def __init__(self,
                 name,
                 vm_id,
                 project,
                 manager,
                 qemu_path=None,
                 host="127.0.0.1",
                 console=None,
                 monitor=None,
                 monitor_host="127.0.0.1"):

        super().__init__(name, vm_id, project, manager, console=console)

        self._host = host
        self._command = []
        self._started = False
        self._process = None
        self._cpulimit_process = None
        self._stdout_file = ""
        self._monitor_host = monitor_host

        # QEMU settings
        self._qemu_path = qemu_path
        self._hda_disk_image = ""
        self._hdb_disk_image = ""
        self._options = ""
        self._ram = 256
        self._monitor = monitor
        self._ethernet_adapters = []
        self._adapter_type = "e1000"
        self._initrd = ""
        self._kernel_image = ""
        self._kernel_command_line = ""
        self._legacy_networking = False
        self._cpu_throttling = 0  # means no CPU throttling
        self._process_priority = "low"

        if self._monitor is not None:
            self._monitor = self._manager.port_manager.reserve_tcp_port(self._monitor)
        else:
            self._monitor = self._manager.port_manager.get_free_tcp_port()

        self.adapters = 1  # creates 1 adapter by default
        log.info("QEMU VM {name} [id={id}] has been created".format(name=self._name,
                                                                    id=self._id))

    @property
    def monitor(self):
        """
        Returns the TCP monitor port.

        :returns: monitor port (integer)
        """

        return self._monitor

    @monitor.setter
    def monitor(self, monitor):
        """
        Sets the TCP monitor port.

        :param monitor: monitor port (integer)
        """

        if monitor == self._monitor:
            return
        if self._monitor:
            self._manager.port_manager.release_monitor_port(self._monitor)
        self._monitor = self._manager.port_manager.reserve_monitor_port(monitor)
        log.info("{module}: '{name}' [{id}]: monitor port set to {port}".format(
            module=self.manager.module_name,
            name=self.name,
            id=self.id,
            port=monitor))

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
            qemu_path = shutil.which(qemu_path)

        if qemu_path is None:
            raise QemuError("QEMU binary path is not set or not found in the path")
        if not os.path.exists(qemu_path):
            raise QemuError("QEMU binary '{}' is not accessible".format(qemu_path))
        if not os.access(qemu_path, os.X_OK):
            raise QemuError("QEMU binary '{}' is not executable".format(qemu_path))

        self._qemu_path = qemu_path
        log.info("QEMU VM {name} [id={id}] has set the QEMU path to {qemu_path}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        qemu_path=qemu_path))

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

        if os.path.isabs(hda_disk_image):
            server_config = Config.instance().get_section_config("Server")
            hda_disk_image = os.path.join(os.path.expanduser(server_config.get("images_path", "~/GNS3/images")), hda_disk_image)

        log.info("QEMU VM {name} [id={id}] has set the QEMU hda disk image path to {disk_image}".format(name=self._name,
                                                                                                        id=self._id,
                                                                                                        disk_image=hda_disk_image))
        self._hda_disk_image = hda_disk_image

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

        if not os.path.isabs(hdb_disk_image):
            server_config = Config.instance().get_section_config("Server")
            hdb_disk_image = os.path.join(os.path.expanduser(server_config.get("images_path", "~/GNS3/images")), hdb_disk_image)

        log.info("QEMU VM {name} [id={id}] has set the QEMU hdb disk image path to {disk_image}".format(name=self._name,
                                                                                                        id=self._id,
                                                                                                        disk_image=hdb_disk_image))
        self._hdb_disk_image = hdb_disk_image

    @property
    def adapters(self):
        """
        Returns the number of Ethernet adapters for this QEMU VM instance.

        :returns: number of adapters
        """

        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this QEMU VM instance.

        :param adapters: number of adapters
        """

        self._ethernet_adapters.clear()
        for adapter_id in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info("QEMU VM {name} [id={id}]: number of Ethernet adapters changed to {adapters}".format(name=self._name,
                                                                                                      id=self._id,
                                                                                                      adapters=adapters))

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this QEMU VM instance.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this QEMU VM instance.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type

        log.info("QEMU VM {name} [id={id}]: adapter type changed to {adapter_type}".format(name=self._name,
                                                                                           id=self._id,
                                                                                           adapter_type=adapter_type))

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
            log.info("QEMU VM {name} [id={id}] has enabled legacy networking".format(name=self._name, id=self._id))
        else:
            log.info("QEMU VM {name} [id={id}] has disabled legacy networking".format(name=self._name, id=self._id))
        self._legacy_networking = legacy_networking

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

        log.info("QEMU VM {name} [id={id}] has set the percentage of CPU allowed to {cpu}".format(name=self._name,
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

        log.info("QEMU VM {name} [id={id}] has set the process priority to {priority}".format(name=self._name,
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

        log.info("QEMU VM {name} [id={id}] has set the RAM to {ram}".format(name=self._name,
                                                                            id=self._id,
                                                                            ram=ram))
        self._ram = ram

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

        log.info("QEMU VM {name} [id={id}] has set the QEMU options to {options}".format(name=self._name,
                                                                                         id=self._id,
                                                                                         options=options))
        self._options = options

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

        log.info("QEMU VM {name} [id={id}] has set the QEMU initrd path to {initrd}".format(name=self._name,
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

        log.info("QEMU VM {name} [id={id}] has set the QEMU kernel image path to {kernel_image}".format(name=self._name,
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

        log.info("QEMU VM {name} [id={id}] has set the QEMU kernel command line to {kernel_command_line}".format(name=self._name,
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
                log.error("could not change process priority for QEMU VM {}: {}".format(self._name, e))

    def _stop_cpulimit(self):
        """
        Stops the cpulimit process.
        """

        if self._cpulimit_process and self._cpulimit_process.returncode is None:
            self._cpulimit_process.kill()
            try:
                self._process.wait(3)
            except subprocess.TimeoutExpired:
                log.error("could not kill cpulimit process {}".format(self._cpulimit_process.pid))

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

        if self.is_running():

            # resume the VM if it is paused
            yield from self.resume()
            return

        else:
            self._command = yield from self._build_command()
            try:
                log.info("starting QEMU: {}".format(self._command))
                self._stdout_file = os.path.join(self.working_dir, "qemu.log")
                log.info("logging to {}".format(self._stdout_file))
                with open(self._stdout_file, "w") as fd:
                    self._process = yield from asyncio.create_subprocess_exec(*self._command,
                                                                              stdout=fd,
                                                                              stderr=subprocess.STDOUT,
                                                                              cwd=self.working_dir)
                log.info("QEMU VM instance {} started PID={}".format(self._id, self._process.pid))
                self._started = True
            except (OSError, subprocess.SubprocessError) as e:
                stdout = self.read_stdout()
                log.error("could not start QEMU {}: {}\n{}".format(self.qemu_path, e, stdout))
                raise QemuError("could not start QEMU {}: {}\n{}".format(self.qemu_path, e, stdout))

            self._set_process_priority()
            if self._cpu_throttling:
                self._set_cpu_throttling()

    @asyncio.coroutine
    def stop(self):
        """
        Stops this QEMU VM.
        """

        # stop the QEMU process
        if self.is_running():
            log.info("stopping QEMU VM instance {} PID={}".format(self._id, self._process.pid))
            try:
                self._process.terminate()
                self._process.wait()
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.returncode is None:
                    log.warn("QEMU VM instance {} PID={} is still running".format(self._id,
                                                                                  self._process.pid))
        self._process = None
        self._started = False
        self._stop_cpulimit()

    @asyncio.coroutine
    def _control_vm(self, command, expected=None):
        """
        Executes a command with QEMU monitor when this VM is running.

        :param command: QEMU monitor command (e.g. info status, stop etc.)
        :params expected: An array with the string attended (Default None)

        :returns: result of the command (Match object or None)
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
                                result = line.decode().strip()
                                break
                except EOFError as e:
                    log.warn("Could not read from QEMU monitor: {}".format(e))
            writer.close()
        return result

    @asyncio.coroutine
    def close(self):

        log.debug('QEMU VM "{name}" [{id}] is closing'.format(name=self._name, id=self._id))
        yield from self.stop()
        if self._console:
            self._manager.port_manager.release_tcp_port(self._console)
            self._console = None
        if self._monitor:
            self._manager.port_manager.release_tcp_port(self._monitor)
            self._monitor = None

    @asyncio.coroutine
    def _get_vm_status(self):
        """
        Returns this VM suspend status (running|paused)

        :returns: status (string)
        """

        result = yield from self._control_vm("info status", [b"running", b"paused"])
        return result.rsplit(' ', 1)[1]

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this QEMU VM.
        """

        vm_status = yield from self._get_vm_status()
        if vm_status == "running":
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
        if vm_status == "paused":
            yield from self._control_vm("cont")
            log.debug("QEMU VM has been resumed")
        else:
            log.info("QEMU VM is not paused to be resumed, current status is {}".format(vm_status))

    @asyncio.coroutine
    def adapter_add_nio_binding(self, adapter_id, nio):
        """
        Adds a port NIO binding.

        :param adapter_id: adapter ID
        :param nio: NIO instance to add to the adapter
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise QemuError("Adapter {adapter_id} doesn't exist on QEMU VM {name}".format(name=self._name,
                                                                                          adapter_id=adapter_id))

        if self.is_running():
            # dynamically configure an UDP tunnel on the QEMU VM adapter
            if nio and isinstance(nio, NIOUDP):
                if self._legacy_networking:
                    yield from self._control_vm("host_net_remove {} gns3-{}".format(adapter_id, adapter_id))
                    yield from self._control_vm("host_net_add udp vlan={},name=gns3-{},sport={},dport={},daddr={}".format(adapter_id,
                                                                                                                          adapter_id,
                                                                                                                          nio.lport,
                                                                                                                          nio.rport,
                                                                                                                          nio.rhost))
                else:
                    # FIXME: does it work? very undocumented feature...
                    # Apparently there is a bug in Qemu...
                    # netdev_add [user|tap|socket|hubport|netmap],id=str[,prop=value][,...] -- add host network device
                    # netdev_del id -- remove host network device
                    yield from self._control_vm("netdev_del gns3-{}".format(adapter_id))
                    yield from self._control_vm("netdev_add socket,id=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_id,
                                                                                                                nio.rhost,
                                                                                                                nio.rport,
                                                                                                                self._host,
                                                                                                                nio.lport))

        adapter.add_nio(0, nio)
        log.info("QEMU VM {name} [id={id}]: {nio} added to adapter {adapter_id}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        nio=nio,
                                                                                        adapter_id=adapter_id))

    @asyncio.coroutine
    def adapter_remove_nio_binding(self, adapter_id):
        """
        Removes a port NIO binding.

        :param adapter_id: adapter ID

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise QemuError("Adapter {adapter_id} doesn't exist on QEMU VM {name}".format(name=self._name,
                                                                                          adapter_id=adapter_id))

        if self.is_running():
            # dynamically disable the QEMU VM adapter
            yield from self._control_vm("host_net_remove {} gns3-{}".format(adapter_id, adapter_id))
            yield from self._control_vm("host_net_add user vlan={},name=gns3-{}".format(adapter_id, adapter_id))

        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport)
        adapter.remove_nio(0)
        log.info("QEMU VM {name} [id={id}]: {nio} removed from adapter {adapter_id}".format(name=self._name,
                                                                                            id=self._id,
                                                                                            nio=nio,
                                                                                            adapter_id=adapter_id))
        return nio

    @property
    def started(self):
        """
        Returns either this QEMU VM has been started or not.

        :returns: boolean
        """

        return self._started

    def read_stdout(self):
        """
        Reads the standard output of the QEMU process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stdout_file:
            try:
                with open(self._stdout_file, errors="replace") as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._stdout_file, e))
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

    def _monitor_options(self):

        if self._monitor:
            return ["-monitor", "telnet:{}:{},server,nowait".format(self._monitor_host, self._monitor)]
        else:
            return []

    @asyncio.coroutine
    def _disk_options(self):

        options = []
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

        try:
            if self._hda_disk_image:
                if not os.path.isfile(self._hda_disk_image) or not os.path.exists(self._hda_disk_image):
                    if os.path.islink(self._hda_disk_image):
                        raise QemuError("hda disk image '{}' linked to '{}' is not accessible".format(self._hda_disk_image, os.path.realpath(self._hda_disk_image)))
                    else:
                        raise QemuError("hda disk image '{}' is not accessible".format(self._hda_disk_image))
                hda_disk = os.path.join(self.working_dir, "hda_disk.qcow2")
                if not os.path.exists(hda_disk):
                    process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-o",
                                                                        "backing_file={}".format(self._hda_disk_image),
                                                                        "-f", "qcow2", hda_disk)
                    retcode = yield from process.wait()
                    log.info("{} returned with {}".format(qemu_img_path, retcode))
            else:
                # create a "FLASH" with 256MB if no disk image has been specified
                hda_disk = os.path.join(self.working_dir, "flash.qcow2")
                if not os.path.exists(hda_disk):
                    process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-f", "qcow2", hda_disk, "128M")
                    retcode = yield from process.wait()
                    log.info("{} returned with {}".format(qemu_img_path, retcode))

        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError("Could not create disk image {}".format(e))

        options.extend(["-hda", hda_disk])
        if self._hdb_disk_image:
            if not os.path.isfile(self._hdb_disk_image) or not os.path.exists(self._hdb_disk_image):
                if os.path.islink(self._hdb_disk_image):
                    raise QemuError("hdb disk image '{}' linked to '{}' is not accessible".format(self._hdb_disk_image, os.path.realpath(self._hdb_disk_image)))
                else:
                    raise QemuError("hdb disk image '{}' is not accessible".format(self._hdb_disk_image))
            hdb_disk = os.path.join(self.working_dir, "hdb_disk.qcow2")
            if not os.path.exists(hdb_disk):
                try:
                    process = yield from asyncio.create_subprocess_exec(qemu_img_path, "create", "-o",
                                                                        "backing_file={}".format(self._hdb_disk_image),
                                                                        "-f", "qcow2", hdb_disk)
                    retcode = yield from process.wait()
                    log.info("{} returned with {}".format(qemu_img_path, retcode))
                except (OSError, subprocess.SubprocessError) as e:
                    raise QemuError("Could not create disk image {}".format(e))
            options.extend(["-hdb", hdb_disk])

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

    def _get_random_mac(self, adapter_id):
        # TODO: let users specify a base mac address
        return "00:00:ab:%02x:%02x:%02d" % (random.randint(0x00, 0xff), random.randint(0x00, 0xff), adapter_id)

    def _network_options(self):

        network_options = []
        adapter_id = 0
        for adapter in self._ethernet_adapters:
            mac = self._get_random_mac(adapter_id)
            if self._legacy_networking:
                network_options.extend(["-net", "nic,vlan={},macaddr={},model={}".format(adapter_id, mac, self._adapter_type)])
            else:
                network_options.extend(["-device", "{},mac={},netdev=gns3-{}".format(self._adapter_type, mac, adapter_id)])
            nio = adapter.get_nio(0)
            if nio and isinstance(nio, NIOUDP):
                if self._legacy_networking:
                    network_options.extend(["-net", "udp,vlan={},name=gns3-{},sport={},dport={},daddr={}".format(adapter_id,
                                                                                                                 adapter_id,
                                                                                                                 nio.lport,
                                                                                                                 nio.rport,
                                                                                                                 nio.rhost)])
                else:
                    network_options.extend(["-netdev", "socket,id=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_id,
                                                                                                            nio.rhost,
                                                                                                            nio.rport,
                                                                                                            self._host,
                                                                                                            nio.lport)])
            else:
                if self._legacy_networking:
                    network_options.extend(["-net", "user,vlan={},name=gns3-{}".format(adapter_id, adapter_id)])
                else:
                    network_options.extend(["-netdev", "user,id=gns3-{}".format(adapter_id)])
            adapter_id += 1

        return network_options

    def _graphic(self):
        """
        Add the correct graphic options depending of the OS
        """
        if sys.platform.startswith("win"):
            return []
        if len(os.environ.get("DISPLAY", "")) > 0:
            return []
        return ["-nographic"]

    @asyncio.coroutine
    def _build_command(self):
        """
        Command to start the QEMU process.
        (to be passed to subprocess.Popen())
        """

        command = [self.qemu_path]
        command.extend(["-name", self._name])
        command.extend(["-m", str(self._ram)])
        disk_options = yield from self._disk_options()
        command.extend(disk_options)
        command.extend(self._linux_boot_options())
        command.extend(self._serial_options())
        command.extend(self._monitor_options())
        additional_options = self._options.strip()
        if additional_options:
            command.extend(shlex.split(additional_options))
        command.extend(self._network_options())
        command.extend(self._graphic())
        return command

    def __json__(self):
        answer = {
            "project_id": self.project.id,
            "vm_id": self.id
        }
        # Qemu has a long list of options. The JSON schema is the single source of informations
        for field in QEMU_OBJECT_SCHEMA["required"]:
            if field not in answer:
                answer[field] = getattr(self, field)
        return answer
