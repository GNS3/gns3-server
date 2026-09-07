#!/usr/bin/env python
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
HTTP-route tests for the tag replay endpoints (sharkd edition): the tag gate
(409 while any marker captures, 404 unknown tag), the merged timeline with
columns, window queries (empty window = success), the display-filter
parameter (400 with sharkd's error text on a bad expression), the lazy frame
detail with the renamed sharkd tree, and 501 when sharkd is unavailable
(hard engine requirement, no degraded mode).
"""

import shutil
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller.project import Project
from gns3server.controller.udp_link import UDPLink
from gns3server.controller import marker_replay

from tests.controller.test_marker_replay import _write_pcap, _icmp_frame, _tcp_syn_frame, _cols

pytestmark = pytest.mark.asyncio

sharkd_present = pytest.mark.skipif(shutil.which("sharkd") is None, reason="sharkd not installed")


@pytest_asyncio.fixture
async def no_residual_sessions():
    yield
    manager = marker_replay._manager
    if manager is not None:
        await manager.close_all()


def _add_marker(project, tag, enabled, node_id, frames=None):
    """Create a paused/capturing link+marker and optionally its pcap."""

    link = UDPLink(project)
    link._markers["icmp"] = {"bpf": "icmp", "tag": tag, "enabled": enabled, "color": None,
                             "highlight_duration": None, "capture_node_id": node_id,
                             "direction": None, "data_link_type": "DLT_EN10MB"}
    project._links[link.id] = link
    if frames is not None:
        _write_pcap(
            f"{project.markers_directory}/{node_id}_{link.id}_icmp.pcap", frames
        )
    return link


class TestReplayRoutes:

    async def test_range_409_while_capturing(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1")
        running = _add_marker(project, tag=7, enabled=True, node_id="n2")

        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=7)
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "icmp" in response.json()["message"]
        assert running.id in response.json()["message"]

    async def test_range_404_unknown_tag(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1")

        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=99)
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_range_501_without_sharkd(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        # A non-empty pcap: the engine must be consulted, and without sharkd
        # the whole feature is unavailable (hard requirement, no degraded mode).
        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 123456, _icmp_frame()),
        ])

        with patch("gns3server.controller.marker_replay.shutil.which", return_value=None):
            response = await client.get(
                app.url_path_for("replay_tag_range", project_id=project.id, tag=7)
            )
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        # The app's HTTPException handler unifies the body as {"message": …}.
        assert "sharkd" in response.json()["message"]

    async def test_range_merges_sources_in_ts_order(
        self, app: FastAPI, client: AsyncClient, project: Project, monkeypatch
    ) -> None:

        # Columns injected hermetically — the merge/order/tiebreak contract
        # must not depend on the engine being installed.
        r1, r2 = UDPLink(project), UDPLink(project)
        project._links.update({r1.id: r1, r2.id: r2})

        def _wire(link, node_id, frames):
            link._markers["icmp"] = {"bpf": "icmp", "tag": 7, "enabled": False, "color": None,
                                     "highlight_duration": None, "capture_node_id": node_id,
                                     "direction": None, "data_link_type": "DLT_EN10MB"}
            _write_pcap(f"{project.markers_directory}/{node_id}_{link.id}_icmp.pcap", frames)

        # r1→r2 captures at t1 and t3; r2→r3 captures at t2 and t3 (same µs
        # as source A's t3 — the tiebreak must keep both frames).
        _wire(r1, "n1", [(1693472000, 500000, b"a" * 60), (1693472002, 0, b"a" * 60)])
        _wire(r2, "n2", [(1693472001, 0, b"b" * 60), (1693472002, 0, b"b" * 60)])

        async def fake_columns(pcap, filter_expr):
            name = pcap.rsplit("/", 1)[-1]
            src = "10.0.0.1" if name.startswith("n1") else "10.0.0.2"
            return {1: _cols(src=src), 2: _cols(src=src)}

        monkeypatch.setattr(marker_replay, "_columns_for", fake_columns)

        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=7)
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["tag"] == 7
        assert body["frame_count"] == 4
        assert body["start"] == "1693472000.500000"
        assert body["end"] == "1693472002.000000"
        assert body["truncated"] is False
        assert [f["node_id"] for f in body["frames"]] == ["n1", "n2", "n1", "n2"]
        assert [f["ts"] for f in body["frames"]] == [
            "1693472000.500000", "1693472001.000000",
            "1693472002.000000", "1693472002.000000",
        ]
        # Wireshark-style columns ride along on every frame entry.
        assert body["frames"][0]["src"] == "10.0.0.1"
        assert body["frames"][1]["src"] == "10.0.0.2"
        assert body["frames"][0]["proto"] == "ICMP"
        assert len(body["sources"]) == 2

    async def test_frames_window_miss_is_empty_success(
        self, app: FastAPI, client: AsyncClient, project: Project, monkeypatch
    ) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 0, b"a" * 60),
        ])

        async def fake_columns(pcap, filter_expr):
            return {1: _cols()}

        monkeypatch.setattr(marker_replay, "_columns_for", fake_columns)

        response = await client.get(
            app.url_path_for("replay_tag_frames", project_id=project.id, tag=7),
            params={"ts": "1693472001.000000", "window_ms": 100},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"frames": []}

    async def test_frames_window_hit(
        self, app: FastAPI, client: AsyncClient, project: Project, monkeypatch
    ) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 0, b"a" * 60),
            (1693472000, 150000, b"a" * 60),
        ])

        async def fake_columns(pcap, filter_expr):
            return {1: _cols(), 2: _cols()}

        monkeypatch.setattr(marker_replay, "_columns_for", fake_columns)

        response = await client.get(
            app.url_path_for("replay_tag_frames", project_id=project.id, tag=7),
            params={"ts": "1693472000.000000", "window_ms": 150},
        )
        assert response.status_code == status.HTTP_200_OK
        assert [f["ts"] for f in response.json()["frames"]] == [
            "1693472000.000000", "1693472000.150000"
        ]

    async def test_detail_404_on_ts_mismatch(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        link = _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 123456, _icmp_frame()),
        ])

        response = await client.get(
            app.url_path_for("replay_tag_frame_detail", project_id=project.id, tag=7),
            params={"ts": "1.000000", "node_id": "n1", "link_id": link.id, "marker": "icmp"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "rebuilt" in response.json()["message"]

    @sharkd_present
    async def test_range_columns_and_filter_end_to_end(
        self, app: FastAPI, client: AsyncClient, project: Project, no_residual_sessions
    ) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 123456, _icmp_frame()),
            (1693472001, 0, _tcp_syn_frame()),
        ])

        # Unfiltered: both frames with real engine columns.
        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=7)
        )
        assert response.status_code == status.HTTP_200_OK
        frames = response.json()["frames"]
        assert [f["proto"] for f in frames] == ["ICMP", "TCP"]
        assert frames[0]["src"] == "10.0.0.1" and frames[0]["dst"] == "10.0.0.3"
        assert "Echo" in frames[0]["info"]
        assert frames[0]["frame_number"] == 1

        # Display filter applied before counting: only the TCP frame survives.
        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=7),
            params={"filter": "tcp"},
        )
        body = response.json()
        assert body["frame_count"] == 1
        assert [f["frame_number"] for f in body["frames"]] == [2]  # original pcap identity
        assert body["start"] == "1693472001.000000"

    @sharkd_present
    async def test_range_invalid_filter_is_400_with_sharkd_text(
        self, app: FastAPI, client: AsyncClient, project: Project, no_residual_sessions
    ) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 123456, _icmp_frame()),
        ])

        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=7),
            params={"filter": "this is (not valid"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "filter" in response.json()["message"].lower()

        # Oversized filters are rejected before reaching the engine.
        response = await client.get(
            app.url_path_for("replay_tag_range", project_id=project.id, tag=7),
            params={"filter": "x" * (marker_replay.FILTER_MAX_LENGTH + 1)},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @sharkd_present
    async def test_detail_decodes_single_frame(
        self, app: FastAPI, client: AsyncClient, project: Project, no_residual_sessions
    ) -> None:

        link = _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 123456, _icmp_frame()),
        ])

        response = await client.get(
            app.url_path_for("replay_tag_frame_detail", project_id=project.id, tag=7),
            params={"ts": "1693472000.123456", "node_id": "n1",
                    "link_id": link.id, "marker": "icmp"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["source"]["frame_number"] == 1
        assert body["hex"] == _icmp_frame().hex()
        assert body["field_count"] > 10

        def find(node, name):
            stack = node if isinstance(node, list) else [node]
            for child in stack:
                if child.get("name") == name:
                    return child
                deep = find(child.get("children", []), name)
                if deep is not None:
                    return deep
            return None

        ttl = find(body["tree"], "ip.ttl")
        assert ttl["label"] == "Time to Live: 64"
        assert ttl["filter_expr"] == "ip.ttl == 64"
        assert ttl["pos"] == 22 and ttl["size"] == 1

    @sharkd_present
    async def test_detail_501_when_sharkd_disappears(
        self, app: FastAPI, client: AsyncClient, project: Project
    ) -> None:

        link = _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 123456, _icmp_frame()),
        ])

        with patch("gns3server.controller.marker_replay.shutil.which", return_value=None):
            response = await client.get(
                app.url_path_for("replay_tag_frame_detail", project_id=project.id, tag=7),
                params={"ts": "1693472000.123456", "node_id": "n1",
                        "link_id": link.id, "marker": "icmp"},
            )
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
