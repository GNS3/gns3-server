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

from gns3server.config import Config
from .hypervisor import Hypervisor
from .dynamips_error import DynamipsError
from ..attic import find_unused_port
from ..attic import wait_socket_is_ready
from pkg_resources import parse_version

import os
import time
import logging

log = logging.getLogger(__name__)


class HypervisorManager(object):
    """
    Manages Dynamips hypervisors.

    :param path: path to the Dynamips executable
    :param working_dir: path to a working directory
    :param host: host/address for hypervisors to listen to
    """

    def __init__(self, path, working_dir, host='127.0.0.1'):

        self._hypervisors = []
        self._path = path
        self._working_dir = working_dir
        self._host = host

        config = Config.instance()
        dynamips_config = config.get_section_config("DYNAMIPS")
        self._hypervisor_start_port_range = dynamips_config.get("hypervisor_start_port_range", 7200)
        self._hypervisor_end_port_range = dynamips_config.get("hypervisor_end_port_range", 7700)
        self._console_start_port_range = dynamips_config.get("console_start_port_range", 2001)
        self._console_end_port_range = dynamips_config.get("console_end_port_range", 2500)
        self._aux_start_port_range = dynamips_config.get("aux_start_port_range", 2501)
        self._aux_end_port_range = dynamips_config.get("aux_end_port_range", 3000)
        self._udp_start_port_range = dynamips_config.get("udp_start_port_range", 10001)
        self._udp_end_port_range = dynamips_config.get("udp_end_port_range", 20000)
        self._ghost_ios_support = dynamips_config.get("ghost_ios_support", True)
        self._mmap_support = dynamips_config.get("mmap_support", True)
        self._jit_sharing_support = dynamips_config.get("jit_sharing_support", False)
        self._sparse_memory_support = dynamips_config.get("sparse_memory_support", True)
        self._allocate_hypervisor_per_device = dynamips_config.get("allocate_hypervisor_per_device", True)
        self._memory_usage_limit_per_hypervisor = dynamips_config.get("memory_usage_limit_per_hypervisor", 1024)
        self._allocate_hypervisor_per_ios_image = dynamips_config.get("allocate_hypervisor_per_ios_image", True)

    def __del__(self):
        """
        Shutdowns all started hypervisors
        """

        self.stop_all_hypervisors()

    @property
    def hypervisors(self):
        """
        Returns all hypervisor instances.

        :returns: list of hypervisor instances
        """

        return self._hypervisors

    @property
    def path(self):
        """
        Returns the Dynamips path.

        :returns: path to Dynamips
        """

        return self._path

    @path.setter
    def path(self, path):
        """
        Set a new Dynamips path.

        :param path: path to Dynamips
        """

        self._path = path
        log.info("Dynamips path set to {}".format(self._path))

    @property
    def working_dir(self):
        """
        Returns the Dynamips working directory path.

        :returns: path to Dynamips working directory
        """

        return self._working_dir

    @working_dir.setter
    def working_dir(self, working_dir):
        """
        Sets a new path to the Dynamips working directory.

        :param working_dir: path to Dynamips working directory
        """

        self._working_dir = os.path.join(working_dir, "dynamips")
        log.info("working directory set to {}".format(self._working_dir))

        # update all existing hypervisors with the new working directory
        for hypervisor in self._hypervisors:
            hypervisor.working_dir = self._working_dir

    @property
    def hypervisor_start_port_range(self):
        """
        Returns the hypervisor start port range value

        :returns: hypervisor start port range value (integer)
        """

        return self._hypervisor_start_port_range

    @hypervisor_start_port_range.setter
    def hypervisor_start_port_range(self, hypervisor_start_port_range):
        """
        Sets a new hypervisor start port range value

        :param hypervisor_start_port_range: hypervisor start port range value (integer)
        """

        if self._hypervisor_start_port_range != hypervisor_start_port_range:
            self._hypervisor_start_port_range = hypervisor_start_port_range
            log.info("hypervisor start port range value set to {}".format(self._hypervisor_start_port_range))

    @property
    def hypervisor_end_port_range(self):
        """
        Returns the hypervisor end port range value

        :returns: hypervisor end port range value (integer)
        """

        return self._hypervisor_end_port_range

    @hypervisor_end_port_range.setter
    def hypervisor_end_port_range(self, hypervisor_end_port_range):
        """
        Sets a new hypervisor end port range value

        :param hypervisor_end_port_range: hypervisor end port range value (integer)
        """

        if self._hypervisor_end_port_range != hypervisor_end_port_range:
            self._hypervisor_end_port_range = hypervisor_end_port_range
            log.info("hypervisor end port range value set to {}".format(self._hypervisor_end_port_range))

    @property
    def console_start_port_range(self):
        """
        Returns the console start port range value

        :returns: console start port range value (integer)
        """

        return self._console_start_port_range

    @console_start_port_range.setter
    def console_start_port_range(self, console_start_port_range):
        """
        Sets a new console start port range value

        :param console_start_port_range: console start port range value (integer)
        """

        if self._console_start_port_range != console_start_port_range:
            self._console_start_port_range = console_start_port_range
            log.info("console start port range value set to {}".format(self._console_start_port_range))

            # update all existing hypervisors with the new value
            for hypervisor in self._hypervisors:
                hypervisor.console_start_port_range = console_start_port_range

    @property
    def console_end_port_range(self):
        """
        Returns the console end port range value

        :returns: console end port range value (integer)
        """

        return self._console_end_port_range

    @console_end_port_range.setter
    def console_end_port_range(self, console_end_port_range):
        """
        Sets a new console end port range value

        :param console_end_port_range: console end port range value (integer)
        """

        if self._console_end_port_range != console_end_port_range:
            self._console_end_port_range = console_end_port_range
            log.info("console end port range value set to {}".format(self._console_end_port_range))

            # update all existing hypervisors with the new value
            for hypervisor in self._hypervisors:
                hypervisor.console_end_port_range = console_end_port_range

    @property
    def aux_start_port_range(self):
        """
        Returns the auxiliary console start port range value

        :returns: auxiliary console  start port range value (integer)
        """

        return self._aux_start_port_range

    @aux_start_port_range.setter
    def aux_start_port_range(self, aux_start_port_range):
        """
        Sets a new auxiliary console start port range value

        :param aux_start_port_range: auxiliary console start port range value (integer)
        """

        if self._aux_start_port_range != aux_start_port_range:
            self._aux_start_port_range = aux_start_port_range
            log.info("auxiliary console start port range value set to {}".format(self._aux_start_port_range))

            # update all existing hypervisors with the new value
            for hypervisor in self._hypervisors:
                hypervisor.aux_start_port_range = aux_start_port_range

    @property
    def aux_end_port_range(self):
        """
        Returns the auxiliary console end port range value

        :returns: auxiliary console end port range value (integer)
        """

        return self._aux_end_port_range

    @aux_end_port_range.setter
    def aux_end_port_range(self, aux_end_port_range):
        """
        Sets a new auxiliary console end port range value

        :param aux_end_port_range: auxiliary console end port range value (integer)
        """

        if self._aux_end_port_range != aux_end_port_range:
            self._aux_end_port_range = aux_end_port_range
            log.info("auxiliary console end port range value set to {}".format(self._aux_end_port_range))

            # update all existing hypervisors with the new value
            for hypervisor in self._hypervisors:
                hypervisor.aux_end_port_range = aux_end_port_range

    @property
    def udp_start_port_range(self):
        """
        Returns the UDP start port range value

        :returns: UDP start port range value (integer)
        """

        return self._udp_start_port_range

    @udp_start_port_range.setter
    def udp_start_port_range(self, udp_start_port_range):
        """
        Sets a new UDP start port range value

        :param udp_start_port_range: UDP start port range value (integer)
        """

        if self._udp_start_port_range != udp_start_port_range:
            self._udp_start_port_range = udp_start_port_range
            log.info("UDP start port range value set to {}".format(self._udp_start_port_range))

            # update all existing hypervisors with the new value
            for hypervisor in self._hypervisors:
                hypervisor.udp_start_port_range = udp_start_port_range

    @property
    def udp_end_port_range(self):
        """
        Returns the UDP end port range value

        :returns: UDP end port range value (integer)
        """

        return self._udp_end_port_range

    @udp_end_port_range.setter
    def udp_end_port_range(self, udp_end_port_range):
        """
        Sets a new UDP end port range value

        :param udp_end_port_range: UDP end port range value (integer)
        """

        if self._udp_end_port_range != udp_end_port_range:
            self._udp_end_port_range = udp_end_port_range
            log.info("UDP end port range value set to {}".format(self._udp_end_port_range))

            # update all existing hypervisors with the new value
            for hypervisor in self._hypervisors:
                hypervisor.udp_end_port_range = udp_end_port_range

    @property
    def ghost_ios_support(self):
        """
        Returns either ghost IOS is activated or not.

        :returns: boolean
        """

        return self._ghost_ios_support

    @ghost_ios_support.setter
    def ghost_ios_support(self, ghost_ios_support):
        """
        Sets ghost IOS support.

        :param ghost_ios_support: boolean
        """

        if self._ghost_ios_support != ghost_ios_support:
            self._ghost_ios_support = ghost_ios_support
            if ghost_ios_support:
                log.info("ghost IOS support enabled")
            else:
                log.info("ghost IOS support disabled")

    @property
    def mmap_support(self):
        """
        Returns either mmap is activated or not.

        :returns: boolean
        """

        return self._mmap_support

    @mmap_support.setter
    def mmap_support(self, mmap_support):
        """
        Sets mmap support.

        :param mmap_support: boolean
        """

        if self._mmap_support != mmap_support:
            self._mmap_support = mmap_support
            if mmap_support:
                log.info("mmap support enabled")
            else:
                log.info("mmap support disabled")

    @property
    def sparse_memory_support(self):
        """
        Returns either sparse memory is activated or not.

        :returns: boolean
        """

        return self._sparse_memory_support

    @sparse_memory_support.setter
    def sparse_memory_support(self, sparse_memory_support):
        """
        Sets sparse memory support.

        :param sparse_memory_support: boolean
        """

        if self._sparse_memory_support != sparse_memory_support:
            self._sparse_memory_support = sparse_memory_support
            if sparse_memory_support:
                log.info("sparse memory support enabled")
            else:
                log.info("sparse memory support disabled")

    @property
    def jit_sharing_support(self):
        """
        Returns either JIT sharing is activated or not.

        :returns: boolean
        """

        return self._jit_sharing_support

    @jit_sharing_support.setter
    def jit_sharing_support(self, jit_sharing_support):
        """
        Sets JIT sharing support.

        :param jit_sharing_support: boolean
        """

        if self._jit_sharing_support != jit_sharing_support:
            self._jit_sharing_support = jit_sharing_support
            if jit_sharing_support:
                log.info("JIT sharing support enabled")
            else:
                log.info("JIT sharing support disabled")

    @property
    def allocate_hypervisor_per_device(self):
        """
        Returns either an hypervisor is created for each device.

        :returns: True or False
        """

        return self._allocate_hypervisor_per_device

    @allocate_hypervisor_per_device.setter
    def allocate_hypervisor_per_device(self, value):
        """
        Sets if an hypervisor is created for each device.

        :param value: True or False
        """

        if self._allocate_hypervisor_per_device != value:
            self._allocate_hypervisor_per_device = value
            if value:
                log.info("allocating an hypervisor per device enabled")
            else:
                log.info("allocating an hypervisor per device disabled")

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
        Sets the memory usage limit per hypervisor

        :param memory_limit: memory limit value (integer)
        """

        if self._memory_usage_limit_per_hypervisor != memory_limit:
            self._memory_usage_limit_per_hypervisor = memory_limit
            log.info("memory usage limit per hypervisor set to {}".format(memory_limit))

    @property
    def allocate_hypervisor_per_ios_image(self):
        """
        Returns if router are grouped per hypervisor
        based on their IOS image.

        :returns: True or False
        """

        return self._allocate_hypervisor_per_ios_image

    @allocate_hypervisor_per_ios_image.setter
    def allocate_hypervisor_per_ios_image(self, value):
        """
        Sets if routers are grouped per hypervisor
        based on their IOS image.

        :param value: True or False
        """

        if self._allocate_hypervisor_per_ios_image != value:
            self._allocate_hypervisor_per_ios_image = value
            if value:
                log.info("allocating an hypervisor per IOS image enabled")
            else:
                log.info("allocating an hypervisor per IOS image disabled")

    def wait_for_hypervisor(self, host, port):
        """
        Waits for an hypervisor to be started (accepting a socket connection)

        :param host: host/address to connect to the hypervisor
        :param port: port to connect to the hypervisor
        """

        begin = time.time()
        # wait for the socket for a maximum of 10 seconds.
        connection_success, last_exception = wait_socket_is_ready(host, port, wait=10.0)

        if not connection_success:
            # FIXME: throw exception here
            log.critical("Couldn't connect to hypervisor on {}:{} :{}".format(host, port,
                                                                              last_exception))
        else:
            log.info("Dynamips server ready after {:.4f} seconds".format(time.time() - begin))

    def start_new_hypervisor(self):
        """
        Creates a new Dynamips process and start it.

        :returns: the new hypervisor instance
        """

        try:
            port = find_unused_port(self._hypervisor_start_port_range, self._hypervisor_end_port_range, self._host)
        except Exception as e:
            raise DynamipsError(e)

        hypervisor = Hypervisor(self._path,
                                self._working_dir,
                                self._host,
                                port)

        log.info("creating new hypervisor {}:{} with working directory {}".format(hypervisor.host, hypervisor.port, self._working_dir))
        hypervisor.start()

        self.wait_for_hypervisor(self._host, port)
        log.info("hypervisor {}:{} has successfully started".format(hypervisor.host, hypervisor.port))

        hypervisor.connect()
        if parse_version(hypervisor.version) < parse_version('0.2.11'):
            raise DynamipsError("Dynamips version must be >= 0.2.11, detected version is {}".format(hypervisor.version))

        hypervisor.console_start_port_range = self._console_start_port_range
        hypervisor.console_end_port_range = self._console_end_port_range
        hypervisor.aux_start_port_range = self._aux_start_port_range
        hypervisor.aux_end_port_range = self._aux_end_port_range
        hypervisor.udp_start_port_range = self._udp_start_port_range
        hypervisor.udp_end_port_range = self._udp_end_port_range
        self._hypervisors.append(hypervisor)
        return hypervisor

    def allocate_hypervisor_for_router(self, router_ios_image, router_ram):
        """
        Allocates a Dynamips hypervisor for a specific router
        (new or existing depending on the RAM amount and IOS image)

        :param router_ios_image: IOS image name
        :param router_ram: amount of RAM (integer)

        :returns: the allocated hypervisor instance
        """

        # allocate an hypervisor for each router by default
        if not self._allocate_hypervisor_per_device:
            for hypervisor in self._hypervisors:
                if self._allocate_hypervisor_per_ios_image:
                    if not hypervisor.image_ref:
                        hypervisor.image_ref = router_ios_image
                    elif hypervisor.image_ref != router_ios_image:
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

        :param router: Router instance
        """

        hypervisor = router.hypervisor
        hypervisor.decrease_memory_load(router.ram)

        if hypervisor.memory_load < 0:
            log.warn("hypervisor {}:{} has a memory load below 0 ({})".format(hypervisor.host,
                                                                              hypervisor.port,
                                                                              hypervisor.memory_load))
            #hypervisor.memory_load = 0

        # memory load at 0MB and no devices managed anymore...
        # let's stop this hypervisor
        if hypervisor.memory_load == 0 and not hypervisor.devices:
            hypervisor.stop()
            self._hypervisors.remove(hypervisor)

    def allocate_hypervisor_for_simulated_device(self):
        """
        Allocates a Dynamips hypervisor for a specific Dynamips simulated device.

        :returns: the allocated hypervisor instance
        """

        # For now always allocate the first hypervisor available,
        # in the future we could randomly allocate.

        if self._hypervisors:
            return self._hypervisors[0]

        # no hypervisor, let's start one!
        return self.start_new_hypervisor()

    def unallocate_hypervisor_for_simulated_device(self, device):
        """
        Unallocates a Dynamips hypervisor for a specific Dynamips simulated device.

        :param device: device instance
        """

        hypervisor = device.hypervisor
        if not hypervisor.devices:
            hypervisor.stop()
            self._hypervisors.remove(hypervisor)

    def stop_all_hypervisors(self):
        """
        Stops all hypervisors.
        """

        for hypervisor in self._hypervisors:
            hypervisor.stop()
        self._hypervisors = []
