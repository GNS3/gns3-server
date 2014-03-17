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
IOU device management (creates command line, processes, files etc.) in
order to run an IOU instance.
"""

import os
import socket
import errno
import signal
import subprocess
import argparse
import threading
import configparser
from .ioucon import start_ioucon
from .iou_error import IOUError
from .adapters.ethernet_adapter import EthernetAdapter
from .adapters.serial_adapter import SerialAdapter
from .nios.nio_udp import NIO_UDP
from .nios.nio_tap import NIO_TAP
from .nios.nio_generic_ethernet import NIO_GenericEthernet

import logging
log = logging.getLogger(__name__)


class IOUDevice(object):
    """
    IOU device implementation.

    :param path: path to IOU executable
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param name: name of this IOU device
    """

    _instances = []

    def __init__(self, path, working_dir, host="127.0.0.1", name=None):

        # find an instance identifier (0 < id <= 512)
        self._id = 0
        for identifier in range(1, 513):
            if identifier not in self._instances:
                self._id = identifier
                self._instances.append(self._id)
                break

        if self._id == 0:
            raise IOUError("Maximum number of IOU instances reached")

        if name:
            self._name = name
        else:
            self._name = "IOU{}".format(self._id)
        self._path = path
        self._iourc = ""
        self._iouyap = ""
        self._console = None
        self._working_dir = None
        self._command = []
        self._process = None
        self._iouyap_process = None
        self._stdout_file = ""
        self._ioucon_thead = None
        self._ioucon_thread_stop_event = None
        self._host = host
        self._started = False

        # IOU settings
        self._ethernet_adapters = [EthernetAdapter(), EthernetAdapter()]  # one adapter = 4 interfaces
        self._serial_adapters = [SerialAdapter(), SerialAdapter()]  # one adapter = 4 interfaces
        self._slots = self._ethernet_adapters + self._serial_adapters
        self._nvram = 128  # Kilobytes
        self._startup_config = ""
        self._ram = 256  # Megabytes

        # update the working directory
        self.working_dir = working_dir

        log.info("IOU device {name} [id={id}] has been created".format(name=self._name,
                                                                       id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for IOU.

        :returns: default values (dictionary)
        """

        iou_defaults = {"name": self._name,
                        "path": self._path,
                        "startup_config": self._startup_config,
                        "ram": self._ram,
                        "nvram": self._nvram,
                        "ethernet_adapters": len(self._ethernet_adapters),
                        "serial_adapters": len(self._serial_adapters),
                        "console": self._console}

        return iou_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this IOU device.

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
        Returns the name of this IOU device.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this IOU device.

        :param new_name: name
        """

        self._name = new_name
        log.info("IOU {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                      id=self._id,
                                                                      new_name=new_name))

    @property
    def path(self):
        """
        Returns the path to the IOU executable.

        :returns: path to IOU
        """

        return(self._path)

    @path.setter
    def path(self, path):
        """
        Sets the path to the IOU executable.

        :param path: path to IOU
        """

        self._path = path
        log.info("IOU {name} [id={id}]: path changed to {path}".format(name=self._name,
                                                                      id=self._id,
                                                                      path=path))

    @property
    def iourc(self):
        """
        Returns the path to the iourc file.

        :returns: path to the iourc file
        """

        return(self._iourc)

    @iourc.setter
    def iourc(self, iourc):
        """
        Sets the path to the iourc file.

        :param path: path to the iourc file.
        """

        self._iourc = iourc
        log.info("IOU {name} [id={id}]: iourc file path set to {path}".format(name=self._name,
                                                                              id=self._id,
                                                                              path=self._iourc))

    @property
    def iouyap(self):
        """
        Returns the path to iouyap

        :returns: path to iouyap
        """

        return(self._iouyap)

    @iouyap.setter
    def iouyap(self, iouyap):
        """
        Sets the path to iouyap.

        :param path: path to iouyap
        """

        self._iouyap = iouyap
        log.info("IOU {name} [id={id}]: iouyap path set to {path}".format(name=self._name,
                                                                          id=self._id,
                                                                          path=self._iouyap))

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
        Sets the working directory for IOU.

        :param working_dir: path to the working directory
        """

        # create our own working directory
        working_dir = os.path.join(working_dir, "device-{}".format(self._id))
        if not os.path.exists(working_dir):
            try:
                os.makedirs(working_dir)
            except EnvironmentError as e:
                raise IOUError("Could not create working directory {}: {}".format(working_dir, e))

        self._working_dir = working_dir
        log.info("IOU {name} [id={id}]: working directory changed to {wd}".format(name=self._name,
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
        log.info("IOU {name} [id={id}]: console port set to {port}".format(name=self._name,
                                                                         id=self._id,
                                                                         port=console))

    def command(self):
        """
        Returns the IOU command line.

        :returns: IOU command line (string)
        """

        return " ".join(self._build_command())

    def delete(self):
        """
        Deletes this IOU device.
        """

        self.stop()
        self._instances.remove(self._id)
        log.info("IOU device {name} [id={id}] has been deleted".format(name=self._name,
                                                                       id=self._id))

    @property
    def started(self):
        """
        Returns either this IOU device has been started or not.

        :returns: boolean
        """

        return self._started

    def _update_iouyap_config(self):
        """
        Updates the iouyap.ini file.
        """

        iouyap_ini = os.path.join(self._working_dir, "iouyap.ini")

        config = configparser.ConfigParser()
        config["default"] = {"netmap": "NETMAP",
                             "base_port": "49000"}

        bay_id = 0
        for adapter in self._slots:
            unit_id = 0
            for unit in adapter.ports.keys():
                nio = adapter.get_nio(unit)
                if nio:
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

                    config["{iouyap_id}:{bay}/{unit}".format(iouyap_id=str(self._id + 512), bay=bay_id, unit=unit_id)] = connection
                unit_id += 1
            bay_id += 1

        try:
            with open(iouyap_ini, "w") as config_file:
                config.write(config_file)
            log.info("IOU {name} [id={id}]: iouyap.ini updated".format(name=self._name,
                                                                       id=self._id))
        except EnvironmentError as e:
            raise IOUError("Could not create {}: {}".format(iouyap_ini, e))

    def _create_netmap_config(self):
        """
        Creates the NETMAP file.
        """

        netmap_path = os.path.join(self._working_dir, "NETMAP")
        try:
            with open(netmap_path, "w") as f:
                for bay in range(0, 16):
                    for unit in range(0, 4):
                        f.write("{iouyap_id}:{bay}/{unit}{iou_id:>5d}:{bay}/{unit}\n".format(iouyap_id=str(self._id + 512),
                                                                                             bay=bay,
                                                                                             unit=unit,
                                                                                             iou_id=self._id))
            log.info("IOU {name} [id={id}]: NETMAP file created".format(name=self._name,
                                                                        id=self._id))
        except EnvironmentError as e:
            raise IOUError("Could not create {}: {}".format(netmap_path, e))

    def _start_ioucon(self):
        """
        Starts ioucon thread (for console connections).
        """

        if not self._ioucon_thead:
            telnet_server = "{}:{}".format(self._host, self._console)
            log.info("starting ioucon for IOU instance {} to accept Telnet connections on {}".format(self._name, telnet_server))
            args = argparse.Namespace(appl_id=str(self._id), debug=False, escape='^^', telnet_limit=0, telnet_server=telnet_server)
            self._ioucon_thread_stop_event = threading.Event()
            self._ioucon_thead = threading.Thread(target=start_ioucon, args=(args, self._ioucon_thread_stop_event))
            self._ioucon_thead.start()

    def _start_iouyap(self):
        """
        Starts iouyap (handles connections to and from this IOU device).
        """

        try:
            self._update_iouyap_config()
            command = [self._iouyap, str(self._id + 512)]  # iouyap has always IOU ID + 512
            log.info("starting iouyap: {}".format(command))
            self._stdout_file = os.path.join(self._working_dir, "iouyap.log")
            log.info("logging to {}".format(self._stdout_file))
            with open(self._stdout_file, "w") as fd:
                self._iouyap_process = subprocess.Popen(command,
                                                        stdout=fd,
                                                        stderr=subprocess.STDOUT,
                                                        cwd=self._working_dir)

            log.info("iouyap started PID={}".format(self._iouyap_process.pid))
        except EnvironmentError as e:
            log.error("could not start iouyap: {}".format(e))
            raise IOUError("Could not start iouyap: {}".format(e))

    def start(self):
        """
        Starts the IOU process.
        """

        if not self.is_running():
            if not self._iourc or not os.path.exists(self._iourc):
                raise IOUError("A iourc file is necessary to start IOU")

            if not self._iouyap or not os.path.exists(self._iouyap):
                raise IOUError("iouyap is necessary to start IOU")

            self._create_netmap_config()
            # created a environment variable pointing to the iourc file.
            env = os.environ.copy()
            env["IOURC"] = self._iourc
            self._command = self._build_command()
            try:
                log.info("starting IOU: {}".format(self._command))
                self._stdout_file = os.path.join(self._working_dir, "iou.log")
                log.info("logging to {}".format(self._stdout_file))
                with open(self._stdout_file, "w") as fd:
                    self._process = subprocess.Popen(self._command,
                                                     stdout=fd,
                                                     stderr=subprocess.STDOUT,
                                                     cwd=self._working_dir,
                                                     env=env)
                log.info("IOU instance {} started PID={}".format(self._id, self._process.pid))
                self._started = True
            except EnvironmentError as e:
                log.error("could not start IOU: {}".format(e))
                raise IOUError("could not start IOU: {}".format(e))

            # start console support
            self._start_ioucon()
            # connections support
            self._start_iouyap()

    def stop(self):
        """
        Stops the IOU process.
        """

        # stop the IOU process
        if self.is_running():
            log.info("stopping IOU instance {} PID={}".format(self._id, self._process.pid))
            try:
                self._process.terminate()
                self._process.wait(1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.poll() == None:
                    log.warn("IOU instance {} PID={} is still running".format(self._id,
                                                                              self._process.pid))
        self._process = None
        self._started = False

        # stop console support
        if self._ioucon_thead:
            self._ioucon_thread_stop_event.set()
            if self._ioucon_thead.is_alive():
                self._ioucon_thead.join(timeout=0.10)
            self._ioucon_thead = None

        # stop iouyap
        if self.is_iouyap_running():
            log.info("stopping iouyap PID={} for IOU instance {}".format(self._iouyap_process.pid, self._id))
            try:
                self._iouyap_process.terminate()
                self._iouyap_process.wait(1)
            except subprocess.TimeoutExpired:
                self._iouyap_process.kill()
                if self._iouyap_process.poll() == None:
                    log.warn("iouyap PID={} for IOU instance {} is still running".format(self._iouyap_process.pid,
                                                                                         self._id))
        self._iouyap_process = None

    def read_stdout(self):
        """
        Reads the standard output of the IOU process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stdout_file:
            try:
                with open(self._stdout_file) as file:
                    output = file.read()
            except EnvironmentError as e:
                log.warn("could not read {}: {}".format(self._stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the IOU process is running

        :returns: True or False
        """

        if self._process and self._process.poll() == None:
            return True
        return False

    def is_iouyap_running(self):
        """
        Checks if the iouyap process is running

        :returns: True or False
        """

        if self._iouyap_process and self._iouyap_process.poll() == None:
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
            raise IOUError("Slot {slot_id} doesn't exist on IOU {name}".format(name=self._name,
                                                                               slot_id=slot_id))

        if not adapter.port_exists(port_id):
            raise IOUError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=adapter,
                                                                                      port_id=port_id))

        adapter.add_nio(port_id, nio)
        log.info("IOU {name} [id={id}]: {nio} added to {slot_id}/{port_id}".format(name=self._name,
                                                                                   id=self._id,
                                                                                   nio=nio,
                                                                                   slot_id=slot_id,
                                                                                   port_id=port_id))
        if self.is_iouyap_running():
            self._update_iouyap_config()
            os.kill(self._iouyap_process.pid, signal.SIGHUP)

    def slot_remove_nio_binding(self, slot_id, port_id):
        """
        Removes a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        """

        try:
            adapter = self._slots[slot_id]
        except IndexError:
            raise IOUError("Slot {slot_id} doesn't exist on IOU {name}".format(name=self._name,
                                                                               slot_id=slot_id))

        if not adapter.port_exists(port_id):
            raise IOUError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=adapter,
                                                                                      port_id=port_id))

        nio = adapter.get_nio(port_id)
        adapter.remove_nio(port_id)
        log.info("IOU {name} [id={id}]: {nio} removed from {slot_id}/{port_id}".format(name=self._name,
                                                                                       id=self._id,
                                                                                       nio=nio,
                                                                                       slot_id=slot_id,
                                                                                       port_id=port_id))
        if self.is_iouyap_running():
            self._update_iouyap_config()
            os.kill(self._iouyap_process.pid, signal.SIGHUP)

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

        #TODO: add support for keepalive and watchdog
        command = [self._path]
        if len(self._ethernet_adapters) != 2:
            command.extend(["-e", str(len(self._ethernet_adapters))])
        if len(self._serial_adapters) != 2:
            command.extend(["-s", str(len(self._serial_adapters))])
        command.extend(["-n", str(self._nvram)])
        command.extend(["-m", str(self._ram)])
        command.extend(["-L"])  # disable local console, use remote console
        if self._startup_config:
            command.extend(["-c", self._startup_config])
        command.extend([str(self._id)])
        return command

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
    def startup_config(self):
        """
        Returns the startup-config for this IOU instance.

        :returns: path to startup-config file
        """

        return self._startup_config

    @startup_config.setter
    def startup_config(self, startup_config):
        """
        Sets the startup-config for this IOU instance.

        :param startup_config: path to startup-config file
        """

        self._startup_config = startup_config
        log.info("IOU {name} [id={id}]: startup_config set to {config}".format(name=self._name,
                                                                                 id=self._id,
                                                                                 config=self._startup_config))

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

    @staticmethod
    def find_unused_port(start_port, end_port, host='127.0.0.1', socket_type="TCP"):
        """
        Finds an unused port in the specified range.

        :param start_port: first port in the range
        :param end_port: last port in the range
        :param host: host/address for bind()
        :param socket_type: TCP (default) or UDP
        """

        if socket_type == "UDP":
            socket_type = socket.SOCK_DGRAM
        else:
            socket_type = socket.SOCK_STREAM

        for port in range(start_port, end_port):
            if port > end_port:
                raise IOUError("Could not find a free port between {0} and {1}".format(start_port, end_port))
            try:
                if ":" in host:
                    # IPv6 address support
                    with socket.socket(socket.AF_INET6, socket_type) as s:
                        s.bind((host, port))   # the port is available if bind is a success
                else:
                    with socket.socket(socket.AF_INET, socket_type) as s:
                        s.bind((host, port))   # the port is available if bind is a success
                return port
            except socket.error as e:
                if e.errno == errno.EADDRINUSE:  # socket already in use
                    continue
                else:
                    raise IOUError("Could not find an unused port: {}".format(e))
