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
import subprocess
import logging

from .dynamips_hypervisor import DynamipsHypervisor

logger = logging.getLogger(__name__)


class Hypervisor(DynamipsHypervisor):
    """
    Hypervisor.

    :param path: path to Dynamips executable
    :param workingdir: working directory
    :param port: port for this hypervisor
    :param host: host/address for this hypervisor
    """

    _instance_count = 0

    def __init__(self, path, workingdir, host, port):

        DynamipsHypervisor.__init__(self, host, port)

        # create an unique ID
        self._id = Hypervisor._instance_count
        Hypervisor._instance_count += 1

        self._path = path
        self._workingdir = workingdir
        self._command = []
        self._process = None
        self._stdout = None

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

        return(self._id)

    @property
    def path(self):
        """
        Returns the path to the Dynamips executable.

        :returns: path to Dynamips
        """

        return(self._path)

    @path.setter
    def path(self, path):
        """
        Set the path to the Dynamips executable.

        :param path: path to Dynamips
        """

        self._path = path

    @property
    def port(self):
        """
        Returns the port used to start the Dynamips hypervisor.

        :returns: port number (integer)
        """

        return(self._port)

    @port.setter
    def port(self, port):
        """
        Set the port used to start the Dynamips hypervisor.

        :param port: port number (integer)
        """

        self._port = port

    @property
    def host(self):
        """
        Returns the host (binding) used to start the Dynamips hypervisor.

        :returns: host/address (string)
        """

        return(self._host)

    @host.setter
    def host(self, host):
        """
        Set the host (binding) used to start the Dynamips hypervisor.

        :param host: host/address (string)
        """

        self._host = host

    @property
    def workingdir(self):
        """
        Returns the working directory used to start the Dynamips hypervisor.

        :returns: path to a working directory
        """

        return(self._workingdir)

    @workingdir.setter
    def workingdir(self, workingdir):
        """
        Set the working directory used to start the Dynamips hypervisor.

        :param workingdir: path to a working directory
        """

        self._workingdir = workingdir

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
        Set the reference IOS image name
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
            logger.info("Starting Dynamips: {}".format(self._command))
            # TODO: create unique filename for stdout
            self.stdout_file = os.path.join(self._workingdir, "dynamips.log")
            fd = open(self.stdout_file, "w")
            # TODO: check for exceptions and if process has already been started
            self._process = subprocess.Popen(self._command,
                                             stdout=fd,
                                             stderr=subprocess.STDOUT,
                                             cwd=self._workingdir)
            logger.info("Dynamips started PID={}".format(self._process.pid))
        except OSError as e:
            logger.error("Could not start Dynamips: {}".format(e))
        finally:
            fd.close()

    def stop(self):
        """
        Stops the Dynamips hypervisor process.
        """

        if self.is_running():
            logger.info("Stopping Dynamips PID={}".format(self._process.pid))
            self._process.kill()

    def read_stdout(self):
        """
        Reads the standard output of the Dynamips process.
        Only use when the process has been stopped or has crashed.
        """

        # TODO: check for exceptions
        with open(self.stdout_file) as file:
            output = file.read()
        return output

    def is_running(self):
        """
        Checks if the process is running

        :returns: True or False
        """

        if self._process and self._process.poll() == None:
            return True
        return False

    def _build_command(self):
        """
        Command to start the Dynamips hypervisor process.
        (to be passed to subprocess.Popen())
        """

        command = [self._path]
        command.extend(["-N1"])  # use instance IDs for filenames
        if self._host != '0.0.0.0':
            command.extend(['-H', self._host + ':' + str(self._port)])
        else:
            command.extend(['-H', self._port])
        return command
