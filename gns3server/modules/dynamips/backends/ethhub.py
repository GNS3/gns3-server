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
        Creates a new Ethernet hub.

        Optional request parameters:
        - name (hub name)

        Response parameters:
        - id (hub identifier)
        - name (hub name)

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        name = None
        if request and "name" in request:
            name = request["name"]

        try:
            if not self._hypervisor_manager:
                self.start_hypervisor_manager()

            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_simulated_device()
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

        Mandatory request parameters:
        - id (hub identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        if ethhub_id not in self._ethernet_hubs:
            self.send_custom_error("Ethernet hub id {} doesn't exist".format(ethhub_id))
            return
        ethhub = self._ethernet_hubs[ethhub_id]

        try:
            ethhub.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(ethhub)
            del self._ethernet_hubs[ethhub_id]
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.ethhub.update")
    def ethhub_update(self, request):
        """
        Updates a Ethernet hub.

        Mandatory request parameters:
        - id (hub identifier)

        Optional request parameters:
        - name (new hub name)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        if ethhub_id not in self._ethernet_hubs:
            self.send_custom_error("Ethernet hub id {} doesn't exist".format(ethhub_id))
            return
        ethhub = self._ethernet_hubs[ethhub_id]

        # rename the hub if requested
        if "name" in request and ethhub.name != request["name"]:
            try:
                ethhub.name = request["name"]
            except DynamipsError as e:
                self.send_custom_error(str(e))
                return

        self.send_response(request)

    @IModule.route("dynamips.ethhub.allocate_udp_port")
    def ethhub_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        Ethernet hub.

        Mandatory request parameters:
        - id (hub identifier)
        - port_id (port identifier)

        Response parameters:
        - port_id (port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        if ethhub_id not in self._ethernet_hubs:
            self.send_custom_error("Ethernet hub id {} doesn't exist".format(ethhub_id))
            return
        ethhub = self._ethernet_hubs[ethhub_id]

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(ethhub)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_id"] = request["port_id"]
        self.send_response(response)

    @IModule.route("dynamips.ethhub.add_nio")
    def ethhub_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an Ethernet hub.

        Mandatory request parameters:
        - id (hub identifier)
        - port (port identifier)
        - port_id (port identifier)
        - nio (nio type, one of the following)
            - "NIO_UDP"
                - lport (local port)
                - rhost (remote host)
                - rport (remote port)
            - "NIO_GenericEthernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - "NIO_LinuxEthernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - "NIO_TAP"
                - tap_device (TAP device name e.g. tap0)
            - "NIO_UNIX"
                - local_file (path to UNIX socket file)
                - remote_file (path to UNIX socket file)
            - "NIO_VDE"
                - control_file (path to VDE control file)
                - local_file (path to VDE local file)
            - "NIO_Null"

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        if ethhub_id not in self._ethernet_hubs:
            self.send_custom_error("Ethernet hub id {} doesn't exist".format(ethhub_id))
            return
        ethhub = self._ethernet_hubs[ethhub_id]
        port = request["port"]

        try:
            nio = self.create_nio(ethhub, request)
            if not nio:
                raise DynamipsError("Requested NIO doesn't exist: {}".format(request["nio"]))
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

        Mandatory request parameters:
        - id (hub identifier)
        - port (port identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        ethhub_id = request["id"]
        if ethhub_id not in self._ethernet_hubs:
            self.send_custom_error("Ethernet hub id {} doesn't exist".format(ethhub_id))
            return
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
