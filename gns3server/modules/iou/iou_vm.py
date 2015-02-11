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

from pkg_resources import parse_version
from .iou_error import IOUError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..adapters.serial_adapter import SerialAdapter
from ..base_vm import BaseVM


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
    """

    def __init__(self, name, vm_id, project, manager, console=None):

        super().__init__(name, vm_id, project, manager)

        self._console = console
        self._command = []
        self._iouyap_process = None
        self._iou_process = None
        self._iou_stdout_file = ""
        self._started = False
        self._iou_path = None
        self._iourc = None
        self._ioucon_thread = None

        # IOU settings
        self._ethernet_adapters = [EthernetAdapter(), EthernetAdapter()]  # one adapter = 4 interfaces
        self._serial_adapters = [SerialAdapter(), SerialAdapter()]  # one adapter = 4 interfaces
        self._slots = self._ethernet_adapters + self._serial_adapters
        self._use_default_iou_values = True  # for RAM & NVRAM values
        self._nvram = 128  # Kilobytes
        self._initial_config = ""
        self._ram = 256  # Megabytes
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
    def iou_path(self):
        """Path of the iou binary"""

        return self._iou_path

    @iou_path.setter
    def iou_path(self, path):
        """
        Path of the iou binary

        :params path: Path to the binary
        """

        self._iou_path = path
        if not os.path.isfile(self._iou_path) or not os.path.exists(self._iou_path):
            if os.path.islink(self._iou_path):
                raise IOUError("IOU image '{}' linked to '{}' is not accessible".format(self._iou_path, os.path.realpath(self._iou_path)))
            else:
                raise IOUError("IOU image '{}' is not accessible".format(self._iou_path))

        try:
            with open(self._iou_path, "rb") as f:
                # read the first 7 bytes of the file.
                elf_header_start = f.read(7)
        except OSError as e:
            raise IOUError("Cannot read ELF header for IOU image '{}': {}".format(self._iou_path, e))

        # IOU images must start with the ELF magic number, be 32-bit, little endian
        # and have an ELF version of 1 normal IOS image are big endian!
        if elf_header_start != b'\x7fELF\x01\x01\x01':
            raise IOUError("'{}' is not a valid IOU image".format(self._iou_path))

        if not os.access(self._iou_path, os.X_OK):
            raise IOUError("IOU image '{}' is not executable".format(self._iou_path))

    @property
    def iourc(self):
        """
        Returns the path to the iourc file.
        :returns: path to the iourc file
        """

        return self._iourc

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

    @iourc.setter
    def iourc(self, iourc):
        """
        Sets the path to the iourc file.
        :param iourc: path to the iourc file.
        """

        self._iourc = iourc
        log.info("IOU {name} [id={id}]: iourc file path set to {path}".format(name=self._name,
                                                                              id=self._id,
                                                                              path=self._iourc))

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
    def application_id(self):
        return self._manager.get_application_id(self.id)

    #TODO: ASYNCIO
    def _library_check(self):
        """
        Checks for missing shared library dependencies in the IOU image.
        """

        try:
            output = subprocess.check_output(["ldd", self._iou_path])
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
            #self._library_check()

            if not self._iourc or not os.path.isfile(self._iourc):
                raise IOUError("A valid iourc file is necessary to start IOU")

            iouyap_path = self.iouyap_path
            if not iouyap_path or not os.path.isfile(iouyap_path):
                raise IOUError("iouyap is necessary to start IOU")

            self._create_netmap_config()
            # created a environment variable pointing to the iourc file.
            env = os.environ.copy()
            env["IOURC"] = self._iourc
            self._command = self._build_command()
            try:
                log.info("Starting IOU: {}".format(self._command))
                self._iou_stdout_file = os.path.join(self.working_dir, "iou.log")
                log.info("Logging to {}".format(self._iou_stdout_file))
                with open(self._iou_stdout_file, "w") as fd:
                    self._iou_process = yield from asyncio.create_subprocess_exec(self._command,
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
                log.error("could not start IOU {}: {}\n{}".format(self._iou_path, e, iou_stdout))
                raise IOUError("could not start IOU {}: {}\n{}".format(self._iou_path, e, iou_stdout))

            # start console support
            #self._start_ioucon()
            # connections support
            #self._start_iouyap()


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
            self._terminate_process()
            try:
                yield from asyncio.wait_for(self._iou_process.wait(), timeout=3)
            except asyncio.TimeoutError:
                self._iou_process.kill()
                if self._iou_process.returncode is None:
                    log.warn("IOU process {} is still running".format(self._iou_process.pid))

            self._iou_process = None
            self._started = False

    def _terminate_process(self):
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

        command = [self._iou_path]
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
