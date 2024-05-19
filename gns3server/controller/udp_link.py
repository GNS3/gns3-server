#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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


from .controller_error import ControllerError, ControllerNotFoundError
from .link import Link


class UDPLink(Link):
    def __init__(self, project, link_id=None):
        super().__init__(project, link_id=link_id)
        self._created = False
        self._link_data = []

    @property
    def debug_link_data(self):
        """
        Use for the debug exports
        """
        return self._link_data

    async def create(self):
        """
        Create the link on the nodes
        """

        node1 = self._nodes[0]["node"]
        adapter_number1 = self._nodes[0]["adapter_number"]
        port_number1 = self._nodes[0]["port_number"]
        node2 = self._nodes[1]["node"]
        adapter_number2 = self._nodes[1]["adapter_number"]
        port_number2 = self._nodes[1]["port_number"]

        # Get an IP allowing communication between both host
        try:
            (node1_host, node2_host) = await node1.compute.get_ip_on_same_subnet(node2.compute)
        except ValueError as e:
            raise ControllerError(f"Cannot get an IP address on same subnet: {e}")

        # Reserve a UDP port on both side
        response = await node1.compute.post(f"/projects/{self._project.id}/ports/udp")
        self._node1_port = response.json["udp_port"]
        response = await node2.compute.post(f"/projects/{self._project.id}/ports/udp")
        self._node2_port = response.json["udp_port"]

        node1_filters = {}
        node2_filters = {}
        filter_node = self._get_filter_node()
        if filter_node == node1:
            node1_filters = self.get_active_filters()
        elif filter_node == node2:
            node2_filters = self.get_active_filters()

        # Create the tunnel on both side
        self._link_data.append(
            {
                "lport": self._node1_port,
                "rhost": node2_host,
                "rport": self._node2_port,
                "type": "nio_udp",
                "filters": node1_filters,
                "suspend": self._suspended,
            }
        )
        await node1.post(f"/adapters/{adapter_number1}/ports/{port_number1}/nio", data=self._link_data[0], timeout=120)

        self._link_data.append(
            {
                "lport": self._node2_port,
                "rhost": node1_host,
                "rport": self._node1_port,
                "type": "nio_udp",
                "filters": node2_filters,
                "suspend": self._suspended,
            }
        )
        try:
            await node2.post(
                f"/adapters/{adapter_number2}/ports/{port_number2}/nio", data=self._link_data[1], timeout=120
            )
        except Exception as e:
            # We clean the first NIO
            await node1.delete(f"/adapters/{adapter_number1}/ports/{port_number1}/nio", timeout=120)
            raise e
        self._created = True

    async def update(self):
        """
        Update the link on the nodes
        """

        if len(self._link_data) == 0:
            return
        node1 = self._nodes[0]["node"]
        node2 = self._nodes[1]["node"]

        node1_filters = {}
        node2_filters = {}
        filter_node = self._get_filter_node()
        if filter_node == node1:
            node1_filters = self.get_active_filters()
        elif filter_node == node2:
            node2_filters = self.get_active_filters()

        adapter_number1 = self._nodes[0]["adapter_number"]
        port_number1 = self._nodes[0]["port_number"]
        self._link_data[0]["filters"] = node1_filters
        self._link_data[0]["suspend"] = self._suspended
        if node1.node_type not in ("ethernet_switch", "ethernet_hub"):
            await node1.put(
                f"/adapters/{adapter_number1}/ports/{port_number1}/nio", data=self._link_data[0], timeout=120
            )

        adapter_number2 = self._nodes[1]["adapter_number"]
        port_number2 = self._nodes[1]["port_number"]
        self._link_data[1]["filters"] = node2_filters
        self._link_data[1]["suspend"] = self._suspended
        if node2.node_type not in ("ethernet_switch", "ethernet_hub"):
            await node2.put(
                f"/adapters/{adapter_number2}/ports/{port_number2}/nio", data=self._link_data[1], timeout=221
            )

    async def delete(self):
        """
        Delete the link and free the resources
        """
        if not self._created:
            return
        try:
            node1 = self._nodes[0]["node"]
            adapter_number1 = self._nodes[0]["adapter_number"]
            port_number1 = self._nodes[0]["port_number"]
        except IndexError:
            return
        try:
            await node1.delete(f"/adapters/{adapter_number1}/ports/{port_number1}/nio", timeout=120)
        # If the node is already deleted (user selected multiple element and delete all in the same time)
        except ControllerNotFoundError:
            pass

        try:
            node2 = self._nodes[1]["node"]
            adapter_number2 = self._nodes[1]["adapter_number"]
            port_number2 = self._nodes[1]["port_number"]
        except IndexError:
            return
        try:
            await node2.delete(f"/adapters/{adapter_number2}/ports/{port_number2}/nio", timeout=120)
        # If the node is already deleted (user selected multiple element and delete all in the same time)
        except ControllerNotFoundError:
            pass
        await super().delete()

    async def reset(self):
        """
        Reset the link.
        """

        # recreate the link on the compute
        await self.delete()
        await self.create()

    async def start_capture(self, data_link_type="DLT_EN10MB", capture_file_name=None):
        """
        Start capture on a link
        """
        if not capture_file_name:
            capture_file_name = self.default_capture_file_name()
        self._capture_node = self._choose_capture_side()
        data = {"capture_file_name": capture_file_name, "data_link_type": data_link_type}
        await self._capture_node["node"].post(
            "/adapters/{adapter_number}/ports/{port_number}/capture/start".format(
                adapter_number=self._capture_node["adapter_number"], port_number=self._capture_node["port_number"]
            ),
            data=data,
        )
        await super().start_capture(data_link_type=data_link_type, capture_file_name=capture_file_name)

    async def stop_capture(self):
        """
        Stop capture on a link
        """
        if self._capture_node:
            await self._capture_node["node"].post(
                "/adapters/{adapter_number}/ports/{port_number}/capture/stop".format(
                    adapter_number=self._capture_node["adapter_number"], port_number=self._capture_node["port_number"]
                )
            )
            self._capture_node = None
        await super().stop_capture()

    def _choose_capture_side(self):
        """
        Run capture on the best candidate.

        The ideal candidate is a node who on controller server and always
        running (capture will not be cut off)

        :returns: Node where the capture should run
        """

        ALWAYS_RUNNING_NODES_TYPE = ("cloud", "nat", "ethernet_switch", "ethernet_hub", "frame_relay_switch", "atm_switch")

        for node in self._nodes:
            if (
                node["node"].compute.id == "local"
                and node["node"].node_type in ALWAYS_RUNNING_NODES_TYPE
                and node["node"].status == "started"
            ):
                return node

        for node in self._nodes:
            if node["node"].node_type in ALWAYS_RUNNING_NODES_TYPE and node["node"].status == "started":
                return node

        for node in self._nodes:
            if node["node"].compute.id == "local" and node["node"].status == "started":
                return node

        for node in self._nodes:
            if node["node"].node_type and node["node"].status == "started":
                return node

        raise ControllerError("Cannot capture because there is no running device on this link")

    async def node_updated(self, node):
        """
        Called when a node member of the link is updated
        """
        if self._capture_node and node == self._capture_node["node"] and node.status != "started":
            await self.stop_capture()
