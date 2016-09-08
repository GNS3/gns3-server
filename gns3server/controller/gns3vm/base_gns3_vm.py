#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import asyncio
import psutil

import logging
log = logging.getLogger(__name__)


class BaseGNS3VM:

    def __init__(self, controller):

        self._controller = controller
        self._vmname = None
        self._ip_address = None
        self._port = 3080
        self._headless = False
        self._vcpus = 1
        self._ram = 1024
        self._user = ""
        self.password = ""
        self._protocol = "http"
        self._running = False

        # limit the number of vCPUs to the number of physical cores (hyper thread CPUs are excluded)
        # because this is likely to degrade performances.
        self._vcpus = psutil.cpu_count(logical=False)
        # we want to allocate half of the available physical memory
        #ram = int(psutil.virtual_memory().total / (1024 * 1024) / 2)
        # value must be a multiple of 4 (VMware requirement)
        #ram -= ram % 4

        ram = 2048

        self._ram = ram

    @property
    def vmname(self):
        """
        Returns the GNS3 VM name.

        :returns: VM name
        """

        return self._vmname

    @vmname.setter
    def vmname(self, new_name):
        """
        Sets the GNS3 VM name

        :param new_name: new VM name
        """

        self._vmname = new_name

    @property
    def protocol(self):
        """
        Get the GNS3 VM protocol

        :returns: Protocol as string
        """
        return self._protocol

    @protocol.setter
    def protocol(self, val):
        """
        Sets the GNS3 VM protocol

        :param val: new VM protocol
        """
        self._protocol = val

    @property
    def user(self):
        """
        Get the GNS3 VM user

        :returns: User as string
        """
        return self._user

    @user.setter
    def user(self, val):
        """
        Sets the GNS3 VM user

        :param val: new VM user
        """
        self._user = val

    @property
    def password(self):
        """
        Get the GNS3 VM password

        :returns: Password as string
        """
        return self._password

    @password.setter
    def password(self, val):
        """
        Sets the GNS3 VM password

        :param val: new VM password
        """
        self._password = val

    @property
    def port(self):
        """
        Returns the GNS3 VM port.

        :returns: VM port
        """

        return self._port

    @port.setter
    def port(self, new_port):
        """
        Sets the GNS3 VM port

        :param new_port: new VM port
        """

        self._port = new_port

    @property
    def ip_address(self):
        """
        Returns the GNS3 VM IP address.

        :returns: VM IP address
        """

        return self._ip_address

    @ip_address.setter
    def ip_address(self, new_ip_address):
        """
        Sets the GNS3 VM IP address.

        :param new_ip_address: new VM IP address
        """

        self._ip_address = new_ip_address

    @property
    def running(self):
        """
        Returns whether the GNS3 VM is running or not.

        :returns: boolean
        """

        return self._running

    @running.setter
    def running(self, value):
        """
        Sets whether the GNS3 VM is running or not.

        :param value: boolean
        """

        self._running = value

    @property
    def headless(self):
        """
        Returns whether the GNS3 VM is headless or not.

        :returns: boolean
        """

        return self._headless

    @headless.setter
    def headless(self, value):
        """
        Sets whether the GNS3 VM is headless or not.

        :param value: boolean
        """

        self._headless = value

    @property
    def vcpus(self):
        """
        Returns the number of allocated vCPUs.

        :returns: number of vCPUs.
        """

        return self._vcpus

    @vcpus.setter
    def vcpus(self, new_vcpus):
        """
        Sets the number of allocated vCPUs.

        :param new_vcpus: new number of vCPUs.
        """

        self._vcpus = new_vcpus

    @property
    def ram(self):
        """
        Returns the amount of allocated RAM.

        :returns: number of vCPUs.
        """

        return self._ram

    @ram.setter
    def ram(self, new_ram):
        """
        Sets the amount of allocated RAM.

        :param new_ram: new amount of RAM.
        """

        self._ram = new_ram

    @property
    def engine(self):
        """
        Returns the engine (virtualization technology used to run the GNS3 VM).

        :returns: engine name
        """

        return self._engine

    @asyncio.coroutine
    def list(self):
        """
        List all VMs
        """

        raise NotImplementedError

    @asyncio.coroutine
    def start(self):
        """
        Starts the GNS3 VM.
        """

        raise NotImplementedError

    @asyncio.coroutine
    def suspend(self):
        """
        Suspend the GNS3 VM.
        """

        raise NotImplementedError

    @asyncio.coroutine
    def stop(self, force=False):
        """
        Stops the GNS3 VM.
        """

        raise NotImplementedError
