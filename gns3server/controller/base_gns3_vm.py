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


class BaseGNS3VM:

    def __init__(self, vmname, port):

        self._vmname = vmname
        self._ip_address = None
        self._port = port
        self._headless = False
        self._running = False

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

    @asyncio.coroutine
    def start(self):
        """
        Starts the GNS3 VM.
        """

        raise NotImplementedError


    @asyncio.coroutine
    def stop(self, force=False):
        """
        Stops the GNS3 VM.
        """

        raise NotImplementedError

    @asyncio.coroutine
    def set_vcpus(self, vcpus):
        """
        Set the number of vCPU cores for the GNS3 VM.

        :param vcpus: number of vCPU cores

        :returns: boolean
        """

        raise NotImplementedError

    @asyncio.coroutine
    def set_ram(self, ram):
        """
        Set the RAM amount for the GNS3 VM.

        :param ram: amount of memory

        :returns: boolean
        """

        raise NotImplementedError
