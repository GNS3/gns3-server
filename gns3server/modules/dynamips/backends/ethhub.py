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
from ..nodes.hub import Hub
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class ETHHUB(object):

    @IModule.route("dynamips.ethhub.create")
    def ethhub_create(self, request):
        """
        Creates a new Ethernet switch.

        :param request: JSON request
        """

        name = None
        if request and "name" in request:
            name = request["name"]

        try:
            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_switch()
            ethhub = Hub(hypervisor, name)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": ethhub.name,
                    "id": ethhub.id}

        self._ethernet_hubs[ethhub.id] = ethhub
        self.send_response(response)

    @IModule.route("dynamips.ethhub.delete")
    def ethhub_delete(self, request):
        """
        Deletes a Ethernet hub.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        ethhub = self._ethernet_hubs[ethhub_id]
        try:
            ethhub.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.ethhub.update")
    def ethhub_update(self, request):
        """
        Updates a Ethernet hub.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        ethhub = self._ethernet_hubs[ethhub_id]
        #ports = request["ports"]

        self.send_response(request)

    @IModule.route("dynamips.ethhub.allocate_udp_port")
    def ethhub_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        Ethernet hub.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        ethhub = self._ethernet_hubs[ethhub_id]

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(ethhub)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(response)

    @IModule.route("dynamips.ethhub.add_nio")
    def ethhub_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an Ethernet hub.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        ethhub = self._ethernet_hubs[ethhub_id]
        port = request["port"]

        try:
            nio = self.create_nio(ethhub, request)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        try:
            ethhub.add_nio(nio, port)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.ethhub.delete_nio")
    def ethsw_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        ethhub = self._ethernet_hubs[ethhub_id]
        port = request["port"]

        try:
            nio = ethhub.remove_nio(port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)
