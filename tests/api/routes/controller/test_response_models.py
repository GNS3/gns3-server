#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
Runtime JSON shape of the endpoints that used to return untyped objects, and
the OpenAPI contract that now describes them.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller import Controller, marker_replay
from gns3server.controller.link import Link
from gns3server.controller.project import Project
from gns3server.controller.udp_link import UDPLink
from tests.controller.test_marker_replay import _write_pcap

pytestmark = pytest.mark.asyncio

TYPED_OPERATIONS = [
    ("post", "/v3/access/api-keys"),
    ("get", "/v3/access/api-keys"),
    ("post", "/v3/access/api-keys/{api_key_id}/revoke"),
    ("post", "/v3/access/api-keys/{api_key_id}/restore"),
    ("get", "/v3/statistics"),
    ("get", "/v3/projects/{project_id}/stats"),
    ("post", "/v3/images/install"),
    ("post", "/v3/appliances/{appliance_id}/version"),
    ("get", "/v3/projects/{project_id}/markers"),
    ("get", "/v3/projects/{project_id}/marker-definitions"),
    ("post", "/v3/projects/{project_id}/marker-definitions"),
    ("put", "/v3/projects/{project_id}/marker-definitions/{def_name}"),
    ("get", "/v3/projects/{project_id}/markers/tags/{tag}/replay/range"),
    ("get", "/v3/projects/{project_id}/markers/tags/{tag}/replay/frames"),
    ("get", "/v3/projects/{project_id}/markers/tags/{tag}/replay/frame/detail"),
    ("get", "/v3/projects/{project_id}/links/{link_id}/markers"),
    ("post", "/v3/projects/{project_id}/links/{link_id}/markers"),
    ("put", "/v3/projects/{project_id}/links/{link_id}/markers/{marker_name}"),
    ("get", "/v3/symbols"),
    ("get", "/v3/symbols/{symbol_id}/dimensions"),
    ("get", "/v3/symbols/default_symbols"),
    ("get", "/v3/projects/{project_id}/links/{link_id}/available_filters"),
    ("post", "/v3/projects/{project_id}/links/{link_id}/capture/wireshark/restart"),
    ("get", "/v3/projects/{project_id}/nodes/{node_id}/dynamips/auto_idlepc"),
    ("post", "/v3/computes/{compute_id}/dynamips/auto_idlepc"),
    ("get", "/v3/gns3vm/engines"),
    ("get", "/v3/gns3vm/engines/{engine}/vms"),
    ("get", "/v3/access/acl/endpoints"),
]


def _is_untyped(schema: dict) -> bool:
    if not schema:
        return True
    if "$ref" in schema:
        return False
    if schema.get("type") == "array":
        return _is_untyped(schema.get("items", {}))
    if schema.get("type") == "object":
        extra = schema.get("additionalProperties")
        if "properties" in schema:
            return False
        return extra in (None, True, {})
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return any(_is_untyped(s) for s in schema[key] if s.get("type") != "null")
    return False


class TestOpenAPIContract:
    async def test_no_untyped_success_response(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get("/openapi.json")
        assert response.status_code == status.HTTP_200_OK
        paths = response.json()["paths"]

        untyped = []
        for method, path in TYPED_OPERATIONS:
            operation = paths[path][method]
            success = [r for code, r in operation["responses"].items() if code.startswith("2") and code != "204"]
            assert success, f"{method.upper()} {path} declares no success response"
            for r in success:
                schema = r["content"]["application/json"]["schema"]
                if _is_untyped(schema):
                    untyped.append(f"{method.upper()} {path}")
        assert not untyped


class TestApiKeys:
    async def _create(self, app: FastAPI, client: AsyncClient, name: str = "ci") -> dict:

        response = await client.post(app.url_path_for("create_api_key"), json={"name": name})
        assert response.status_code == status.HTTP_201_CREATED
        return response.json()

    async def test_create(self, app: FastAPI, client: AsyncClient) -> None:

        body = await self._create(app, client, "created")
        assert set(body) == {"api_key_id", "api_key", "name", "key_prefix", "created_at"}
        assert body["name"] == "created"
        assert body["api_key"].startswith(f"gns3_{body['api_key_id']}_")
        assert body["key_prefix"] == body["api_key"][:8]
        assert isinstance(body["created_at"], str)
        uuid.UUID(body["api_key_id"])

    async def test_list(self, app: FastAPI, client: AsyncClient) -> None:

        created = await self._create(app, client, "listed")
        response = await client.get(app.url_path_for("list_api_keys"))
        assert response.status_code == status.HTTP_200_OK
        entry = next(k for k in response.json() if k["api_key_id"] == created["api_key_id"])
        assert set(entry) == {"api_key_id", "name", "key_prefix", "created_at", "last_used_at", "revoked"}
        assert entry["name"] == "listed"
        assert entry["last_used_at"] is None
        assert entry["revoked"] is False
        assert entry["created_at"] == created["created_at"]

    async def test_revoke_and_restore(self, app: FastAPI, client: AsyncClient) -> None:

        created = await self._create(app, client, "toggled")
        key_id = created["api_key_id"]

        response = await client.post(app.url_path_for("revoke_api_key", api_key_id=key_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "API key 'toggled' revoked"}
        keys = (await client.get(app.url_path_for("list_api_keys"))).json()
        assert next(k for k in keys if k["api_key_id"] == key_id)["revoked"] is True

        response = await client.post(app.url_path_for("restore_api_key", api_key_id=key_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "API key 'toggled' restored"}
        keys = (await client.get(app.url_path_for("list_api_keys"))).json()
        assert next(k for k in keys if k["api_key_id"] == key_id)["revoked"] is False

    async def test_revoke_unknown_key(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.post(app.url_path_for("revoke_api_key", api_key_id=str(uuid.uuid4())))
        assert response.status_code == status.HTTP_404_NOT_FOUND


COMPUTE_STATISTICS = {
    "memory_total": 8000,
    "memory_free": 4000,
    "memory_used": 4000,
    "swap_total": 1000,
    "swap_free": 900,
    "swap_used": 100,
    "cpu_usage_percent": 12,
    "cpu_count": 4,
    "cpu_count_physical": None,
    "cpu_model": "Test CPU",
    "memory_usage_percent": 50,
    "swap_usage_percent": 10,
    "disk_usage_percent": 30,
    "disk_total": 100000,
    "disk_used": 30000,
    "disk_free": 70000,
    "load_average": [0.5, 0.4, 0.3],
    "load_average_percent": [12.5, 10.0, 7.5],
}


class TestStatistics:
    async def test_statistics_shape(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        webwireshark = {
            "total_containers": 1,
            "running_containers": 1,
            "active_sessions": 0,
            "containers": [
                {
                    "project_id": project.id,
                    "project_name": project.name,
                    "container_id": "abcdef123456",
                    "status": "running",
                    "running": True,
                    "active_sessions": 0,
                    "memory_limit": "unlimited",
                    "cpu_limit": "unlimited",
                    "pids_limit": "unlimited",
                    "memory": "10MiB / 1GiB",
                    "cpu": "0.5%",
                    "pids": 3,
                },
                {
                    "project_id": project.id,
                    "project_name": project.name,
                    "container_id": "123456abcdef",
                    "status": "exited",
                    "running": False,
                },
            ],
        }
        with patch(
            "gns3server.api.routes.controller.controller.collect_webwireshark_stats",
            new=AsyncMock(return_value=webwireshark),
        ):
            response = await client.get(app.url_path_for("statistics"))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"uptime_seconds", "computes", "projects", "nodes", "links", "webwireshark"}
        assert isinstance(body["uptime_seconds"], int)
        assert body["projects"] == {"total": 1, "opened": 1, "closed": 0}
        assert body["nodes"] == {
            "total": 0,
            "open_project_nodes": 0,
            "closed_project_nodes": 0,
            "by_type": {},
            "by_status": {},
        }
        assert body["links"] == {"total": 0, "capturing": 0}
        assert body["webwireshark"] == webwireshark

    async def test_statistics_compute_entry(
        self, app: FastAPI, client: AsyncClient, controller: Controller, project: Project
    ) -> None:

        compute = MagicMock()
        compute.id = "local"
        compute.name = "local"
        reply = MagicMock()
        reply.json = dict(COMPUTE_STATISTICS)
        compute.get = AsyncMock(return_value=reply)
        controller._computes = {"local": compute}

        response = await client.get(app.url_path_for("statistics"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["computes"] == [
            {"compute_id": "local", "compute_name": "local", "statistics": COMPUTE_STATISTICS}
        ]

    async def test_statistics_compute_missing_fields_stay_absent(
        self, app: FastAPI, client: AsyncClient, controller: Controller, project: Project
    ) -> None:

        compute = MagicMock()
        compute.id = "old"
        compute.name = "old"
        reply = MagicMock()
        reply.json = {"memory_total": 8000, "cpu_count": 2}
        compute.get = AsyncMock(return_value=reply)
        controller._computes = {"old": compute}

        response = await client.get(app.url_path_for("statistics"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["computes"][0]["statistics"] == {"memory_total": 8000, "cpu_count": 2}

    async def test_project_stats(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        link._markers["a"] = {"bpf": "icmp"}
        link._markers["b"] = {"bpf": "arp"}
        project._links = {link.id: link}

        response = await client.get(app.url_path_for("get_project_stats", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"nodes": 0, "links": 1, "drawings": 0, "snapshots": 0, "markers": 2}


class TestSymbols:
    async def test_list_shape(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_symbols"))
        assert response.status_code == status.HTTP_200_OK
        symbols = response.json()
        assert symbols
        for symbol in symbols:
            assert set(symbol) == {"symbol_id", "filename", "theme", "builtin"}
            assert isinstance(symbol["builtin"], bool)

    async def test_default_symbols(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_default_symbols"))
        assert response.status_code == status.HTTP_200_OK
        themes = response.json()
        assert themes["Classic"]["firewall"] == ":/symbols/classic/firewall.svg"
        assert themes == Controller.instance().symbols.default_symbols()

    async def test_dimensions(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(
            app.url_path_for("get_symbol_dimensions", symbol_id=":/symbols/classic/firewall.svg")
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert set(body) == {"width", "height"}
        assert isinstance(body["width"], int)
        assert isinstance(body["height"], int)


class TestLinkRoutes:
    async def test_wireshark_restart(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = Link(project)
        project._links = {link.id: link}
        with patch("gns3server.controller.link.Link._restart_web_wireshark", new=AsyncMock()):
            response = await client.post(app.url_path_for("restart_wireshark", project_id=project.id, link_id=link.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "restarted"}

    async def test_available_filters_keep_optional_parameter_keys_absent(
        self, app: FastAPI, client: AsyncClient, project: Project
    ) -> None:

        link = Link(project)
        project._links = {link.id: link}
        with patch.object(Link, "_get_filter_node", return_value=object()):
            response = await client.get(app.url_path_for("get_filters", project_id=project.id, link_id=link.id))
        assert response.status_code == status.HTTP_200_OK
        by_type = {f["type"]: f for f in response.json()}
        assert by_type["bpf"]["parameters"] == [{"name": "Filters", "type": "text"}]
        assert by_type["delay"]["parameters"][0] == {
            "name": "Latency",
            "minimum": 1,
            "maximum": 32767,
            "unit": "ms",
            "type": "int",
        }

    async def test_link_markers_keep_missing_keys_absent(
        self, app: FastAPI, client: AsyncClient, project: Project
    ) -> None:

        link = UDPLink(project)
        link._markers["legacy"] = {"bpf": "icmp", "tag": 1, "enabled": True}
        link._markers["global-arp"] = {"bpf": "arp", "inherited_from": "arp", "capture_node_id": "n1"}
        project._links = {link.id: link}

        response = await client.get(app.url_path_for("get_markers", project_id=project.id, link_id=link.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == link._markers


class TestMarkerAggregation:
    async def test_project_markers_and_definitions(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        link._markers["web"] = {
            "bpf": "tcp port 80",
            "tag": 4,
            "enabled": False,
            "color": "#ff5722",
            "highlight_duration": 800,
            "capture_node_id": "n1",
            "direction": "tx",
            "data_link_type": "DLT_EN10MB",
        }
        link._markers["global-arp"] = {
            "bpf": "arp",
            "tag": None,
            "enabled": True,
            "color": None,
            "highlight_duration": None,
            "capture_node_id": "n1",
            "direction": None,
            "data_link_type": "DLT_EN10MB",
            "inherited_from": "arp",
        }
        project._links = {link.id: link}
        project._marker_definitions = {
            "arp": {
                "bpf": "arp",
                "tag": None,
                "direction": None,
                "color": None,
                "highlight_duration": None,
                "data_link_type": "DLT_EN10MB",
                "paused": False,
            },
            "old": {"bpf": "icmp", "tag": 5},
        }

        response = await client.get(app.url_path_for("get_project_markers", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            f"{link.id}/web": {**link._markers["web"], "link_id": link.id, "node_id": "n1"},
            f"{link.id}/global-arp": {**link._markers["global-arp"], "link_id": link.id, "node_id": "n1"},
        }

        response = await client.get(app.url_path_for("get_marker_definitions", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "arp": {**project._marker_definitions["arp"], "link_ids": [link.id]},
            "old": {"bpf": "icmp", "tag": 5, "link_ids": []},
        }


class TestReplayFrameDetail:
    async def test_frame_detail_passes_unknown_tree_keys_through(
        self, app: FastAPI, client: AsyncClient, project: Project, monkeypatch
    ) -> None:

        detail = {
            "ts": "1693472000.000000",
            "source": {"node_id": "n1", "link_id": "l1", "marker": "icmp", "frame_number": 1},
            "field_count": 3,
            "hex": "0200",
            "tree": [
                {
                    "element": "proto",
                    "label": "Internet Protocol",
                    "name": "ip",
                    "filter_expr": "ip",
                    "pos": 14,
                    "size": 20,
                    "children": [{"label": "TTL: 64", "name": "ip.ttl", "expert": "Chat", "generated": True}],
                    "future_key": {"a": 1},
                }
            ],
        }
        monkeypatch.setattr(marker_replay, "decode_frame", AsyncMock(return_value=detail))

        response = await client.get(
            app.url_path_for("replay_tag_frame_detail", project_id=project.id, tag=7),
            params={"ts": "1693472000.000000", "node_id": "n1", "link_id": "l1", "marker": "icmp"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == detail

    async def test_range_empty_timeline(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = UDPLink(project)
        link._markers["icmp"] = {
            "bpf": "icmp",
            "tag": 9,
            "enabled": False,
            "color": None,
            "highlight_duration": None,
            "capture_node_id": "n1",
            "direction": None,
            "data_link_type": "DLT_EN10MB",
        }
        project._links = {link.id: link}
        _write_pcap(f"{project.markers_directory}/n1_{link.id}_icmp.pcap", [])

        response = await client.get(app.url_path_for("replay_tag_range", project_id=project.id, tag=9))
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "tag": 9,
            "start": None,
            "end": None,
            "frame_count": 0,
            "sources": [
                {"node_id": "n1", "link_id": link.id, "marker": "icmp", "data_link_type": "DLT_EN10MB", "count": 0}
            ],
            "frames": [],
        }
