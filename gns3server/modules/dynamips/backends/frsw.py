# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

from gns3server.modules import IModule
from ..nodes.frame_relay_switch import FrameRelaySwitch
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class FRSW(object):

    @IModule.route("dynamips.frsw.create")
    def frsw_create(self, request):
        """
        Creates a new Frame-Relay switch.

        :param request: JSON request
        """

        name = None
        if request and "name" in request:
            name = request["name"]

        try:
            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_simulated_device()
            frsw = FrameRelaySwitch(hypervisor, name)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": frsw.name,
                    "id": frsw.id}

        self._frame_relay_switches[frsw.id] = frsw
        self.send_response(response)

    @IModule.route("dynamips.frsw.delete")
    def frsw_delete(self, request):
        """
        Deletes a Frame Relay switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        frsw_id = request["id"]
        frsw = self._frame_relay_switches[frsw_id]
        try:
            frsw.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(frsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.frsw.update")
    def frsw_update(self, request):
        """
        Updates a Frame Relay switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        frsw_id = request["id"]
        frsw = self._frame_relay_switches[frsw_id]
        self.send_response(request)

    @IModule.route("dynamips.frsw.allocate_udp_port")
    def frsw_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        Frame Relay switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        frsw_id = request["id"]
        frsw = self._frame_relay_switches[frsw_id]

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(frsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_name"] = request["port_name"]
        self.send_response(response)

    @IModule.route("dynamips.frsw.add_nio")
    def frsw_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an Frame-Relay switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        frsw_id = request["id"]
        frsw = self._frame_relay_switches[frsw_id]

        port = request["port"]
        mappings = request["mappings"]

        try:
            nio = self.create_nio(frsw, request)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        try:
            frsw.add_nio(nio, port)

            # add the VCs mapped with this port/nio
            for source, destination in mappings.items():
                source_port, source_dlci = map(int, source.split(':'))
                destination_port, destination_dlci = map(int, destination.split(':'))
                if frsw.has_port(destination_port):
                    if (source_port, source_dlci) not in frsw.mapping and (destination_port, destination_dlci) not in frsw.mapping:
                        frsw.map_vc(source_port, source_dlci, destination_port, destination_dlci)
                        frsw.map_vc(destination_port, destination_dlci, source_port, source_dlci)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.frsw.delete_nio")
    def frsw_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        frsw_id = request["id"]
        frsw = self._frame_relay_switches[frsw_id]
        port = request["port"]

        try:
            # remove the VCs mapped with this port/nio
            for source, destination in frsw.mapping.copy().items():
                source_port, source_dlci = source
                destination_port, destination_dlci = destination
                if port == source_port:
                    frsw.unmap_vc(source_port, source_dlci, destination_port, destination_dlci)
                    frsw.unmap_vc(destination_port, destination_dlci, source_port, source_dlci)

            nio = frsw.remove_nio(port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)
