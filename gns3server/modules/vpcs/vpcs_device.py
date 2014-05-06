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
import re
import signal
import subprocess
import argparse
import threading
import configparser
from .vpcscon import start_vpcscon
from .vpcs_error import VPCSError
from .nios.nio_udp import NIO_UDP
from .nios.nio_tap import NIO_TAP

import logging
log = logging.getLogger(__name__)


class VPCSDevice(object):
    """
    VPCS device implementation.

    :param path: path to VPCS executable
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param name: name of this VPCS device
    """

    _instances = []

    def __init__(self, path, working_dir, host="127.0.0.1", name=None):

        # find an instance identifier (0 <= id < 255)
        # This 255 limit is due to a restriction on the number of possible
        # mac addresses given in VPCS using the -m option
        self._id = 0
        for identifier in range(0, 255):
            if identifier not in self._instances:
                self._id = identifier
                self._instances.append(self._id)
                break

        if self._id == 0:
            raise VPCSError("Maximum number of VPCS instances reached")

        if name:
            self._name = name
        else:
            self._name = "VPCS{}".format(self._id)
        self._path = path
        self._console = None
        self._working_dir = None
        self._command = []
        self._process = None
        self._vpcs_stdout_file = ""
        self._vpcscon_thead = None
        self._vpcscon_thread_stop_event = None
        self._host = host
        self._started = False

        # VPCS settings
        self._script_file = ""
        
        # update the working directory
        self.working_dir = working_dir

        log.info("VPCS device {name} [id={id}] has been created".format(name=self._name,
                                                                       id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for VPCS.

        :returns: default values (dictionary)
        """

        vpcs_defaults = {"name": self._name,
                        "path": self._path,
                        "script_file": self._script_file,
                        "console": self._console}

        return vpcs_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this VPCS device.

        :returns: id (integer)
        """

        return(self._id)

    @classmethod
    def reset(cls):
        """
        Resets allocated instance list.
        """

        cls._instances.clear()

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

        self._name = new_name
        log.info("VPCS {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                      id=self._id,
                                                                      new_name=new_name))

    @property
    def path(self):
        """
        Returns the path to the VPCS executable.

        :returns: path to VPCS
        """

        return(self._path)

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

        # create our own working directory
        working_dir = os.path.join(working_dir, "vpcs", "device-{}".format(self._id))
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

        self._console = console
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
        self._instances.remove(self._id)
        log.info("VPCS device {name} [id={id}] has been deleted".format(name=self._name,
                                                                       id=self._id))

    @property
    def started(self):
        """
        Returns either this VPCS device has been started or not.

        :returns: boolean
        """

        return self._started

    def _start_vpcscon(self):
        """
        Starts vpcscon thread (for console connections).
        """

        if not self._vpcscon_thead:
            telnet_server = "{}:{}".format(self._host, self._console)
            log.info("starting vpcscon for VPCS instance {} to accept Telnet connections on {}".format(self._name, telnet_server))
            args = argparse.Namespace(appl_id=str(self._id), debug=False, escape='^^', telnet_limit=0, telnet_server=telnet_server)
            self._vpcscon_thread_stop_event = threading.Event()
            self._vpcscon_thead = threading.Thread(target=start_vpcscon, args=(args, self._vpcscon_thread_stop_event))
            self._vpcscon_thead.start()                                                                                                     ", ".join(missing_libs)))

    def start(self):
        """
        Starts the VPCS process.
        """

        if not self.is_running():

            if not os.path.isfile(self._path):
                raise VPCSError("VPCS image '{}' is not accessible".format(self._path))

            if not os.access(self._path, os.X_OK):
                raise VPCSError("VPCS image '{}' is not executable".format(self._path))

            self._command = self._build_command()
            try:
                log.info("starting VPCS: {}".format(self._command))
                self._vpcs_stdout_file = os.path.join(self._working_dir, "vpcs.log")
                log.info("logging to {}".format(self._vpcs_stdout_file))
                with open(self._vpcs_stdout_file, "w") as fd:
                    self._process = subprocess.Popen(self._command,
                                                     stdout=fd,
                                                     stderr=subprocess.STDOUT,
                                                     cwd=self._working_dir)
                log.info("VPCS instance {} started PID={}".format(self._id, self._process.pid))
                self._started = True
            except FileNotFoundError as e:
                raise VPCSError("could not start VPCS: {}: 32-bit binary support is probably not installed".format(e))
            except OSError as e:
                vpcs_stdout = self.read_vpcs_stdout()
                log.error("could not start VPCS {}: {}\n{}".format(self._path, e, vpcs_stdout))
                raise VPCSError("could not start VPCS {}: {}\n{}".format(self._path, e, vpcs_stdout))

            # start console support
            self._start_vpcscon()

    def stop(self):
        """
        Stops the VPCS process.
        """

        # stop the VPCS process
        if self.is_running():
            log.info("stopping VPCS instance {} PID={}".format(self._id, self._process.pid))
            try:
                self._process.terminate()
                self._process.wait(1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.poll() == None:
                    log.warn("VPCS instance {} PID={} is still running".format(self._id,
                                                                              self._process.pid))
        self._process = None
        self._started = False

        # stop console support
        if self._vpcscon_thead:
            self._vpcscon_thread_stop_event.set()
            if self._vpcscon_thead.is_alive():
                self._vpcscon_thead.join(timeout=0.10)
            self._vpcscon_thead = None


    def read_vpcs_stdout(self):
        """
        Reads the standard output of the VPCS process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._vpcs_stdout_file:
            try:
                with open(self._vpcs_stdout_file) as file:
                    output = file.read()
            except OSError as e:
                log.warn("could not read {}: {}".format(self._vpcs_stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the VPCS process is running

        :returns: True or False
        """

        if self._process and self._process.poll() == None:
            return True
        return False


    def slot_add_nio_binding(self, slot_id, port_id, nio):
        """
        Adds a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._slots[slot_id]
        except IndexError:
            raise VPCSError("Slot {slot_id} doesn't exist on VPCS {name}".format(name=self._name,
                                                                               slot_id=slot_id))

        if not adapter.port_exists(port_id):
            raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=adapter,
                                                                                      port_id=port_id))

        adapter.add_nio(port_id, nio)
        log.info("VPCS {name} [id={id}]: {nio} added to {slot_id}/{port_id}".format(name=self._name,
                                                                                   id=self._id,
                                                                                   nio=nio,
                                                                                   slot_id=slot_id,
                                                                                   port_id=port_id))

    def slot_remove_nio_binding(self, slot_id, port_id):
        """
        Removes a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        """

        try:
            adapter = self._slots[slot_id]
        except IndexError:
            raise VPCSError("Slot {slot_id} doesn't exist on VPCS {name}".format(name=self._name,
                                                                               slot_id=slot_id))

        if not adapter.port_exists(port_id):
            raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=adapter,
                                                                                      port_id=port_id))

        nio = adapter.get_nio(port_id)
        adapter.remove_nio(port_id)
        log.info("VPCS {name} [id={id}]: {nio} removed from {slot_id}/{port_id}".format(name=self._name,
                                                                                       id=self._id,
                                                                                       nio=nio,
                                                                                       slot_id=slot_id,
                                                                                       port_id=port_id))

    def _build_command(self):
        """
        Command to start the VPCS process.
        (to be passed to subprocess.Popen())

        VPCS command line:
        usage: vpcs [options] [scriptfile]
        Option:
            -h         print this help then exit
            -v         print version information then exit

            -p port    run as a daemon listening on the tcp 'port'
            -m num     start byte of ether address, default from 0
            -r file    load and execute script file
                       compatible with older versions, DEPRECATED.

            -e         tap mode, using /dev/tapx (linux only)
            -u         udp mode, default

        udp mode options:
            -s port    local udp base port, default from 20000
            -c port    remote udp base port (dynamips udp port), default from 30000
            -t ip      remote host IP, default 127.0.0.1

        hypervisor mode option:
            -H port    run as the hypervisor listening on the tcp 'port'

          If no 'scriptfile' specified, vpcs will read and execute the file named
          'startup.vpc' if it exsits in the current directory.

        """

        command = [self._path]
        command.extend(["-p", str(self._console)])
        command.extend(["-s", str(self._lport)])
        command.extend(["-c", str(self._rport)])
        command.extend(["-t", str(self._rhost)])
        command.extend(["-m", str(self._id)]) #The unique ID is used to set the mac address offset
        if self._script_file:
            command.extend([self._script_file])
        return command

    @property
    def script_file(self):
        """
        Returns the startup-config for this VPCS instance.

        :returns: path to startup-config file
        """

        return self._script_file

    @script_file.setter
    def script_file(self, script_file):
        """
        Sets the startup-config for this VPCS instance.

        :param script_file: path to startup-config file
        """

        self._script_file = script_file
        log.info("VPCS {name} [id={id}]: script_file set to {config}".format(name=self._name,
                                                                                 id=self._id,
                                                                                 config=self._script_file))


