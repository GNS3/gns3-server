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

import re
from gns3server.modules import IModule
from ..nodes.atm_switch import ATMSwitch
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class ATMSW(object):

    @IModule.route("dynamips.atmsw.create")
    def atmsw_create(self, request):
        """
        Creates a new ATM switch.

        :param request: JSON request
        """

        name = None
        if request and "name" in request:
            name = request["name"]

        try:
            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_simulated_device()
            atmsw = ATMSwitch(hypervisor, name)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": atmsw.name,
                    "id": atmsw.id}

        self._atm_switches[atmsw.id] = atmsw
        self.send_response(response)

    @IModule.route("dynamips.atmsw.delete")
    def atmsw_delete(self, request):
        """
        Deletes a ATM switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        atmsw_id = request["id"]
        atmsw = self._atm_switches[atmsw_id]
        try:
            atmsw.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(atmsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.atmsw.update")
    def atmsw_update(self, request):
        """
        Updates a ATM switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        atmsw_id = request["id"]
        atmsw = self._atm_switches[atmsw_id]
        self.send_response(request)

    @IModule.route("dynamips.atmsw.allocate_udp_port")
    def atmsw_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        ATM switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        atmsw_id = request["id"]
        atmsw = self._atm_switches[atmsw_id]

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(atmsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_name"] = request["port_name"]
        self.send_response(response)

    @IModule.route("dynamips.atmsw.add_nio")
    def atmsw_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an ATM switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        atmsw_id = request["id"]
        atmsw = self._atm_switches[atmsw_id]

        port = request["port"]
        mappings = request["mappings"]

        try:
            nio = self.create_nio(atmsw, request)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        try:
            atmsw.add_nio(nio, port)
            pvc_entry = re.compile(r"""^([0-9]*):([0-9]*):([0-9]*)$""")
            for source, destination in mappings.items():
                match_source_pvc = pvc_entry.search(source)
                match_destination_pvc = pvc_entry.search(destination)
                if match_source_pvc and match_destination_pvc:
                    # add the virtual channels mapped with this port/nio
                    source_port, source_vpi, source_vci = map(int, match_source_pvc.group(1, 2, 3))
                    destination_port, destination_vpi, destination_vci = map(int, match_destination_pvc.group(1, 2, 3))
                    if atmsw.has_port(destination_port):
                        if (source_port, source_vpi, source_vci) not in atmsw.mapping and \
                           (destination_port, destination_vpi, destination_vci) not in atmsw.mapping:
                            atmsw.map_pvc(source_port, source_vpi, source_vci, destination_port, destination_vpi, destination_vci)
                            atmsw.map_pvc(destination_port, destination_vpi, destination_vci, source_port, source_vpi, source_vci)
                else:
                    # add the virtual paths mapped with this port/nio
                    source_port, source_vpi = map(int, source.split(':'))
                    destination_port, destination_vpi = map(int, destination.split(':'))
                    if atmsw.has_port(destination_port):
                        if (source_port, source_vpi) not in atmsw.mapping and (destination_port, destination_vpi) not in atmsw.mapping:
                            atmsw.map_vp(source_port, source_vpi, destination_port, destination_vpi)
                            atmsw.map_vp(destination_port, destination_vpi, source_port, source_vpi)

        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.atmsw.delete_nio")
    def atmsw_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        atmsw_id = request["id"]
        atmsw = self._atm_switches[atmsw_id]
        port = request["port"]

        try:
            for source, destination in atmsw.mapping.copy().items():
                if len(source) == 3 and len(destination) == 3:
                    # remove the virtual channels mapped with this port/nio
                    source_port, source_vpi, source_vci = source
                    destination_port, destination_vpi, destination_vci = destination
                    if port == source_port:
                        atmsw.unmap_pvc(source_port, source_vpi, source_vci, destination_port, destination_vpi, destination_vci)
                        atmsw.unmap_pvc(destination_port, destination_vpi, destination_vci, source_port, source_vpi, source_vci)
                else:
                    # remove the virtual paths mapped with this port/nio
                    source_port, source_vpi = source
                    destination_port, destination_vpi = destination
                    if port == source_port:
                        atmsw.unmap_vp(source_port, source_vpi, destination_port, destination_vpi)
                        atmsw.unmap_vp(destination_port, destination_vpi, source_port, source_vpi)

            nio = atmsw.remove_nio(port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)
