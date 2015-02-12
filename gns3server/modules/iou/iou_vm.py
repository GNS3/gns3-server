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
IOU VM management (creates command line, processes, files etc.) in
order to run an IOU instance.
"""

import os
import sys
import subprocess
import signal
import re
import asyncio
import shutil
import argparse
import threading
import configparser

from pkg_resources import parse_version
from .iou_error import IOUError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..adapters.serial_adapter import SerialAdapter
from ..base_vm import BaseVM
from .ioucon import start_ioucon


import logging
log = logging.getLogger(__name__)


class IOUVM(BaseVM):
    module_name = 'iou'

    """
    IOU vm implementation.

    :param name: name of this IOU vm
    :param vm_id: IOU instance identifier
    :param project: Project instance
    :param manager: parent VM Manager
    :param console: TCP console port
    :params console_host: TCP console host IP
    :params ethernet_adapters: Number of ethernet adapters
    :params serial_adapters: Number of serial adapters
    :params ram: Ram MB
    :params nvram: Nvram KB
    """

    def __init__(self, name, vm_id, project, manager,
                 console=None,
                 console_host="0.0.0.0",
                 ram=None,
                 nvram=None,
                 ethernet_adapters=None,
                 serial_adapters=None):

        super().__init__(name, vm_id, project, manager)

        self._console = console
        self._command = []
        self._iouyap_process = None
        self._iou_process = None
        self._iou_stdout_file = ""
        self._started = False
        self._path = None
        self._iourc_path = None
        self._ioucon_thread = None
        self._console_host = console_host

        # IOU settings
        self._ethernet_adapters = []
        self._serial_adapters = []
        self.ethernet_adapters = 2 if ethernet_adapters is None else ethernet_adapters  # one adapter = 4 interfaces
        self.serial_adapters = 2 if serial_adapters is None else serial_adapters # one adapter = 4 interfaces
        self._use_default_iou_values = True  # for RAM & NVRAM values
        self._nvram = 128 if nvram is None else nvram  # Kilobytes
        self._initial_config = ""
        self._ram = 256 if ram is None else ram  # Megabytes
        self._l1_keepalives = False  # used to overcome the always-up Ethernet interfaces (not supported by all IOSes).

        if self._console is not None:
            self._console = self._manager.port_manager.reserve_console_port(self._console)
        else:
            self._console = self._manager.port_manager.get_free_console_port()

    def close(self):

        if self._console:
            self._manager.port_manager.release_console_port(self._console)
            self._console = None

    @property
    def path(self):
        """Path of the iou binary"""

        return self._path

    @path.setter
    def path(self, path):
        """
        Path of the iou binary

        :params path: Path to the binary
        """

        self._path = path
        if not os.path.isfile(self._path) or not os.path.exists(self._path):
            if os.path.islink(self._path):
                raise IOUError("IOU image '{}' linked to '{}' is not accessible".format(self._path, os.path.realpath(self._path)))
            else:
                raise IOUError("IOU image '{}' is not accessible".format(self._path))

        try:
            with open(self._path, "rb") as f:
                # read the first 7 bytes of the file.
                elf_header_start = f.read(7)
        except OSError as e:
            raise IOUError("Cannot read ELF header for IOU image '{}': {}".format(self._path, e))

        # IOU images must start with the ELF magic number, be 32-bit, little endian
        # and have an ELF version of 1 normal IOS image are big endian!
        if elf_header_start != b'\x7fELF\x01\x01\x01':
            raise IOUError("'{}' is not a valid IOU image".format(self._path))

        if not os.access(self._path, os.X_OK):
            raise IOUError("IOU image '{}' is not executable".format(self._path))

    @property
    def iourc_path(self):
        """
        Returns the path to the iourc file.
        :returns: path to the iourc file
        """

        return self._iourc_path

    @iourc_path.setter
    def iourc_path(self, path):
        """
        Set path to IOURC file
        """

        self._iourc_path = path
        log.info("IOU {name} [id={id}]: iourc file path set to {path}".format(name=self._name,
                                                                              id=self._id,
                                                                              path=self._iourc_path))

    @property
    def use_default_iou_values(self):
        """
        Returns if this device uses the default IOU image values.
        :returns: boolean
        """

        return self._use_default_iou_values

    @use_default_iou_values.setter
    def use_default_iou_values(self, state):
        """
        Sets if this device uses the default IOU image values.
        :param state: boolean
        """

        self._use_default_iou_values = state
        if state:
            log.info("IOU {name} [id={id}]: uses the default IOU image values".format(name=self._name, id=self._id))
        else:
            log.info("IOU {name} [id={id}]: does not use the default IOU image values".format(name=self._name, id=self._id))

    def _check_requirements(self):
        """
        Check if IOUYAP is available
        """
        path = self.iouyap_path
        if not path:
            raise IOUError("No path to a IOU executable has been set")

        if not os.path.isfile(path):
            raise IOUError("IOU program '{}' is not accessible".format(path))

        if not os.access(path, os.X_OK):
            raise IOUError("IOU program '{}' is not executable".format(path))

    def __json__(self):

        return {"name": self.name,
                "vm_id": self.id,
                "console": self._console,
                "project_id": self.project.id,
                "path": self.path,
                "ethernet_adapters": len(self._ethernet_adapters),
                "serial_adapters": len(self._serial_adapters),
                "ram": self._ram,
                "nvram": self._nvram
                }

    @property
    def iouyap_path(self):
        """
        Returns the IOUYAP executable path.

        :returns: path to IOUYAP
        """

        path = self._manager.config.get_section_config("IOU").get("iouyap_path", "iouyap")
        if path == "iouyap":
            path = shutil.which("iouyap")
        return path

    @property
    def console(self):
        """
        Returns the console port of this IOU vm.

        :returns: console port
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Change console port

        :params console: Console port (integer)
        """

        if console == self._console:
            return
        if self._console:
            self._manager.port_manager.release_console_port(self._console)
        self._console = self._manager.port_manager.reserve_console_port(console)

    @property
    def ram(self):
        """
        Returns the amount of RAM allocated to this IOU instance.
        :returns: amount of RAM in Mbytes (integer)
        """

        return self._ram

    @ram.setter
    def ram(self, ram):
        """
        Sets amount of RAM allocated to this IOU instance.
        :param ram: amount of RAM in Mbytes (integer)
        """

        if self._ram == ram:
            return

        log.info("IOU {name} [id={id}]: RAM updated from {old_ram}MB to {new_ram}MB".format(name=self._name,
                                                                                            id=self._id,
                                                                                            old_ram=self._ram,
                                                                                            new_ram=ram))

        self._ram = ram

    @property
    def nvram(self):
        """
        Returns the mount of NVRAM allocated to this IOU instance.
        :returns: amount of NVRAM in Kbytes (integer)
        """

        return self._nvram

    @nvram.setter
    def nvram(self, nvram):
        """
        Sets amount of NVRAM allocated to this IOU instance.
        :param nvram: amount of NVRAM in Kbytes (integer)
        """

        if self._nvram == nvram:
            return

        log.info("IOU {name} [id={id}]: NVRAM updated from {old_nvram}KB to {new_nvram}KB".format(name=self._name,
                                                                                                  id=self._id,
                                                                                                  old_nvram=self._nvram,
                                                                                                  new_nvram=nvram))
        self._nvram = nvram

    @property
    def application_id(self):
        return self._manager.get_application_id(self.id)

    # TODO: ASYNCIO
    def _library_check(self):
        """
        Checks for missing shared library dependencies in the IOU image.
        """

        try:
            output = subprocess.check_output(["ldd", self._path])
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            log.warn("could not determine the shared library dependencies for {}: {}".format(self._path, e))
            return

        p = re.compile("([\.\w]+)\s=>\s+not found")
        missing_libs = p.findall(output.decode("utf-8"))
        if missing_libs:
            raise IOUError("The following shared library dependencies cannot be found for IOU image {}: {}".format(self._path,
                                                                                                                   ", ".join(missing_libs)))

    @asyncio.coroutine
    def start(self):
        """
        Starts the IOU process.
        """

        self._check_requirements()
        if not self.is_running():

            # TODO: ASYNC
            # self._library_check()

            if self._iourc_path and not os.path.isfile(self._iourc_path):
                raise IOUError("A valid iourc file is necessary to start IOU")

            iouyap_path = self.iouyap_path
            if not iouyap_path or not os.path.isfile(iouyap_path):
                raise IOUError("iouyap is necessary to start IOU")

            self._create_netmap_config()
            # created a environment variable pointing to the iourc file.
            env = os.environ.copy()
            if self._iourc_path:
                env["IOURC"] = self._iourc_path
            self._command = self._build_command()
            try:
                log.info("Starting IOU: {}".format(self._command))
                self._iou_stdout_file = os.path.join(self.working_dir, "iou.log")
                log.info("Logging to {}".format(self._iou_stdout_file))
                with open(self._iou_stdout_file, "w") as fd:
                    self._iou_process = yield from asyncio.create_subprocess_exec(*self._command,
                                                                                  stdout=fd,
                                                                                  stderr=subprocess.STDOUT,
                                                                                  cwd=self.working_dir,
                                                                                  env=env)
                log.info("IOU instance {} started PID={}".format(self._id, self._iou_process.pid))
                self._started = True
            except FileNotFoundError as e:
                raise IOUError("could not start IOU: {}: 32-bit binary support is probably not installed".format(e))
            except (OSError, subprocess.SubprocessError) as e:
                iou_stdout = self.read_iou_stdout()
                log.error("could not start IOU {}: {}\n{}".format(self._path, e, iou_stdout))
                raise IOUError("could not start IOU {}: {}\n{}".format(self._path, e, iou_stdout))

            # start console support
            self._start_ioucon()
            # connections support
            self._start_iouyap()

    def _start_iouyap(self):
        """
        Starts iouyap (handles connections to and from this IOU device).
        """

        try:
            self._update_iouyap_config()
            command = [self.iouyap_path, "-q", str(self.application_id + 512)]  # iouyap has always IOU ID + 512
            log.info("starting iouyap: {}".format(command))
            self._iouyap_stdout_file = os.path.join(self.working_dir, "iouyap.log")
            log.info("logging to {}".format(self._iouyap_stdout_file))
            with open(self._iouyap_stdout_file, "w") as fd:
                self._iouyap_process = subprocess.Popen(command,
                                                        stdout=fd,
                                                        stderr=subprocess.STDOUT,
                                                        cwd=self.working_dir)

            log.info("iouyap started PID={}".format(self._iouyap_process.pid))
        except (OSError, subprocess.SubprocessError) as e:
            iouyap_stdout = self.read_iouyap_stdout()
            log.error("could not start iouyap: {}\n{}".format(e, iouyap_stdout))
            raise IOUError("Could not start iouyap: {}\n{}".format(e, iouyap_stdout))

    def _update_iouyap_config(self):
        """
        Updates the iouyap.ini file.
        """

        iouyap_ini = os.path.join(self.working_dir, "iouyap.ini")

        config = configparser.ConfigParser()
        config["default"] = {"netmap": "NETMAP",
                             "base_port": "49000"}

        bay_id = 0
        for adapter in self._slots:
            unit_id = 0
            for unit in adapter.ports.keys():
                nio = adapter.get_nio(unit)
                if nio:
                    connection = None
                    if isinstance(nio, NIO_UDP):
                        # UDP tunnel
                        connection = {"tunnel_udp": "{lport}:{rhost}:{rport}".format(lport=nio.lport,
                                                                                     rhost=nio.rhost,
                                                                                     rport=nio.rport)}
                    elif isinstance(nio, NIO_TAP):
                        # TAP interface
                        connection = {"tap_dev": "{tap_device}".format(tap_device=nio.tap_device)}

                    elif isinstance(nio, NIO_GenericEthernet):
                        # Ethernet interface
                        connection = {"eth_dev": "{ethernet_device}".format(ethernet_device=nio.ethernet_device)}

                    if connection:
                        interface = "{iouyap_id}:{bay}/{unit}".format(iouyap_id=str(self.application_id + 512), bay=bay_id, unit=unit_id)
                        config[interface] = connection

                        if nio.capturing:
                            pcap_data_link_type = nio.pcap_data_link_type.upper()
                            if pcap_data_link_type == "DLT_PPP_SERIAL":
                                pcap_protocol = "ppp"
                            elif pcap_data_link_type == "DLT_C_HDLC":
                                pcap_protocol = "hdlc"
                            elif pcap_data_link_type == "DLT_FRELAY":
                                pcap_protocol = "fr"
                            else:
                                pcap_protocol = "ethernet"
                            capture_info = {"pcap_file": "{pcap_file}".format(pcap_file=nio.pcap_output_file),
                                            "pcap_protocol": pcap_protocol,
                                            "pcap_overwrite": "y"}
                            config[interface].update(capture_info)

                unit_id += 1
            bay_id += 1

        try:
            with open(iouyap_ini, "w") as config_file:
                config.write(config_file)
            log.info("IOU {name} [id={id}]: iouyap.ini updated".format(name=self._name,
                                                                       id=self._id))
        except OSError as e:
            raise IOUError("Could not create {}: {}".format(iouyap_ini, e))

    @asyncio.coroutine
    def stop(self):
        """
        Stops the IOU process.
        """

        # stop console support
        if self._ioucon_thread:
            self._ioucon_thread_stop_event.set()
            if self._ioucon_thread.is_alive():
                self._ioucon_thread.join(timeout=3.0)  # wait for the thread to free the console port
            self._ioucon_thread = None

        if self.is_running():
            self._terminate_process_iou()
            try:
                yield from asyncio.wait_for(self._iou_process.wait(), timeout=3)
            except asyncio.TimeoutError:
                self._iou_process.kill()
                if self._iou_process.returncode is None:
                    log.warn("IOU process {} is still running".format(self._iou_process.pid))

            self._iou_process = None

            if self._iouyap_process is not None:
                self._terminate_process_iouyap()
                try:
                    yield from asyncio.wait_for(self._iouyap_process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    self._iou_process.kill()
                    if self._iouyap_process.returncode is None:
                        log.warn("IOUYAP process {} is still running".format(self._iou_process.pid))

            self._started = False

    def _terminate_process_iouyap(self):
        """Terminate the process if running"""

        if self._iou_process:
            log.info("Stopping IOUYAP instance {} PID={}".format(self.name, self._iouyap_process.pid))
            try:
                self._iouyap_process.terminate()
            # Sometime the process can already be dead when we garbage collect
            except ProcessLookupError:
                pass

    def _terminate_process_iou(self):
        """Terminate the process if running"""

        if self._iou_process:
            log.info("Stopping IOU instance {} PID={}".format(self.name, self._iou_process.pid))
            try:
                self._iou_process.terminate()
            # Sometime the process can already be dead when we garbage collect
            except ProcessLookupError:
                pass

    @asyncio.coroutine
    def reload(self):
        """
        Reload the IOU process. (Stop / Start)
        """

        yield from self.stop()
        yield from self.start()

    def is_running(self):
        """
        Checks if the IOU process is running

        :returns: True or False
        """

        if self._iou_process:
            return True
        return False

    def _create_netmap_config(self):
        """
        Creates the NETMAP file.
        """

        netmap_path = os.path.join(self.working_dir, "NETMAP")
        try:
            with open(netmap_path, "w") as f:
                for bay in range(0, 16):
                    for unit in range(0, 4):
                        f.write("{iouyap_id}:{bay}/{unit}{iou_id:>5d}:{bay}/{unit}\n".format(iouyap_id=str(self.application_id + 512),
                                                                                             bay=bay,
                                                                                             unit=unit,
                                                                                             iou_id=self.application_id))
            log.info("IOU {name} [id={id}]: NETMAP file created".format(name=self._name,
                                                                        id=self._id))
        except OSError as e:
            raise IOUError("Could not create {}: {}".format(netmap_path, e))

    def _build_command(self):
        """
        Command to start the IOU process.
        (to be passed to subprocess.Popen())
        IOU command line:
        Usage: <image> [options] <application id>
        <image>: unix-js-m | unix-is-m | unix-i-m | ...
        <application id>: instance identifier (0 < id <= 1024)
        Options:
        -e <n>        Number of Ethernet interfaces (default 2)
        -s <n>        Number of Serial interfaces (default 2)
        -n <n>        Size of nvram in Kb (default 64KB)
        -b <string>   IOS debug string
        -c <name>     Configuration file name
        -d            Generate debug information
        -t            Netio message trace
        -q            Suppress informational messages
        -h            Display this help
        -C            Turn off use of host clock
        -m <n>        Megabytes of router memory (default 256MB)
        -L            Disable local console, use remote console
        -l            Enable Layer 1 keepalive messages
        -u <n>        UDP port base for distributed networks
        -R            Ignore options from the IOURC file
        -U            Disable unix: file system location
        -W            Disable watchdog timer
        -N            Ignore the NETMAP file
        """

        command = [self._path]
        if len(self._ethernet_adapters) != 2:
            command.extend(["-e", str(len(self._ethernet_adapters))])
        if len(self._serial_adapters) != 2:
            command.extend(["-s", str(len(self._serial_adapters))])
        if not self.use_default_iou_values:
            command.extend(["-n", str(self._nvram)])
            command.extend(["-m", str(self._ram)])
        command.extend(["-L"])  # disable local console, use remote console
        if self._initial_config:
            command.extend(["-c", self._initial_config])
        if self._l1_keepalives:
            self._enable_l1_keepalives(command)
        command.extend([str(self.application_id)])
        return command

    def read_iou_stdout(self):
        """
        Reads the standard output of the IOU process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._iou_stdout_file:
            try:
                with open(self._iou_stdout_file, errors="replace") as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._iou_stdout_file, e))
        return output

    def read_iouyap_stdout(self):
        """
        Reads the standard output of the iouyap process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._iouyap_stdout_file:
            try:
                with open(self._iouyap_stdout_file, errors="replace") as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._iouyap_stdout_file, e))
        return output

    def _start_ioucon(self):
        """
        Starts ioucon thread (for console connections).
        """

        if not self._ioucon_thread:
            telnet_server = "{}:{}".format(self._console_host, self.console)
            log.info("Starting ioucon for IOU instance {} to accept Telnet connections on {}".format(self._name, telnet_server))
            args = argparse.Namespace(appl_id=str(self.application_id), debug=False, escape='^^', telnet_limit=0, telnet_server=telnet_server)
            self._ioucon_thread_stop_event = threading.Event()
            self._ioucon_thread = threading.Thread(target=start_ioucon, args=(args, self._ioucon_thread_stop_event))
            self._ioucon_thread.start()

    @property
    def ethernet_adapters(self):
        """
        Returns the number of Ethernet adapters for this IOU instance.
        :returns: number of adapters
        """

        return len(self._ethernet_adapters)

    @ethernet_adapters.setter
    def ethernet_adapters(self, ethernet_adapters):
        """
        Sets the number of Ethernet adapters for this IOU instance.
        :param ethernet_adapters: number of adapters
        """

        self._ethernet_adapters.clear()
        for _ in range(0, ethernet_adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info("IOU {name} [id={id}]: number of Ethernet adapters changed to {adapters}".format(name=self._name,
                                                                                                  id=self._id,
                                                                                                  adapters=len(self._ethernet_adapters)))

        self._slots = self._ethernet_adapters + self._serial_adapters

    @property
    def serial_adapters(self):
        """
        Returns the number of Serial adapters for this IOU instance.
        :returns: number of adapters
        """

        return len(self._serial_adapters)

    @serial_adapters.setter
    def serial_adapters(self, serial_adapters):
        """
        Sets the number of Serial adapters for this IOU instance.
        :param serial_adapters: number of adapters
        """

        self._serial_adapters.clear()
        for _ in range(0, serial_adapters):
            self._serial_adapters.append(SerialAdapter())

        log.info("IOU {name} [id={id}]: number of Serial adapters changed to {adapters}".format(name=self._name,
                                                                                                id=self._id,
                                                                                                adapters=len(self._serial_adapters)))

        self._slots = self._ethernet_adapters + self._serial_adapters
