# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Project inventory aggregation over the raw GNS3 REST listings.

Replaces the aggregation previously living on the ``Project`` dataclass
(``nodes_inventory`` / ``links_summary``). The output shapes are kept
field-for-field: they feed the LLM topology context and the Nornir
inventory, so any change here is consumer-visible.
"""

from typing import Any
from urllib.parse import urlparse

from gns3server.agent.gns3_copilot.gns3_client.api_handlers import _get_connector


def build_nodes_inventory(
    nodes: list[dict[str, Any]], server_host: str | None
) -> dict[str, Any]:
    """
    Build an inventory-style dict keyed by node name.

    Shape (per node name):
        {server, name, node_id, console_port, console_type, type, ports,
         status, x, y, tags, netmiko_device_type, default_username,
         default_password}
    """
    inventory: dict[str, Any] = {}
    for n in nodes:
        inventory[n.get("name")] = {
            "server": server_host,
            "name": n.get("name"),
            "node_id": n.get("node_id"),
            "console_port": n.get("console"),
            "console_type": n.get("console_type"),
            "type": n.get("node_type"),
            "ports": n.get("ports"),
            "status": n.get("status"),
            "x": n.get("x"),
            "y": n.get("y"),
            "tags": n.get("tags") if n.get("tags") else [],
            "netmiko_device_type": n.get("netmiko_device_type"),
            "default_username": n.get("default_username"),
            "default_password": n.get("default_password"),
        }
    return inventory


def build_links_summary(
    nodes: list[dict[str, Any]], links: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """
    Build a human/LLM-friendly link list resolving node and port names.

    Shape (per link): {link_id, node_a, port_a, node_b, port_b}.
    Links whose endpoints cannot be resolved are skipped, mirroring the
    original Project.links_summary behavior.
    """
    summary: list[dict[str, str]] = []
    for link in links:
        if not link.get("nodes"):
            continue
        side_a = link["nodes"][0]
        side_b = link["nodes"][1]
        try:
            node_a = next(
                x for x in nodes if x.get("node_id") == side_a["node_id"]
            )
            port_a = str(
                next(
                    p["name"]
                    for p in (node_a.get("ports") or [])
                    if p["port_number"] == side_a["port_number"]
                    and p["adapter_number"] == side_a["adapter_number"]
                )
            )
            node_b = next(
                x for x in nodes if x.get("node_id") == side_b["node_id"]
            )
            port_b = str(
                next(
                    p["name"]
                    for p in (node_b.get("ports") or [])
                    if p["port_number"] == side_b["port_number"]
                    and p["adapter_number"] == side_b["adapter_number"]
                )
            )
            name_a = str(node_a["name"]) if node_a.get("name") else "Unknown"
            name_b = str(node_b["name"]) if node_b.get("name") else "Unknown"
            summary.append({
                "link_id": link.get("link_id"),
                "node_a": name_a,
                "port_a": port_a,
                "node_b": name_b,
                "port_b": port_b,
            })
        except (StopIteration, KeyError, AttributeError):
            # Prevent errors when lookups can't match data
            continue
    return summary


def fetch_project_inventory(
    gns3_ctx: dict[str, Any], project_id: str
) -> dict[str, Any]:
    """
    Fetch a project's metadata, nodes and links and return the aggregated
    inventory — the equivalent of the old ``Project.get()`` +
    ``nodes_inventory()`` + ``links_summary()`` sequence (minus the
    stats/snapshots/drawings calls no consumer ever read).
    """
    conn = _get_connector(gns3_ctx)
    base = conn.base_url
    project = conn.http_call("get", f"{base}/projects/{project_id}").json()
    nodes = conn.http_call("get", f"{base}/projects/{project_id}/nodes").json()
    links = conn.http_call("get", f"{base}/projects/{project_id}/links").json()
    server_host = urlparse(gns3_ctx["server_url"]).hostname
    return {
        "project_id": project.get("project_id", project_id),
        "name": project.get("name"),
        "status": project.get("status"),
        "nodes_inventory": build_nodes_inventory(nodes, server_host),
        "links_summary": build_links_summary(nodes, links),
    }
