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

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ComputeStatistics(BaseModel):
    """
    Resource usage reported by a compute.

    Fields come from the compute itself, so a compute running another build
    may omit some of them.
    """

    memory_total: Optional[int] = None
    memory_free: Optional[int] = None
    memory_used: Optional[int] = None
    swap_total: Optional[int] = None
    swap_free: Optional[int] = None
    swap_used: Optional[int] = None
    cpu_usage_percent: Optional[int] = None
    cpu_count: Optional[int] = None
    cpu_count_physical: Optional[int] = None
    cpu_model: Optional[str] = None
    memory_usage_percent: Optional[int] = None
    swap_usage_percent: Optional[int] = None
    disk_usage_percent: Optional[int] = None
    disk_total: Optional[int] = None
    disk_used: Optional[int] = None
    disk_free: Optional[int] = None
    load_average: Optional[List[float]] = None
    load_average_percent: Optional[List[float]] = None


class ComputeStatisticsEntry(BaseModel):
    """
    Statistics of one compute.
    """

    compute_id: str
    compute_name: str
    statistics: ComputeStatistics


class ProjectCountStatistics(BaseModel):
    """
    Project counts by status.
    """

    total: int
    opened: int
    closed: int


class NodeStatistics(BaseModel):
    """
    Node counts across all projects.
    """

    total: int
    open_project_nodes: int
    closed_project_nodes: int
    by_type: Dict[str, int] = Field(..., description="Node count by node type")
    by_status: Dict[str, int] = Field(..., description="Node count by status, open projects only")


class LinkStatistics(BaseModel):
    """
    Link counts across all projects.
    """

    total: int
    capturing: int


class WebWiresharkContainer(BaseModel):
    """
    A Web Wireshark container.
    """

    project_id: str
    project_name: str
    container_id: str
    status: str
    running: bool
    active_sessions: Optional[int] = None
    memory_limit: Optional[str] = None
    cpu_limit: Optional[str] = None
    pids_limit: Optional[Union[int, str]] = Field(None, description="Process limit, or 'unlimited'")
    memory: Optional[str] = Field(None, description="Current memory usage")
    cpu: Optional[str] = Field(None, description="Current CPU usage")
    pids: Optional[int] = Field(None, description="Current process count")


class WebWiresharkStatistics(BaseModel):
    """
    Web Wireshark container statistics across all opened projects.
    """

    total_containers: int
    running_containers: int
    active_sessions: int
    containers: List[WebWiresharkContainer]


class ServerStatistics(BaseModel):
    """
    Server statistics.
    """

    uptime_seconds: int
    computes: List[ComputeStatisticsEntry]
    projects: ProjectCountStatistics
    nodes: NodeStatistics
    links: LinkStatistics
    webwireshark: WebWiresharkStatistics
