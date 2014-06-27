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
from ..nodes.frame_relay_switch import FrameRelaySwitch
from ..dynamips_error import DynamipsError

from ..schemas.frsw import FRSW_CREATE_SCHEMA
from ..schemas.frsw import FRSW_DELETE_SCHEMA
from ..schemas.frsw import FRSW_UPDATE_SCHEMA
from ..schemas.frsw import FRSW_ALLOCATE_UDP_PORT_SCHEMA
from ..schemas.frsw import FRSW_ADD_NIO_SCHEMA
from ..schemas.frsw import FRSW_DELETE_NIO_SCHEMA
from ..schemas.frsw import FRSW_START_CAPTURE_SCHEMA
from ..schemas.frsw import FRSW_STOP_CAPTURE_SCHEMA

import logging
log = logging.getLogger(__name__)


class FRSW(object):

    @IModule.route("dynamips.frsw.create")
    def frsw_create(self, request):
        """
        Creates a new Frame-Relay switch.

        Mandatory request parameters:
        - name (switch name)

        Response parameters:
        - id (switch identifier)
        - name (switch name)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, FRSW_CREATE_SCHEMA):
            return

        name = request["name"]
        try:
            if not self._hypervisor_manager:
                self.start_hypervisor_manager()

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

        Mandatory request parameters:
        - id (switch identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, FRSW_DELETE_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw_id = request["id"]
        frsw = self.get_device_instance(frsw_id, self._frame_relay_switches)
        if not frsw:
            return

        try:
            frsw.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(frsw)
            del self._frame_relay_switches[frsw_id]
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.frsw.update")
    def frsw_update(self, request):
        """
        Updates a Frame Relay switch.

        Mandatory request parameters:
        - id (switch identifier)

        Optional request parameters:
        - name (new switch name)

        Response parameters:
        - name if updated

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, FRSW_UPDATE_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw = self.get_device_instance(request["id"], self._frame_relay_switches)
        if not frsw:
            return

        response = {}
        # rename the switch if requested
        if "name" in request and frsw.name != request["name"]:
            try:
                frsw.name = request["name"]
                response["name"] = frsw.name
            except DynamipsError as e:
                self.send_custom_error(str(e))
                return

        self.send_response(request)

    @IModule.route("dynamips.frsw.allocate_udp_port")
    def frsw_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        Frame Relay switch.

        Mandatory request parameters:
        - id (switch identifier)
        - port_id (port identifier)

        Response parameters:
        - port_id (port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, FRSW_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw = self.get_device_instance(request["id"], self._frame_relay_switches)
        if not frsw:
            return

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(frsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_id"] = request["port_id"]
        self.send_response(response)

    @IModule.route("dynamips.frsw.add_nio")
    def frsw_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an Frame-Relay switch.

        Mandatory request parameters:
        - id (switch identifier)
        - port (port identifier)
        - port_id (port identifier)
        - mappings (VCs mapped to the port)
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
        if not self.validate_request(request, FRSW_ADD_NIO_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw = self.get_device_instance(request["id"], self._frame_relay_switches)
        if not frsw:
            return

        port = request["port"]
        mappings = request["mappings"]

        try:
            nio = self.create_nio(frsw, request)
            if not nio:
                raise DynamipsError("Requested NIO doesn't exist: {}".format(request["nio"]))
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

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("dynamips.frsw.delete_nio")
    def frsw_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (switch identifier)
        - port (port identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, FRSW_DELETE_NIO_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw = self.get_device_instance(request["id"], self._frame_relay_switches)
        if not frsw:
            return

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

        self.send_response(True)

    @IModule.route("dynamips.frsw.start_capture")
    def frsw_start_capture(self, request):
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
        if not self.validate_request(request, FRSW_START_CAPTURE_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw = self.get_device_instance(request["id"], self._frame_relay_switches)
        if not frsw:
            return

        port = request["port"]
        capture_file_name = request["capture_file_name"]
        data_link_type = request.get("data_link_type")

        try:
            capture_file_path = os.path.join(frsw.hypervisor.working_dir, "captures", capture_file_name)
            frsw.start_capture(port, capture_file_path, data_link_type)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"],
                    "capture_file_path": capture_file_path}
        self.send_response(response)

    @IModule.route("dynamips.frsw.stop_capture")
    def frsw_stop_capture(self, request):
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
        if not self.validate_request(request, FRSW_STOP_CAPTURE_SCHEMA):
            return

        # get the Frame relay switch instance
        frsw = self.get_device_instance(request["id"], self._frame_relay_switches)
        if not frsw:
            return

        port = request["port"]
        try:
            frsw.stop_capture(port)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"]}
        self.send_response(response)
