# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

import os
import time
import subprocess
import tempfile

from .dynamips_hypervisor import DynamipsHypervisor
from .dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class Hypervisor(DynamipsHypervisor):
    """
    Hypervisor.

    :param path: path to Dynamips executable
    :param working_dir: working directory
    :param port: port for this hypervisor
    :param host: host/address for this hypervisor
    """

    _instance_count = 0

    def __init__(self, path, working_dir, host, port):

        DynamipsHypervisor.__init__(self, working_dir, host, port)

        # create an unique ID
        self._id = Hypervisor._instance_count
        Hypervisor._instance_count += 1

        self._path = path
        self._command = []
        self._process = None
        self._stdout_file = ""
        self._started = False

        # settings used the load-balance hypervisors
        # (for the hypervisor manager)
        self._memory_load = 0
        self._ios_image_ref = ""

    @property
    def id(self):
        """
        Returns the unique ID for this hypervisor.

        :returns: id (integer)
        """

        return self._id

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

    @property
    def port(self):
        """
        Returns the port used to start the Dynamips hypervisor.

        :returns: port number (integer)
        """

        return self._port

    @port.setter
    def port(self, port):
        """
        Sets the port used to start the Dynamips hypervisor.

        :param port: port number (integer)
        """

        self._port = port

    @property
    def host(self):
        """
        Returns the host (binding) used to start the Dynamips hypervisor.

        :returns: host/address (string)
        """

        return self._host

    @host.setter
    def host(self, host):
        """
        Sets the host (binding) used to start the Dynamips hypervisor.

        :param host: host/address (string)
        """

        self._host = host

    @property
    def image_ref(self):
        """
        Returns the reference IOS image name
        (used by the hypervisor manager for load-balancing purposes).

        :returns: image reference name
        """

        return self._ios_image_ref

    @image_ref.setter
    def image_ref(self, ios_image_name):
        """
        Sets the reference IOS image name
        (used by the hypervisor manager for load-balancing purposes).

        :param ios_image_name: image reference name
        """

        self._ios_image_ref = ios_image_name

    def increase_memory_load(self, memory):
        """
        Increases the memory load of this hypervisor.
        (used by the hypervisor manager for load-balancing purposes).

        :param memory: amount of RAM (integer)
        """

        self._memory_load += memory

    def decrease_memory_load(self, memory):
        """
        Decreases the memory load of this hypervisor.
        (used by the hypervisor manager for load-balancing purposes).

        :param memory: amount of RAM (integer)
        """

        self._memory_load -= memory

    @property
    def memory_load(self):
        """
        Returns the memory load of this hypervisor.
        (used by the hypervisor manager for load-balancing purposes).

        :returns: amount of RAM (integer)
        """

        return self._memory_load

    def start(self):
        """
        Starts the Dynamips hypervisor process.
        """

        self._command = self._build_command()
        try:
            log.info("starting Dynamips: {}".format(self._command))
            with tempfile.NamedTemporaryFile(delete=False) as fd:
                self._stdout_file = fd.name
                log.info("Dynamips process logging to {}".format(fd.name))
                self._process = subprocess.Popen(self._command,
                                                 stdout=fd,
                                                 stderr=subprocess.STDOUT,
                                                 cwd=self._working_dir)
            log.info("Dynamips started PID={}".format(self._process.pid))
            self._started = True
        except OSError as e:
            log.error("could not start Dynamips: {}".format(e))
            raise DynamipsError("could not start Dynamips: {}".format(e))

    def stop(self):
        """
        Stops the Dynamips hypervisor process.
        """

        if self.is_running():
            DynamipsHypervisor.stop(self)
            log.info("stopping Dynamips PID={}".format(self._process.pid))
            try:
                # give some time for the hypervisor to properly stop.
                # time to delete UNIX NIOs for instance.
                time.sleep(0.01)
                self._process.terminate()
                self._process.wait(1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.poll() is None:
                    log.warn("Dynamips process {} is still running".format(self._process.pid))

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
                with open(self._stdout_file, errors="replace") as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the process is running

        :returns: True or False
        """

        if self._process and self._process.poll() is None:
            return True
        return False

    def _build_command(self):
        """
        Command to start the Dynamips hypervisor process.
        (to be passed to subprocess.Popen())
        """

        command = [self._path]
        command.extend(["-N1"])  # use instance IDs for filenames
        command.extend(["-l", "dynamips_log_{}.txt".format(self._port)])  # log file
        if self._host != "0.0.0.0" and self._host != "::":
            command.extend(["-H", "{}:{}".format(self._host, self._port)])
        else:
            command.extend(["-H", str(self._port)])
        return command
