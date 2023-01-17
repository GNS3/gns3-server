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
Represents a Dynamips hypervisor and starts/stops the associated Dynamips process.
"""

import sys
import os
import subprocess
import asyncio

from gns3server.utils.asyncio import wait_for_process_termination
from .dynamips_hypervisor import DynamipsHypervisor
from .dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class Hypervisor(DynamipsHypervisor):

    """
    Hypervisor.

    :param path: path to Dynamips executable
    :param working_dir: working directory
    :param host: host/address for this hypervisor
    :param port: port for this hypervisor
    :param console_host: host/address for console connections
    """

    _instance_count = 1

    def __init__(self, path, working_dir, host, port, console_host, bind_console_host=False):

        super().__init__(working_dir, host, port)

        # create an unique ID
        self._id = Hypervisor._instance_count
        Hypervisor._instance_count += 1

        self._console_host = console_host
        self._bind_console_host = bind_console_host
        self._path = path
        self._command = []
        self._process = None
        self._stdout_file = ""
        self._started = False

    @property
    def id(self):
        """
        Returns the unique ID for this hypervisor.

        :returns: id (integer)
        """

        return self._id

    @property
    def process(self):
        """
        Returns the subprocess of the Hypervisor

        :returns: subprocess
        """

        return self._process

    @property
    def started(self):
        """
        Returns either this hypervisor has been started or not.

        :returns: boolean
        """

        return self._started

    @property
    def path(self):
        """
        Returns the path to the Dynamips executable.

        :returns: path to Dynamips
        """

        return self._path

    @path.setter
    def path(self, path):
        """
        Sets the path to the Dynamips executable.

        :param path: path to Dynamips
        """

        self._path = path

    async def start(self):
        """
        Starts the Dynamips hypervisor process.
        """

        self._command = self._build_command()
        env = os.environ.copy()
        if sys.platform.startswith("win"):
            # add the Npcap directory to $PATH to force Dynamips to use npcap DLL instead of Winpcap (if installed)
            system_root = os.path.join(os.path.expandvars("%SystemRoot%"), "System32", "Npcap")
            if os.path.isdir(system_root):
                env["PATH"] = system_root + ';' + env["PATH"]
        try:
            log.info("Starting Dynamips: {}".format(self._command))
            self._stdout_file = os.path.join(self.working_dir, "dynamips_i{}_stdout.txt".format(self._id))
            log.info("Dynamips process logging to {}".format(self._stdout_file))
            with open(self._stdout_file, "w", encoding="utf-8") as fd:
                self._process = await asyncio.create_subprocess_exec(*self._command,
                                                                          stdout=fd,
                                                                          stderr=subprocess.STDOUT,
                                                                          cwd=self._working_dir,
                                                                          env=env)
            log.info("Dynamips process started PID={}".format(self._process.pid))
            self._started = True
        except (OSError, subprocess.SubprocessError) as e:
            log.error("Could not start Dynamips: {}".format(e))
            raise DynamipsError("Could not start Dynamips: {}".format(e))

    async def stop(self):
        """
        Stops the Dynamips hypervisor process.
        """

        if self.is_running():
            log.info("Stopping Dynamips process PID={}".format(self._process.pid))
            await DynamipsHypervisor.stop(self)
            # give some time for the hypervisor to properly stop.
            # time to delete UNIX NIOs for instance.
            await asyncio.sleep(0.01)
            try:
                await wait_for_process_termination(self._process, timeout=3)
            except asyncio.TimeoutError:
                if self._process.returncode is None:
                    log.warning("Dynamips process {} is still running... killing it".format(self._process.pid))
                    try:
                        self._process.kill()
                    except OSError as e:
                        log.error("Cannot stop the Dynamips process: {}".format(e))
                    if self._process.returncode is None:
                        log.warning('Dynamips hypervisor with PID={} is still running'.format(self._process.pid))

        if self._stdout_file and os.access(self._stdout_file, os.W_OK):
            try:
                os.remove(self._stdout_file)
            except OSError as e:
                log.warning("could not delete temporary Dynamips log file: {}".format(e))
        self._started = False

    def read_stdout(self):
        """
        Reads the standard output of the Dynamips process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stdout_file and os.access(self._stdout_file, os.R_OK):
            try:
                with open(self._stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warning("could not read {}: {}".format(self._stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the process is running

        :returns: True or False
        """

        if self._process and self._process.returncode is None:
            return True
        return False

    def _build_command(self):
        """
        Command to start the Dynamips hypervisor process.
        (to be passed to subprocess.Popen())
        """

        command = [self._path]
        command.extend(["-N1"])  # use instance IDs for filenames
        command.extend(["-l", "dynamips_i{}_log.txt".format(self._id)])  # log file

        if self._bind_console_host:
            # support was added in Dynamips version 0.2.23
            command.extend(["-H", "{}:{}".format(self._host, self._port), "--console-binding-addr", self._console_host])
        elif self._console_host != "0.0.0.0" and self._console_host != "::":
            command.extend(["-H", "{}:{}".format(self._host, self._port)])
        else:
            command.extend(["-H", str(self._port)])

        return command
