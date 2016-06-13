# -*- coding: utf-8 -*-
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

from ...error import NodeError
from ...base_node import BaseNode

import logging
log = logging.getLogger(__name__)


class EthernetSwitch(BaseNode):

    """
    Ethernet switch.

    :param name: name for this switch
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    """

    def __init__(self, name, node_id, project, manager):

        super().__init__(name, node_id, project, manager)

    def __json__(self):

        return {"name": self.name,
                "node_id": self.id,
                "project_id": self.project.id}

    @asyncio.coroutine
    def create(self):
        """
        Creates this switch.
        """

        super().create()
        log.info('Ethernet switch "{name}" [{id}] has been created'.format(name=self._name, id=self._id))

    @asyncio.coroutine
    def delete(self):
        """
        Deletes this switch.
        """

        raise NotImplementedError()

    @asyncio.coroutine
    def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on this switch.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        raise NotImplementedError()

    @asyncio.coroutine
    def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of this switch.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the allocated port
        """

        raise NotImplementedError()

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
