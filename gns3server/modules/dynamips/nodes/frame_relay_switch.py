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
Interface for Dynamips virtual Frame-Relay switch module.
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L642
"""

import asyncio

from .device import Device
from ..nios.nio_udp import NIOUDP
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class FrameRelaySwitch(Device):

    """
    Dynamips Frame Relay switch.

    :param name: name for this switch
    :param device_id: Device instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, device_id, project, manager, hypervisor=None):

        super().__init__(name, device_id, project, manager, hypervisor)
        self._nios = {}
        self._mappings = {}

    def __json__(self):

        mappings = {}
        for source, destination in self._mappings.items():
            mappings[str(source)] = str(destination)

        return {"name": self.name,
                "device_id": self.id,
                "project_id": self.project.id,
                "mappings": mappings}

    @asyncio.coroutine
    def create(self):

        if self._hypervisor is None:
            module_workdir = self.project.module_working_directory(self.manager.module_name.lower())
            self._hypervisor = yield from self.manager.start_new_hypervisor(working_dir=module_workdir)

        yield from self._hypervisor.send('frsw create "{}"'.format(self._name))
        log.info('Frame Relay switch "{name}" [{id}] has been created'.format(name=self._name, id=self._id))
        self._hypervisor.devices.append(self)

    @asyncio.coroutine
    def set_name(self, new_name):
        """
        Renames this Frame Relay switch.

        :param new_name: New name for this switch
        """

        yield from self._hypervisor.send('frsw rename "{name}" "{new_name}"'.format(name=self._name, new_name=new_name))
        log.info('Frame Relay switch "{name}" [{id}]: renamed to "{new_name}"'.format(name=self._name,
                                                                                      id=self._id,
                                                                                      new_name=new_name))
        self._name = new_name

    @property
    def nios(self):
        """
        Returns all the NIOs member of this Frame Relay switch.

        :returns: nio list
        """

        return self._nios

    @property
    def mappings(self):
        """
        Returns port mappings

        :returns: mappings list
        """

        return self._mappings

    @asyncio.coroutine
    def delete(self):
        """
        Deletes this Frame Relay switch.
        """

        for nio in self._nios.values():
            if nio and isinstance(nio, NIOUDP):
                self.manager.port_manager.release_udp_port(nio.lport, self._project)

        try:
            yield from self._hypervisor.send('frsw delete "{}"'.format(self._name))
            log.info('Frame Relay switch "{name}" [{id}] has been deleted'.format(name=self._name, id=self._id))
        except DynamipsError:
            log.debug("Could not properly delete Frame relay switch {}".format(self._name))
        if self._hypervisor and self in self._hypervisor.devices:
            self._hypervisor.devices.remove(self)
        if self._hypervisor and not self._hypervisor.devices:
            yield from self.hypervisor.stop()

    def has_port(self, port):
        """
        Checks if a port exists on this Frame Relay switch.

        :returns: boolean
        """

        if port in self._nios:
            return True
        return False

    def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on Frame Relay switch.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise DynamipsError("Port {} isn't free".format(port_number))

        log.info('Frame Relay switch "{name}" [{id}]: NIO {nio} bound to port {port}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             nio=nio,
                                                                                             port=port_number))

        self._nios[port_number] = nio

    @asyncio.coroutine
    def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of this Frame Relay switch.

        :param port_number: allocated port number

        :returns: the NIO that was bound to the allocated port
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        # remove VCs mapped with the port
        for source, destination in self._mappings.copy().items():
            source_port, source_dlci = source
            destination_port, destination_dlci = destination
            if port_number == source_port:
                yield from self.unmap_vc(source_port, source_dlci, destination_port, destination_dlci)
                yield from self.unmap_vc(destination_port, destination_dlci, source_port, source_dlci)

        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        log.info('Frame Relay switch "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 nio=nio,
                                                                                                 port=port_number))

        del self._nios[port_number]
        return nio

    @asyncio.coroutine
    def set_mappings(self, mappings):
        """
        Applies VC mappings

        :param mappings: mappings (dict)
        """

        for source, destination in mappings.items():
            if not isinstance(source, str) or not isinstance(destination, str):
                raise DynamipsError("Invalid Frame-Relay mappings")
            source_port, source_dlci = map(int, source.split(':'))
            destination_port, destination_dlci = map(int, destination.split(':'))
            if self.has_port(destination_port):
                if (source_port, source_dlci) not in self.mappings and (destination_port, destination_dlci) not in self.mappings:
                    yield from self.map_vc(source_port, source_dlci, destination_port, destination_dlci)
                    yield from self.map_vc(destination_port, destination_dlci, source_port, source_dlci)

    @asyncio.coroutine
    def map_vc(self, port1, dlci1, port2, dlci2):
        """
        Creates a new Virtual Circuit connection (unidirectional).

        :param port1: input port
        :param dlci1: input DLCI
        :param port2: output port
        :param dlci2: output DLCI
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        yield from self._hypervisor.send('frsw create_vc "{name}" {input_nio} {input_dlci} {output_nio} {output_dlci}'.format(name=self._name,
                                                                                                                              input_nio=nio1,
                                                                                                                              input_dlci=dlci1,
                                                                                                                              output_nio=nio2,
                                                                                                                              output_dlci=dlci2))

        log.info('Frame Relay switch "{name}" [{id}]: VC from port {port1} DLCI {dlci1} to port {port2} DLCI {dlci2} created'.format(name=self._name,
                                                                                                                                     id=self._id,
                                                                                                                                     port1=port1,
                                                                                                                                     dlci1=dlci1,
                                                                                                                                     port2=port2,
                                                                                                                                     dlci2=dlci2))

        self._mappings[(port1, dlci1)] = (port2, dlci2)

    @asyncio.coroutine
    def unmap_vc(self, port1, dlci1, port2, dlci2):
        """
        Deletes a Virtual Circuit connection (unidirectional).

        :param port1: input port
        :param dlci1: input DLCI
        :param port2: output port
        :param dlci2: output DLCI
        """

        if port1 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port1))

        if port2 not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port2))

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        yield from self._hypervisor.send('frsw delete_vc "{name}" {input_nio} {input_dlci} {output_nio} {output_dlci}'.format(name=self._name,
                                                                                                                              input_nio=nio1,
                                                                                                                              input_dlci=dlci1,
                                                                                                                              output_nio=nio2,
                                                                                                                              output_dlci=dlci2))

        log.info('Frame Relay switch "{name}" [{id}]: VC from port {port1} DLCI {dlci1} to port {port2} DLCI {dlci2} deleted'.format(name=self._name,
                                                                                                                                     id=self._id,
                                                                                                                                     port1=port1,
                                                                                                                                     dlci1=dlci1,
                                                                                                                                     port2=port2,
                                                                                                                                     dlci2=dlci2))
        del self._mappings[(port1, dlci1)]

    @asyncio.coroutine
    def start_capture(self, port_number, output_file, data_link_type="DLT_FRELAY"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_FRELAY
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {} has already a filter applied".format(port_number))

        yield from nio.bind_filter("both", "capture")
        yield from nio.setup_filter("both", '{} "{}"'.format(data_link_type, output_file))

        log.info('Frame relay switch "{name}" [{id}]: starting packet capture on port {port}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     port=port_number))

    @asyncio.coroutine
    def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]
        yield from nio.unbind_filter("both")
        log.info('Frame relay switch "{name}" [{id}]: stopping packet capture on port {port}'.format(name=self._name,
                                                                                                     id=self._id,
                                                                                                     port=port_number))
