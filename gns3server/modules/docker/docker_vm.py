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
Docker container instance.
"""

import asyncio
import shutil
import psutil

from docker.utils import create_host_config
from gns3server.ubridge.hypervisor import Hypervisor
from pkg_resources import parse_version
from .docker_error import DockerError
from ..base_vm import BaseVM
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP

import logging
log = logging.getLogger(__name__)


class Container(BaseVM):
    """Docker container implementation.

    :param name: Docker container name
    :param vm_id: Docker VM identifier
    :param project: Project instance
    :param manager: Manager instance
    :param image: Docker image
    """

    def __init__(self, name, vm_id, project, manager, image, startcmd=None):
        self._name = name
        self._id = vm_id
        self._project = project
        self._manager = manager
        self._image = image
        self._startcmd = startcmd
        self._veths = []
        self._ethernet_adapters = []
        self._ubridge_hypervisor = None
        self._temporary_directory = None
        self._hw_virtualization = False

        log.debug(
            "{module}: {name} [{image}] initialized.".format(
                module=self.manager.module_name,
                name=self.name,
                image=self._image))

    def __json__(self):
        return {
            "name": self._name,
            "vm_id": self._id,
            "cid": self._cid,
            "project_id": self._project.id,
            "image": self._image,
        }

    @property
    def veths(self):
        """Returns Docker host veth interfaces."""
        return self._veths

    @asyncio.coroutine
    def _get_container_state(self):
        """Returns the container state (e.g. running, paused etc.)

        :returns: state
        :rtype: str
        """
        try:
            result = yield from self.manager.execute(
                "inspect_container", {"container": self._cid})
            result_dict = {state.lower(): value for state, value in result["State"].items()}
            for state, value in result_dict.items():
                if value is True:
                    # a container can be both paused and running
                    if state == "paused":
                        return "paused"
                    if state == "running":
                        if "paused" in result_dict and result_dict["paused"] is True:
                            return "paused"
                    return state.lower()
            return 'exited'
        except Exception as err:
            raise DockerError("Could not get container state for {0}: ".format(
                self._name), str(err))

    @asyncio.coroutine
    def create(self):
        """Creates the Docker container."""
        params = {
            "name": self._name,
            "image": self._image,
            "network_disabled": True,
            "host_config": create_host_config(
                privileged=True, cap_add=['ALL'])
        }
        if self._startcmd:
            params.update({'command': self._startcmd})

        result = yield from self.manager.execute("create_container", params)
        self._cid = result['Id']
        log.info("Docker container '{name}' [{id}] created".format(
            name=self._name, id=self._id))
        return True

    @property
    def ubridge_path(self):
        """Returns the uBridge executable path.

        :returns: path to uBridge
        """
        path = self._manager.config.get_section_config("Server").get(
            "ubridge_path", "ubridge")
        if path == "ubridge":
            path = shutil.which("ubridge")
        return path

    @asyncio.coroutine
    def _start_ubridge(self):
        """Starts uBridge (handles connections to and from this Docker VM)."""
        server_config = self._manager.config.get_section_config("Server")
        server_host = server_config.get("host")
        self._ubridge_hypervisor = Hypervisor(
            self._project, self.ubridge_path, self.working_dir, server_host)

        log.info("Starting new uBridge hypervisor {}:{}".format(
            self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.start()
        log.info("Hypervisor {}:{} has successfully started".format(
            self._ubridge_hypervisor.host, self._ubridge_hypervisor.port))
        yield from self._ubridge_hypervisor.connect()
        if parse_version(
                self._ubridge_hypervisor.version) < parse_version('0.9.1'):
            raise DockerError(
                "uBridge version must be >= 0.9.1, detected version is {}".format(
                    self._ubridge_hypervisor.version))

    @asyncio.coroutine
    def start(self):
        """Starts this Docker container."""

        state = yield from self._get_container_state()
        if state == "paused":
            yield from self.unpause()
        else:
            result = yield from self.manager.execute(
                "start", {"container": self._cid})

        yield from self._start_ubridge()
        for adapter_number in range(0, self.adapters):
            nio = self._ethernet_adapters[adapter_number].get_nio(0)
            if nio:
                yield from self._add_ubridge_connection(nio, adapter_number)

        log.info("Docker container '{name}' [{image}] started".format(
            name=self._name, image=self._image))

    def is_running(self):
        """Checks if the container is running.

        :returns: True or False
        :rtype: bool
        """
        state = yield from self._get_container_state()
        if state == "running":
            return True
        return False

    @asyncio.coroutine
    def restart(self):
        """Restarts this Docker container."""
        result = yield from self.manager.execute(
            "restart", {"container": self._cid})
        log.info("Docker container '{name}' [{image}] restarted".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def stop(self):
        """Stops this Docker container."""

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            yield from self._ubridge_hypervisor.stop()

        state = yield from self._get_container_state()
        if state == "paused":
            yield from self.unpause()
        result = yield from self.manager.execute(
            "kill", {"container": self._cid})
        log.info("Docker container '{name}' [{image}] stopped".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def pause(self):
        """Pauses this Docker container."""
        result = yield from self.manager.execute(
            "pause", {"container": self._cid})
        log.info("Docker container '{name}' [{image}] paused".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def unpause(self):
        """Unpauses this Docker container."""
        result = yield from self.manager.execute(
            "unpause", {"container": self._cid})
        state = yield from self._get_container_state()
        log.info("Docker container '{name}' [{image}] unpaused".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def remove(self):
        """Removes this Docker container."""
        state = yield from self._get_container_state()
        if state == "paused":
            yield from self.unpause()
        if state == "running":
            yield from self.stop()
        result = yield from self.manager.execute(
            "remove_container", {"container": self._cid, "force": True})
        log.info("Docker container '{name}' [{image}] removed".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def close(self):
        """Closes this Docker container."""
        log.debug("Docker container '{name}' [{id}] is closing".format(
            name=self.name, id=self._cid))
        for adapter in self._ethernet_adapters.values():
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(
                            nio.lport, self._project)

        yield from self.remove()

        log.info("Docker container '{name}' [{id}] closed".format(
            name=self.name, id=self._cid))
        self._closed = True

    def _add_ubridge_connection(self, nio, adapter_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance
        :param adapter_number: adapter number
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(
                    name=self.name, adapter_number=adapter_number))

        if nio and isinstance(nio, NIOUDP):
            for index in range(128):
                if "gns3-veth{}ext".format(index) not in psutil.net_if_addrs():
                    adapter.ifc = "eth{}".format(str(index))
                    adapter.host_ifc = "gns3-veth{}ext".format(str(index))
                    adapter.guest_ifc = "gns3-veth{}int".format(str(index))
                    break
            if not hasattr(adapter, "ifc"):
                raise DockerError(
                    "Adapter {adapter_number} couldn't allocate interface on Docker container '{name}'".format(
                        name=self.name, adapter_number=adapter_number))

        yield from self._ubridge_hypervisor.send(
            'docker create_veth {hostif} {guestif}'.format(
                guestif=adapter.guest_ifc, hostif=adapter.host_ifc))
        self._veths.append(adapter.host_ifc)

        namespace = yield from self.get_namespace()
        yield from self._ubridge_hypervisor.send(
            'docker move_to_ns {ifc} {ns}'.format(
                ifc=adapter.guest_ifc, ns=namespace))

        yield from self._ubridge_hypervisor.send(
            'bridge create bridge{}'.format(adapter_number))
        yield from self._ubridge_hypervisor.send(
            'bridge add_nio_linux_raw bridge{adapter} {ifc}'.format(
                ifc=adapter.host_ifc, adapter=adapter_number))

        if isinstance(nio, NIOUDP):
            yield from self._ubridge_hypervisor.send(
                'bridge add_nio_udp bridge{adapter} {lport} {rhost} {rport}'.format(
                    adapter=adapter_number, lport=nio.lport, rhost=nio.rhost,
                    rport=nio.rport))

        if nio.capturing:
            yield from self._ubridge_hypervisor.send(
                'bridge start_capture bridge{adapter} "{pcap_file}"'.format(
                    adapter=adapter_number, pcap_file=nio.pcap_output_file))

        yield from self._ubridge_hypervisor.send(
            'bridge start bridge{adapter}'.format(adapter=adapter_number))

    def _delete_ubridge_connection(self, adapter_number):
        """Deletes a connection in uBridge.

        :param adapter_number: adapter number
        """
        yield from self._ubridge_hypervisor.send("bridge delete bridge{name}".format(
            name=adapter_number))

        adapter = self._ethernet_adapters[adapter_number]
        yield from self._ubridge_hypervisor.send("docker delete_veth {name}".format(
            name=adapter.host_ifc))

    def adapter_add_nio_binding(self, adapter_number, nio):
        """Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(
                    name=self.name, adapter_number=adapter_number))

        adapter.add_nio(0, nio)
        log.info(
            "Docker container '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(
                name=self.name,
                id=self._id,
                nio=nio,
                adapter_number=adapter_number))

    def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number))

        adapter.remove_nio(0)
        try:
            yield from self._delete_ubridge_connection(adapter_number)
        except:
            pass

        log.info(
            "Docker VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(
                name=self.name, id=self.id, nio=adapter.host_ifc,
                adapter_number=adapter_number))

    @property
    def adapters(self):
        """Returns the number of Ethernet adapters for this Docker VM.

        :returns: number of adapters
        :rtype: int
        """
        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """Sets the number of Ethernet adapters for this Docker container.

        :param adapters: number of adapters
        """

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info(
            'Docker container "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(
                name=self._name,
                id=self._id,
                adapters=adapters))

    def get_namespace(self):
        result = yield from self.manager.execute(
            "inspect_container", {"container": self._cid})
        return int(result['State']['Pid'])
