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
import os
from gns3server.modules import IModule
from ..nodes.atm_switch import ATMSwitch
from ..dynamips_error import DynamipsError

from ..schemas.atmsw import ATMSW_CREATE_SCHEMA
from ..schemas.atmsw import ATMSW_DELETE_SCHEMA
from ..schemas.atmsw import ATMSW_UPDATE_SCHEMA
from ..schemas.atmsw import ATMSW_ALLOCATE_UDP_PORT_SCHEMA
from ..schemas.atmsw import ATMSW_ADD_NIO_SCHEMA
from ..schemas.atmsw import ATMSW_DELETE_NIO_SCHEMA
from ..schemas.atmsw import ATMSW_START_CAPTURE_SCHEMA
from ..schemas.atmsw import ATMSW_STOP_CAPTURE_SCHEMA

import logging
log = logging.getLogger(__name__)


class ATMSW(object):

    @IModule.route("dynamips.atmsw.create")
    def atmsw_create(self, request):
        """
        Creates a new ATM switch.

        Mandatory request parameters:
        - name (switch name)

        Response parameters:
        - id (switch identifier)
        - name (switch name)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ATMSW_CREATE_SCHEMA):
            return

        name = request["name"]
        try:
            if not self._hypervisor_manager:
                self.start_hypervisor_manager()

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

        Mandatory request parameters:
        - id (switch identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ATMSW_DELETE_SCHEMA):
            return

        # get the ATM switch instance
        atmsw_id = request["id"]
        atmsw = self.get_device_instance(atmsw_id, self._atm_switches)
        if not atmsw:
            return

        try:
            atmsw.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(atmsw)
            del self._atm_switches[atmsw_id]
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("dynamips.atmsw.update")
    def atmsw_update(self, request):
        """
        Updates a ATM switch.

        Mandatory request parameters:
        - id (switch identifier)

        Optional request parameters:
        - name (new switch name)

        Response parameters:
        - name if changed

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ATMSW_UPDATE_SCHEMA):
            return

        # get the ATM switch instance
        atmsw = self.get_device_instance(request["id"], self._atm_switches)
        if not atmsw:
            return

        response = {}
        # rename the switch if requested
        if "name" in request and atmsw.name != request["name"]:
            try:
                atmsw.name = request["name"]
                response["name"] = atmsw.name
            except DynamipsError as e:
                self.send_custom_error(str(e))
                return

        self.send_response(response)

    @IModule.route("dynamips.atmsw.allocate_udp_port")
    def atmsw_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        ATM switch.

        Mandatory request parameters:
        - id (switch identifier)
        - port_id (port identifier)

        Response parameters:
        - port_id (port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ATMSW_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the ATM switch instance
        atmsw = self.get_device_instance(request["id"], self._atm_switches)
        if not atmsw:
            return

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(atmsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_id"] = request["port_id"]
        self.send_response(response)

    @IModule.route("dynamips.atmsw.add_nio")
    def atmsw_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an ATM switch.

        Mandatory request parameters:
        - id (switch identifier)
        - port (port identifier)
        - port_id (port identifier)
        - mappings (VCs/VPs mapped to the port)
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
        if not self.validate_request(request, ATMSW_ADD_NIO_SCHEMA):
            return

        # get the ATM switch instance
        atmsw = self.get_device_instance(request["id"], self._atm_switches)
        if not atmsw:
            return

        port = request["port"]
        mappings = request["mappings"]

        try:
            nio = self.create_nio(atmsw, request)
            if not nio:
                raise DynamipsError("Requested NIO doesn't exist: {}".format(request["nio"]))
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

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("dynamips.atmsw.delete_nio")
    def atmsw_delete_nio(self, request):
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
        if not self.validate_request(request, ATMSW_DELETE_NIO_SCHEMA):
            return

        # get the ATM switch instance
        atmsw = self.get_device_instance(request["id"], self._atm_switches)
        if not atmsw:
            return

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

        self.send_response(True)

    @IModule.route("dynamips.atmsw.start_capture")
    def atmsw_start_capture(self, request):
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
        if not self.validate_request(request, ATMSW_START_CAPTURE_SCHEMA):
            return

        # get the ATM switch instance
        atmsw = self.get_device_instance(request["id"], self._atm_switches)
        if not atmsw:
            return

        port = request["port"]
        capture_file_name = request["capture_file_name"]
        data_link_type = request.get("data_link_type")

        try:
            capture_file_path = os.path.join(atmsw.hypervisor.working_dir, "captures", capture_file_name)
            atmsw.start_capture(port, capture_file_path, data_link_type)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"],
                    "capture_file_path": capture_file_path}
        self.send_response(response)

    @IModule.route("dynamips.atmsw.stop_capture")
    def atmsw_stop_capture(self, request):
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
        if not self.validate_request(request, ATMSW_STOP_CAPTURE_SCHEMA):
            return

        # get the ATM switch instance
        atmsw = self.get_device_instance(request["id"], self._atm_switches)
        if not atmsw:
            return

        port = request["port"]
        try:
            atmsw.stop_capture(port)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"]}
        self.send_response(response)
