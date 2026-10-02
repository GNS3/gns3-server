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

import os
from unittest.mock import MagicMock, call, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.compute.project import Project
from tests.utils import asyncio_patch

# The builtin Ethernet switch talks to uBridge (brctl/bridge modules) instead of
# the Dynamips hypervisor. These are the seams we stub so the routes can be
# exercised without launching a real uBridge / creating kernel interfaces.
_NODE = "gns3server.compute.builtin.nodes.ethernet_switch.EthernetSwitch"

pytestmark = pytest.mark.asyncio


class TestEthernetSwitchNodesRoutes:
    @pytest_asyncio.fixture(autouse=True)
    async def stub_ubridge(self):
        """Keep uBridge from really starting and capture every command."""
        with (
            asyncio_patch(f"{_NODE}._start_ubridge"),
            asyncio_patch(f"{_NODE}._stop_ubridge"),
            asyncio_patch(f"{_NODE}._ubridge_send"),
        ):
            yield

    @pytest_asyncio.fixture
    async def ethernet_switch(self, app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> dict:

        params = {"name": "Ethernet Switch"}
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id), json=params
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
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project
    ) -> None:

        params = {"name": "Ethernet Switch 1"}
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id), json=params
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "Ethernet Switch 1"
        assert response.json()["project_id"] == compute_project.id
        assert response.json()["status"] == "started"

        # creation stands up the kernel bridge with VLAN filtering
        node = compute_project.get_node(response.json()["node_id"])
        br = node._bridge_name
        node._ubridge_send.assert_has_calls(
            [
                call(f'brctl delete "{br}"'),
                call(f'brctl create "{br}"'),
                call(f'link set "{br}" up'),
                call(f'brctl vlanfiltering "{br}" on'),
            ]
        )

    async def test_ethernet_switch_get(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        response = await compute_client.get(
            app.url_path_for(
                "compute:get_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            )
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Ethernet Switch"
        assert response.json()["project_id"] == compute_project.id
        assert response.json()["status"] == "started"

    async def test_ethernet_switch_duplicate(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        # create destination switch first
        params = {"name": "Ethernet Switch 2"}
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id), json=params
        )
        assert response.status_code == status.HTTP_201_CREATED

        params = {"destination_node_id": response.json()["node_id"]}
        response = await compute_client.post(
            app.url_path_for(
                "compute:duplicate_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            ),
            json=params,
        )
        assert response.status_code == status.HTTP_201_CREATED

    async def test_ethernet_switch_update(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        params = {"name": "test", "console_type": "none"}

        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            ),
            json=params,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "test"
        # renaming a builtin switch does not touch uBridge (the kernel bridge is
        # name-independent); nothing should have been sent.
        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.assert_not_called()

    async def test_ethernet_switch_update_ports_qinq_proto(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
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
                node_id=ethernet_switch["node_id"],
            ),
            json=port_params,
        )
        assert response.status_code == status.HTTP_200_OK

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.assert_any_call(f'brctl setvlanproto "{node._bridge_name}" 0x88a8')

    @pytest.mark.parametrize(
        "ports_settings",
        (
            {"name": "Ethernet0", "port_number": 0, "type": "dot42q", "vlan": 1},  # bad type
            {"name": "Ethernet0", "port_number": 0, "type": "access"},  # missing vlan
            {
                "name": "Ethernet0",
                "port_number": 0,
                "type": "dot1q",
                "vlan": 1,
                "ethertype": "0x88A8",
            },  # ethertype only for qinq
            {"name": "Ethernet0", "port_number": 0, "type": "qinq", "vlan": 1, "ethertype": "0x4242"},  # bad ethertype
            {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 0},  # vlan < 1
            {"name": "Ethernet0", "port_number": 0, "type": "access", "vlan": 4242},  # vlan > 4094
        ),
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
                node_id=ethernet_switch["node_id"],
            ),
            json={"ports_mapping": [ports_settings]},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_ethernet_switch_delete(
        self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict
    ) -> None:

        response = await compute_client.delete(
            app.url_path_for(
                "compute:delete_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_ethernet_switch_start(
        self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict
    ) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:start_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_stop(self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:stop_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_suspend(
        self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict
    ) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:suspend_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_reload(
        self, app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict
    ) -> None:

        response = await compute_client.post(
            app.url_path_for(
                "compute:reload_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            )
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    async def test_ethernet_switch_create_udp_access(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
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
        node._ubridge_send.assert_has_calls(
            [
                call(f"bridge create {relay}"),
                call(f'bridge add_nio_tap {relay} "{tap}"'),
                call(f'brctl addif "{br}" "{tap}"'),
                call(f'brctl vlan_del "{br}" "{tap}" 1'),
                call(f'brctl vlan_add "{br}" "{tap}" 1 pvid untagged'),
                call(f"bridge add_nio_udp {relay} {nio.lport} {nio.rhost} {nio.rport}"),
                call(f"bridge reset_packet_filters {relay}"),
                call(f"bridge start {relay}"),
            ]
        )

    async def test_ethernet_switch_create_udp_dot1q(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        # make port 0 a dot1q trunk with native VLAN 10
        await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            ),
            json={
                "ports_mapping": [
                    {"name": "Ethernet0", "port_number": 0, "type": "dot1q", "vlan": 10},
                ]
            },
        )
        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        response = await compute_client.post(url, json=self._udp_params())
        assert response.status_code == status.HTTP_201_CREATED

        br = node._bridge_name
        tap = f"{br}-0"
        # trunk: drop default 1, admit all VIDs tagged, mark native 10 PVID/untagged
        node._ubridge_send.assert_has_calls(
            [
                call(f'brctl vlan_del "{br}" "{tap}" 1'),
                call(f'brctl vlan_add "{br}" "{tap}" 1 vid 4094'),
                call(f'brctl vlan_add "{br}" "{tap}" 10 pvid untagged'),
            ]
        )

    async def test_ethernet_switch_delete_nio(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        await compute_client.post(url, json=self._udp_params())

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        url = app.url_path_for(
            "compute:delete_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        response = await compute_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # the port's relay bridge and TAP are released from the kernel bridge
        br = node._bridge_name
        tap = f"{br}-0"
        relay = f"{node.id}-0"
        node._ubridge_send.assert_has_calls(
            [
                call(f'brctl delif "{br}" "{tap}"'),
                call(f"bridge delete {relay}"),
            ]
        )

    async def test_ethernet_switch_update_nio(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
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
            port_number="0",
        )
        response = await compute_client.put(url, json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["filters"] == {"packet_loss": [10]}

        # update_nio re-applies the filters on the port's uBridge relay
        relay = node._ubridge_bridge_name(0)
        node._ubridge_send.assert_any_call(f"bridge reset_packet_filters {relay}")

    async def test_ethernet_switch_toggle_marker(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        # a marker installed via the NIO registers in the node's filter-bridge map
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
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
            marker_name="icmp",
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
            marker_name="nope",
        )
        response = await compute_client.put(url, json={"enabled": True})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_ethernet_switch_start_capture(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        # capture needs a wired port
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        await compute_client.post(url, json=self._udp_params())

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        params = {"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"}
        url = app.url_path_for(
            "compute:start_ethernet_switch_capture",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )

        response = await compute_client.post(url, json=params)
        assert response.status_code == status.HTTP_200_OK
        assert "test.pcap" in response.json()["pcap_file_path"]
        relay = f"{node.id}-0"
        node._ubridge_send.assert_any_call(f'bridge start_capture {relay} "{node.get_nio(0).pcap_output_file}"')

    async def test_ethernet_switch_stop_capture(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:

        # start a capture first
        await compute_client.post(
            app.url_path_for(
                "compute:create_ethernet_switch_nio",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number="0",
            ),
            json=self._udp_params(),
        )
        await compute_client.post(
            app.url_path_for(
                "compute:start_ethernet_switch_capture",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number="0",
            ),
            json={"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"},
        )

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()
        relay = f"{node.id}-0"

        response = await compute_client.post(
            app.url_path_for(
                "compute:stop_ethernet_switch_capture",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number="0",
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        node._ubridge_send.assert_any_call(f"bridge stop_capture {relay}")

    # ------------------------------------------------------------------ #
    # kernel datapath: absorbed anchors (nio_anchor)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _anchor_params(anchor: str = "gv00010203e0p0", **extra) -> dict:
        params = {"type": "nio_anchor", "anchor": anchor}
        params.update(extra)
        return params

    @staticmethod
    def _sysfs(anchor_exists: bool = True, bridge_member: bool = True):
        """An ``os.path.exists`` that answers the /sys/class/net probes of the
        kernel-port wiring, delegating everything else to the real one."""
        real = os.path.exists

        def fake(path):
            value = str(path)
            if "/brif/" in value:
                return bridge_member
            if value.startswith("/sys/class/net/"):
                return anchor_exists
            return real(path)

        return patch("os.path.exists", new=fake)

    async def test_ethernet_switch_create_anchor_nio(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        A kernel link joins the peer's anchor straight to the switch bridge
        with the port's VLAN mode applied — no relay, no per-port TAP.
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=True):
            response = await compute_client.post(url, json=self._anchor_params(anchor))
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["type"] == "nio_anchor"

        node = compute_project.get_node(ethernet_switch["node_id"])
        br = node._bridge_name
        # access VLAN 1 (default): the anchor replaces the port TAP as the
        # bridge port, so it carries the port's membership
        node._ubridge_send.assert_any_call(f'brctl addif "{br}" "{anchor}"')
        node._ubridge_send.assert_any_call(f'brctl vlan_del "{br}" "{anchor}" 1')
        node._ubridge_send.assert_any_call(f'brctl vlan_add "{br}" "{anchor}" 1 pvid untagged')
        node._ubridge_send.assert_any_call(f'link set "{anchor}" up')
        # no relay was created for this port
        assert not any("bridge create" in str(c) for c in node._ubridge_send.call_args_list)
        assert node._kernel_ports[0] == anchor
        assert node.get_nio(0).anchor == anchor

    async def test_ethernet_switch_create_anchor_nio_defers_when_anchor_missing(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        The peer's anchor only exists while the peer runs: a link created
        against a stopped peer must not fail (nor stop the switch's
        uBridge) — the join is deferred to the re-push after the peer
        starts.
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=False):
            response = await compute_client.post(url, json=self._anchor_params(anchor))
        assert response.status_code == status.HTTP_201_CREATED

        node = compute_project.get_node(ethernet_switch["node_id"])
        assert node._kernel_ports[0] == anchor
        assert node.get_nio(0).anchor == anchor
        assert not any("addif" in str(c) for c in node._ubridge_send.call_args_list)
        assert not any("brctl" in str(c) for c in node._ubridge_send.call_args_list)

    async def test_ethernet_switch_update_anchor_nio_reconciles(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        Updating a joined kernel port reconciles on the anchor: tc
        impairments, markers and the carrier the suspend flag drives.
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=True):
            await compute_client.post(url, json=self._anchor_params(anchor))

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        update_url = app.url_path_for(
            "compute:update_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=True, bridge_member=True):
            response = await compute_client.put(
                update_url, json=self._anchor_params(anchor, filters={"delay": [10]}, suspend=True)
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["suspend"] is True

        node._ubridge_send.assert_any_call(f'tc reset "{anchor}"')
        node._ubridge_send.assert_any_call(f'tc netem set "{anchor}" delay 10')
        node._ubridge_send.assert_any_call(f'link set "{anchor}" down')
        # no re-join on a plain reconcile
        assert not any("addif" in str(c) for c in node._ubridge_send.call_args_list)

    async def test_ethernet_switch_update_anchor_nio_completes_deferred_join(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        The controller re-pushes the switch NIO once the peer starts: a join
        deferred at link creation completes (the anchor exists but is not a
        bridge member), and a peer restart that replaced its anchor under
        the same name re-joins.
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=False):
            await compute_client.post(url, json=self._anchor_params(anchor))

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        update_url = app.url_path_for(
            "compute:update_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        # the anchor exists now (peer started) but is not a bridge member
        with self._sysfs(anchor_exists=True, bridge_member=False):
            response = await compute_client.put(update_url, json=self._anchor_params(anchor))
        assert response.status_code == status.HTTP_201_CREATED

        br = node._bridge_name
        node._ubridge_send.assert_any_call(f'brctl addif "{br}" "{anchor}"')
        node._ubridge_send.assert_any_call(f'brctl vlan_add "{br}" "{anchor}" 1 pvid untagged')
        node._ubridge_send.assert_any_call(f'link set "{anchor}" up')

    async def test_ethernet_switch_delete_anchor_nio(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        Removing a kernel link resets the anchor's qdisc, takes it out of
        the switch bridge and drops its carrier — the anchor itself survives
        (it belongs to the peer).
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=True):
            await compute_client.post(url, json=self._anchor_params(anchor))

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        with self._sysfs(anchor_exists=True):
            response = await compute_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        br = node._bridge_name
        node._ubridge_send.assert_any_call(f'tc reset "{anchor}"')
        node._ubridge_send.assert_any_call(f'brctl delif "{br}" "{anchor}"')
        node._ubridge_send.assert_any_call(f'link set "{anchor}" down')
        assert 0 not in node._kernel_ports
        assert 0 not in node._nios

    async def test_ethernet_switch_capture_anchor_nio(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        Capture on a kernel port runs on the absorbed anchor (AF_PACKET),
        not on a relay.
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=True):
            await compute_client.post(url, json=self._anchor_params(anchor))

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        response = await compute_client.post(
            app.url_path_for(
                "compute:start_ethernet_switch_capture",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number="0",
            ),
            json={"capture_file_name": "test.pcap", "data_link_type": "DLT_EN10MB"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert any(
            c.args and str(c.args[0]).startswith(f'capture start_kernel {anchor} "')
            for c in node._ubridge_send.call_args_list
        ), node._ubridge_send.call_args_list

        response = await compute_client.post(
            app.url_path_for(
                "compute:stop_ethernet_switch_capture",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number="0",
            )
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        node._ubridge_send.assert_any_call("capture stop_kernel")

    async def test_ethernet_switch_batch_create_anchor_nio(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        The project-open batch endpoint accepts anchor NIOs (a reopen must
        not 422 the switch's kernel links).
        """

        anchor = "gv00010203e0p3"
        params = {
            "nios": [
                {
                    "node_id": ethernet_switch["node_id"],
                    "adapter_number": 0,
                    "port_number": 3,
                    "nio": {"type": "nio_anchor", "anchor": anchor},
                }
            ]
        }
        with self._sysfs(anchor_exists=False):
            response = await compute_client.post(
                app.url_path_for("compute:create_batch_nios", project_id=compute_project.id), json=params
            )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["added"] == 1

        node = compute_project.get_node(ethernet_switch["node_id"])
        assert node._kernel_ports[3] == anchor

    # ------------------------------------------------------------------ #
    # switch-to-switch cascade: one veth pair joins the two bridges
    # ------------------------------------------------------------------ #

    @staticmethod
    def _cascade_params(anchor: str, peer: str) -> dict:
        return {"type": "nio_anchor", "anchor": anchor, "peer": peer}

    def _cascade_sysfs(self, anchor: str, exists: dict):
        """An ``os.path.exists`` whose answer for *one* interface flips with
        the ``exists`` flag — for the create-race test, where the pair comes
        into being between the pre-check and the failed create."""
        real = os.path.exists

        def fake(path):
            value = str(path)
            if value == f"/sys/class/net/{anchor}":
                return exists["value"]
            if "/brif/" in value:
                return True
            if value.startswith("/sys/class/net/"):
                return True
            return real(value)

        return patch("os.path.exists", new=fake)

    async def test_ethernet_switch_create_cascade_nio_creates_the_pair(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        A cascade port is one end of a link-owned veth pair: the switch
        creates the pair (uBridge's docker create_veth — the same primitive
        every Docker adapter is born from) and enslaves its own end into its
        bridge with the port's VLAN mode, exactly like an absorbed anchor.
        """

        anchor, peer = "gs1a2b3c4d5e0", "gs1a2b3c4d5e1"
        node = compute_project.get_node(ethernet_switch["node_id"])
        exists = {"value": False}

        async def create_the_pair(command):
            if "create_veth" in str(command):
                exists["value"] = True

        node._ubridge_send.side_effect = create_the_pair

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._cascade_sysfs(anchor, exists):
            response = await compute_client.post(url, json=self._cascade_params(anchor, peer))
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["peer"] == peer

        node = compute_project.get_node(ethernet_switch["node_id"])
        br = node._bridge_name
        node._ubridge_send.assert_any_call(f'docker create_veth "{anchor}" "{peer}"')
        node._ubridge_send.assert_any_call(f'brctl addif "{br}" "{anchor}"')
        node._ubridge_send.assert_any_call(f'brctl vlan_add "{br}" "{anchor}" 1 pvid untagged')
        node._ubridge_send.assert_any_call(f'link set "{anchor}" up')
        assert node._kernel_ports[0] == anchor
        assert node._cascade_peers[0] == peer

    async def test_ethernet_switch_create_cascade_nio_reuses_an_existing_pair(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        An existing end (this switch restarted, or a leftover from a previous
        life of this link id) is reused as-is: the other end may still be a
        live port of the peer switch, so the pair is never destroyed here —
        a stale tc qdisc is all a reused end can carry, and the reset clears
        it before the join.
        """

        anchor, peer = "gs1a2b3c4d5e0", "gs1a2b3c4d5e1"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._cascade_sysfs(anchor, {"value": True}):
            response = await compute_client.post(url, json=self._cascade_params(anchor, peer))
        assert response.status_code == status.HTTP_201_CREATED

        node = compute_project.get_node(ethernet_switch["node_id"])
        br = node._bridge_name
        node._ubridge_send.assert_any_call(f'tc reset "{anchor}"')
        node._ubridge_send.assert_any_call(f'brctl addif "{br}" "{anchor}"')
        assert not any("create_veth" in str(c) for c in node._ubridge_send.call_args_list)

    async def test_ethernet_switch_create_cascade_nio_lost_create_race(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        Both cascade sides create the pair when their end is missing, so the
        two uBridge processes can race: the loser's create fails with
        "exists", the kernel re-check shows the pair is there, and the join
        proceeds — a lost race is not an error.
        """

        from gns3server.compute.ubridge.ubridge_error import UbridgeError

        anchor, peer = "gs1a2b3c4d5e0", "gs1a2b3c4d5e1"
        node = compute_project.get_node(ethernet_switch["node_id"])
        exists = {"value": False}

        async def lose_the_race(command):
            if "create_veth" in str(command):
                # the peer switch's create won between our pre-check and now
                exists["value"] = True
                raise UbridgeError("202-interface already exists")

        node._ubridge_send.side_effect = lose_the_race

        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._cascade_sysfs(anchor, exists):
            response = await compute_client.post(url, json=self._cascade_params(anchor, peer))
        assert response.status_code == status.HTTP_201_CREATED

        br = node._bridge_name
        node._ubridge_send.assert_any_call(f'brctl addif "{br}" "{anchor}"')
        assert node._kernel_ports[0] == anchor

    async def test_ethernet_switch_create_cascade_nio_hardens_own_end_l2only(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        ``docker create_veth`` hardens only its FIRST end (the Docker shape:
        host anchor plus a container leg that keeps its L3 life) — but a
        cascade end the peer's winning create minted is that second,
        unhardened end, and the kernel gives it an IPv6 link-local (a silent
        L3 identity on the switch fabric, ubridge-l2-anchor-spec §E). Each
        switch therefore hardens its OWN end once the pair exists, whatever
        branch brought it there (fresh create, lost race, reuse).
        """

        anchor, peer = "gs1a2b3c4d5e0", "gs1a2b3c4d5e1"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        # pre-existing end: the branch whose end create_veth did NOT harden
        with self._cascade_sysfs(anchor, {"value": True}):
            response = await compute_client.post(url, json=self._cascade_params(anchor, peer))
        assert response.status_code == status.HTTP_201_CREATED

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.assert_any_call(f'link l2only "{anchor}" on')
        # only its own end — the peer's end is the peer switch's to harden
        assert not any(f'"{peer}"' in str(c) and "l2only" in str(c) for c in node._ubridge_send.call_args_list)

    async def test_ethernet_switch_delete_cascade_nio_destroys_the_pair(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        The cascade pair dies with the link: the teardown detaches the link
        state, delifs the end, and destroys the pair (deleting one veth end
        takes the peer end with it — either side's teardown converges on the
        same gone pair).
        """

        anchor, peer = "gs1a2b3c4d5e0", "gs1a2b3c4d5e1"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._cascade_sysfs(anchor, {"value": True}):
            await compute_client.post(url, json=self._cascade_params(anchor, peer))

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        response = await compute_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        br = node._bridge_name
        node._ubridge_send.assert_any_call(f'brctl delif "{br}" "{anchor}"')
        node._ubridge_send.assert_any_call(f'docker delete_veth "{anchor}"')
        assert node._kernel_ports == {}
        assert node._cascade_peers == {}

    # ------------------------------------------------------------------ #
    # in-place VLAN reconfiguration (no port ever leaves the bridge)
    # ------------------------------------------------------------------ #

    async def test_ethernet_switch_update_ports_reconfigures_in_place(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        Changing a wired port's VLAN edits its membership in place: delete the
        old membership, add the new one — the port is never detached from the
        bridge (a relay TAP here; the TAP is the cloud/relay-side port).
        """

        node = compute_project.get_node(ethernet_switch["node_id"])
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        await compute_client.post(url, json=self._udp_params())
        node._ubridge_send.reset_mock()

        ports = [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1} for i in range(8)]
        ports[0]["vlan"] = 10
        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            ),
            json={"ports_mapping": ports},
        )
        assert response.status_code == status.HTTP_200_OK

        br = node._bridge_name
        tap = f"{br}-0"
        commands = [c.args[0] for c in node._ubridge_send.call_args_list]
        assert commands == [
            f'brctl vlan_del "{br}" "{tap}" 1',
            f'brctl vlan_add "{br}" "{tap}" 10 pvid untagged',
        ], commands
        assert not any("delif" in c or "addif" in c for c in commands)

    async def test_ethernet_switch_update_ports_leaves_untouched_ports_alone(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        Only ports whose mode/VLAN changed are touched: re-saving the mapping
        no longer re-programs every wired port.
        """

        node = compute_project.get_node(ethernet_switch["node_id"])
        for port_number in (0, 1):
            url = app.url_path_for(
                "compute:create_ethernet_switch_nio",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
                adapter_number="0",
                port_number=str(port_number),
            )
            await compute_client.post(url, json=self._udp_params())
        node._ubridge_send.reset_mock()

        ports = [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1} for i in range(8)]
        ports[1]["vlan"] = 20
        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            ),
            json={"ports_mapping": ports},
        )
        assert response.status_code == status.HTTP_200_OK

        br = node._bridge_name
        commands = [c.args[0] for c in node._ubridge_send.call_args_list]
        assert commands == [
            f'brctl vlan_del "{br}" "{br}-1" 1',
            f'brctl vlan_add "{br}" "{br}-1" 20 pvid untagged',
        ], commands
        assert not any(f'"{br}-0"' in c for c in commands)

    async def test_ethernet_switch_vlan_transition_table(self, compute_project: Project, ethernet_switch: dict) -> None:
        """
        Every mode transition is expressed as in-place VLAN edits: the old
        mode's entries the new mode does not want, then the new mode's
        entries. The dot1q admits-all entry is one range operation in both
        directions, and same-to-same emits nothing.
        """

        node = compute_project.get_node(ethernet_switch["node_id"])
        br = node._bridge_name
        iface = "gvdeadbeef0p0"

        cases = [
            (
                {"type": "access", "vlan": 10},
                {"type": "dot1q", "vlan": 20},
                [
                    f'brctl vlan_del "{br}" "{iface}" 10',
                    f'brctl vlan_add "{br}" "{iface}" 1 vid 4094',
                    f'brctl vlan_add "{br}" "{iface}" 20 pvid untagged',
                ],
            ),
            (
                {"type": "dot1q", "vlan": 20},
                {"type": "access", "vlan": 30},
                [
                    f'brctl vlan_del "{br}" "{iface}" 1 vid 4094',
                    f'brctl vlan_add "{br}" "{iface}" 30 pvid untagged',
                ],
            ),
            (
                {"type": "dot1q", "vlan": 20},
                {"type": "dot1q", "vlan": 30},
                [
                    f'brctl vlan_del "{br}" "{iface}" 20',
                    f'brctl vlan_add "{br}" "{iface}" 30 pvid untagged',
                ],
            ),
            (
                {"type": "qinq", "vlan": 2},
                {"type": "dot1q", "vlan": 5},
                [
                    f'brctl vlan_del "{br}" "{iface}" 2',
                    f'brctl vlan_add "{br}" "{iface}" 1 vid 4094',
                    f'brctl vlan_add "{br}" "{iface}" 5 pvid untagged',
                ],
            ),
            (
                {"type": "dot1q", "vlan": 5},
                {"type": "qinq", "vlan": 2},
                [
                    f'brctl vlan_del "{br}" "{iface}" 1 vid 4094',
                    f'brctl vlan_add "{br}" "{iface}" 2 pvid untagged',
                ],
            ),
            (
                {"type": "access", "vlan": 10},
                {"type": "qinq", "vlan": 2},
                [
                    f'brctl vlan_del "{br}" "{iface}" 10',
                    f'brctl vlan_add "{br}" "{iface}" 2 pvid untagged',
                ],
            ),
            (
                {"type": "qinq", "vlan": 2},
                {"type": "access", "vlan": 10},
                [
                    f'brctl vlan_del "{br}" "{iface}" 2',
                    f'brctl vlan_add "{br}" "{iface}" 10 pvid untagged',
                ],
            ),
            (
                {"type": "qinq", "vlan": 2},
                {"type": "qinq", "vlan": 9},
                [
                    f'brctl vlan_del "{br}" "{iface}" 2',
                    f'brctl vlan_add "{br}" "{iface}" 9 pvid untagged',
                ],
            ),
            (
                {"type": "access", "vlan": 7},
                {"type": "access", "vlan": 7},
                [],
            ),
        ]
        for old_settings, new_settings, expected in cases:
            node._ubridge_send.reset_mock()
            await node._reconfigure_port_vlan(iface, old_settings, new_settings)
            commands = [c.args[0] for c in node._ubridge_send.call_args_list]
            assert commands == expected, (old_settings, new_settings, commands)
            assert not any("delif" in c or "addif" in c for c in commands)

    async def test_ethernet_switch_update_ports_reconfigures_absorbed_anchor_in_place(
        self, app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict
    ) -> None:
        """
        The same in-place reconcile applies to an absorbed kernel anchor (a
        peer node's interface): a ports_mapping update issues VLAN edits on
        it and never detaches it from the bridge.
        """

        anchor = "gv00010203e0p0"
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number="0",
        )
        with self._sysfs(anchor_exists=True):
            await compute_client.post(url, json=self._anchor_params(anchor))

        node = compute_project.get_node(ethernet_switch["node_id"])
        node._ubridge_send.reset_mock()

        ports = [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1} for i in range(8)]
        ports[0]["vlan"] = 10
        response = await compute_client.put(
            app.url_path_for(
                "compute:update_ethernet_switch",
                project_id=ethernet_switch["project_id"],
                node_id=ethernet_switch["node_id"],
            ),
            json={"ports_mapping": ports},
        )
        assert response.status_code == status.HTTP_200_OK

        br = node._bridge_name
        commands = [c.args[0] for c in node._ubridge_send.call_args_list]
        assert commands == [
            f'brctl vlan_del "{br}" "{anchor}" 1',
            f'brctl vlan_add "{br}" "{anchor}" 10 pvid untagged',
        ], commands
        assert not any("delif" in c or "addif" in c for c in commands)
