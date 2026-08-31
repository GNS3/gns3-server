# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 GNS3 Technologies Inc.
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

import pytest
import pytest_asyncio

from fastapi import FastAPI, status
from httpx import AsyncClient
from tests.utils import asyncio_patch, AsyncioMagicMock
from unittest.mock import call, MagicMock

from gns3server.compute.project import Project

# The builtin Ethernet switch talks to uBridge (brctl/bridge modules) instead of
# the Dynamips hypervisor. These are the seams we stub so the routes can be
# exercised without launching a real uBridge / creating kernel interfaces.
_NODE = "gns3server.compute.builtin.nodes.ethernet_switch.EthernetSwitch"

pytestmark = pytest.mark.asyncio


class TestEthernetSwitchNodesRoutes:

    @pytest_asyncio.fixture(autouse=True)
    async def stub_ubridge(self):
        """Keep uBridge from really starting and capture every command."""
        with asyncio_patch(f"{_NODE}._start_ubridge"), asyncio_patch(f"{_NODE}._stop_ubridge"), \
                asyncio_patch(f"{_NODE}._ubridge_send"):
            yield

    @pytest_asyncio.fixture
    async def ethernet_switch(self, app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> dict:

        params = {"name": "Ethernet Switch"}
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id),
            json=params
        )
        assert response.status_code == status.HTTP_201_CREATED

        json_response = response.json()
        node = compute_project.get_node(json_response["node_id"])
        # Pretend uBridge is up so the is_running() guards in remove/close pass.
        node._ubridge_hypervisor = MagicMock()
        node._ubridge_hypervisor.is_running.return_value = True
        node._ubridge_send.reset_mock()
        return json_response

    @staticmethod
    def _udp_params() -> dict:
        return {"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1"}

    async def test_ethernet_switch_create(
            self, app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project
    ) -> None:

        params = {"name": "Ethernet Switch 1"}
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id),
            json=params
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "Ethernet Switch 1"
        assert response.json()["project_id"] == compute_project.id
        assert response.json()["status"] == "started"

        # creation stands up the kernel bridge with VLAN filtering
        node = compute_project.get_node(response.json()["node_id"])
        br = node._bridge_name
        node._ubridge_send.assert_has_calls([
            call(f'brctl delete "{br}"'),
            call(f'brctl create "{br}"'),
            call(f'link set "{br}" up'),
            call(f'brctl vlanfiltering "{br}" on'),
        ])

    async def test_ethernet_switch_get(
            self, app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        response = await compute_client.get(
            app.url_path_for(
                "compute:get_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Ethernet Switch"
        assert response.json()["project_id"] == compute_project.id
        assert response.json()["status"] == "started"

    async def test_ethernet_switch_duplicate(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        # create destination switch first
        params = {"name": "Ethernet Switch 2"}
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id),
            json=params
        )
        assert response.status_code == status.HTTP_201_CREATED

        params = {"destination_node_id": response.json()["node_id"]}
        response = await compute_client.post(
            app.url_path_for(
                "compute:duplicate_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]), json=params
        )
        assert response.status_code == status.HTTP_201_CREATED

    async def test_ethernet_switch_update(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        params = {"name": "test", "console_type": "none"}

        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]),
            json=params
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "test"
        # renaming a builtin switch does not touch uBridge (the kernel bridge is
        # name-independent); nothing should have been sent.
        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.assert_not_called()

    async def test_ethernet_switch_update_ports_qinq_proto(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        # a QinQ port with the 802.1ad ethertype must switch the bridge protocol
        port_params = {
            "ports_mapping": [
                {"name": "Ethernet0", "port_number": 0, "type": "qinq", "vlan": 2, "ethertype": "0x88A8"},
                {"name": "Ethernet1", "port_number": 1, "type": "access", "vlan": 4},
            ],
        }

        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]),
            json=port_params
        )
        assert response.status_code == status.HTTP_200_OK

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.assert_any_call(f'brctl setvlanproto "{node._bridge_name}" 0x88a8')

    @pytest.mark.parametrize(
        "ports_settings",
        (
                {"name": "Ethernet0", "port_number": 0, "type": "dot42q", "vlan": 1},          # bad type
                {"name": "Ethernet0", "port_number": 0, "type": "access"},                     # missing vlan
                {"name": "Ethernet0", "port_number": 0, "type": "dot1q", "vlan": 1,
                 "ethertype": "0x88A8"},                                                       # ethertype only for qinq
                {"name": "Ethernet0", "port_number": 0, "type": "qinq", "vlan": 1,
                 "ethertype": "0x4242"},                                                        # bad ethertype
                {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 0},          # vlan < 1
                {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 4242},       # vlan > 4094
        )
    )
    async def test_ethernet_switch_update_ports_invalid(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            ethernet_switch: dict,
            ports_settings: dict,
    ) -> None:

        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]),
            json={"ports_mapping": [ports_settings]}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_ethernet_switch_delete(
            self, app: FastAPI,
            compute_client: AsyncClient,
            ethernet_switch: dict
    ) -> None:

        response = await compute_client.delete(
            app.url_path_for(
                "compute:delete_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_ethernet_switch_start(self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:start_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_stop(self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:stop_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_suspend(self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:suspend_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_reload(self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:reload_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_create_udp_access(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        response = await compute_client.post(url, json=self._udp_params())
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["type"] == "nio_udp"

        node = compute_project.get_node(ethernet_switch["node_id"])
        nio = node.get_nio(0)
        br = node._bridge_name
        tap = f"{br}-0"
        relay = f"{node.id}-0"
        # access VLAN 1 (default): drop default PVID 1, re-add 1 as PVID/untagged
        node._ubridge_send.assert_has_calls([
            call(f"bridge create {relay}"),
            call(f'bridge add_nio_tap {relay} "{tap}"'),
            call(f'brctl addif "{br}" "{tap}"'),
            call(f'brctl vlan_del "{br}" "{tap}" 1'),
            call(f'brctl vlan_add "{br}" "{tap}" 1 pvid untagged'),
            call(f"bridge add_nio_udp {relay} {nio.lport} {nio.rhost} {nio.rport}"),
            call(f"bridge reset_packet_filters {relay}"),
            call(f"bridge start {relay}"),
        ])

    async def test_ethernet_switch_create_udp_dot1q(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        # make port 0 a dot1q trunk with native VLAN 10
        await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"]),
            json={"ports_mapping": [
                {"name": "Ethernet0", "port_number": 0, "type": "dot1q", "vlan": 10},
            ]}
        )
        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        response = await compute_client.post(url, json=self._udp_params())
        assert response.status_code == status.HTTP_201_CREATED

        br = node._bridge_name
        tap = f"{br}-0"
        # trunk: drop default 1, admit all VIDs tagged, mark native 10 PVID/untagged
        node._ubridge_send.assert_has_calls([
            call(f'brctl vlan_del "{br}" "{tap}" 1'),
            call(f'brctl vlan_add "{br}" "{tap}" 1 vid 4094'),
            call(f'brctl vlan_add "{br}" "{tap}" 10 pvid untagged'),
        ])

    async def test_ethernet_switch_delete_nio(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        await compute_client.post(url, json=self._udp_params())

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        url = app.url_path_for(
            "compute:delete_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        response = await compute_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # the port's relay bridge and TAP are released from the kernel bridge
        br = node._bridge_name
        tap = f"{br}-0"
        relay = f"{node.id}-0"
        node._ubridge_send.assert_has_calls([
            call(f'brctl delif "{br}" "{tap}"'),
            call(f"bridge delete {relay}"),
        ])

    async def test_ethernet_switch_update_nio(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        params = self._udp_params()
        params["filters"] = {"delay": [10, 0]}
        response = await compute_client.post(url, json=params)
        assert response.status_code == status.HTTP_201_CREATED

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        params["filters"] = {"packet_loss": [10]}
        params["markers"] = {}
        url = app.url_path_for(
            "compute:update_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        response = await compute_client.put(url, json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["filters"] == {"packet_loss": [10]}

        # update_nio re-applies the filters on the port's uBridge relay
        relay = node._ubridge_bridge_name(0)
        node._ubridge_send.assert_any_call(f"bridge reset_packet_filters {relay}")

    async def test_ethernet_switch_toggle_marker(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        # a marker installed via the NIO registers in the node's filter-bridge map
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        params = self._udp_params()
        params["markers"] = {"icmp": {"bpf": "icmp", "link_id": "link-1", "enabled": True}}
        response = await compute_client.post(url, json=params)
        assert response.status_code == status.HTTP_201_CREATED

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        url = app.url_path_for(
            "compute:toggle_ethernet_switch_marker",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            marker_name="icmp"
        )
        response = await compute_client.put(url, json={"enabled": False})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"marker_name": "icmp", "enabled": False}
        relay = node._ubridge_bridge_name(0)
        node._ubridge_send.assert_any_call(f"bridge enable_packet_filter {relay} icmp off")

        # toggling an unknown marker is a 404
        url = app.url_path_for(
            "compute:toggle_ethernet_switch_marker",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            marker_name="nope"
        )
        response = await compute_client.put(url, json={"enabled": True})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_ethernet_switch_start_capture(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        # capture needs a wired port
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0"
        )
        await compute_client.post(url, json=self._udp_params())

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        params = {"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
        url = app.url_path_for("compute:start_ethernet_switch_capture",
                               project_id=ethernet_switch["project_id"],
                               node_id=ethernet_switch["node_id"],
                               adapter_number="0",
                               port_number="0")

        response = await compute_client.post(url, json=params)
        assert response.status_code == status.HTTP_200_OK
        assert "test.pcap" in response.json()["pcap_file_path"]
        relay = f"{node.id}-0"
        node._ubridge_send.assert_any_call(f'bridge start_capture {relay} "{node.get_nio(0).pcap_output_file}"')

    async def test_ethernet_switch_stop_capture(
            self,
            app: FastAPI,
            compute_client: AsyncClient,
            compute_project: Project,
            ethernet_switch: dict
    ) -> None:

        # start a capture first
        await compute_client.post(
            app.url_path_for(
                "compute:create_ethernet_switch_nio",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number="0"
            ),
            json=self._udp_params()
        )
        await compute_client.post(
            app.url_path_for("compute:start_ethernet_switch_capture",
                             project_id=ethernet_switch["project_id"],
                             node_id=ethernet_switch["node_id"],
                             adapter_number="0",
                             port_number="0"),
            json={"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
        )

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()
        relay = f"{node.id}-0"

        response = await compute_client.post(
            app.url_path_for("compute:stop_ethernet_switch_capture",
                             project_id=ethernet_switch["project_id"],
                             node_id=ethernet_switch["node_id"],
                             adapter_number="0",
                             port_number="0")
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        node._ubridge_send.assert_any_call(f"bridge stop_capture {relay}")
