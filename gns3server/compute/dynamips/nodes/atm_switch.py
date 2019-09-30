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
Interface for Dynamips virtual ATM switch module ("atmsw").
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L593
"""

import asyncio
import re

from .device import Device
from ..nios.nio_udp import NIOUDP
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class ATMSwitch(Device):

    """
    Dynamips ATM switch.

    :param name: name for this switch
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, mappings=None, hypervisor=None):

        super().__init__(name, node_id, project, manager, hypervisor)
        self._nios = {}
        self._active_mappings = {}
        self._mappings = {}
        if mappings:
            self._mappings = mappings

    def __json__(self):

        mappings = {}
        for source, destination in self._mappings.items():
            mappings[source] = destination

        return {"name": self.name,
                "node_id": self.id,
                "project_id": self.project.id,
                "mappings": mappings,
                "status": "started"}

    async def create(self):

        if self._hypervisor is None:
            module_workdir = self.project.module_working_directory(self.manager.module_name.lower())
            self._hypervisor = await self.manager.start_new_hypervisor(working_dir=module_workdir)

        await self._hypervisor.send('atmsw create "{}"'.format(self._name))
        log.info('ATM switch "{name}" [{id}] has been created'.format(name=self._name, id=self._id))
        self._hypervisor.devices.append(self)

    async def set_name(self, new_name):
        """
        Renames this ATM switch.

        :param new_name: New name for this switch
        """

        await self._hypervisor.send('atmsw rename "{name}" "{new_name}"'.format(name=self._name, new_name=new_name))
        log.info('ATM switch "{name}" [{id}]: renamed to "{new_name}"'.format(name=self._name,
                                                                              id=self._id,
                                                                              new_name=new_name))
        self._name = new_name

    @property
    def nios(self):
        """
        Returns all the NIOs member of this ATM switch.

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

    @mappings.setter
    def mappings(self, mappings):
        """
        Sets port mappings

        :param mappings: mappings list
        """

        self._mappings = mappings

    async def close(self):
        for nio in self._nios.values():
            if nio:
                await nio.close()

        if self._hypervisor:
            try:
                await self._hypervisor.send('atmsw delete "{}"'.format(self._name))
                log.info('ATM switch "{name}" [{id}] has been deleted'.format(name=self._name, id=self._id))
            except DynamipsError:
                log.debug("Could not properly delete ATM switch {}".format(self._name))
        if self._hypervisor and self in self._hypervisor.devices:
            self._hypervisor.devices.remove(self)
        if self._hypervisor and not self._hypervisor.devices:
            await self.hypervisor.stop()
            self._hypervisor = None
        return True

    async def delete(self):
        """
        Deletes this ATM switch.
        """
        await self.close()

    def has_port(self, port):
        """
        Checks if a port exists on this ATM switch.

        :returns: boolean
        """

        if port in self._nios:
            return True
        return False

    async def add_nio(self, nio, port_number):
        """
        Adds a NIO as new port on ATM switch.

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise DynamipsError("Port {} isn't free".format(port_number))

        log.info('ATM switch "{name}" [id={id}]: NIO {nio} bound to port {port}'.format(name=self._name,
                                                                                        id=self._id,
                                                                                        nio=nio,
                                                                                        port=port_number))

        self._nios[port_number] = nio
        await self.set_mappings(self._mappings)

    async def remove_nio(self, port_number):
        """
        Removes the specified NIO as member of this ATM switch.

        :param port_number: allocated port number
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        await self.stop_capture(port_number)
        # remove VCs mapped with the port
        for source, destination in self._active_mappings.copy().items():
            if len(source) == 3 and len(destination) == 3:
                # remove the virtual channels mapped with this port/nio
                source_port, source_vpi, source_vci = source
                destination_port, destination_vpi, destination_vci = destination
                if port_number == source_port:
                    log.info('ATM switch "{name}" [{id}]: unmapping VCC between port {source_port} VPI {source_vpi} VCI {source_vci} and port {destination_port} VPI {destination_vpi} VCI {destination_vci}'.format(name=self._name,
                                                                                                                                                                                                                     id=self._id,
                                                                                                                                                                                                                     source_port=source_port,
                                                                                                                                                                                                                     source_vpi=source_vpi,
                                                                                                                                                                                                                     source_vci=source_vci,
                                                                                                                                                                                                                     destination_port=destination_port,
                                                                                                                                                                                                                     destination_vpi=destination_vpi,
                                                                                                                                                                                                                     destination_vci=destination_vci))
                    await self.unmap_pvc(source_port, source_vpi, source_vci, destination_port, destination_vpi, destination_vci)
                    await self.unmap_pvc(destination_port, destination_vpi, destination_vci, source_port, source_vpi, source_vci)
            else:
                # remove the virtual paths mapped with this port/nio
                source_port, source_vpi = source
                destination_port, destination_vpi = destination
                if port_number == source_port:
                    log.info('ATM switch "{name}" [{id}]: unmapping VPC between port {source_port} VPI {source_vpi} and port {destination_port} VPI {destination_vpi}'.format(name=self._name,
                                                                                                                                                                              id=self._id,
                                                                                                                                                                              source_port=source_port,
                                                                                                                                                                              source_vpi=source_vpi,
                                                                                                                                                                              destination_port=destination_port,
                                                                                                                                                                              destination_vpi=destination_vpi))
                    await self.unmap_vp(source_port, source_vpi, destination_port, destination_vpi)
                    await self.unmap_vp(destination_port, destination_vpi, source_port, source_vpi)

        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        log.info('ATM switch "{name}" [{id}]: NIO {nio} removed from port {port}'.format(name=self._name,
                                                                                         id=self._id,
                                                                                         nio=nio,
                                                                                         port=port_number))

        del self._nios[port_number]
        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if port_number not in self._nios:
            raise DynamipsError("Port {} is not allocated".format(port_number))

        nio = self._nios[port_number]

        if not nio:
            raise DynamipsError("Port {} is not connected".format(port_number))

        return nio

    async def set_mappings(self, mappings):
        """
        Applies VC mappings

        :param mappings: mappings (dict)
        """

        pvc_entry = re.compile(r"""^([0-9]*):([0-9]*):([0-9]*)$""")
        for source, destination in mappings.items():
            if not isinstance(source, str) or not isinstance(destination, str):
                raise DynamipsError("Invalid ATM mappings")
            match_source_pvc = pvc_entry.search(source)
            match_destination_pvc = pvc_entry.search(destination)
            if match_source_pvc and match_destination_pvc:
                # add the virtual channels
                source_port, source_vpi, source_vci = map(int, match_source_pvc.group(1, 2, 3))
                destination_port, destination_vpi, destination_vci = map(int, match_destination_pvc.group(1, 2, 3))
                if self.has_port(destination_port):
                    if (source_port, source_vpi, source_vci) not in self._active_mappings and \
                       (destination_port, destination_vpi, destination_vci) not in self._active_mappings:
                        log.info('ATM switch "{name}" [{id}]: mapping VCC between port {source_port} VPI {source_vpi} VCI {source_vci} and port {destination_port} VPI {destination_vpi} VCI {destination_vci}'.format(name=self._name,
                                                                                                                                                                                                                       id=self._id,
                                                                                                                                                                                                                       source_port=source_port,
                                                                                                                                                                                                                       source_vpi=source_vpi,
                                                                                                                                                                                                                       source_vci=source_vci,
                                                                                                                                                                                                                       destination_port=destination_port,
                                                                                                                                                                                                                       destination_vpi=destination_vpi,
                                                                                                                                                                                                                       destination_vci=destination_vci))
                        await self.map_pvc(source_port, source_vpi, source_vci, destination_port, destination_vpi, destination_vci)
                        await self.map_pvc(destination_port, destination_vpi, destination_vci, source_port, source_vpi, source_vci)
            else:
                # add the virtual paths
                source_port, source_vpi = map(int, source.split(':'))
                destination_port, destination_vpi = map(int, destination.split(':'))
                if self.has_port(destination_port):
                    if (source_port, source_vpi) not in self._active_mappings and (destination_port, destination_vpi) not in self._active_mappings:
                        log.info('ATM switch "{name}" [{id}]: mapping VPC between port {source_port} VPI {source_vpi} and port {destination_port} VPI {destination_vpi}'.format(name=self._name,
                                                                                                                                                                                id=self._id,
                                                                                                                                                                                source_port=source_port,
                                                                                                                                                                                source_vpi=source_vpi,
                                                                                                                                                                                destination_port=destination_port,
                                                                                                                                                                                destination_vpi=destination_vpi))
                        await self.map_vp(source_port, source_vpi, destination_port, destination_vpi)
                        await self.map_vp(destination_port, destination_vpi, source_port, source_vpi)

    async def map_vp(self, port1, vpi1, port2, vpi2):
        """
        Creates a new Virtual Path connection.

        :param port1: input port
        :param vpi1: input vpi
        :param port2: output port
        :param vpi2: output vpi
        """

        if port1 not in self._nios:
            return

        if port2 not in self._nios:
            return

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        await self._hypervisor.send('atmsw create_vpc "{name}" {input_nio} {input_vpi} {output_nio} {output_vpi}'.format(name=self._name,
                                                                                                                              input_nio=nio1,
                                                                                                                              input_vpi=vpi1,
                                                                                                                              output_nio=nio2,
                                                                                                                              output_vpi=vpi2))

        log.info('ATM switch "{name}" [{id}]: VPC from port {port1} VPI {vpi1} to port {port2} VPI {vpi2} created'.format(name=self._name,
                                                                                                                          id=self._id,
                                                                                                                          port1=port1,
                                                                                                                          vpi1=vpi1,
                                                                                                                          port2=port2,
                                                                                                                          vpi2=vpi2))

        self._active_mappings[(port1, vpi1)] = (port2, vpi2)

    async def unmap_vp(self, port1, vpi1, port2, vpi2):
        """
        Deletes a new Virtual Path connection.

        :param port1: input port
        :param vpi1: input vpi
        :param port2: output port
        :param vpi2: output vpi
        """

        if port1 not in self._nios:
            return

        if port2 not in self._nios:
            return

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        await self._hypervisor.send('atmsw delete_vpc "{name}" {input_nio} {input_vpi} {output_nio} {output_vpi}'.format(name=self._name,
                                                                                                                              input_nio=nio1,
                                                                                                                              input_vpi=vpi1,
                                                                                                                              output_nio=nio2,
                                                                                                                              output_vpi=vpi2))

        log.info('ATM switch "{name}" [{id}]: VPC from port {port1} VPI {vpi1} to port {port2} VPI {vpi2} deleted'.format(name=self._name,
                                                                                                                          id=self._id,
                                                                                                                          port1=port1,
                                                                                                                          vpi1=vpi1,
                                                                                                                          port2=port2,
                                                                                                                          vpi2=vpi2))

        del self._active_mappings[(port1, vpi1)]

    async def map_pvc(self, port1, vpi1, vci1, port2, vpi2, vci2):
        """
        Creates a new Virtual Channel connection (unidirectional).

        :param port1: input port
        :param vpi1: input vpi
        :param vci1: input vci
        :param port2: output port
        :param vpi2: output vpi
        :param vci2: output vci
        """

        if port1 not in self._nios:
            return

        if port2 not in self._nios:
            return

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        await self._hypervisor.send('atmsw create_vcc "{name}" {input_nio} {input_vpi} {input_vci} {output_nio} {output_vpi} {output_vci}'.format(name=self._name,
                                                                                                                                                       input_nio=nio1,
                                                                                                                                                       input_vpi=vpi1,
                                                                                                                                                       input_vci=vci1,
                                                                                                                                                       output_nio=nio2,
                                                                                                                                                       output_vpi=vpi2,
                                                                                                                                                       output_vci=vci2))

        log.info('ATM switch "{name}" [{id}]: VCC from port {port1} VPI {vpi1} VCI {vci1} to port {port2} VPI {vpi2} VCI {vci2} created'.format(name=self._name,
                                                                                                                                                id=self._id,
                                                                                                                                                port1=port1,
                                                                                                                                                vpi1=vpi1,
                                                                                                                                                vci1=vci1,
                                                                                                                                                port2=port2,
                                                                                                                                                vpi2=vpi2,
                                                                                                                                                vci2=vci2))

        self._active_mappings[(port1, vpi1, vci1)] = (port2, vpi2, vci2)

    async def unmap_pvc(self, port1, vpi1, vci1, port2, vpi2, vci2):
        """
        Deletes a new Virtual Channel connection (unidirectional).

        :param port1: input port
        :param vpi1: input vpi
        :param vci1: input vci
        :param port2: output port
        :param vpi2: output vpi
        :param vci2: output vci
        """

        if port1 not in self._nios:
            return

        if port2 not in self._nios:
            return

        nio1 = self._nios[port1]
        nio2 = self._nios[port2]

        await self._hypervisor.send('atmsw delete_vcc "{name}" {input_nio} {input_vpi} {input_vci} {output_nio} {output_vpi} {output_vci}'.format(name=self._name,
                                                                                                                                                       input_nio=nio1,
                                                                                                                                                       input_vpi=vpi1,
                                                                                                                                                       input_vci=vci1,
                                                                                                                                                       output_nio=nio2,
                                                                                                                                                       output_vpi=vpi2,
                                                                                                                                                       output_vci=vci2))

        log.info('ATM switch "{name}" [{id}]: VCC from port {port1} VPI {vpi1} VCI {vci1} to port {port2} VPI {vpi2} VCI {vci2} deleted'.format(name=self._name,
                                                                                                                                                id=self._id,
                                                                                                                                                port1=port1,
                                                                                                                                                vpi1=vpi1,
                                                                                                                                                vci1=vci1,
                                                                                                                                                port2=port2,
                                                                                                                                                vpi2=vpi2,
                                                                                                                                                vci2=vci2))
        del self._active_mappings[(port1, vpi1, vci1)]

    async def start_capture(self, port_number, output_file, data_link_type="DLT_ATM_RFC1483"):
        """
        Starts a packet capture.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_ATM_RFC1483
        """

        nio = self.get_nio(port_number)
        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {} has already a filter applied".format(port_number))

        await nio.start_packet_capture(output_file, data_link_type)
        log.info('ATM switch "{name}" [{id}]: starting packet capture on port {port}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             port=port_number))

    async def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: allocated port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return
        await nio.stop_packet_capture()
        log.info('ATM switch "{name}" [{id}]: stopping packet capture on port {port}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             port=port_number))
