#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

import uuid
from typing import Tuple
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller.compute import Compute
from gns3server.controller.link import FILTERS, Link
from gns3server.controller.node import Node
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.project import Project
from gns3server.controller.udp_link import UDPLink
from tests.utils import AsyncioMagicMock, asyncio_patch

pytestmark = pytest.mark.asyncio


class TestLinkRoutes:
    @pytest_asyncio.fixture
    async def nodes(self, compute: Compute, project: Project) -> Tuple[Node, Node]:

        response = MagicMock()
        response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=response)

        node1 = await project.add_node(compute, "node1", None, node_type="qemu")
        node1._ports = [EthernetPort("E0", 0, 0, 3)]
        node2 = await project.add_node(compute, "node2", None, node_type="qemu")
        node2._ports = [EthernetPort("E0", 0, 2, 4)]
        return node1, node2

    async def test_create_link(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes

        filters = {"delay": [10, 0], "frequency_drop": [50]}

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={
                    "nodes": [
                        {
                            "node_id": node1.id,
                            "adapter_number": 0,
                            "port_number": 3,
                            "label": {"text": "Text", "x": 42, "y": 0},
                        },
                        {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                    ],
                    "filters": filters,
                },
            )

        assert mock.called
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["link_id"] is not None
        assert len(response.json()["nodes"]) == 2
        assert response.json()["nodes"][0]["label"]["x"] == 42
        assert len(project.links) == 1
        assert list(project.links.values())[0].filters == filters

    async def test_create_links_batch(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        valid = {
            "nodes": [
                {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
                {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
            ]
        }
        same_node = {
            "nodes": [
                {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
                {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
            ]
        }
        unknown_node = {
            "nodes": [
                {"node_id": str(uuid.uuid4()), "adapter_number": 0, "port_number": 3},
                {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
            ]
        }

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create"):
            response = await client.post(
                app.url_path_for("create_links", project_id=project.id), json=[same_node, unknown_node, valid]
            )

        assert response.status_code == status.HTTP_200_OK
        results = response.json()
        assert [r["status_code"] for r in results] == [409, 404, 201]
        assert results[0]["link"] is None
        assert results[0]["error"]["message"]
        assert results[1]["error"]["message"]
        assert results[2]["error"] is None
        assert results[2]["link"]["link_id"] in project.links
        assert len(project.links) == 1

    async def test_create_link_failure(
        self, app: FastAPI, client: AsyncClient, compute: Compute, project: Project
    ) -> None:
        """
        Make sure the link is deleted if we failed to create it.

        The failure is triggered by connecting the link to itself
        """

        response = MagicMock()
        response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=response)

        node1 = await project.add_node(compute, "node1", None, node_type="qemu")
        node1._ports = [EthernetPort("E0", 0, 0, 3), EthernetPort("E0", 0, 0, 4)]

        response = await client.post(
            app.url_path_for("create_link", project_id=project.id),
            json={
                "nodes": [
                    {
                        "node_id": node1.id,
                        "adapter_number": 0,
                        "port_number": 3,
                        "label": {"text": "Text", "x": 42, "y": 0},
                    },
                    {"node_id": node1.id, "adapter_number": 0, "port_number": 4},
                ]
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert len(project.links) == 0

    async def test_create_link_by_port_name(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create"):
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={
                    "nodes": [
                        {"node_id": node1.id, "port_name": "E0"},
                        {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                    ]
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        first, second = response.json()["nodes"]
        assert (first["adapter_number"], first["port_number"]) == (0, 3)
        assert (second["adapter_number"], second["port_number"]) == (2, 4)

    async def test_create_link_unknown_port_name(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes

        response = await client.post(
            app.url_path_for("create_link", project_id=project.id),
            json={
                "nodes": [
                    {"node_id": node1.id, "port_name": "nope"},
                    {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                ]
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert len(project.links) == 0

    async def test_create_link_auto_port(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        node1._ports = [EthernetPort("E1", 0, 0, 5), EthernetPort("E0", 0, 0, 3)]

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create"):
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={"nodes": [{"node_id": node1.id, "port": "auto"}, {"node_id": node2.id, "port": "auto"}]},
            )
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["nodes"][0]["port_number"] == 3

            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={"nodes": [{"node_id": node1.id, "port": "auto"}, {"node_id": node2.id, "port": "auto"}]},
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["code"] == "no_free_port"
        assert len(project.links) == 1

    async def test_create_link_port_in_use_code(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        body = {
            "nodes": [
                {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
                {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
            ]
        }

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create"):
            first = await client.post(app.url_path_for("create_link", project_id=project.id), json=body)
            second = await client.post(app.url_path_for("create_link", project_id=project.id), json=body)

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_409_CONFLICT
        assert second.json()["code"] == "port_in_use"
        assert len(project.links) == 1

    async def test_create_link_invalid_port_selector(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        valid = {"node_id": node2.id, "adapter_number": 2, "port_number": 4}

        for bad in (
            {"node_id": node1.id},
            {"node_id": node1.id, "adapter_number": 0},
            {"node_id": node1.id, "port_name": "E0", "port": "auto"},
            {"node_id": node1.id, "adapter_number": 0, "port_number": 3, "port_name": "E0"},
        ):
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id), json={"nodes": [bad, valid]}
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_link(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={
                    "nodes": [
                        {
                            "node_id": node1.id,
                            "adapter_number": 0,
                            "port_number": 3,
                            "label": {"text": "Text", "x": 42, "y": 0},
                        },
                        {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                    ]
                },
            )

        assert mock.called
        link_id = response.json()["link_id"]
        assert response.json()["nodes"][0]["label"]["x"] == 42
        response = await client.get(app.url_path_for("get_link", project_id=project.id, link_id=link_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["nodes"][0]["label"]["x"] == 42

    async def test_link_etag_and_if_match(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create"):
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={
                    "nodes": [
                        {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
                        {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                    ]
                },
            )
        link_id = response.json()["link_id"]
        url = app.url_path_for("get_link", project_id=project.id, link_id=link_id)

        response = await client.get(url)
        assert response.status_code == status.HTTP_200_OK
        etag = response.headers["ETag"]
        assert (await client.get(url)).headers["ETag"] == etag

        response = await client.put(url, json={"show_filters_icon": False}, headers={"If-Match": etag})
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["ETag"] != etag
        assert (await client.get(url)).headers["ETag"] == response.headers["ETag"]

        response = await client.put(url, json={"show_filters_icon": True}, headers={"If-Match": etag})
        assert response.status_code == status.HTTP_412_PRECONDITION_FAILED
        assert "message" in response.json()
        assert (await client.get(url)).json()["show_filters_icon"] is False

        response = await client.put(url, json={"show_filters_icon": True})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["show_filters_icon"] is True

    async def test_update_link_suspend(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={
                    "nodes": [
                        {
                            "node_id": node1.id,
                            "adapter_number": 0,
                            "port_number": 3,
                            "label": {"text": "Text", "x": 42, "y": 0},
                        },
                        {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                    ]
                },
            )

        assert mock.called
        link_id = response.json()["link_id"]
        assert response.json()["nodes"][0]["label"]["x"] == 42

        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link_id),
            json={
                "nodes": [
                    {
                        "node_id": node1.id,
                        "adapter_number": 0,
                        "port_number": 3,
                        "label": {"text": "Hello", "x": 64, "y": 0},
                    },
                    {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                ],
                "suspend": True,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["nodes"][0]["label"]["x"] == 64
        assert response.json()["suspend"]
        assert response.json()["filters"] == {}

    async def test_update_link(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        filters = {"delay": [10, 0], "frequency_drop": [50]}

        node1, node2 = nodes
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
            response = await client.post(
                app.url_path_for("create_link", project_id=project.id),
                json={
                    "nodes": [
                        {
                            "node_id": node1.id,
                            "adapter_number": 0,
                            "port_number": 3,
                            "label": {"text": "Text", "x": 42, "y": 0},
                        },
                        {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                    ]
                },
            )

        assert mock.called
        link_id = response.json()["link_id"]
        assert response.json()["nodes"][0]["label"]["x"] == 42

        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link_id),
            json={
                "nodes": [
                    {
                        "node_id": node1.id,
                        "adapter_number": 0,
                        "port_number": 3,
                        "label": {"text": "Hello", "x": 64, "y": 0},
                    },
                    {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
                ],
                "filters": filters,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["nodes"][0]["label"]["x"] == 64
        assert list(project.links.values())[0].filters == filters

    async def test_list_link(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        filters = {"delay": [10, 0], "frequency_drop": [50]}

        node1, node2 = nodes
        nodes = [
            {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
            {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
        ]
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as mock:
            await client.post(
                app.url_path_for("create_link", project_id=project.id), json={"nodes": nodes, "filters": filters}
            )

        assert mock.called
        response = await client.get(app.url_path_for("get_links", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["filters"] == filters

        # test listing links from a closed project
        await project.close(ignore_notification=True)
        response = await client.get(app.url_path_for("get_links", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        assert response.json()[0]["filters"] == filters

    async def test_reset_link(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.delete") as delete_mock:
            with asyncio_patch("gns3server.controller.udp_link.UDPLink.create") as create_mock:
                response = await client.post(app.url_path_for("reset_link", project_id=project.id, link_id=link.id))
                assert delete_mock.called
                assert create_mock.called
                assert response.status_code == status.HTTP_200_OK

    async def test_start_capture(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        with asyncio_patch("gns3server.controller.link.Link.start_capture") as mock:
            response = await client.post(
                app.url_path_for("start_capture", project_id=project.id, link_id=link.id), json={}
            )
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED

    async def test_stop_capture(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        with asyncio_patch("gns3server.controller.link.Link.stop_capture") as mock:
            response = await client.post(app.url_path_for("stop_capture", project_id=project.id, link_id=link.id))
            assert mock.called
            assert response.status_code == status.HTTP_204_NO_CONTENT

    # async def test_pcap(controller_api, http_client, project):
    #
    #     async def pcap_capture():
    #         async with http_client.get(controller_api.get_url("/projects/{}/links/{}/pcap".format(project.id, link.id))) as response:
    #             response.body = await response.content.read(5)
    #             print("READ", response.body)
    #             return response
    #
    #     with asyncio_patch("gns3server.controller.link.Link.capture_node") as mock:
    #         link = Link(project)
    #         link._capture_file_name = "test"
    #         link._capturing = True
    #         with open(link.capture_file_path, "w+") as f:
    #             f.write("hello")
    #         project._links = {link.id: link}
    #         response = await pcap_capture()
    #         assert mock.called
    #         assert response.status_code == 200
    #         assert b'hello' == response.body

    async def test_delete_link(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        with asyncio_patch("gns3server.controller.link.Link.delete") as mock:
            response = await client.delete(app.url_path_for("delete_link", project_id=project.id, link_id=link.id))
        assert mock.called
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_list_filters(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        with patch("gns3server.controller.link.Link.available_filters", return_value=FILTERS) as mock:
            response = await client.get(app.url_path_for("get_filters", project_id=project.id, link_id=link.id))
        assert mock.called
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == FILTERS

    async def test_update_link_filters(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        filters = {
            "frequency_drop": [50],
            "packet_loss": [10],
            "delay": [10, 5],
            "corrupt": [3],
            "bpf": ["icmp"],
        }
        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link.id), json={"filters": filters}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["filters"] == filters
        assert link.filters == filters

    async def test_update_link_disabled_filters(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link.id),
            json={"filters": {"delay": [0, 0], "packet_loss": [0], "corrupt": [], "bpf": [""]}},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["filters"] == {}

    @pytest.mark.parametrize(
        "filters",
        [
            {"packet_loss": [101]},
            {"packet_loss": [-1]},
            {"corrupt": [101]},
            {"frequency_drop": [-2]},
            {"frequency_drop": [32768]},
            {"delay": [32768, 0]},
            {"delay": [10, -1]},
            {"packet_loss": [1, 2]},
            {"bpf": [1]},
            {"packet_loss": ["abc"]},
        ],
    )
    async def test_update_link_invalid_filter_values(
        self, app: FastAPI, client: AsyncClient, project: Project, filters: dict
    ) -> None:

        link = Link(project)
        project._links = {link.id: link}
        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link.id), json={"filters": filters}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "message" in response.json()
        assert link.filters == {}

    async def test_update_link_unknown_filter_type(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link.id),
            json={"filters": {"unknown": [1]}},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "message" in response.json()
        assert link.filters == {}

    async def test_update_link_invalid_delay_latency(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        response = await client.put(
            app.url_path_for("update_link", project_id=project.id, link_id=link.id), json={"filters": {"delay": [0, 5]}}
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_openapi_link_filters(self, app: FastAPI) -> None:

        schemas = app.openapi()["components"]["schemas"]
        link_filters = schemas["LinkFilters"]
        assert link_filters["additionalProperties"] is False
        assert set(link_filters["properties"]) == {"frequency_drop", "packet_loss", "delay", "corrupt", "bpf"}
        assert schemas["LinkFilterDefinition"]["properties"]["parameters"]["items"] == {
            "$ref": "#/components/schemas/LinkFilterParameter"
        }
        path = "/v3/projects/{project_id}/links/{link_id}/available_filters"
        responses = app.openapi()["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert responses["items"] == {"$ref": "#/components/schemas/LinkFilterDefinition"}

    async def test_get_udp_interface(self, app: FastAPI, client: AsyncClient, project: Project) -> None:
        """
        Test getting UDP tunnel interface information from a link.
        """

        link = Link(project)
        project._links = {link.id: link}

        cloud_node = MagicMock()
        cloud_node.node_type = "cloud"
        cloud_node.id = str(uuid.uuid4())
        cloud_node.name = "Cloud1"

        compute = MagicMock()
        response = MagicMock()
        response.json = {
            "ports_mapping": [
                {
                    "port_number": 1,
                    "type": "udp",
                    "lport": 20000,
                    "rhost": "127.0.0.1",
                    "rport": 30000,
                    "name": "UDP tunnel 1",
                }
            ]
        }
        compute.get = AsyncioMagicMock(return_value=response)
        cloud_node.compute = compute

        link._nodes = [{"node": cloud_node, "port_number": 1}]

        response = await client.get(app.url_path_for("get_iface", project_id=project.id, link_id=link.id))

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["node_id"] == cloud_node.id
        assert result["lport"] == 20000
        assert result["rhost"] == "127.0.0.1"
        assert result["rport"] == 30000
        assert result["type"] == "udp"

    async def test_get_ethernet_interface(self, app: FastAPI, client: AsyncClient, project: Project) -> None:
        """
        Test getting ethernet interface information from a link.
        """
        link = Link(project)
        project._links = {link.id: link}

        cloud_node = MagicMock()
        cloud_node.node_type = "cloud"
        cloud_node.id = str(uuid.uuid4())
        cloud_node.name = "Cloud1"

        compute = MagicMock()
        response = MagicMock()
        response.json = {
            "ports_mapping": [{"port_number": 1, "type": "ethernet", "interface": "eth0", "name": "Ethernet 1"}]
        }
        compute.get = AsyncioMagicMock(return_value=response)
        cloud_node.compute = compute

        link._nodes = [{"node": cloud_node, "port_number": 1}]

        response = await client.get(app.url_path_for("get_iface", project_id=project.id, link_id=link.id))

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["node_id"] == cloud_node.id
        assert result["interface"] == "eth0"
        assert result["type"] == "ethernet"
