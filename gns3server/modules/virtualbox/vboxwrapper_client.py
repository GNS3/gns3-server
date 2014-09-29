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
Client to VirtualBox wrapper.
"""

import os
import time
import subprocess
import tempfile
import socket
import re

from pkg_resources import parse_version
from ..attic import wait_socket_is_ready
from .virtualbox_error import VirtualBoxError

import logging
log = logging.getLogger(__name__)


class VboxWrapperClient(object):
    """
    VirtualBox Wrapper client.

    :param path: path to VirtualBox wrapper executable
    :param working_dir: working directory
    :param port: port
    :param host: host/address
    """

    # Used to parse the VirtualBox wrapper response codes
    error_re = re.compile(r"""^2[0-9]{2}-""")
    success_re = re.compile(r"""^1[0-9]{2}\s{1}""")

    def __init__(self, path, working_dir, host, port=11525, timeout=30.0):

        self._path = path
        self._command = []
        self._process = None
        self._working_dir = working_dir
        self._stderr_file = ""
        self._started = False
        self._host = host
        self._port = port
        self._timeout = timeout
        self._socket = None

    @property
    def started(self):
        """
        Returns either VirtualBox wrapper has been started or not.

        :returns: boolean
        """

        return self._started

    @property
    def path(self):
        """
        Returns the path to the VirtualBox wrapper executable.

        :returns: path to VirtualBox wrapper
        """

        return self._path

    @path.setter
    def path(self, path):
        """
        Sets the path to the VirtualBox wrapper executable.

        :param path: path to VirtualBox wrapper
        """

        self._path = path

    @property
    def port(self):
        """
        Returns the port used to start the VirtualBox wrapper.

        :returns: port number (integer)
        """

        return self._port

    @port.setter
    def port(self, port):
        """
        Sets the port used to start the VirtualBox wrapper.

        :param port: port number (integer)
        """

        self._port = port

    @property
    def host(self):
        """
        Returns the host (binding) used to start the VirtualBox wrapper.

        :returns: host/address (string)
        """

        return self._host

    @host.setter
    def host(self, host):
        """
        Sets the host (binding) used to start the VirtualBox wrapper.

        :param host: host/address (string)
        """

        self._host = host

    def start(self):
        """
        Starts the VirtualBox wrapper process.
        """

        self._command = self._build_command()
        try:
            log.info("starting VirtualBox wrapper: {}".format(self._command))
            with tempfile.NamedTemporaryFile(delete=False) as fd:
                with open(os.devnull, "w") as null:
                    self._stderr_file = fd.name
                    log.info("VirtualBox wrapper process logging to {}".format(fd.name))
                    self._process = subprocess.Popen(self._command,
                                                     stdout=null,
                                                     stderr=fd,
                                                     cwd=self._working_dir)
            log.info("VirtualBox wrapper started PID={}".format(self._process.pid))

            time.sleep(0.1) # give some time for vboxwrapper to start
            if self._process.poll() is not None:
                raise VirtualBoxError("Could not start VirtualBox wrapper: {}".format(self.read_stderr()))

            self.wait_for_vboxwrapper(self._host, self._port)
            self.connect()
            self._started = True

            version = self.send('vboxwrapper version')[0]
            if parse_version(version) < parse_version("0.9.1"):
                self.stop()
                raise VirtualBoxError("VirtualBox wrapper version must be >= 0.9.1")

        except OSError as e:
            log.error("could not start VirtualBox wrapper: {}".format(e))
            raise VirtualBoxError("Could not start VirtualBox wrapper: {}".format(e))

    def wait_for_vboxwrapper(self, host, port):
        """
        Waits for vboxwrapper to be started (accepting a socket connection)

        :param host: host/address to connect to the vboxwrapper
        :param port: port to connect to the vboxwrapper
        """

        begin = time.time()
        # wait for the socket for a maximum of 10 seconds.
        connection_success, last_exception = wait_socket_is_ready(host, port, wait=10.0)

        if not connection_success:
            raise VirtualBoxError("Couldn't connect to vboxwrapper on {}:{} :{}".format(host, port,
                                                                                 last_exception))
        else:
            log.info("vboxwrapper server ready after {:.4f} seconds".format(time.time() - begin))

    def stop(self):
        """
        Stops the VirtualBox wrapper process.
        """

        if self.connected():
            try:
                self.send("vboxwrapper stop")
            except VirtualBoxError:
                pass
            if self._socket:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                self._socket = None

        if self.is_running():
            log.info("stopping VirtualBox wrapper PID={}".format(self._process.pid))
            try:
                # give some time for the VirtualBox wrapper to properly stop.
                time.sleep(0.01)
                self._process.terminate()
                self._process.wait(1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.poll() is None:
                    log.warn("VirtualBox wrapper process {} is still running".format(self._process.pid))

        if self._stderr_file and os.access(self._stderr_file, os.W_OK):
            try:
                os.remove(self._stderr_file)
            except OSError as e:
                log.warning("could not delete temporary VirtualBox wrapper log file: {}".format(e))
        self._started = False

    def read_stderr(self):
        """
        Reads the standard error output of the VirtualBox wrapper process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stderr_file and os.access(self._stderr_file, os.R_OK):
            try:
                with open(self._stderr_file, errors="replace") as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._stderr_file, e))
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
        Command to start the VirtualBox wrapper process.
        (to be passed to subprocess.Popen())
        """

        command = [self._path]
        if self._host != "0.0.0.0" and self._host != "::":
            command.extend(["-l", self._host, "-p", str(self._port)])
        else:
            command.extend(["-p", str(self._port)])
        return command

    def connect(self):
        """
        Connects to the VirtualBox wrapper.
        """

        # connect to a local address by default
        # if listening to all addresses (IPv4 or IPv6)
        if self._host == "0.0.0.0":
            host = "127.0.0.1"
        elif self._host == "::":
            host = "::1"
        else:
            host = self._host

        try:
            self._socket = socket.create_connection((host, self._port), self._timeout)
        except OSError as e:
            raise VirtualBoxError("Could not connect to the VirtualBox wrapper: {}".format(e))

    def connected(self):
        """
        Returns either the client is connected to vboxwrapper or not.

        :return: boolean
        """

        if self._socket:
            return True
        return False

    def reset(self):
        """
        Resets the VirtualBox wrapper (used to get an empty configuration).
        """

        pass

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
        Sets the working directory for the VirtualBox wrapper.

        :param working_dir: path to the working directory
        """

        # encase working_dir in quotes to protect spaces in the path
        #self.send("hypervisor working_dir {}".format('"' + working_dir + '"'))
        self._working_dir = working_dir
        log.debug("working directory set to {}".format(self._working_dir))

    @property
    def socket(self):
        """
        Returns the current socket used to communicate with the VirtualBox wrapper.

        :returns: socket instance
        """

        assert self._socket
        return self._socket

    def get_vm_list(self):
        """
        Returns the list of all VirtualBox VMs.

        :returns: list of VM names
        """

        return self.send('vbox vm_list')

    def send(self, command):
        """
        Sends commands to the VirtualBox wrapper.

        :param command: a VirtualBox wrapper command

        :returns: results as a list
        """

        # VirtualBox wrapper responses are of the form:
        #   1xx yyyyyy\r\n
        #   1xx yyyyyy\r\n
        #   ...
        #   100-yyyy\r\n
        # or
        #   2xx-yyyy\r\n
        #
        # Where 1xx is a code from 100-199 for a success or 200-299 for an error
        # The result might be multiple lines and might be less than the buffer size
        # but still have more data. The only thing we know for sure is the last line
        # will begin with '100-' or a '2xx-' and end with '\r\n'

        if not self._socket:
            raise VirtualBoxError("Not connected")

        try:
            command = command.strip() + '\n'
            log.debug("sending {}".format(command))
            self.socket.sendall(command.encode('utf-8'))
        except OSError as e:
            self._socket = None
            raise VirtualBoxError("Lost communication with {host}:{port} :{error}"
                                .format(host=self._host, port=self._port, error=e))

        # Now retrieve the result
        data = []
        buf = ''
        while True:
            try:
                chunk = self.socket.recv(1024)
                buf += chunk.decode("utf-8")
            except OSError as e:
                self._socket = None
                raise VirtualBoxError("Communication timed out with {host}:{port} :{error}"
                                      .format(host=self._host, port=self._port, error=e))


            # If the buffer doesn't end in '\n' then we can't be done
            try:
                if buf[-1] != '\n':
                    continue
            except IndexError:
                self._socket = None
                raise VirtualBoxError("Could not communicate with {host}:{port}"
                                      .format(host=self._host, port=self._port))

            data += buf.split('\r\n')
            if data[-1] == '':
                data.pop()
            buf = ''

            if len(data) == 0:
                raise VirtualBoxError("no data returned from {host}:{port}"
                                      .format(host=self._host, port=self._port))

            # Does it contain an error code?
            if self.error_re.search(data[-1]):
                raise VirtualBoxError(data[-1][4:])

            # Or does the last line begin with '100-'? Then we are done!
            if data[-1][:4] == '100-':
                data[-1] = data[-1][4:]
                if data[-1] == 'OK':
                    data.pop()
                break

        # Remove success responses codes
        for index in range(len(data)):
            if self.success_re.search(data[index]):
                data[index] = data[index][4:]

        log.debug("returned result {}".format(data))
        return data
