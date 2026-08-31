# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 GNS3 Technologies Inc.
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

"""
HTTP-route tests for the traffic-insight marker endpoints: per-link markers,
project-level definitions, and the project-wide aggregation view.
"""

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from tests.utils import asyncio_patch

from gns3server.controller.project import Project
from gns3server.controller.udp_link import UDPLink

pytestmark = pytest.mark.asyncio


def _inherited(link, name="arp"):
    """Inject an inherited marker so the controller's inheritance guard can fire."""
    link._markers[f"global-{name}"] = {
        "bpf": name, "tag": None, "enabled": True, "color": None,
        "highlight_duration": None, "capture_node_id": "node-id",
        "inherited_from": name,
    }


class TestMarkerRoutes:

    # -----------------------------------------------------------------------
    # Per-link markers
    # -----------------------------------------------------------------------

    async def test_create_marker(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.start_marker") as mock:
            response = await client.post(
                app.url_path_for("create_marker", project_id=project.id, link_id=link.id),
                json={"bpf": "icmp", "tag": 3, "color": "#ff5722", "highlight_duration": 800},
            )

        assert response.status_code == status.HTTP_201_CREATED
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["bpf"] == "icmp"
        assert kwargs["tag"] == 3
        assert kwargs["color"] == "#ff5722"
        assert kwargs["highlight_duration"] == 800
        assert kwargs["name"].startswith("marker-")

    async def test_create_marker_with_explicit_name(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.start_marker") as mock:
            response = await client.post(
                app.url_path_for("create_marker", project_id=project.id, link_id=link.id),
                json={"name": "web", "bpf": "tcp port 80"},
            )
        assert response.status_code == status.HTTP_201_CREATED
        _, kwargs = mock.call_args
        assert kwargs["name"] == "web"

    async def test_create_marker_global_prefix_rejected(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.start_marker") as mock:
            response = await client.post(
                app.url_path_for("create_marker", project_id=project.id, link_id=link.id),
                json={"name": "global-x", "bpf": "icmp"},
            )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert not mock.called  # rejected before reaching the controller

    async def test_create_marker_bad_format_rejected(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        response = await client.post(
            app.url_path_for("create_marker", project_id=project.id, link_id=link.id),
            json={"name": "bad name!", "bpf": "icmp"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_marker_name_too_long_rejected(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        response = await client.post(
            app.url_path_for("create_marker", project_id=project.id, link_id=link.id),
            json={"name": "x" * 33, "bpf": "icmp"},  # max_length is 32
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_get_markers(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        link._markers["web"] = {"bpf": "tcp port 80", "tag": None, "enabled": True,
                                "color": None, "highlight_duration": 800, "capture_node_id": "n1"}
        project._links = {link.id: link}

        response = await client.get(
            app.url_path_for("get_markers", project_id=project.id, link_id=link.id)
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["web"]["highlight_duration"] == 800

    async def test_update_marker(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.update_marker") as mock:
            response = await client.put(
                app.url_path_for("update_marker", project_id=project.id, link_id=link.id, marker_name="web"),
                json={"bpf": "udp port 53", "highlight_duration": 1500},
            )
        assert response.status_code == status.HTTP_200_OK
        _, kwargs = mock.call_args
        assert kwargs["bpf"] == "udp port 53"
        assert kwargs["highlight_duration"] == 1500

    async def test_update_inherited_marker_rejected(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        _inherited(link, "arp")
        project._links = {link.id: link}

        response = await client.put(
            app.url_path_for("update_marker", project_id=project.id, link_id=link.id, marker_name="global-arp"),
            json={"name": "global-arp", "bpf": "arp"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "inherited" in response.json()["message"]

    async def test_delete_marker(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        project._links = {link.id: link}

        with asyncio_patch("gns3server.controller.udp_link.UDPLink.stop_marker") as mock:
            response = await client.delete(
                app.url_path_for("delete_marker", project_id=project.id, link_id=link.id, marker_name="web")
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock.assert_called_once_with("web")

    async def test_delete_inherited_marker_rejected(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        _inherited(link, "arp")
        project._links = {link.id: link}

        response = await client.delete(
            app.url_path_for("delete_marker", project_id=project.id, link_id=link.id, marker_name="global-arp")
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    # -----------------------------------------------------------------------
    # Project-level marker definitions
    # -----------------------------------------------------------------------

    async def test_create_marker_definition(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        with asyncio_patch("gns3server.controller.project.Project.create_marker_definition") as mock:
            response = await client.post(
                app.url_path_for("create_marker_definition", project_id=project.id),
                json={"name": "arp", "bpf": "arp", "highlight_duration": 1200},
            )
        assert response.status_code == status.HTTP_201_CREATED
        _, kwargs = mock.call_args
        assert kwargs["name"] == "arp"
        assert kwargs["bpf"] == "arp"
        assert kwargs["highlight_duration"] == 1200

    async def test_create_marker_definition_global_prefix_rejected(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        with asyncio_patch("gns3server.controller.project.Project.create_marker_definition") as mock:
            response = await client.post(
                app.url_path_for("create_marker_definition", project_id=project.id),
                json={"name": "global-x", "bpf": "arp"},
            )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert not mock.called

    async def test_update_marker_definition(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        with asyncio_patch("gns3server.controller.project.Project.update_marker_definition") as mock:
            response = await client.put(
                app.url_path_for("update_marker_definition", project_id=project.id, def_name="arp"),
                json={"bpf": "arp or rarp", "highlight_duration": 900},
            )
        assert response.status_code == status.HTTP_200_OK
        _, kwargs = mock.call_args
        assert kwargs["bpf"] == "arp or rarp"
        assert kwargs["highlight_duration"] == 900

    async def test_delete_marker_definition(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        with asyncio_patch("gns3server.controller.project.Project.delete_marker_definition") as mock:
            response = await client.delete(
                app.url_path_for("delete_marker_definition", project_id=project.id, def_name="arp")
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock.assert_called_once_with("arp")

    async def test_get_marker_definitions(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        project._marker_definitions = {
            "arp": {"bpf": "arp", "tag": 5, "color": None, "highlight_duration": 1200},
        }
        project._links = {}

        response = await client.get(
            app.url_path_for("get_marker_definitions", project_id=project.id)
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["arp"]["bpf"] == "arp"
        assert body["arp"]["highlight_duration"] == 1200
        assert body["arp"]["link_ids"] == []

    # -----------------------------------------------------------------------
    # Aggregation
    # -----------------------------------------------------------------------

    async def test_get_project_markers(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        link._markers["icmp"] = {"bpf": "icmp", "tag": 1, "enabled": True, "color": "#ff5722",
                                 "highlight_duration": 800, "capture_node_id": "node-1"}
        project._links = {link.id: link}

        response = await client.get(
            app.url_path_for("get_project_markers", project_id=project.id)
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        key = f"{link.id}/icmp"
        assert key in body
        assert body[key]["highlight_duration"] == 800
        assert body[key]["link_id"] == link.id
        assert body[key]["node_id"] == "node-1"
