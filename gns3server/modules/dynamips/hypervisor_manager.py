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

from .hypervisor import Hypervisor
import socket
import time
import logging

log = logging.getLogger(__name__)


class HypervisorManager(object):
    """
    Manages Dynamips hypervisors.

    :param path: path to the Dynamips executable
    :param working_dir: path to a working directory
    :param host: host/address for hypervisors to listen to
    :param base_port: base TCP port for hypervisors
    :param base_console: base TCP port for consoles
    :param base_aux: base TCP port for auxiliary consoles
    :param base_udp: base UDP port for UDP tunnels
    """

    def __init__(self,
                 path,
                 working_dir,
                 host='127.0.0.1',
                 base_hypervisor_port=7200,
                 base_console_port=2000,
                 base_aux_port=3000,
                 base_udp_port=10000):

        self._hypervisors = []
        self._path = path
        self._working_dir = working_dir
        self._host = host
        self._base_hypervisor_port = base_hypervisor_port
        self._current_port = self._base_hypervisor_port
        self._base_console_port = base_console_port
        self._base_aux_port = base_aux_port
        self._base_udp_port = base_udp_port
        self._current_base_udp_port = self._base_udp_port
        self._udp_incrementation_per_hypervisor = 100
        self._ghost_ios_support = True
        self._mmap_support = True
        self._jit_sharing_support = False
        self._sparse_memory_support = True
        self._allocate_hypervisor_per_device = True
        self._memory_usage_limit_per_hypervisor = 1024
        self._allocate_hypervisor_per_ios_image = True

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

        self._working_dir = working_dir
        log.info("working directory set to {}".format(self._working_dir))

        # update all existing hypervisors with the new working directory
        for hypervisor in self._hypervisors:
            hypervisor.working_dir = working_dir

    @property
    def base_hypervisor_port(self):
        """
        Returns the base hypervisor port.

        :returns: base hypervisor port (integer)
        """

        return self._base_hypervisor_port

    @base_hypervisor_port.setter
    def base_hypervisor_port(self, base_hypervisor_port):
        """
        Set a new base hypervisor port.

        :param base_hypervisor_port: base hypervisor port (integer)
        """

        if self._base_hypervisor_port != base_hypervisor_port:
            self._base_hypervisor_port = base_hypervisor_port
            self._current_port = self._base_hypervisor_port
            log.info("base hypervisor port set to {}".format(self._base_hypervisor_port))

    @property
    def base_console_port(self):
        """
        Returns the base console port.

        :returns: base console port (integer)
        """

        return self._base_console_port

    @base_console_port.setter
    def base_console_port(self, base_console_port):
        """
        Set a new base console port.

        :param base_console_port: base console port (integer)
        """

        if self._base_console_port != base_console_port:
            self._base_console_port = base_console_port
            log.info("base console port set to {}".format(self._base_console_port))

    @property
    def base_aux_port(self):
        """
        Returns the base auxiliary console port.

        :returns: base auxiliary console  port (integer)
        """

        return self._base_aux_port

    @base_aux_port.setter
    def base_aux_port(self, base_aux_port):
        """
        Set a new base auxiliary console port.

        :param base_aux_port: base auxiliary console port (integer)
        """

        if self._base_aux_port != base_aux_port:
            self._base_aux_port = base_aux_port
            log.info("base aux port set to {}".format(self._base_aux_port))

    @property
    def base_udp_port(self):
        """
        Returns the base UDP port.

        :returns: base UDP  port (integer)
        """

        return self._base_udp_port

    @base_udp_port.setter
    def base_udp_port(self, base_udp_port):
        """
        Set a new base UDP port.

        :param base_udp_port: base UDP port (integer)
        """

        if self._base_udp_port != base_udp_port:
            self._base_udp_port = base_udp_port
            self._current_base_udp_port = self._base_udp_port
            log.info("base UDP port set to {}".format(self._base_udp_port))

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

    def wait_for_hypervisor(self, host, port, timeout=10):
        """
        Waits for an hypervisor to be started (accepting a socket connection)

        :param host: host/address to connect to the hypervisor
        :param port: port to connect to the hypervisor
        :param timeout: timeout value (default is 10 seconds)
        """

        connection_success = False
        begin = time.time()
        # try to connect for 10 seconds
        while(time.time() - begin < 10.0):
            time.sleep(0.01)
            try:
                with socket.create_connection((host, port), timeout):
                    pass
            except socket.error as e:
                last_exception = e
                continue
            connection_success = True
            break

        if not connection_success:
            # FIXME: throw exception here
            log.critical("Couldn't connect to hypervisor on {}:{} :{}".format(host, port,
                                                                             last_exception))
        else:
            log.info("Dynamips server ready after {:.4f} seconds".format(time.time() - begin))

    def allocate_tcp_port(self, max_port=100):
        """
        Allocates a new TCP port for a Dynamips hypervisor.

        :param max_port: maximum number of port to scan in
        order to find one available for use.

        :returns: port number (integer)
        """

        start_port = self._current_port
        end_port = start_port + max_port
        allocated_port = Hypervisor.find_unused_port(start_port, end_port, self._host)
        if allocated_port - self._current_port > 1:
            self._current_port += allocated_port - self._current_port
        else:
            self._current_port += 1
        return allocated_port

    def start_new_hypervisor(self):
        """
        Creates a new Dynamips process and start it.

        :returns: the new hypervisor instance
        """

        port = self.allocate_tcp_port()
#         working_dir = os.path.join(self._working_dir, "instance-{}".format(port))
#         if not os.path.exists(working_dir):
#             try:
#                 os.makedirs(working_dir)
#             except OSError as e:
#                 raise DynamipsError("{}".format(e))

        hypervisor = Hypervisor(self._path,
                                self._working_dir,
                                self._host,
                                port)

        log.info("creating new hypervisor {}:{}".format(hypervisor.host, hypervisor.port))
        hypervisor.start()

        self.wait_for_hypervisor(self._host, port)
        log.info("hypervisor {}:{} has successfully started".format(hypervisor.host, hypervisor.port))

        hypervisor.connect()
        hypervisor.baseconsole = self._base_console_port
        hypervisor.baseaux = self._base_aux_port
        hypervisor.baseudp = self._current_base_udp_port
        self._current_base_udp_port += self._udp_incrementation_per_hypervisor
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
            hypervisor.memory_load = 0

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
