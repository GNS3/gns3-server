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
VPCS device management (creates command line, processes, files etc.) in
order to run an VPCS instance.
"""

import os
import sys
import subprocess
import signal
import re
import asyncio
import socket
import shutil

from pkg_resources import parse_version
from .vpcs_error import VPCSError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIO_UDP
from ..nios.nio_tap import NIO_TAP
from ..attic import has_privileged_access

from ..base_vm import BaseVM

import logging
log = logging.getLogger(__name__)


class VPCSDevice(BaseVM):
    """
    VPCS device implementation.

    :param name: name of this VPCS device
    :param uuid: VPCS instance UUID
    :param manager: parent VM Manager
    :param working_dir: path to a working directory
    :param console: TCP console port
    """
    def __init__(self, name, uuid, manager, working_dir=None, console=None):

        super().__init__(name, uuid, manager)

        # TODO: Hardcodded for testing
        #self._working_dir = working_dir
        self._working_dir = "/tmp"

        self._path = self._config.get_section_config("VPCS").get("path", "vpcs")

        self._console = console

        self._command = []
        self._process = None
        self._vpcs_stdout_file = ""
        self._started = False

        # VPCS settings
        self._script_file = ""
        self._ethernet_adapter = EthernetAdapter()  # one adapter with 1 Ethernet interface

        # working_dir_path = os.path.join(working_dir, "vpcs", "pc-{}".format(self._id))
        #
        # if vpcs_id and not os.path.isdir(working_dir_path):
        #     raise VPCSError("Working directory {} doesn't exist".format(working_dir_path))
        #
        # # create the device own working directory
        # self.working_dir = working_dir_path
        #
        try:
            if not self._console:
                self._console = self._manager.port_manager.get_free_console_port()
            else:
                self._console = self._manager.port_manager.reserve_console_port(self._console)
        except Exception as e:
            raise VPCSError(e)

        self._check_requirements()

    def _check_requirements(self):
        """
        Check if VPCS is available with the correct version
        """

        if self._path == "vpcs":
            self._path = shutil.which("vpcs")

        if not self._path:
            raise VPCSError("No path to a VPCS executable has been set")

        if not os.path.isfile(self._path):
            raise VPCSError("VPCS program '{}' is not accessible".format(self._path))

        if not os.access(self._path, os.X_OK):
            raise VPCSError("VPCS program '{}' is not executable".format(self._path))

        self._check_vpcs_version()

    @property
    def console(self):
        """
        Returns the console port of this VPCS device.

        :returns: console port
        """

        return self._console

    #FIXME: correct way to subclass a property?
    @BaseVM.name.setter
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

        log.info("VPCS {name} [{uuid}]: renamed to {new_name}".format(name=self._name,
                                                                      uuid=self.uuid,
                                                                      new_name=new_name))
        BaseVM.name = new_name

    def _check_vpcs_version(self):
        """
        Checks if the VPCS executable version is >= 0.5b1.
        """
        #TODO: should be async
        try:
            output = subprocess.check_output([self._path, "-v"], cwd=self._working_dir)
            match = re.search("Welcome to Virtual PC Simulator, version ([0-9a-z\.]+)", output.decode("utf-8"))
            if match:
                version = match.group(1)
                if parse_version(version) < parse_version("0.5b1"):
                    raise VPCSError("VPCS executable version must be >= 0.5b1")
            else:
                raise VPCSError("Could not determine the VPCS version for {}".format(self._path))
        except (OSError, subprocess.SubprocessError) as e:
            raise VPCSError("Error while looking for the VPCS version: {}".format(e))

    @asyncio.coroutine
    def start(self):
        """
        Starts the VPCS process.
        """

        if not self.is_running():
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
                    self._process = yield from asyncio.create_subprocess_exec(*self._command,
                                                                              stdout=fd,
                                                                              stderr=subprocess.STDOUT,
                                                                              cwd=self._working_dir,
                                                                              creationflags=flags)
                log.info("VPCS instance {} started PID={}".format(self.name, self._process.pid))
                self._started = True
            except (OSError, subprocess.SubprocessError) as e:
                vpcs_stdout = self.read_vpcs_stdout()
                log.error("could not start VPCS {}: {}\n{}".format(self._path, e, vpcs_stdout))
                raise VPCSError("could not start VPCS {}: {}\n{}".format(self._path, e, vpcs_stdout))

    @asyncio.coroutine
    def stop(self):
        """
        Stops the VPCS process.
        """

        # stop the VPCS process
        if self.is_running():
            log.info("stopping VPCS instance {} PID={}".format(self.name, self._process.pid))
            if sys.platform.startswith("win32"):
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()

            yield from self._process.wait()

        self._process = None
        self._started = False

    def read_vpcs_stdout(self):
        """
        Reads the standard output of the VPCS process.
        Only use when the process has been stopped or has crashed.
        """
        #TODO: should be async
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

        if self._process:
            return True
        return False

    def port_add_nio_binding(self, port_id, nio_settings):
        """
        Adds a port NIO binding.

        :param port_id: port ID
        :param nio: NIO instance to add to the slot/port
        """

        if not self._ethernet_adapter.port_exists(port_id):
            raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                       port_id=port_id))

        nio = None
        if nio_settings["type"] == "nio_udp":
            lport = nio_settings["lport"]
            rhost = nio_settings["rhost"]
            rport = nio_settings["rport"]
            try:
                #TODO: handle IPv6
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect((rhost, rport))
            except OSError as e:
                raise VPCSError("Could not create an UDP connection to {}:{}: {}".format(rhost, rport, e))
            nio = NIO_UDP(lport, rhost, rport)
        elif nio_settings["type"] == "nio_tap":
            tap_device = nio_settings["tap_device"]
            if not has_privileged_access(self._path):
                raise VPCSError("{} has no privileged access to {}.".format(self._path, tap_device))
            nio = NIO_TAP(tap_device)
        if not nio:
            raise VPCSError("Requested NIO does not exist or is not supported: {}".format(nio_settings["type"]))


        self._ethernet_adapter.add_nio(port_id, nio)
        log.info("VPCS {name} {uuid}]: {nio} added to port {port_id}".format(name=self._name,
                                                                             uuid=self.uuid,
                                                                             nio=nio,
                                                                             port_id=port_id))
        return nio

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
        log.info("VPCS {name} [{uuid}]: {nio} removed from port {port_id}".format(name=self._name,
                                                                                  uuid=self.uuid,
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
            print(nio)
            print(isinstance(nio, NIO_UDP))
            if isinstance(nio, NIO_UDP):
                # UDP tunnel
                command.extend(["-s", str(nio.lport)])  # source UDP port
                command.extend(["-c", str(nio.rport)])  # destination UDP port
                command.extend(["-t", nio.rhost])  # destination host

            elif isinstance(nio, NIO_TAP):
                # TAP interface
                command.extend(["-e"])
                command.extend(["-d", nio.tap_device])

        #FIXME: find workaround
        #command.extend(["-m", str(self._id)])   # the unique ID is used to set the MAC address offset
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
        log.info("VPCS {name} [{uuid}]: script_file set to {config}".format(name=self._name,
                                                                            uuid=self.uuid,
                                                                            config=self._script_file))
