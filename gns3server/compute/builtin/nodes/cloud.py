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

import asyncio

from ...node_error import NodeError
from ...base_node import BaseNode
from ...nios.nio_udp import NIOUDP

from gns3server.utils.interfaces import interfaces

import logging
log = logging.getLogger(__name__)


class Cloud(BaseNode):

    """
    Cloud.

    :param name: name for this cloud
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    """

    def __init__(self, name, node_id, project, manager, ports=None):

        super().__init__(name, node_id, project, manager)
        self._nios = {}
        self._ports = []
        if ports:
            self._ports = ports

    def __json__(self):

        host_interfaces = []
        network_interfaces = interfaces()
        for interface in network_interfaces:
            interface_type = "ethernet"
            if interface["name"].startswith("tap"):
                # found no way to reliably detect a TAP interface
                interface_type = "tap"
            host_interfaces.append({"name": interface["name"],
                                    "type": interface_type})

        return {"name": self.name,
                "node_id": self.id,
                "project_id": self.project.id,
                "ports": self._ports,
                "interfaces": host_interfaces}

    @property
    def ports(self):
        """
        Ports on this cloud.

        :returns: ports info
        """

        return self._ports

    @ports.setter
    def ports(self, ports):
        """
        Set the ports on this cloud.

        :param ports: ports info
        """

        self._ports = ports

    def create(self):
        """
        Creates this cloud.
        """

        super().create()
        log.info('Cloud "{name}" [{id}] has been created'.format(name=self._name, id=self._id))

    def delete(self):
        """
        Deletes this cloud.
        """

        for nio in self._nios.values():
            if nio and isinstance(nio, NIOUDP):
                self.manager.port_manager.release_udp_port(nio.lport, self._project)

        super().delete()
        log.info('Cloud "{name}" [{id}] has been deleted'.format(name=self._name, id=self._id))

    @asyncio.coroutine
    def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on this cloud.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise NodeError("Port {} isn't free".format(port_number))

        log.info('Cloud "{name}" [{id}]: NIO {nio} bound to port {port}'.format(name=self._name,
                                                                                id=self._id,
                                                                                nio=nio,
                                                                                port=port_number))
        self._nios[port_number] = nio
        for port_settings in self._ports:
            if port_settings["port_number"] == port_number:
                #yield from self.set_port_settings(port_number, port_settings)
                break


    @asyncio.coroutine
    def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of cloud.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the allocated port
        """

        if port_number not in self._nios:
            raise NodeError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        log.info('Cloud "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                    id=self._id,
                                                                                    nio=nio,
                                                                                    port=port_number))

        del self._nios[port_number]
        return nio

    @asyncio.coroutine
    def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        raise NotImplementedError()

    @asyncio.coroutine
    def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        raise NotImplementedError()
