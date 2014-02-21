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
from ..nodes.ethernet_switch import EthernetSwitch
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class ETHSW(object):

    @IModule.route("dynamips.ethsw.create")
    def ethsw_create(self, request):
        """
        Creates a new Ethernet switch.

        :param request: JSON request
        """

        name = None
        if request and "name" in request:
            name = request["name"]

        try:
            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_simulated_device()
            ethsw = EthernetSwitch(hypervisor, name)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": ethsw.name,
                    "id": ethsw.id}

        self._ethernet_switches[ethsw.id] = ethsw
        self.send_response(response)

    @IModule.route("dynamips.ethsw.delete")
    def ethsw_delete(self, request):
        """
        Deletes a Ethernet switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethsw_id = request["id"]
        ethsw = self._ethernet_switches[ethsw_id]
        try:
            ethsw.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(ethsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.ethsw.update")
    def ethsw_update(self, request):
        """
        Updates a Ethernet switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethsw_id = request["id"]
        ethsw = self._ethernet_switches[ethsw_id]
        ports = request["ports"]

        for port, info in ports.items():
            vlan = info["vlan"]
            port_type = info["type"]
            if port_type == "access":
                ethsw.set_access_port(int(port), vlan)
            elif port_type == "dot1q":
                ethsw.set_dot1q_port(int(port), vlan)
            elif port_type == "qinq":
                ethsw.set_qinq_port(int(port), vlan)

        self.send_response(request)

    @IModule.route("dynamips.ethsw.allocate_udp_port")
    def ethsw_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        Ethernet switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethsw_id = request["id"]
        ethsw = self._ethernet_switches[ethsw_id]

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(ethsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_name"] = request["port_name"]
        self.send_response(response)

    @IModule.route("dynamips.ethsw.add_nio")
    def ethsw_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an Ethernet switch.

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethsw_id = request["id"]
        ethsw = self._ethernet_switches[ethsw_id]

        port = request["port"]
        vlan = request["vlan"]
        port_type = request["port_type"]
        try:
            nio = self.create_nio(ethsw, request)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        try:
            ethsw.add_nio(nio, port)
            if port_type == "access":
                ethsw.set_access_port(port, vlan)
            elif port_type == "dot1q":
                ethsw.set_dot1q_port(port, vlan)
            elif port_type == "qinq":
                ethsw.set_qinq_port(port, vlan)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.ethsw.delete_nio")
    def ethsw_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethsw_id = request["id"]
        ethsw = self._ethernet_switches[ethsw_id]
        port = request["port"]

        try:
            nio = ethsw.remove_nio(port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)
