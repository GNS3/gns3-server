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
VPCS device management (creates command line, processes, files etc.) in
order to run an VPCS instance.
"""

import os
import sys
import subprocess
import signal
import shutil
import re

from pkg_resources import parse_version
from .vpcs_error import VPCSError
from .adapters.ethernet_adapter import EthernetAdapter
from .nios.nio_udp import NIO_UDP
from .nios.nio_tap import NIO_TAP
from ..attic import find_unused_port

import logging
log = logging.getLogger(__name__)


class VPCSDevice(object):
    """
    VPCS device implementation.

    :param name: name of this VPCS device
    :param path: path to VPCS executable
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param vpcs_id: VPCS instance ID
    :param console: TCP console port
    :param console_start_port_range: TCP console port range start
    :param console_end_port_range: TCP console port range end
    """

    _instances = []
    _allocated_console_ports = []

    def __init__(self,
                 name,
                 path,
                 working_dir,
                 host="127.0.0.1",
                 vpcs_id=None,
                 console=None,
                 console_start_port_range=4512,
                 console_end_port_range=5000):


        if not vpcs_id:
            # find an instance identifier is none is provided (1 <= id <= 255)
            # This 255 limit is due to a restriction on the number of possible
            # MAC addresses given in VPCS using the -m option
            self._id = 0
            for identifier in range(1, 256):
                if identifier not in self._instances:
                    self._id = identifier
                    self._instances.append(self._id)
                    break

            if self._id == 0:
                raise VPCSError("Maximum number of VPCS instances reached")
        else:
            if vpcs_id in self._instances:
                raise VPCSError("VPCS identifier {} is already used by another VPCS device".format(vpcs_id))
            self._id = vpcs_id
            self._instances.append(self._id)

        self._name = name
        self._path = path
        self._console = console
        self._working_dir = None
        self._host = host
        self._command = []
        self._process = None
        self._vpcs_stdout_file = ""
        self._started = False
        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range

        # VPCS settings
        self._script_file = ""
        self._ethernet_adapter = EthernetAdapter()  # one adapter with 1 Ethernet interface

        working_dir_path = os.path.join(working_dir, "vpcs", "pc-{}".format(self._id))

        if vpcs_id and not os.path.isdir(working_dir_path):
            raise VPCSError("Working directory {} doesn't exist".format(working_dir_path))

        # create the device own working directory
        self.working_dir = working_dir_path

        if not self._console:
            # allocate a console port
            try:
                self._console = find_unused_port(self._console_start_port_range,
                                                 self._console_end_port_range,
                                                 self._host,
                                                 ignore_ports=self._allocated_console_ports)
            except Exception as e:
                raise VPCSError(e)

        if self._console in self._allocated_console_ports:
            raise VPCSError("Console port {} is already used by another VPCS device".format(console))
        self._allocated_console_ports.append(self._console)

        log.info("VPCS device {name} [id={id}] has been created".format(name=self._name,
                                                                        id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for VPCS.

        :returns: default values (dictionary)
        """

        vpcs_defaults = {"name": self._name,
                         "script_file": self._script_file,
                         "console": self._console}

        return vpcs_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this VPCS device.

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

    @property
    def name(self):
        """
        Returns the name of this VPCS device.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this VPCS device.

        :param new_name: name
        """

        if self._script_file:
            # update the startup.vpc
            config_path = os.path.join(self._working_dir, "startup.vpc")
            if os.path.isfile(config_path):
                try:
                    with open(config_path, "r+", errors="replace") as f:
                        old_config = f.read()
                        new_config = old_config.replace(self._name, new_name)
                        f.seek(0)
                        f.write(new_config)
                except OSError as e:
                    raise VPCSError("Could not amend the configuration {}: {}".format(config_path, e))

        log.info("VPCS {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                       id=self._id,
                                                                       new_name=new_name))
        self._name = new_name

    @property
    def path(self):
        """
        Returns the path to the VPCS executable.

        :returns: path to VPCS
        """

        return self._path

    @path.setter
    def path(self, path):
        """
        Sets the path to the VPCS executable.

        :param path: path to VPCS
        """

        self._path = path
        log.info("VPCS {name} [id={id}]: path changed to {path}".format(name=self._name,
                                                                        id=self._id,
                                                                        path=path))

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
        Sets the working directory for VPCS.

        :param working_dir: path to the working directory
        """

        try:
            os.makedirs(working_dir)
        except FileExistsError:
            pass
        except OSError as e:
            raise VPCSError("Could not create working directory {}: {}".format(working_dir, e))

        self._working_dir = working_dir
        log.info("VPCS {name} [id={id}]: working directory changed to {wd}".format(name=self._name,
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
            raise VPCSError("Console port {} is already used by another VPCS device".format(console))

        self._allocated_console_ports.remove(self._console)
        self._console = console
        self._allocated_console_ports.append(self._console)
        log.info("VPCS {name} [id={id}]: console port set to {port}".format(name=self._name,
                                                                            id=self._id,
                                                                            port=console))

    def command(self):
        """
        Returns the VPCS command line.

        :returns: VPCS command line (string)
        """

        return " ".join(self._build_command())

    def delete(self):
        """
        Deletes this VPCS device.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console and self.console in self._allocated_console_ports:
            self._allocated_console_ports.remove(self.console)

        log.info("VPCS device {name} [id={id}] has been deleted".format(name=self._name,
                                                                        id=self._id))

    def clean_delete(self):
        """
        Deletes this VPCS device & all files (configs, logs etc.)
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console:
            self._allocated_console_ports.remove(self.console)

        try:
            shutil.rmtree(self._working_dir)
        except OSError as e:
            log.error("could not delete VPCS device {name} [id={id}]: {error}".format(name=self._name,
                                                                                      id=self._id,
                                                                                      error=e))
            return

        log.info("VPCS device {name} [id={id}] has been deleted (including associated files)".format(name=self._name,
                                                                                                     id=self._id))

    @property
    def started(self):
        """
        Returns either this VPCS device has been started or not.

        :returns: boolean
        """

        return self._started

    def _check_vpcs_version(self):
        """
        Checks if the VPCS executable version is >= 0.5b1.
        """

        try:
            output = subprocess.check_output([self._path, "-v"], cwd=self._working_dir)
            match = re.search("Welcome to Virtual PC Simulator, version ([0-9a-z\.]+)", output.decode("utf-8"))
            if match:
                version = match.group(1)
                if parse_version(version) < parse_version("0.5b1"):
                    raise VPCSError("VPCS executable version must be >= 0.5b1")
            else:
                raise VPCSError("Could not determine the VPCS version for {}".format(self._path))
        except (OSError, subprocess.CalledProcessError) as e:
            raise VPCSError("Error while looking for the VPCS version: {}".format(e))

    def start(self):
        """
        Starts the VPCS process.
        """

        if not self.is_running():

            if not self._path:
                raise VPCSError("No path to a VPCS executable has been set")

            if not os.path.isfile(self._path):
                raise VPCSError("VPCS program '{}' is not accessible".format(self._path))

            if not os.access(self._path, os.X_OK):
                raise VPCSError("VPCS program '{}' is not executable".format(self._path))

            self._check_vpcs_version()

            if not self._ethernet_adapter.get_nio(0):
                raise VPCSError("This VPCS instance must be connected in order to start")

            self._command = self._build_command()
            try:
                log.info("starting VPCS: {}".format(self._command))
                self._vpcs_stdout_file = os.path.join(self._working_dir, "vpcs.log")
                log.info("logging to {}".format(self._vpcs_stdout_file))
                flags = 0
                if sys.platform.startswith("win32"):
                    flags = subprocess.CREATE_NEW_PROCESS_GROUP
                with open(self._vpcs_stdout_file, "w") as fd:
                    self._process = subprocess.Popen(self._command,
                                                     stdout=fd,
                                                     stderr=subprocess.STDOUT,
                                                     cwd=self._working_dir,
                                                     creationflags=flags)
                log.info("VPCS instance {} started PID={}".format(self._id, self._process.pid))
                self._started = True
            except OSError as e:
                vpcs_stdout = self.read_vpcs_stdout()
                log.error("could not start VPCS {}: {}\n{}".format(self._path, e, vpcs_stdout))
                raise VPCSError("could not start VPCS {}: {}\n{}".format(self._path, e, vpcs_stdout))

    def stop(self):
        """
        Stops the VPCS process.
        """

        # stop the VPCS process
        if self.is_running():
            log.info("stopping VPCS instance {} PID={}".format(self._id, self._process.pid))
            if sys.platform.startswith("win32"):
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()

            self._process.wait()

        self._process = None
        self._started = False

    def read_vpcs_stdout(self):
        """
        Reads the standard output of the VPCS process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._vpcs_stdout_file:
            try:
                with open(self._vpcs_stdout_file, errors="replace") as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._vpcs_stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the VPCS process is running

        :returns: True or False
        """

        if self._process and self._process.poll() is None:
            return True
        return False

    def port_add_nio_binding(self, port_id, nio):
        """
        Adds a port NIO binding.

        :param port_id: port ID
        :param nio: NIO instance to add to the slot/port
        """

        if not self._ethernet_adapter.port_exists(port_id):
            raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                       port_id=port_id))

        self._ethernet_adapter.add_nio(port_id, nio)
        log.info("VPCS {name} [id={id}]: {nio} added to port {port_id}".format(name=self._name,
                                                                               id=self._id,
                                                                               nio=nio,
                                                                               port_id=port_id))

    def port_remove_nio_binding(self, port_id):
        """
        Removes a port NIO binding.

        :param port_id: port ID

        :returns: NIO instance
        """

        if not self._ethernet_adapter.port_exists(port_id):
            raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                       port_id=port_id))

        nio = self._ethernet_adapter.get_nio(port_id)
        self._ethernet_adapter.remove_nio(port_id)
        log.info("VPCS {name} [id={id}]: {nio} removed from port {port_id}".format(name=self._name,
                                                                                   id=self._id,
                                                                                   nio=nio,
                                                                                   port_id=port_id))
        return nio

    def _build_command(self):
        """
        Command to start the VPCS process.
        (to be passed to subprocess.Popen())

        VPCS command line:
        usage: vpcs [options] [scriptfile]
        Option:
            -h         print this help then exit
            -v         print version information then exit

            -i num     number of vpc instances to start (default is 9)
            -p port    run as a daemon listening on the tcp 'port'
            -m num     start byte of ether address, default from 0
            -r file    load and execute script file
                       compatible with older versions, DEPRECATED.

            -e         tap mode, using /dev/tapx by default (linux only)
            -u         udp mode, default

        udp mode options:
            -s port    local udp base port, default from 20000
            -c port    remote udp base port (dynamips udp port), default from 30000
            -t ip      remote host IP, default 127.0.0.1

        tap mode options:
            -d device  device name, works only when -i is set to 1

        hypervisor mode option:
            -H port    run as the hypervisor listening on the tcp 'port'

          If no 'scriptfile' specified, vpcs will read and execute the file named
          'startup.vpc' if it exsits in the current directory.

        """

        command = [self._path]
        command.extend(["-p", str(self._console)])  # listen to console port

        nio = self._ethernet_adapter.get_nio(0)
        if nio:
            if isinstance(nio, NIO_UDP):
                # UDP tunnel
                command.extend(["-s", str(nio.lport)])  # source UDP port
                command.extend(["-c", str(nio.rport)])  # destination UDP port
                command.extend(["-t", nio.rhost])  # destination host

            elif isinstance(nio, NIO_TAP):
                # TAP interface
                command.extend(["-e"])
                command.extend(["-d", nio.tap_device])

        command.extend(["-m", str(self._id)])   # the unique ID is used to set the MAC address offset
        command.extend(["-i", "1"])  # option to start only one VPC instance
        command.extend(["-F"])  # option to avoid the daemonization of VPCS
        if self._script_file:
            command.extend([self._script_file])
        return command

    @property
    def script_file(self):
        """
        Returns the script-file for this VPCS instance.

        :returns: path to script-file
        """

        return self._script_file

    @script_file.setter
    def script_file(self, script_file):
        """
        Sets the script-file for this VPCS instance.

        :param script_file: path to base-script-file
        """

        self._script_file = script_file
        log.info("VPCS {name} [id={id}]: script_file set to {config}".format(name=self._name,
                                                                             id=self._id,
                                                                             config=self._script_file))
