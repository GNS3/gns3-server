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
from unittest.mock import call

from gns3server.compute.project import Project

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def ethernet_switch(app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> dict:

    params = {"name": "Ethernet Switch"}
    with asyncio_patch("gns3server.compute.dynamips.nodes.ethernet_switch.EthernetSwitch.create") as mock:
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id),
            json=params
        )
        assert mock.called
        assert response.status_code == status.HTTP_201_CREATED

    json_response = response.json()
    node = compute_project.get_node(json_response["node_id"])
    node._hypervisor = AsyncioMagicMock()
    node._hypervisor.send = AsyncioMagicMock()
    node._hypervisor.version = "0.2.16"
    return json_response


async def test_ethernet_switch_create(app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> None:

    params = {"name": "Ethernet Switch 1"}
    with asyncio_patch("gns3server.compute.dynamips.nodes.ethernet_switch.EthernetSwitch.create") as mock:
        response = await compute_client.post(
            app.url_path_for("compute:create_ethernet_switch", project_id=compute_project.id),
            json=params
        )
        assert mock.called
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "Ethernet Switch 1"
        assert response.json()["project_id"] == compute_project.id


async def test_ethernet_switch_get(app: FastAPI, compute_client: AsyncClient, compute_project: Project, ethernet_switch: dict) -> None:

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
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        ethernet_switch: dict
) -> None:

    # create destination switch first
    params = {"name": "Ethernet Switch 2"}
    with asyncio_patch("gns3server.compute.dynamips.nodes.ethernet_switch.EthernetSwitch.create") as mock:
        response = await compute_client.post(
            app.url_path_for(
                "compute:create_ethernet_switch",
                project_id=compute_project.id),
            json=params
        )
        assert mock.called
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
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        ethernet_switch: dict
) -> None:

    params = {
        "name": "test",
        "console_type": "telnet"
    }

    response = await compute_client.put(
        app.url_path_for(
            "compute:update_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"]),
        json=params
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "test"
    node = compute_project.get_node(ethernet_switch["node_id"])
    node._hypervisor.send.assert_called_with("ethsw rename \"Ethernet Switch\" \"test\"")


async def test_ethernet_switch_update_ports(
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        ethernet_switch: dict
) -> None:

    port_params = {
        "ports_mapping": [
            {
                "name": "Ethernet0",
                "port_number": 0,
                "type": "qinq",
                "vlan": 1
            },
            {
                "name": "Ethernet1",
                "port_number": 1,
                "type": "qinq",
                "vlan": 2,
                "ethertype": "0x88A8"
            },
            {
                "name": "Ethernet2",
                "port_number": 2,
                "type": "dot1q",
                "vlan": 3,
            },
            {
                "name": "Ethernet3",
                "port_number": 3,
                "type": "access",
                "vlan": 4,
            }
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

    nio_params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    for port_mapping in port_params["ports_mapping"]:
        port_number = port_mapping["port_number"]
        vlan = port_mapping["vlan"]
        port_type = port_mapping["type"]
        ethertype = port_mapping.get("ethertype", "")
        url = app.url_path_for(
            "compute:create_ethernet_switch_nio",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"],
            adapter_number="0",
            port_number=f"{port_number}"
        )
        await compute_client.post(url, json=nio_params)

        node = compute_project.get_node(ethernet_switch["node_id"])
        nio = node.get_nio(port_number)
        calls = [
            call.send(f'nio create_udp {nio.name} 4242 127.0.0.1 4343'),
            call.send(f'ethsw add_nio "Ethernet Switch" {nio.name}'),
            call.send(f'ethsw set_{port_type}_port "Ethernet Switch" {nio.name} {vlan} {ethertype}'.strip())
        ]
        node._hypervisor.send.assert_has_calls(calls)
        node._hypervisor.send.reset_mock()


@pytest.mark.parametrize(
    "ports_settings",
    (
            (
                    {
                        "name": "Ethernet0",
                        "port_number": 0,
                        "type": "dot42q",  # invalid port type
                        "vlan": 1,
                    }
            ),
            (
                    {
                        "name": "Ethernet0",
                        "port_number": 0,
                        "type": "access",  # missing vlan field
                    }
            ),
            (
                    {
                        "name": "Ethernet0",
                        "port_number": 0,
                        "type": "dot1q",
                        "vlan": 1,
                        "ethertype": "0x88A8"  # EtherType is only for QinQ
                    }
            ),
            (
                    {
                        "name": "Ethernet0",
                        "port_number": 0,
                        "type": "qinq",
                        "vlan": 1,
                        "ethertype": "0x4242"  # not a valid EtherType
                    }
            ),
            (
                    {
                        "name": "Ethernet0",
                        "port_number": 0,
                        "type": "access",
                        "vlan": 0,  # minimum vlan number is 1
                    }
            ),
            (
                    {
                        "name": "Ethernet0",
                        "port_number": 0,
                        "type": "access",
                        "vlan": 4242,  # maximum vlan number is 4094
                    }
            ),
    )
)
async def test_ethernet_switch_update_ports_invalid(
        app: FastAPI,
        compute_client: AsyncClient,
        ethernet_switch: dict,
        ports_settings: dict,
) -> None:

    port_params = {
        "ports_mapping": [ports_settings]
    }

    response = await compute_client.put(
        app.url_path_for(
            "compute:update_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"]),
        json=port_params
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_ethernet_switch_delete(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    response = await compute_client.delete(
        app.url_path_for(
            "compute:delete_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"]
        )
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ethernet_switch_start(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    response = await compute_client.post(
        app.url_path_for(
            "compute:start_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"])
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ethernet_switch_stop(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    response = await compute_client.post(
        app.url_path_for(
            "compute:stop_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"])
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ethernet_switch_suspend(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    response = await compute_client.post(
        app.url_path_for(
            "compute:suspend_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"])
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ethernet_switch_reload(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    response = await compute_client.post(
        app.url_path_for(
            "compute:reload_ethernet_switch",
            project_id=ethernet_switch["project_id"],
            node_id=ethernet_switch["node_id"])
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_ethernet_switch_create_udp(
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        ethernet_switch: dict
) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for(
        "compute:create_ethernet_switch_nio",
        project_id=ethernet_switch["project_id"],
        node_id=ethernet_switch["node_id"],
        adapter_number="0",
        port_number="0"
    )
    response = await compute_client.post(url, json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["type"] == "nio_udp"

    node = compute_project.get_node(ethernet_switch["node_id"])
    nio = node.get_nio(0)
    calls = [
        call.send(f'nio create_udp {nio.name} 4242 127.0.0.1 4343'),
        call.send(f'ethsw add_nio "Ethernet Switch" {nio.name}'),
        call.send(f'ethsw set_access_port "Ethernet Switch" {nio.name} 1')
    ]
    node._hypervisor.send.assert_has_calls(calls)


async def test_ethernet_switch_delete_nio(
        app: FastAPI,
        compute_client: AsyncClient,
        compute_project: Project,
        ethernet_switch: dict
) -> None:

    params = {
        "type": "nio_udp",
        "lport": 4242,
        "rport": 4343,
        "rhost": "127.0.0.1"
    }

    url = app.url_path_for(
        "compute:create_ethernet_switch_nio",
        project_id=ethernet_switch["project_id"],
        node_id=ethernet_switch["node_id"],
        adapter_number="0",
        port_number="0"
    )
    await compute_client.post(url, json=params)

    node = compute_project.get_node(ethernet_switch["node_id"])
    node._hypervisor.send.reset_mock()
    nio = node.get_nio(0)

    url = app.url_path_for(
        "compute:delete_ethernet_switch_nio",
        project_id=ethernet_switch["project_id"],
        node_id=ethernet_switch["node_id"],
        adapter_number="0",
        port_number="0"
    )
    response = await compute_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    calls = [
        call(f'ethsw remove_nio "Ethernet Switch" {nio.name}'),
        call(f'nio delete {nio.name}')
    ]
    node._hypervisor.send.assert_has_calls(calls)


async def test_ethernet_switch_start_capture(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    params = {
        "capture_file_name": "test.pcap",
        "data_link_type": "DLT_EN10MB"
    }

    url = app.url_path_for("compute:start_ethernet_switch_capture",
                           project_id=ethernet_switch["project_id"],
                           node_id=ethernet_switch["node_id"],
                           adapter_number="0",
                           port_number="0")

    with asyncio_patch("gns3server.compute.dynamips.nodes.ethernet_switch.EthernetSwitch.start_capture") as mock:
        response = await compute_client.post(url, json=params)
        assert response.status_code == status.HTTP_200_OK
        assert mock.called
        assert "test.pcap" in response.json()["pcap_file_path"]


async def test_ethernet_switch_stop_capture(app: FastAPI, compute_client: AsyncClient, ethernet_switch: dict) -> None:

    url = app.url_path_for("compute:stop_ethernet_switch_capture",
                           project_id=ethernet_switch["project_id"],
                           node_id=ethernet_switch["node_id"],
                           adapter_number="0",
                           port_number="0")

    with asyncio_patch("gns3server.compute.dynamips.nodes.ethernet_switch.EthernetSwitch.stop_capture") as mock:
        response = await compute_client.post(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert mock.called
