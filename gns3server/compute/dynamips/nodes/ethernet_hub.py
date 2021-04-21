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
Hub object that uses the Bridge interface to create a hub with ports.
"""

from .bridge import Bridge
from ..nios.nio_udp import NIOUDP
from ..dynamips_error import DynamipsError
from ...error import NodeError

import logging

log = logging.getLogger(__name__)


class EthernetHub(Bridge):

    """
    Dynamips Ethernet hub (based on Bridge)

    :param name: name for this hub
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param ports: initial hub ports
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, ports=None, hypervisor=None):

        super().__init__(name, node_id, project, manager, hypervisor)
        self._mappings = {}
        if ports is None:
            # create 8 ports by default
            self._ports = []
            for port_number in range(0, 8):
                self._ports.append({"port_number": port_number, "name": f"Ethernet{port_number}"})
        else:
            self._ports = ports

    def asdict(self):

        return {
            "name": self.name,
            "usage": self.usage,
            "node_id": self.id,
            "project_id": self.project.id,
            "ports_mapping": self._ports,
            "status": "started",
        }

    @property
    def ports_mapping(self):
        """
        Ports on this hub

        :returns: ports info
        """

        return self._ports

    @ports_mapping.setter
    def ports_mapping(self, ports):
        """
        Set the ports on this hub

        :param ports: ports info
        """
        if ports != self._ports:
            if len(self._mappings) > 0:
                raise NodeError("Can't modify a hub already connected.")

            port_number = 0
            for port in ports:
                port["name"] = f"Ethernet{port_number}"
                port["port_number"] = port_number
                port_number += 1

            self._ports = ports

    async def create(self):

        await Bridge.create(self)
        log.info(f'Ethernet hub "{self._name}" [{self._id}] has been created')

    @property
    def mappings(self):
        """
        Returns port mappings

        :returns: mappings list
        """

        return self._mappings

    async def delete(self):
        return await self.close()

    async def close(self):
        """
        Deletes this hub.
        """

        for nio in self._nios:
            if nio:
                await nio.close()

        try:
            await Bridge.delete(self)
            log.info(f'Ethernet hub "{self._name}" [{self._id}] has been deleted')
        except DynamipsError:
            log.debug(f"Could not properly delete Ethernet hub {self._name}")
        if self._hypervisor and not self._hypervisor.devices:
            await self.hypervisor.stop()
            self._hypervisor = None
        return True

    async def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on this hub.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number not in [port["port_number"] for port in self._ports]:
            raise DynamipsError(f"Port {port_number} doesn't exist")

        if port_number in self._mappings:
            raise DynamipsError(f"Port {port_number} isn't free")

        await Bridge.add_nio(self, nio)

        log.info(
            'Ethernet hub "{name}" [{id}]: NIO {nio} bound to port {port}'.format(
                name=self._name, id=self._id, nio=nio, port=port_number
            )
        )
        self._mappings[port_number] = nio

    async def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of this hub.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the allocated port
        """

        if port_number not in self._mappings:
            raise DynamipsError(f"Port {port_number} is not allocated")

        await self.stop_capture(port_number)
        nio = self._mappings[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        await Bridge.remove_nio(self, nio)

        log.info(
            'Ethernet hub "{name}" [{id}]: NIO {nio} removed from port {port}'.format(
                name=self._name, id=self._id, nio=nio, port=port_number
            )
        )

        del self._mappings[port_number]
        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if port_number not in self._mappings:
            raise DynamipsError(f"Port {port_number} is not allocated")

        nio = self._mappings[port_number]

        if not nio:
            raise DynamipsError(f"Port {port_number} is not connected")

        return nio

    async def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        nio = self.get_nio(port_number)
        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError(f"Port {port_number} has already a filter applied")

        await nio.start_packet_capture(output_file, data_link_type)
        log.info(
            'Ethernet hub "{name}" [{id}]: starting packet capture on port {port}'.format(
                name=self._name, id=self._id, port=port_number
            )
        )

    async def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return
        await nio.stop_packet_capture()
        log.info(
            'Ethernet hub "{name}" [{id}]: stopping packet capture on port {port}'.format(
                name=self._name, id=self._id, port=port_number
            )
        )
