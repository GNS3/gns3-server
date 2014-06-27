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

import os
from gns3server.modules import IModule
from ..nodes.hub import Hub
from ..dynamips_error import DynamipsError

from ..schemas.ethhub import ETHHUB_CREATE_SCHEMA
from ..schemas.ethhub import ETHHUB_DELETE_SCHEMA
from ..schemas.ethhub import ETHHUB_UPDATE_SCHEMA
from ..schemas.ethhub import ETHHUB_ALLOCATE_UDP_PORT_SCHEMA
from ..schemas.ethhub import ETHHUB_ADD_NIO_SCHEMA
from ..schemas.ethhub import ETHHUB_DELETE_NIO_SCHEMA
from ..schemas.ethhub import ETHHUB_START_CAPTURE_SCHEMA
from ..schemas.ethhub import ETHHUB_STOP_CAPTURE_SCHEMA

import logging
log = logging.getLogger(__name__)


class ETHHUB(object):

    @IModule.route("dynamips.ethhub.create")
    def ethhub_create(self, request):
        """
        Creates a new Ethernet hub.

        Mandatory request parameters:
        - name (hub name)

        Response parameters:
        - id (hub identifier)
        - name (hub name)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_CREATE_SCHEMA):
            return

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
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_DELETE_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub_id = request["id"]
        ethhub = self.get_device_instance(ethhub_id, self._ethernet_hubs)
        if not ethhub:
            return

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
        - name if changed

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_UPDATE_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub = self.get_device_instance(request["id"], self._ethernet_hubs)
        if not ethhub:
            return

        response = {}
        # rename the hub if requested
        if "name" in request and ethhub.name != request["name"]:
            try:
                ethhub.name = request["name"]
                response["name"] = ethhub.name
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

        # validate the request
        if not self.validate_request(request, ETHHUB_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub = self.get_device_instance(request["id"], self._ethernet_hubs)
        if not ethhub:
            return

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
        - nio (one of the following)
            - type "nio_udp"
                - lport (local port)
                - rhost (remote host)
                - rport (remote port)
            - type "nio_generic_ethernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - type "nio_linux_ethernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - type "nio_tap"
                - tap_device (TAP device name e.g. tap0)
            - type "nio_unix"
                - local_file (path to UNIX socket file)
                - remote_file (path to UNIX socket file)
            - type "nio_vde"
                - control_file (path to VDE control file)
                - local_file (path to VDE local file)
            - type "nio_null"

        Response parameters:
        - port_id (unique port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_ADD_NIO_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub = self.get_device_instance(request["id"], self._ethernet_hubs)
        if not ethhub:
            return

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

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("dynamips.ethhub.delete_nio")
    def ethhub_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (hub identifier)
        - port (port identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_DELETE_NIO_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub = self.get_device_instance(request["id"], self._ethernet_hubs)
        if not ethhub:
            return

        port = request["port"]
        try:
            nio = ethhub.remove_nio(port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.ethhub.start_capture")
    def ethhub_start_capture(self, request):
        """
        Starts a packet capture.

        Mandatory request parameters:
        - id (vm identifier)
        - port (port identifier)
        - port_id (port identifier)
        - capture_file_name

        Optional request parameters:
        - data_link_type (PCAP DLT_* value)

        Response parameters:
        - port_id (port identifier)
        - capture_file_path (path to the capture file)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_START_CAPTURE_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub = self.get_device_instance(request["id"], self._ethernet_hubs)
        if not ethhub:
            return

        port = request["port"]
        capture_file_name = request["capture_file_name"]
        data_link_type = request.get("data_link_type")

        try:
            capture_file_path = os.path.join(ethhub.hypervisor.working_dir, "captures", capture_file_name)
            ethhub.start_capture(port, capture_file_path, data_link_type)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"],
                    "capture_file_path": capture_file_path}
        self.send_response(response)

    @IModule.route("dynamips.ethhub.stop_capture")
    def ethhub_stop_capture(self, request):
        """
        Stops a packet capture.

        Mandatory request parameters:
        - id (vm identifier)
        - port_id (port identifier)
        - port (port number)

        Response parameters:
        - port_id (port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHHUB_STOP_CAPTURE_SCHEMA):
            return

        # get the Ethernet hub instance
        ethhub = self.get_device_instance(request["id"], self._ethernet_hubs)
        if not ethhub:
            return

        port = request["port"]
        try:
            ethhub.stop_capture(port)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"]}
        self.send_response(response)
