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
Manages Dynamips hypervisors (load-balancing etc.)
"""

from __future__ import unicode_literals
from .hypervisor import Hypervisor
import socket
import time
import logging

log = logging.getLogger(__name__)


class HypervisorManager(object):
    """
    Manages Dynamips hypervisors.

    :param path: path to the Dynamips executable
    :param workingdir: path to a working directory
    :param host: host/address for hypervisors to listen to
    :param base_port: base TCP port for hypervisors
    :param base_console: base TCP port for consoles
    :param base_aux: base TCP port for auxiliary consoles
    :param base_udp: base UDP port for UDP tunnels
    """

    def __init__(self,
                 path,
                 workingdir,
                 host='127.0.0.1',
                 base_port=7200,
                 base_console=2000,
                 base_aux=3000,
                 base_udp=10000):

        self._hypervisors = []
        self._path = path
        self._workingdir = workingdir
        self._base_port = base_port
        self._current_port = self._base_port
        self._base_console = base_console
        self._base_aux = base_aux
        self._base_udp = base_udp
        self._host = host
        self._clean_workingdir = False
        self._ghost_ios = True
        self._mmap = True
        self._jit_sharing = False
        self._sparsemem = True
        self._memory_usage_limit_per_hypervisor = 1024
        self._group_ios_per_hypervisor = True

    def __del__(self):
        """
        Shutdowns all started hypervisors
        """

        self.stop_all_hypervisors()

    @property
    def hypervisors(self):
        """
        Returns all hypervisor instances.

        :returns: list of hypervisor objects
        """

        return self._hypervisors

    @property
    def memory_usage_limit_per_hypervisor(self):
        """
        Returns the memory usage limit per hypervisor

        :returns: limit value (integer)
        """

        return self._memory_usage_limit_per_hypervisor

    @memory_usage_limit_per_hypervisor.setter
    def memory_usage_limit_per_hypervisor(self, memory_limit):
        """
        Set the memory usage limit per hypervisor

        :param memory_limit: memory limit value (integer)
        """

        self._memory_usage_limit_per_hypervisor = memory_limit

    @property
    def group_ios_per_hypervisor(self):
        """
        Returns if router are grouped per hypervisor
        based on their IOS image.

        :returns: True or False
        """

        return self._group_ios_per_hypervisor

    @group_ios_per_hypervisor.setter
    def group_ios_per_hypervisor(self, value):
        """
        Set if router are grouped per hypervisor
        based on their IOS image.

        :param value: True or False
        """

        self._group_ios_per_hypervisor = value

    def wait_for_hypervisor(self, host, port, timeout=10):
        """
        Waits for an hypervisor to be started (accepting a socket connection)

        :param host: host/address to connect to the hypervisor
        :param port: port to connect to the hypervisor
        :param timeout: timeout value (default is 10 seconds)
        """

        # try to connect 5 times
        for _ in range(0, 5):
            try:
                s = socket.create_connection((host, port), timeout)
            except socket.error as e:
                time.sleep(0.5)
                last_exception = e
                continue
            connection_success = True
            break

        if connection_success:
            s.close()
            #time.sleep(0.1)
        else:
            log.critical("Couldn't connect to hypervisor on {}:{} :{}".format(host, port,
                                                                             last_exception))

    def start_new_hypervisor(self):
        """
        Creates a new Dynamips process and start it.

        :returns: the new hypervisor object
        """

        hypervisor = Hypervisor(self._path,
                                self._workingdir,
                                self._host,
                                self._current_port)

        log.info("creating new hypervisor {}:{}".format(hypervisor.host, hypervisor.port))
        hypervisor.start()

        self.wait_for_hypervisor(self._host, self._current_port)
        log.info("hypervisor {}:{} has successfully started".format(hypervisor.host, hypervisor.port))

        hypervisor.connect()
        self._hypervisors.append(hypervisor)
        self._current_port += 1
        return hypervisor

    def allocate_hypervisor_for_router(self, router_ios_image, router_ram):
        """
        Allocates a Dynamips hypervisor for a specific router
        (new or existing depending on the RAM amount and IOS image)

        :param router_ios_image: IOS image name
        :param router_ram: amount of RAM (integer)

        :returns: the allocated hypervisor object
        """

        for hypervisor in self._hypervisors:
            if self._group_ios_per_hypervisor and hypervisor.image_ref != router_ios_image:
                continue
            if (hypervisor.memory_load + router_ram) <= self._memory_usage_limit_per_hypervisor:
                current_memory_load = hypervisor.memory_load
                hypervisor.increase_memory_load(router_ram)
                log.info("allocating existing hypervisor {}:{}, RAM={}+{}".format(hypervisor.host,
                                                                                  hypervisor.port,
                                                                                  current_memory_load,
                                                                                  router_ram))
                return hypervisor

        hypervisor = self.start_new_hypervisor()
        hypervisor.image_ref = router_ios_image
        hypervisor.increase_memory_load(router_ram)
        return hypervisor

    def unallocate_hypervisor_for_router(self, router):
        """
        Unallocates a Dynamips hypervisor for a specific router.

        :param router: router object
        """

        hypervisor = router.hypervisor
        hypervisor.decrease_memory_load(router.ram)

        if hypervisor.memory_load < 0:
            log.warn("hypervisor {}:{} has a memory load below 0 ({})".format(hypervisor.host,
                                                                              hypervisor.port,
                                                                              hypervisor.memory_load))
            hypervisor.memory_load = 0

        # memory load at 0MB and no devices managed anymore...
        # let's stop this hypervisor
        if hypervisor.memory_load == 0 and not hypervisor.devices:
            hypervisor.stop()
            self._hypervisors.remove(hypervisor)

    def stop_all_hypervisors(self):
        """
        Stops all hypervisors.
        """

        for hypervisor in self._hypervisors:
            hypervisor.stop()
