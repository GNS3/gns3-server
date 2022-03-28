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
Represents a uBridge hypervisor and starts/stops the associated uBridge process.
"""

import sys
import os
import subprocess
import asyncio
import socket
import re

from gns3server.utils import parse_version
from gns3server.utils.asyncio import wait_for_process_termination
from gns3server.utils.asyncio import subprocess_check_output
from .ubridge_hypervisor import UBridgeHypervisor
from .ubridge_error import UbridgeError

import logging

log = logging.getLogger(__name__)


class Hypervisor(UBridgeHypervisor):

    """
    Hypervisor.

    :param project: Project instance
    :param path: path to uBridge executable
    :param working_dir: working directory
    :param host: host/address for this hypervisor
    :param port: port for this hypervisor
    """

    _instance_count = 1

    def __init__(self, project, path, working_dir, host, port=None):

        if port is None:
            try:
                port = None
                info = socket.getaddrinfo(host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
                if not info:
                    raise UbridgeError(f"getaddrinfo returns an empty list on {host}")
                for res in info:
                    af, socktype, proto, _, sa = res
                    # let the OS find an unused port for the uBridge hypervisor
                    with socket.socket(af, socktype, proto) as sock:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        sock.bind(sa)
                        port = sock.getsockname()[1]
                        break
            except OSError as e:
                raise UbridgeError(f"Could not find free port for the uBridge hypervisor: {e}")

        super().__init__(host, port)
        self._project = project
        self._path = path
        self._working_dir = working_dir
        self._command = []
        self._process = None
        self._stdout_file = ""
        self._started = False
        self._version = ""

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
        Returns the path to the uBridge executable.

        :returns: path to uBridge
        """

        return self._path

    @path.setter
    def path(self, path):
        """
        Sets the path to the uBridge executable.

        :param path: path to uBridge
        """

        self._path = path

    @property
    def version(self):
        """
        Returns the uBridge version.

        :returns: string
        """

        return self._version

    async def _check_ubridge_version(self, env=None):
        """
        Checks if the ubridge executable version
        """
        try:
            output = await subprocess_check_output(self._path, "-v", cwd=self._working_dir, env=env)
            match = re.search(r"ubridge version ([0-9a-z\.]+)", output)
            if match:
                self._version = match.group(1)
                if sys.platform.startswith("darwin"):
                    minimum_required_version = "0.9.12"
                else:
                    # uBridge version 0.9.14 is required for packet filters
                    # to work for IOU nodes.
                    minimum_required_version = "0.9.14"
                if parse_version(self._version) < parse_version(minimum_required_version):
                    raise UbridgeError(f"uBridge executable version must be >= {minimum_required_version}")
            else:
                raise UbridgeError(f"Could not determine uBridge version for {self._path}")
        except (OSError, subprocess.SubprocessError) as e:
            raise UbridgeError(f"Error while looking for uBridge version: {e}")

    async def start(self):
        """
        Starts the uBridge hypervisor process.
        """

        env = os.environ.copy()
        await self._check_ubridge_version(env)
        try:
            command = self._build_command()
            log.info(f"starting ubridge: {command}")
            self._stdout_file = os.path.join(self._working_dir, "ubridge.log")
            log.info(f"logging to {self._stdout_file}")
            with open(self._stdout_file, "w", encoding="utf-8") as fd:
                self._process = await asyncio.create_subprocess_exec(
                    *command, stdout=fd, stderr=subprocess.STDOUT, cwd=self._working_dir, env=env
                )

            log.info(f"ubridge started PID={self._process.pid}")
            # recv: Bad address is received by uBridge when a docker image stops by itself
            # see https://github.com/GNS3/gns3-gui/issues/2957
            # monitor_process(self._process, self._termination_callback)
        except (OSError, subprocess.SubprocessError) as e:
            ubridge_stdout = self.read_stdout()
            log.error(f"Could not start ubridge: {e}\n{ubridge_stdout}")
            raise UbridgeError(f"Could not start ubridge: {e}\n{ubridge_stdout}")

    def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if returncode != 0:
            error_msg = f"uBridge process has stopped, return code: {returncode}\n{self.read_stdout()}\n"
            log.error(error_msg)
            self._project.emit("log.error", {"message": error_msg})
        else:
            log.info("uBridge process has stopped, return code: %d", returncode)

    async def stop(self):
        """
        Stops the uBridge hypervisor process.
        """

        if self.is_running():
            log.info(f"Stopping uBridge process PID={self._process.pid}")
            await UBridgeHypervisor.stop(self)
            try:
                await wait_for_process_termination(self._process, timeout=3)
            except asyncio.TimeoutError:
                if self._process and self._process.returncode is None:
                    log.warning(f"uBridge process {self._process.pid} is still running... killing it")
                    try:
                        self._process.kill()
                    except ProcessLookupError:
                        pass

        if self._stdout_file and os.access(self._stdout_file, os.W_OK):
            try:
                os.remove(self._stdout_file)
            except OSError as e:
                log.warning(f"could not delete temporary uBridge log file: {e}")
        self._process = None
        self._started = False

    def read_stdout(self):
        """
        Reads the standard output of the uBridge process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stdout_file and os.access(self._stdout_file, os.R_OK):
            try:
                with open(self._stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warning(f"could not read {self._stdout_file}: {e}")
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
        Command to start the uBridge hypervisor process.
        (to be passed to subprocess.Popen())
        """

        command = [self._path]
        command.extend(["-H", f"{self._host}:{self._port}"])
        if log.getEffectiveLevel() == logging.DEBUG:
            command.extend(["-d", "1"])
        return command
