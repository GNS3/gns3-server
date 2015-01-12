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
import ntpath
import telnetlib
import time
import re

from gns3server.config import Config
from gns3dms.cloud.rackspace_ctrl import get_provider

from .qemu_error import QemuError
from .adapters.ethernet_adapter import EthernetAdapter
from .nios.nio_udp import NIO_UDP
from ..attic import find_unused_port

import logging
log = logging.getLogger(__name__)


class QemuVM(object):
    """
    QEMU VM implementation.

    :param name: name of this QEMU VM
    :param qemu_path: path to the QEMU binary
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param qemu_id: QEMU VM instance ID
    :param console: TCP console port
    :param console_host: IP address to bind for console connections
    :param console_start_port_range: TCP console port range start
    :param console_end_port_range: TCP console port range end
    :param monitor: TCP monitor port
    :param monitor_host: IP address to bind for monitor connections
    :param monitor_start_port_range: TCP monitor port range start
    :param monitor_end_port_range: TCP monitor port range end
    """

    _instances = []
    _allocated_console_ports = []
    _allocated_monitor_ports = []

    def __init__(self,
                 name,
                 qemu_path,
                 working_dir,
                 host="127.0.0.1",
                 qemu_id=None,
                 console=None,
                 console_host="0.0.0.0",
                 console_start_port_range=5001,
                 console_end_port_range=5500,
                 monitor=None,
                 monitor_host="0.0.0.0",
                 monitor_start_port_range=5501,
                 monitor_end_port_range=6000):

        if not qemu_id:
            self._id = 0
            for identifier in range(1, 1024):
                if identifier not in self._instances:
                    self._id = identifier
                    self._instances.append(self._id)
                    break

            if self._id == 0:
                raise QemuError("Maximum number of QEMU VM instances reached")
        else:
            if qemu_id in self._instances:
                raise QemuError("QEMU identifier {} is already used by another QEMU VM instance".format(qemu_id))
            self._id = qemu_id
            self._instances.append(self._id)

        self._name = name
        self._working_dir = None
        self._host = host
        self._command = []
        self._started = False
        self._process = None
        self._cpulimit_process = None
        self._stdout_file = ""
        self._console_host = console_host
        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range
        self._monitor_host = monitor_host
        self._monitor_start_port_range = monitor_start_port_range
        self._monitor_end_port_range = monitor_end_port_range
        self._cloud_path = None

        # QEMU settings
        self._qemu_path = qemu_path
        self._hda_disk_image = ""
        self._hdb_disk_image = ""
        self._options = ""
        self._ram = 256
        self._console = console
        self._monitor = monitor
        self._ethernet_adapters = []
        self._adapter_type = "e1000"
        self._initrd = ""
        self._kernel_image = ""
        self._kernel_command_line = ""
        self._legacy_networking = False
        self._cpu_throttling = 0  # means no CPU throttling
        self._process_priority = "low"

        working_dir_path = os.path.join(working_dir, "qemu", "vm-{}".format(self._id))

        if qemu_id and not os.path.isdir(working_dir_path):
            raise QemuError("Working directory {} doesn't exist".format(working_dir_path))

        # create the device own working directory
        self.working_dir = working_dir_path

        if not self._console:
            # allocate a console port
            try:
                self._console = find_unused_port(self._console_start_port_range,
                                                 self._console_end_port_range,
                                                 self._console_host,
                                                 ignore_ports=self._allocated_console_ports)
            except Exception as e:
                raise QemuError(e)

        if self._console in self._allocated_console_ports:
            raise QemuError("Console port {} is already used by another QEMU VM".format(console))
        self._allocated_console_ports.append(self._console)

        if not self._monitor:
            # allocate a monitor port
            try:
                self._monitor = find_unused_port(self._monitor_start_port_range,
                                                 self._monitor_end_port_range,
                                                 self._monitor_host,
                                                 ignore_ports=self._allocated_monitor_ports)
            except Exception as e:
                raise QemuError(e)

        if self._monitor in self._allocated_monitor_ports:
            raise QemuError("Monitor port {} is already used by another QEMU VM".format(monitor))
        self._allocated_monitor_ports.append(self._monitor)

        self.adapters = 1  # creates 1 adapter by default
        log.info("QEMU VM {name} [id={id}] has been created".format(name=self._name,
                                                                    id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for this QEMU VM.

        :returns: default values (dictionary)
        """

        qemu_defaults = {"name": self._name,
                         "qemu_path": self._qemu_path,
                         "ram": self._ram,
                         "hda_disk_image": self._hda_disk_image,
                         "hdb_disk_image": self._hdb_disk_image,
                         "options": self._options,
                         "adapters": self.adapters,
                         "adapter_type": self._adapter_type,
                         "console": self._console,
                         "monitor": self._monitor,
                         "initrd": self._initrd,
                         "kernel_image": self._kernel_image,
                         "kernel_command_line": self._kernel_command_line,
                         "legacy_networking": self._legacy_networking,
                         "cpu_throttling": self._cpu_throttling,
                         "process_priority": self._process_priority
                         }

        return qemu_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this QEMU VM.

        :returns: id (integer)
        """

        return self._id

    @classmethod
    def reset(cls):
        """
        Resets allocated instance list.
        """

        cls._instances.clear()
        cls._allocated_console_ports.clear()
        cls._allocated_monitor_ports.clear()

    @property
    def name(self):
        """
        Returns the name of this QEMU VM.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this QEMU VM.

        :param new_name: name
        """

        log.info("QEMU VM {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                          id=self._id,
                                                                          new_name=new_name))

        self._name = new_name

    @property
    def working_dir(self):
        """
        Returns current working directory

        :returns: path to the working directory
        """

        return self._working_dir

    @working_dir.setter
    def working_dir(self, working_dir):
        """
        Sets the working directory this QEMU VM.

        :param working_dir: path to the working directory
        """

        try:
            os.makedirs(working_dir)
        except FileExistsError:
            pass
        except OSError as e:
            raise QemuError("Could not create working directory {}: {}".format(working_dir, e))

        self._working_dir = working_dir
        log.info("QEMU VM {name} [id={id}]: working directory changed to {wd}".format(name=self._name,
                                                                                      id=self._id,
                                                                                      wd=self._working_dir))

    @property
    def console(self):
        """
        Returns the TCP console port.

        :returns: console port (integer)
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        if console in self._allocated_console_ports:
            raise QemuError("Console port {} is already used by another QEMU VM".format(console))

        self._allocated_console_ports.remove(self._console)
        self._console = console
        self._allocated_console_ports.append(self._console)

        log.info("QEMU VM {name} [id={id}]: console port set to {port}".format(name=self._name,
                                                                               id=self._id,
                                                                               port=console))

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

        if monitor in self._allocated_monitor_ports:
            raise QemuError("Monitor port {} is already used by another QEMU VM".format(monitor))

        self._allocated_monitor_ports.remove(self._monitor)
        self._monitor = monitor
        self._allocated_monitor_ports.append(self._monitor)

        log.info("QEMU VM {name} [id={id}]: monitor port set to {port}".format(name=self._name,
                                                                               id=self._id,
                                                                               port=monitor))

    def delete(self):
        """
        Deletes this QEMU VM.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self._console and self._console in self._allocated_console_ports:
            self._allocated_console_ports.remove(self._console)

        if self._monitor and self._monitor in self._allocated_monitor_ports:
            self._allocated_monitor_ports.remove(self._monitor)

        log.info("QEMU VM {name} [id={id}] has been deleted".format(name=self._name,
                                                                    id=self._id))

    def clean_delete(self):
        """
        Deletes this QEMU VM & all files.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self._console:
            self._allocated_console_ports.remove(self._console)

        if self._monitor:
            self._allocated_monitor_ports.remove(self._monitor)

        try:
            shutil.rmtree(self._working_dir)
        except OSError as e:
            log.error("could not delete QEMU VM {name} [id={id}]: {error}".format(name=self._name,
                                                                                  id=self._id,
                                                                                  error=e))
            return

        log.info("QEMU VM {name} [id={id}] has been deleted (including associated files)".format(name=self._name,
                                                                                                 id=self._id))

    @property
    def cloud_path(self):
        """
        Returns the cloud path where images can be downloaded from.

        :returns: cloud path
        """

        return self._cloud_path

    @cloud_path.setter
    def cloud_path(self, cloud_path):
        """
        Sets the cloud path where images can be downloaded from.

        :param cloud_path:
        :return:
        """

        self._cloud_path = cloud_path

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

        log.info("QEMU VM {name} [id={id}] has set the QEMU path to {qemu_path}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        qemu_path=qemu_path))
        self._qemu_path = qemu_path

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
                subprocess.call(['renice', '-n', str(priority), '-p', str(self._process.pid)])
            except (OSError, subprocess.SubprocessError) as e:
                log.error("could not change process priority for QEMU VM {}: {}".format(self._name, e))

    def _stop_cpulimit(self):
        """
        Stops the cpulimit process.
        """

        if self._cpulimit_process and self._cpulimit_process.poll() is None:
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
            subprocess.Popen([cpulimit_exec, "--lazy", "--pid={}".format(self._process.pid), "--limit={}".format(self._cpu_throttling)], cwd=self._working_dir)
            log.info("CPU throttled to {}%".format(self._cpu_throttling))
        except FileNotFoundError:
            raise QemuError("cpulimit could not be found, please install it or deactivate CPU throttling")
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError("Could not throttle CPU: {}".format(e))

    def start(self):
        """
        Starts this QEMU VM.
        """

        if self.is_running():

            # resume the VM if it is paused
            self.resume()
            return

        else:

            if not os.path.isfile(self._qemu_path) or not os.path.exists(self._qemu_path):
                found = False
                paths = [os.getcwd()] + os.environ["PATH"].split(os.pathsep)
                # look for the qemu binary in the current working directory and $PATH
                for path in paths:
                    try:
                        if self._qemu_path in os.listdir(path) and os.access(os.path.join(path, self._qemu_path), os.X_OK):
                            self._qemu_path = os.path.join(path, self._qemu_path)
                            found = True
                            break
                    except OSError:
                        continue

                if not found:
                    raise QemuError("QEMU binary '{}' is not accessible".format(self._qemu_path))

            if self.cloud_path is not None:
                # Download from Cloud Files
                if self.hda_disk_image != "":
                    _, filename = ntpath.split(self.hda_disk_image)
                    src = '{}/{}'.format(self.cloud_path, filename)
                    dst = os.path.join(self.working_dir, filename)
                    if not os.path.isfile(dst):
                        cloud_settings = Config.instance().cloud_settings()
                        provider = get_provider(cloud_settings)
                        log.debug("Downloading file from {} to {}...".format(src, dst))
                        provider.download_file(src, dst)
                        log.debug("Download of {} complete.".format(src))
                    self.hda_disk_image = dst
                if self.hdb_disk_image != "":
                    _, filename = ntpath.split(self.hdb_disk_image)
                    src = '{}/{}'.format(self.cloud_path, filename)
                    dst = os.path.join(self.working_dir, filename)
                    if not os.path.isfile(dst):
                        cloud_settings = Config.instance().cloud_settings()
                        provider = get_provider(cloud_settings)
                        log.debug("Downloading file from {} to {}...".format(src, dst))
                        provider.download_file(src, dst)
                        log.debug("Download of {} complete.".format(src))
                    self.hdb_disk_image = dst

                if self.initrd != "":
                    _, filename = ntpath.split(self.initrd)
                    src = '{}/{}'.format(self.cloud_path, filename)
                    dst = os.path.join(self.working_dir, filename)
                    if not os.path.isfile(dst):
                        cloud_settings = Config.instance().cloud_settings()
                        provider = get_provider(cloud_settings)
                        log.debug("Downloading file from {} to {}...".format(src, dst))
                        provider.download_file(src, dst)
                        log.debug("Download of {} complete.".format(src))
                    self.initrd = dst
                if self.kernel_image != "":
                    _, filename = ntpath.split(self.kernel_image)
                    src = '{}/{}'.format(self.cloud_path, filename)
                    dst = os.path.join(self.working_dir, filename)
                    if not os.path.isfile(dst):
                        cloud_settings = Config.instance().cloud_settings()
                        provider = get_provider(cloud_settings)
                        log.debug("Downloading file from {} to {}...".format(src, dst))
                        provider.download_file(src, dst)
                        log.debug("Download of {} complete.".format(src))
                    self.kernel_image = dst

            self._command = self._build_command()
            try:
                log.info("starting QEMU: {}".format(self._command))
                self._stdout_file = os.path.join(self._working_dir, "qemu.log")
                log.info("logging to {}".format(self._stdout_file))
                with open(self._stdout_file, "w") as fd:
                    self._process = subprocess.Popen(self._command,
                                                     stdout=fd,
                                                     stderr=subprocess.STDOUT,
                                                     cwd=self._working_dir)
                log.info("QEMU VM instance {} started PID={}".format(self._id, self._process.pid))
                self._started = True
            except (OSError, subprocess.SubprocessError) as e:
                stdout = self.read_stdout()
                log.error("could not start QEMU {}: {}\n{}".format(self._qemu_path, e, stdout))
                raise QemuError("could not start QEMU {}: {}\n{}".format(self._qemu_path, e, stdout))

            self._set_process_priority()
            if self._cpu_throttling:
                self._set_cpu_throttling()

    def stop(self):
        """
        Stops this QEMU VM.
        """

        # stop the QEMU process
        if self.is_running():
            log.info("stopping QEMU VM instance {} PID={}".format(self._id, self._process.pid))
            try:
                self._process.terminate()
                self._process.wait(1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.poll() is None:
                    log.warn("QEMU VM instance {} PID={} is still running".format(self._id,
                                                                                  self._process.pid))
        self._process = None
        self._started = False
        self._stop_cpulimit()

    def _control_vm(self, command, expected=None, timeout=30):
        """
        Executes a command with QEMU monitor when this VM is running.

        :param command: QEMU monitor command (e.g. info status, stop etc.)
        :param timeout: how long to wait for QEMU monitor

        :returns: result of the command (Match object or None)
        """

        result = None
        if self.is_running() and self._monitor:
            log.debug("Execute QEMU monitor command: {}".format(command))
            try:
                tn = telnetlib.Telnet(self._monitor_host, self._monitor, timeout=timeout)
            except OSError as e:
                log.warn("Could not connect to QEMU monitor: {}".format(e))
                return result
            try:
                tn.write(command.encode('ascii') + b"\n")
                time.sleep(0.1)
            except OSError as e:
                log.warn("Could not write to QEMU monitor: {}".format(e))
                tn.close()
                return result
            if expected:
                try:
                    ind, match, dat = tn.expect(list=expected, timeout=timeout)
                    if match:
                        result = match
                except EOFError as e:
                    log.warn("Could not read from QEMU monitor: {}".format(e))
            tn.close()
        return result

    def _get_vm_status(self):
        """
        Returns this VM suspend status (running|paused)

        :returns: status (string)
        """

        result = None

        match = self._control_vm("info status", [b"running", b"paused"])
        if match:
            result = match.group(0).decode('ascii')
        return result

    def suspend(self):
        """
        Suspends this QEMU VM.
        """

        vm_status = self._get_vm_status()
        if vm_status == "running":
            self._control_vm("stop")
            log.debug("QEMU VM has been suspended")
        else:
            log.info("QEMU VM is not running to be suspended, current status is {}".format(vm_status))

    def reload(self):
        """
        Reloads this QEMU VM.
        """

        self._control_vm("system_reset")
        log.debug("QEMU VM has been reset")

    def resume(self):
        """
        Resumes this QEMU VM.
        """

        vm_status = self._get_vm_status()
        if vm_status == "paused":
            self._control_vm("cont")
            log.debug("QEMU VM has been resumed")
        else:
            log.info("QEMU VM is not paused to be resumed, current status is {}".format(vm_status))

    def port_add_nio_binding(self, adapter_id, nio):
        """
        Adds a port NIO binding.

        :param adapter_id: adapter ID
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise QemuError("Adapter {adapter_id} doesn't exist on QEMU VM {name}".format(name=self._name,
                                                                                          adapter_id=adapter_id))

        if self.is_running():
            # dynamically configure an UDP tunnel on the QEMU VM adapter
            if nio and isinstance(nio, NIO_UDP):
                if self._legacy_networking:
                    self._control_vm("host_net_remove {} gns3-{}".format(adapter_id, adapter_id))
                    self._control_vm("host_net_add udp vlan={},name=gns3-{},sport={},dport={},daddr={}".format(adapter_id,
                                                                                                              adapter_id,
                                                                                                              nio.lport,
                                                                                                              nio.rport,
                                                                                                              nio.rhost))
                else:
                    self._control_vm("host_net_remove {} gns3-{}".format(adapter_id, adapter_id))
                    self._control_vm("host_net_add socket vlan={},name=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_id,
                                                                                                                adapter_id,
                                                                                                                nio.rhost,
                                                                                                                nio.rport,
                                                                                                                self._host,
                                                                                                                nio.lport))

        adapter.add_nio(0, nio)
        log.info("QEMU VM {name} [id={id}]: {nio} added to adapter {adapter_id}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        nio=nio,
                                                                                        adapter_id=adapter_id))

    def port_remove_nio_binding(self, adapter_id):
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
            self._control_vm("host_net_remove {} gns3-{}".format(adapter_id, adapter_id))
            self._control_vm("host_net_add user vlan={},name=gns3-{}".format(adapter_id, adapter_id))

        nio = adapter.get_nio(0)
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

        if self._process and self._process.poll() is None:
            return True
        return False

    def command(self):
        """
        Returns the QEMU command line.

        :returns: QEMU command line (string)
        """

        return " ".join(self._build_command())

    def _serial_options(self):

        if self._console:
            return ["-serial", "telnet:{}:{},server,nowait".format(self._console_host, self._console)]
        else:
            return []

    def _monitor_options(self):

        if self._monitor:
            return ["-monitor", "telnet:{}:{},server,nowait".format(self._monitor_host, self._monitor)]
        else:
            return []

    def _disk_options(self):

        options = []
        qemu_img_path = ""
        qemu_path_dir = os.path.dirname(self._qemu_path)
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
                hda_disk = os.path.join(self._working_dir, "hda_disk.qcow2")
                if not os.path.exists(hda_disk):
                    retcode = subprocess.call([qemu_img_path, "create", "-o",
                                               "backing_file={}".format(self._hda_disk_image),
                                               "-f", "qcow2", hda_disk])
                    log.info("{} returned with {}".format(qemu_img_path, retcode))
            else:
                # create a "FLASH" with 256MB if no disk image has been specified
                hda_disk = os.path.join(self._working_dir, "flash.qcow2")
                if not os.path.exists(hda_disk):
                    retcode = subprocess.call([qemu_img_path, "create", "-f", "qcow2", hda_disk, "128M"])
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
            hdb_disk = os.path.join(self._working_dir, "hdb_disk.qcow2")
            if not os.path.exists(hdb_disk):
                try:
                    retcode = subprocess.call([qemu_img_path, "create", "-o",
                                              "backing_file={}".format(self._hdb_disk_image),
                                              "-f", "qcow2", hdb_disk])
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

    def _network_options(self):

        network_options = []
        adapter_id = 0
        for adapter in self._ethernet_adapters:
            #TODO: let users specify a base mac address
            mac = "00:00:ab:%02x:%02x:%02d" % (random.randint(0x00, 0xff), random.randint(0x00, 0xff), adapter_id)
            network_options.extend(["-net", "nic,vlan={},macaddr={},model={}".format(adapter_id, mac, self._adapter_type)])
            nio = adapter.get_nio(0)
            if nio and isinstance(nio, NIO_UDP):
                if self._legacy_networking:
                    network_options.extend(["-net", "udp,vlan={},name=gns3-{},sport={},dport={},daddr={}".format(adapter_id,
                                                                                                                adapter_id,
                                                                                                                nio.lport,
                                                                                                                nio.rport,
                                                                                                                nio.rhost)])
                else:
                    network_options.extend(["-net", "socket,vlan={},name=gns3-{},udp={}:{},localaddr={}:{}".format(adapter_id,
                                                                                                                  adapter_id,
                                                                                                                  nio.rhost,
                                                                                                                  nio.rport,
                                                                                                                  self._host,
                                                                                                                  nio.lport)])
            else:
                network_options.extend(["-net", "user,vlan={},name=gns3-{}".format(adapter_id, adapter_id)])
            adapter_id += 1

        return network_options

    def _build_command(self):
        """
        Command to start the QEMU process.
        (to be passed to subprocess.Popen())
        """

        command = [self._qemu_path]
        command.extend(["-name", self._name])
        command.extend(["-m", str(self._ram)])
        command.extend(self._disk_options())
        command.extend(self._linux_boot_options())
        command.extend(self._serial_options())
        command.extend(self._monitor_options())
        additional_options = self._options.strip()
        if additional_options:
            command.extend(shlex.split(additional_options))
        command.extend(self._network_options())
        return command
