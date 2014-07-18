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
import re
import signal
import subprocess
import argparse
import threading
import configparser
import shutil

from .ioucon import start_ioucon
from .iou_error import IOUError
from .adapters.ethernet_adapter import EthernetAdapter
from .adapters.serial_adapter import SerialAdapter
from .nios.nio_udp import NIO_UDP
from .nios.nio_tap import NIO_TAP
from .nios.nio_generic_ethernet import NIO_GenericEthernet
from ..attic import find_unused_port

import logging
log = logging.getLogger(__name__)


class IOUDevice(object):
    """
    IOU device implementation.

    :param name: name of this IOU device
    :param path: path to IOU executable
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param iou_id: IOU instance ID
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
                 iou_id = None,
                 console=None,
                 console_start_port_range=4001,
                 console_end_port_range=4512):

        if not iou_id:
            # find an instance identifier if none is provided (0 < id <= 512)
            self._id = 0
            for identifier in range(1, 513):
                if identifier not in self._instances:
                    self._id = identifier
                    self._instances.append(self._id)
                    break

            if self._id == 0:
                raise IOUError("Maximum number of IOU instances reached")
        else:
            if iou_id in self._instances:
                raise IOUError("IOU identifier {} is already used by another IOU device".format(iou_id))
            self._id = iou_id
            self._instances.append(self._id)

        self._name = name
        self._path = path
        self._iourc = ""
        self._iouyap = ""
        self._console = console
        self._working_dir = None
        self._command = []
        self._process = None
        self._iouyap_process = None
        self._iou_stdout_file = ""
        self._iouyap_stdout_file = ""
        self._ioucon_thead = None
        self._ioucon_thread_stop_event = None
        self._host = host
        self._started = False
        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range

        # IOU settings
        self._ethernet_adapters = [EthernetAdapter(), EthernetAdapter()]  # one adapter = 4 interfaces
        self._serial_adapters = [SerialAdapter(), SerialAdapter()]  # one adapter = 4 interfaces
        self._slots = self._ethernet_adapters + self._serial_adapters
        self._use_default_iou_values = True  # for RAM & NVRAM values
        self._nvram = 128  # Kilobytes
        self._initial_config = ""
        self._ram = 256  # Megabytes
        self._l1_keepalives = False  # used to overcome the always-up Ethernet interfaces (not supported by all IOSes).

        working_dir_path = os.path.join(working_dir, "iou", "device-{}".format(self._id))

        if iou_id and not os.path.isdir(working_dir_path):
            raise IOUError("Working directory {} doesn't exist".format(working_dir_path))

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
                raise IOUError(e)

        if self._console in self._allocated_console_ports:
            raise IOUError("Console port {} is already in used another IOU device".format(console))
        self._allocated_console_ports.append(self._console)

        log.info("IOU device {name} [id={id}] has been created".format(name=self._name,
                                                                       id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for IOU.

        :returns: default values (dictionary)
        """

        iou_defaults = {"name": self._name,
                        "path": self._path,
                        "intial_config": self._initial_config,
                        "use_default_iou_values": self._use_default_iou_values,
                        "ram": self._ram,
                        "nvram": self._nvram,
                        "ethernet_adapters": len(self._ethernet_adapters),
                        "serial_adapters": len(self._serial_adapters),
                        "console": self._console,
                        "l1_keepalives": self._l1_keepalives}

        return iou_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this IOU device.

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

        if self._initial_config:
            # update the initial-config
            config_path = os.path.join(self._working_dir, "initial-config.cfg")
            if os.path.isfile(config_path):
                try:
                    with open(config_path, "r+", errors="replace") as f:
                        old_config = f.read()
                        new_config = old_config.replace(self._name, new_name)
                        f.seek(0)
                        f.write(new_config)
                except OSError as e:
                    raise IOUError("Could not amend the configuration {}: {}".format(config_path, e))

        log.info("IOU {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                      id=self._id,
                                                                      new_name=new_name))
        self._name = new_name

    @property
    def path(self):
        """
        Returns the path to the IOU executable.

        :returns: path to IOU
        """

        return self._path

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

        return self._iourc

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

    @property
    def iouyap(self):
        """
        Returns the path to iouyap

        :returns: path to iouyap
        """

        return self._iouyap

    @iouyap.setter
    def iouyap(self, iouyap):
        """
        Sets the path to iouyap.

        :param iouyap: path to iouyap
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

        try:
            os.makedirs(working_dir)
        except FileExistsError:
            pass
        except OSError as e:
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

        if console in self._allocated_console_ports:
            raise IOUError("Console port {} is already used by another IOU device".format(console))

        self._allocated_console_ports.remove(self._console)
        self._console = console
        self._allocated_console_ports.append(self._console)
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
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console and self.console in self._allocated_console_ports:
            self._allocated_console_ports.remove(self.console)

        log.info("IOU device {name} [id={id}] has been deleted".format(name=self._name,
                                                                       id=self._id))

    def clean_delete(self):
        """
        Deletes this IOU device & all files (nvram, initial-config etc.)
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console:
            self._allocated_console_ports.remove(self.console)

        try:
            shutil.rmtree(self._working_dir)
        except OSError as e:
            log.error("could not delete IOU device {name} [id={id}]: {error}".format(name=self._name,
                                                                                     id=self._id,
                                                                                     error=e))
            return

        log.info("IOU device {name} [id={id}] has been deleted (including associated files)".format(name=self._name,
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
                    connection = None
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

                    if connection:
                        interface = "{iouyap_id}:{bay}/{unit}".format(iouyap_id=str(self._id + 512), bay=bay_id, unit=unit_id)
                        config[interface] = connection

                        if nio.capturing:
                            pcap_data_link_type = nio.pcap_data_link_type.upper()
                            if pcap_data_link_type == "DLT_PPP_SERIAL":
                                pcap_protocol = "ppp"
                            elif pcap_data_link_type == "DLT_C_HDLC":
                                pcap_protocol = "hdlc"
                            elif pcap_data_link_type == "DLT_FRELAY":
                                pcap_protocol = "fr"
                            else:
                                pcap_protocol = "ethernet"
                            capture_info = {"pcap_file": "{pcap_file}".format(pcap_file=nio.pcap_output_file),
                                            "pcap_protocol": pcap_protocol,
                                            "pcap_overwrite": "y"}
                            config[interface].update(capture_info)

                unit_id += 1
            bay_id += 1

        try:
            with open(iouyap_ini, "w") as config_file:
                config.write(config_file)
            log.info("IOU {name} [id={id}]: iouyap.ini updated".format(name=self._name,
                                                                       id=self._id))
        except OSError as e:
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
        except OSError as e:
            raise IOUError("Could not create {}: {}".format(netmap_path, e))

    def _start_ioucon(self):
        """
        Starts ioucon thread (for console connections).
        """

        if not self._ioucon_thead:
            telnet_server = "{}:{}".format(self._host, self.console)
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
            command = [self._iouyap, "-q", str(self._id + 512)]  # iouyap has always IOU ID + 512
            log.info("starting iouyap: {}".format(command))
            self._iouyap_stdout_file = os.path.join(self._working_dir, "iouyap.log")
            log.info("logging to {}".format(self._iouyap_stdout_file))
            with open(self._iouyap_stdout_file, "w") as fd:
                self._iouyap_process = subprocess.Popen(command,
                                                        stdout=fd,
                                                        stderr=subprocess.STDOUT,
                                                        cwd=self._working_dir)

            log.info("iouyap started PID={}".format(self._iouyap_process.pid))
        except OSError as e:
            iouyap_stdout = self.read_iouyap_stdout()
            log.error("could not start iouyap: {}\n{}".format(e, iouyap_stdout))
            raise IOUError("Could not start iouyap: {}\n{}".format(e, iouyap_stdout))

    def _library_check(self):
        """
        Checks for missing shared library dependencies in the IOU image.
        """

        try:
            output = subprocess.check_output(["ldd", self._path])
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            log.warn("could not determine the shared library dependencies for {}: {}".format(self._path, e))
            return

        p = re.compile("([\.\w]+)\s=>\s+not found")
        missing_libs = p.findall(output.decode("utf-8"))
        if missing_libs:
            raise IOUError("The following shared library dependencies cannot be found for IOU image {}: {}".format(self._path,
                                                                                                                   ", ".join(missing_libs)))

    def start(self):
        """
        Starts the IOU process.
        """

        if not self.is_running():

            if not os.path.isfile(self._path) or not os.path.exists(self._path):
                raise IOUError("IOU image '{}' is not accessible".format(self._path))

            try:
                with open(self._path, "rb") as f:
                    # read the first 7 bytes of the file.
                    elf_header_start = f.read(7)
            except OSError as e:
                raise IOUError("Cannot read ELF header for IOU image '{}': {}".format(self._path, e))

            # IOU images must start with the ELF magic number, be 32-bit, little endian
            # and have an ELF version of 1 normal IOS image are big endian!
            if elf_header_start != b'\x7fELF\x01\x01\x01':
                raise IOUError("'{}' is not a valid IOU image".format(self._path))

            if not os.access(self._path, os.X_OK):
                raise IOUError("IOU image '{}' is not executable".format(self._path))

            self._library_check()

            if not self._iourc or not os.path.isfile(self._iourc):
                raise IOUError("A iourc file is necessary to start IOU")

            if not self._iouyap or not os.path.isfile(self._iouyap):
                raise IOUError("iouyap is necessary to start IOU")

            self._create_netmap_config()
            # created a environment variable pointing to the iourc file.
            env = os.environ.copy()
            env["IOURC"] = self._iourc
            self._command = self._build_command()
            try:
                log.info("starting IOU: {}".format(self._command))
                self._iou_stdout_file = os.path.join(self._working_dir, "iou.log")
                log.info("logging to {}".format(self._iou_stdout_file))
                with open(self._iou_stdout_file, "w") as fd:
                    self._process = subprocess.Popen(self._command,
                                                     stdout=fd,
                                                     stderr=subprocess.STDOUT,
                                                     cwd=self._working_dir,
                                                     env=env)
                log.info("IOU instance {} started PID={}".format(self._id, self._process.pid))
                self._started = True
            except FileNotFoundError as e:
                raise IOUError("could not start IOU: {}: 32-bit binary support is probably not installed".format(e))
            except OSError as e:
                iou_stdout = self.read_iou_stdout()
                log.error("could not start IOU {}: {}\n{}".format(self._path, e, iou_stdout))
                raise IOUError("could not start IOU {}: {}\n{}".format(self._path, e, iou_stdout))

            # start console support
            self._start_ioucon()
            # connections support
            self._start_iouyap()

    def stop(self):
        """
        Stops the IOU process.
        """

        # stop console support
        if self._ioucon_thead:
            self._ioucon_thread_stop_event.set()
            if self._ioucon_thead.is_alive():
                self._ioucon_thead.join(timeout=3.0)  # wait for the thread to free the console port
            self._ioucon_thead = None

        # stop iouyap
        if self.is_iouyap_running():
            log.info("stopping iouyap PID={} for IOU instance {}".format(self._iouyap_process.pid, self._id))
            try:
                self._iouyap_process.terminate()
                self._iouyap_process.wait(1)
            except subprocess.TimeoutExpired:
                self._iouyap_process.kill()
                if self._iouyap_process.poll() is None:
                    log.warn("iouyap PID={} for IOU instance {} is still running".format(self._iouyap_process.pid,
                                                                                         self._id))
        self._iouyap_process = None

        # stop the IOU process
        if self.is_running():
            log.info("stopping IOU instance {} PID={}".format(self._id, self._process.pid))
            try:
                self._process.terminate()
                self._process.wait(1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                if self._process.poll() is None:
                    log.warn("IOU instance {} PID={} is still running".format(self._id,
                                                                              self._process.pid))
        self._process = None
        self._started = False

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

    def is_running(self):
        """
        Checks if the IOU process is running

        :returns: True or False
        """

        if self._process and self._process.poll() is None:
            return True
        return False

    def is_iouyap_running(self):
        """
        Checks if the iouyap process is running

        :returns: True or False
        """

        if self._iouyap_process and self._iouyap_process.poll() is None:
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

        :returns: NIO instance
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

        return nio

    def _enable_l1_keepalives(self, command):
        """
        Enables L1 keepalive messages if supported.

        :param command: command line
        """

        env = os.environ.copy()
        env["IOURC"] = self._iourc
        try:
            output = subprocess.check_output([self._path, "-h"], stderr=subprocess.STDOUT, cwd=self._working_dir, env=env)
            if re.search("-l\s+Enable Layer 1 keepalive messages", output.decode("utf-8")):
                command.extend(["-l"])
            else:
                raise IOUError("layer 1 keepalive messages are not supported by {}".format(os.path.basename(self._path)))
        except (OSError, subprocess.CalledProcessError) as e:
            log.warn("could not determine if layer 1 keepalive messages are supported by {}: {}".format(os.path.basename(self._path), e))

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

        command = [self._path]
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
        command.extend([str(self._id)])
        return command

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

    @property
    def l1_keepalives(self):
        """
        Returns either layer 1 keepalive messages option is enabled or disabled.

        :returns: boolean
        """

        return self._l1_keepalives

    @l1_keepalives.setter
    def l1_keepalives(self, state):
        """
        Enables or disables layer 1 keepalive messages.

        :param state: boolean
        """

        self._l1_keepalives = state
        if state:
            log.info("IOU {name} [id={id}]: has activated layer 1 keepalive messages".format(name=self._name, id=self._id))
        else:
            log.info("IOU {name} [id={id}]: has deactivated layer 1 keepalive messages".format(name=self._name, id=self._id))

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
    def initial_config(self):
        """
        Returns the initial-config for this IOU instance.

        :returns: path to initial-config file
        """

        return self._initial_config

    @initial_config.setter
    def initial_config(self, initial_config):
        """
        Sets the initial-config for this IOU instance.

        :param initial_config: path to initial-config file
        """

        self._initial_config = initial_config
        log.info("IOU {name} [id={id}]: initial_config set to {config}".format(name=self._name,
                                                                               id=self._id,
                                                                               config=self._initial_config))

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

    def start_capture(self, slot_id, port_id, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param slot_id: slot ID
        :param port_id: port ID
        :param port: allocated port
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
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
        if nio.capturing:
            raise IOUError("Packet capture is already activated on {slot_id}/{port_id}".format(slot_id=slot_id,
                                                                                               port_id=port_id))

        try:
            os.makedirs(os.path.dirname(output_file))
        except FileExistsError:
            pass
        except OSError as e:
            raise IOUError("Could not create captures directory {}".format(e))

        nio.startPacketCapture(output_file, data_link_type)

        log.info("IOU {name} [id={id}]: starting packet capture on {slot_id}/{port_id}".format(name=self._name,
                                                                                               id=self._id,
                                                                                               slot_id=slot_id,
                                                                                               port_id=port_id))

        if self.is_iouyap_running():
            self._update_iouyap_config()
            os.kill(self._iouyap_process.pid, signal.SIGHUP)

    def stop_capture(self, slot_id, port_id):
        """
        Stops a packet capture.

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
        nio.stopPacketCapture()
        log.info("IOU {name} [id={id}]: stopping packet capture on {slot_id}/{port_id}".format(name=self._name,
                                                                                               id=self._id,
                                                                                               slot_id=slot_id,
                                                                                               port_id=port_id))
        if self.is_iouyap_running():
            self._update_iouyap_config()
            os.kill(self._iouyap_process.pid, signal.SIGHUP)
