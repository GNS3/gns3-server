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
HTTP-route tests for the tag replay endpoints: the tag gate (409 while any
marker captures, 404 unknown tag), the merged timeline, window queries
(empty window = success), and the lazy frame detail (ts guard, isomorphic
JSON, 501 when tshark is unavailable).
"""

import shutil
from unittest.mock import patch

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller.project import Project
from gns3server.controller.udp_link import UDPLink

from tests.controller.test_marker_replay import _write_pcap, _icmp_frame

pytestmark = pytest.mark.asyncio

tshark_present = pytest.mark.skipif(shutil.which("tshark") is None, reason="tshark not installed")


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

    async def test_range_merges_sources_in_ts_order(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        # r1→r2 captures at t1 and t3; r2→r3 captures at t2 and t3 (same µs
        # as source A's t3 — the tiebreak must keep both frames).
        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 500000, b"a" * 60),
            (1693472002, 0, b"a" * 60),
        ])
        _add_marker(project, tag=7, enabled=False, node_id="n2", frames=[
            (1693472001, 0, b"b" * 60),
            (1693472002, 0, b"b" * 60),
        ])

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
        assert len(body["sources"]) == 2

    async def test_frames_window_miss_is_empty_success(
        self, app: FastAPI, client: AsyncClient, project: Project
    ) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 0, b"a" * 60),
        ])

        response = await client.get(
            app.url_path_for("replay_tag_frames", project_id=project.id, tag=7),
            params={"ts": "1693472001.000000", "window_ms": 100},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"frames": []}

    async def test_frames_window_hit(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        _add_marker(project, tag=7, enabled=False, node_id="n1", frames=[
            (1693472000, 0, b"a" * 60),
            (1693472000, 150000, b"a" * 60),
        ])

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

    async def test_detail_501_without_tshark(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

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

    @tshark_present
    async def test_detail_decodes_single_frame(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

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
        assert "tshark" in body["tshark_version"].lower()

        ip = next(p for p in body["tree"] if p.get("name") == "ip")
        ttl = next(f for f in ip["children"] if f.get("name") == "ip.ttl")
        # Values arrive as strings, exactly as tshark emitted them.
        assert ttl["show"] == "64" and ttl["showname"] == "Time to Live: 64"
