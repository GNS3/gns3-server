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
API routes for compute.
"""

import os
import psutil
import cpuinfo

from functools import lru_cache
from gns3server.config import Config
from gns3server.utils.cpu_percent import CpuPercent
from gns3server.version import __version__
from gns3server.utils.path import get_default_project_directory, is_safe_path
from gns3server.compute.port_manager import PortManager
from gns3server.compute.project_manager import ProjectManager
from gns3server.utils.interfaces import interfaces
from gns3server.compute.qemu import Qemu
from gns3server.compute.virtualbox import VirtualBox
from gns3server.compute.vmware import VMware
from gns3server import schemas

from fastapi import APIRouter, HTTPException, Body, Response, status
from fastapi.encoders import jsonable_encoder
from uuid import UUID
from typing import Optional, List

router = APIRouter()


@lru_cache(maxsize=1)
def get_cpu_model() -> str:
    return cpuinfo.get_cpu_info().get("brand_raw", "")


@router.post("/projects/{project_id}/ports/udp", status_code=status.HTTP_201_CREATED)
def allocate_udp_port(project_id: UUID) -> dict:
    """
    Allocate a UDP port on the compute.
    """

    pm = ProjectManager.instance()
    project = pm.get_project(str(project_id))
    m = PortManager.instance()
    udp_port = m.get_free_udp_port(project)
    return {"udp_port": udp_port}


@router.post("/projects/{project_id}/ports/udp/batch", status_code=status.HTTP_201_CREATED)
def batch_allocate_udp_ports(project_id: UUID, body: dict) -> dict:
    """
    Allocate multiple UDP ports on the compute in a single call.

    Used during project loading to pre-allocate all required UDP ports
    before creating links, reducing HTTP round-trips.
    """

    count = body.get("count", 1)
    try:
        count = max(1, min(int(count), 10000))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="count must be a positive integer")
    pm = ProjectManager.instance()
    project = pm.get_project(str(project_id))
    m = PortManager.instance()
    udp_ports = [m.get_free_udp_port(project) for _ in range(count)]
    return {"udp_ports": udp_ports}


@router.get("/network/interfaces")
def network_interfaces() -> List[dict]:
    """
    List all the network interfaces available on the compute"
    """

    network_interfaces = interfaces()
    return network_interfaces


@router.get("/network/ports")
def network_ports() -> dict:
    """
    List all the ports used on the compute"
    """

    m = PortManager.instance()
    return m.asdict()


@router.get("/version")
def compute_version() -> dict:
    """
    Retrieve the server version number.
    """

    return {"version": __version__}


@router.get("/statistics")
def compute_statistics() -> dict:
    """
    Retrieve the server version number.
    """

    try:
        memory_total = psutil.virtual_memory().total
        memory_free = psutil.virtual_memory().available
        memory_used = memory_total - memory_free  # actual memory usage in a cross platform fashion
        swap_total = psutil.swap_memory().total
        swap_free = psutil.swap_memory().free
        swap_used = psutil.swap_memory().used
        cpu_percent = int(CpuPercent.get())
        cpu_count = psutil.cpu_count(logical=True) or 1
        cpu_count_physical = psutil.cpu_count(logical=False)
        raw_load_average = psutil.getloadavg()
        load_average = [round(x, 2) for x in raw_load_average]
        load_average_percent = [round(x / cpu_count * 100, 2) for x in raw_load_average]
        memory_percent = int(psutil.virtual_memory().percent)
        swap_percent = int(psutil.swap_memory().percent)
        disk_usage = psutil.disk_usage(get_default_project_directory())
        disk_usage_percent = int(disk_usage.percent)
    except psutil.Error as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # raise HTTPConflict(text="Psutil error detected: {}".format(e))

    return {
        "memory_total": memory_total,
        "memory_free": memory_free,
        "memory_used": memory_used,
        "swap_total": swap_total,
        "swap_free": swap_free,
        "swap_used": swap_used,
        "cpu_usage_percent": cpu_percent,
        "cpu_count": cpu_count,
        "cpu_count_physical": cpu_count_physical,
        "cpu_model": get_cpu_model(),
        "memory_usage_percent": memory_percent,
        "swap_usage_percent": swap_percent,
        "disk_usage_percent": disk_usage_percent,
        "disk_total": disk_usage.total,
        "disk_used": disk_usage.used,
        "disk_free": disk_usage.free,
        "load_average": load_average,
        "load_average_percent": load_average_percent,
    }


@router.get("/qemu/capabilities")
async def get_qemu_capabilities() -> dict:
    capabilities = {"kvm": []}
    kvms = await Qemu.get_kvm_archs()
    if kvms:
        capabilities["kvm"] = kvms
    return capabilities


@router.get("/virtualbox/vms", response_model=List[dict])
async def get_virtualbox_vms() -> List[dict]:

    vbox_manager = VirtualBox.instance()
    return await vbox_manager.list_vms()


@router.get("/vmware/vms", response_model=List[dict])
async def get_vms() -> List[dict]:
    vmware_manager = VMware.instance()
    return await vmware_manager.list_vms()
