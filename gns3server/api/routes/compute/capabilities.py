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

"""
API routes for capabilities
"""

import sys

import psutil
from fastapi import APIRouter, Request

from gns3server import schemas
from gns3server.compute import MODULES
from gns3server.compute.ubridge.tc_probe import (
    probe_bridge_tap_support,
    probe_iol_tap_support,
    probe_tc_capabilities,
    probe_tap_support,
)
from gns3server.utils.path import get_default_project_directory
from gns3server.utils.tc_capabilities import usable_ebpf_modes
from gns3server.version import __version__

router = APIRouter()


@router.get("/capabilities", response_model=schemas.Capabilities)
async def get_capabilities(request: Request) -> dict:

    node_types = []
    for module in MODULES:
        node_types.extend(module.node_types())

    # Kernel-datapath packet filters: what this host's uBridge can run,
    # probed as the server's own user (None = unknown, old/missing uBridge).
    ubridge_tc = None
    caps = await probe_tc_capabilities()
    if caps:
        ubridge_tc = {
            "netem": [keyword for keyword in caps.get("netem", "").split(",") if keyword],
            "ebpf": caps.get("ebpf") == "1",
            "ebpf_modes": list(usable_ebpf_modes(caps)),
            "cbpf": caps.get("cbpf") == "1",
        }

    # Persistent TAP support: the anchor QEMU adapters need for the kernel
    # datapath. None = unknown (probe failed or uBridge too old).
    ubridge_tap = await probe_tap_support()

    # IOL-port TAP termination (iol_bridge add_nio_tap): the anchor IOU's
    # Ethernet ports need for the kernel datapath. None = unknown.
    ubridge_iol_tap = await probe_iol_tap_support()

    # Swappable TAP leg on the generic bridge module (bridge delete_nio_tap):
    # what lets an IOL runner container's per-port bridge carry a kernel-link
    # anchor. None = unknown (probe failed or uBridge too old).
    ubridge_bridge_tap = await probe_bridge_tap_support()

    # record the controller hostname or IP address
    if request.client:
        request.app.state.controller_host = request.client.host

    return {
        "version": __version__,
        "platform": sys.platform,
        "cpus": psutil.cpu_count(logical=True),
        "memory": psutil.virtual_memory().total,
        "disk_size": psutil.disk_usage(get_default_project_directory()).total,
        "node_types": node_types,
        "ubridge_tc": ubridge_tc,
        "ubridge_tap": ubridge_tap,
        "ubridge_iol_tap": ubridge_iol_tap,
        "ubridge_bridge_tap": ubridge_bridge_tap,
    }
