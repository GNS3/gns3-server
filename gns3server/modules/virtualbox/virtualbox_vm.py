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
VirtualBox VM instance.
"""

import os
import shutil

from pkg_resources import parse_version
from .virtualbox_error import VirtualBoxError
from .adapters.ethernet_adapter import EthernetAdapter
from .nios.nio_udp import NIO_UDP
from ..attic import find_unused_port

import logging
log = logging.getLogger(__name__)


class VirtualBoxVM(object):
    """
    VirtualBox VM implementation.

    :param name: name of this VirtualBox VM
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param vbox_id: VirtalBox VM instance ID
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
                 vbox_id=None,
                 console=None,
                 console_start_port_range=4512,
                 console_end_port_range=5000):

        if not vbox_id:
            self._id = 0
            for identifier in range(1, 1024):
                if identifier not in self._instances:
                    self._id = identifier
                    self._instances.append(self._id)
                    break

            if self._id == 0:
                raise VirtualBoxError("Maximum number of VirtualBox VM instances reached")
        else:
            if vbox_id in self._instances:
                raise VirtualBoxError("VirtualBox identifier {} is already used by another VirtualBox VM instance".format(vbox_id))
            self._id = vbox_id
            self._instances.append(self._id)

        self._name = name
        self._console = console
        self._working_dir = None
        self._host = host
        self._command = []
        self._vboxwrapper_process = None
        self._vboxwrapper_stdout_file = ""
        self._host = "127.0.0.1"
        self._started = False
        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range

        # VirtualBox settings
        self._ethernet_adapter = EthernetAdapter()  # one adapter with 1 Ethernet interface

        working_dir_path = os.path.join(working_dir, "vbox", "vm-{}".format(self._id))

        if vbox_id and not os.path.isdir(working_dir_path):
            raise VirtualBoxError("Working directory {} doesn't exist".format(working_dir_path))

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
                raise VirtualBoxError(e)

        if self._console in self._allocated_console_ports:
            raise VirtualBoxError("Console port {} is already used by another VirtualBox VM".format(console))
        self._allocated_console_ports.append(self._console)

        log.info("VirtualBox VM {name} [id={id}] has been created".format(name=self._name,
                                                                          id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for this VirtualBox VM.

        :returns: default values (dictionary)
        """

        vbox_defaults = {"name": self._name,
                         "console": self._console}

        return vbox_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this VirtualBox VM.

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
        Returns the name of this VirtualBox VM.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this VirtualBox VM.

        :param new_name: name
        """

        log.info("VirtualBox VM {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                                id=self._id,
                                                                                new_name=new_name))
        self._name = new_name

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
        Sets the working directory this VirtualBox VM.

        :param working_dir: path to the working directory
        """

        try:
            os.makedirs(working_dir)
        except FileExistsError:
            pass
        except OSError as e:
            raise VirtualBoxError("Could not create working directory {}: {}".format(working_dir, e))

        self._working_dir = working_dir
        log.info("VirtualBox VM {name} [id={id}]: working directory changed to {wd}".format(name=self._name,
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
            raise VirtualBoxError("Console port {} is already used by another VirtualBox VM".format(console))

        self._allocated_console_ports.remove(self._console)
        self._console = console
        self._allocated_console_ports.append(self._console)
        log.info("VirtualBox VM {name} [id={id}]: console port set to {port}".format(name=self._name,
                                                                                     id=self._id,
                                                                                     port=console))

    def delete(self):
        """
        Deletes this VirtualBox VM.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console and self.console in self._allocated_console_ports:
            self._allocated_console_ports.remove(self.console)

        log.info("VirtualBox VM {name} [id={id}] has been deleted".format(name=self._name,
                                                                          id=self._id))

    def clean_delete(self):
        """
        Deletes this VirtualBox VM & all files.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console:
            self._allocated_console_ports.remove(self.console)

        try:
            shutil.rmtree(self._working_dir)
        except OSError as e:
            log.error("could not delete VirtualBox VM {name} [id={id}]: {error}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        error=e))
            return

        log.info("VirtualBox VM {name} [id={id}] has been deleted (including associated files)".format(name=self._name,
                                                                                                       id=self._id))

    def start(self):
        """
        Starts this VirtualBox VM.
        """

        pass

    def stop(self):
        """
        Stops this VirtualBox VM.
        """

        pass

#     def port_add_nio_binding(self, port_id, nio):
#         """
#         Adds a port NIO binding.
# 
#         :param port_id: port ID
#         :param nio: NIO instance to add to the slot/port
#         """
# 
#         if not self._ethernet_adapter.port_exists(port_id):
#             raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
#                                                                                        port_id=port_id))
# 
#         self._ethernet_adapter.add_nio(port_id, nio)
#         log.info("VPCS {name} [id={id}]: {nio} added to port {port_id}".format(name=self._name,
#                                                                                id=self._id,
#                                                                                nio=nio,
#                                                                                port_id=port_id))

#     def port_remove_nio_binding(self, port_id):
#         """
#         Removes a port NIO binding.
# 
#         :param port_id: port ID
# 
#         :returns: NIO instance
#         """
# 
#         if not self._ethernet_adapter.port_exists(port_id):
#             raise VPCSError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=self._ethernet_adapter,
#                                                                                        port_id=port_id))
# 
#         nio = self._ethernet_adapter.get_nio(port_id)
#         self._ethernet_adapter.remove_nio(port_id)
#         log.info("VPCS {name} [id={id}]: {nio} removed from port {port_id}".format(name=self._name,
#                                                                                    id=self._id,
#                                                                                    nio=nio,
#                                                                                    port_id=port_id))
#        return nio
