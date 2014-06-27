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
from ..nodes.ethernet_switch import EthernetSwitch
from ..dynamips_error import DynamipsError

from ..schemas.ethsw import ETHSW_CREATE_SCHEMA
from ..schemas.ethsw import ETHSW_DELETE_SCHEMA
from ..schemas.ethsw import ETHSW_UPDATE_SCHEMA
from ..schemas.ethsw import ETHSW_ALLOCATE_UDP_PORT_SCHEMA
from ..schemas.ethsw import ETHSW_ADD_NIO_SCHEMA
from ..schemas.ethsw import ETHSW_DELETE_NIO_SCHEMA
from ..schemas.ethsw import ETHSW_START_CAPTURE_SCHEMA
from ..schemas.ethsw import ETHSW_STOP_CAPTURE_SCHEMA

import logging
log = logging.getLogger(__name__)


class ETHSW(object):

    @IModule.route("dynamips.ethsw.create")
    def ethsw_create(self, request):
        """
        Creates a new Ethernet switch.

        Mandatory request parameters:
        - name (switch name)

        Response parameters:
        - id (switch identifier)
        - name (switch name)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHSW_CREATE_SCHEMA):
            return

        name = request["name"]
        try:
            if not self._hypervisor_manager:
                self.start_hypervisor_manager()

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

        Mandatory request parameters:
        - id (switch identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHSW_DELETE_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw_id = request["id"]
        ethsw = self.get_device_instance(ethsw_id, self._ethernet_switches)
        if not ethsw:
            return

        try:
            ethsw.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_simulated_device(ethsw)
            del self._ethernet_switches[ethsw_id]
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("dynamips.ethsw.update")
    def ethsw_update(self, request):
        """
        Updates a Ethernet switch.

        Mandatory request parameters:
        - id (switch identifier)

        Optional request parameters:
        - name (new switch name)
        - ports (ports settings)

        Response parameters:
        - name if changed

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHSW_UPDATE_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw = self.get_device_instance(request["id"], self._ethernet_switches)
        if not ethsw:
            return

        if "ports" in request:
            ports = request["ports"]

            # update the port settings
            for port, info in ports.items():
                vlan = info["vlan"]
                port_type = info["type"]
                try:
                    if port_type == "access":
                        ethsw.set_access_port(int(port), vlan)
                    elif port_type == "dot1q":
                        ethsw.set_dot1q_port(int(port), vlan)
                    elif port_type == "qinq":
                        ethsw.set_qinq_port(int(port), vlan)
                except DynamipsError as e:
                    self.send_custom_error(str(e))
                    return

        response = {}
        # rename the switch if requested
        if "name" in request and ethsw.name != request["name"]:
            try:
                ethsw.name = request["name"]
                response["name"] = ethsw.name
            except DynamipsError as e:
                self.send_custom_error(str(e))
                return

        self.send_response(response)

    @IModule.route("dynamips.ethsw.allocate_udp_port")
    def ethsw_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO for an
        Ethernet switch.

        Mandatory request parameters:
        - id (switch identifier)
        - port_id (port identifier)

        Response parameters:
        - port_id (port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, ETHSW_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw = self.get_device_instance(request["id"], self._ethernet_switches)
        if not ethsw:
            return

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(ethsw)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_id"] = request["port_id"]
        self.send_response(response)

    @IModule.route("dynamips.ethsw.add_nio")
    def ethsw_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an Ethernet switch.

        Mandatory request parameters:
        - id (switch identifier)
        - port (port identifier)
        - port_id (port identifier)
        - vlan (vlan identifier)
        - port_type ("access", "dot1q" or "qinq")
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
        if not self.validate_request(request, ETHSW_ADD_NIO_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw = self.get_device_instance(request["id"], self._ethernet_switches)
        if not ethsw:
            return

        port = request["port"]
        vlan = request["vlan"]
        port_type = request["port_type"]
        try:
            nio = self.create_nio(ethsw, request)
            if not nio:
                raise DynamipsError("Requested NIO doesn't exist: {}".format(request["nio"]))
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

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("dynamips.ethsw.delete_nio")
    def ethsw_delete_nio(self, request):
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
        if not self.validate_request(request, ETHSW_DELETE_NIO_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw = self.get_device_instance(request["id"], self._ethernet_switches)
        if not ethsw:
            return

        port = request["port"]
        try:
            nio = ethsw.remove_nio(port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.ethsw.start_capture")
    def ethsw_start_capture(self, request):
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
        if not self.validate_request(request, ETHSW_START_CAPTURE_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw = self.get_device_instance(request["id"], self._ethernet_switches)
        if not ethsw:
            return

        port = request["port"]
        capture_file_name = request["capture_file_name"]
        data_link_type = request.get("data_link_type")

        try:
            capture_file_path = os.path.join(ethsw.hypervisor.working_dir, "captures", capture_file_name)
            ethsw.start_capture(port, capture_file_path, data_link_type)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"],
                    "capture_file_path": capture_file_path}
        self.send_response(response)

    @IModule.route("dynamips.ethsw.stop_capture")
    def ethsw_stop_capture(self, request):
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
        if not self.validate_request(request, ETHSW_STOP_CAPTURE_SCHEMA):
            return

        # get the Ethernet switch instance
        ethsw = self.get_device_instance(request["id"], self._ethernet_switches)
        if not ethsw:
            return

        port = request["port"]
        try:
            ethsw.stop_capture(port)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"]}
        self.send_response(response)
