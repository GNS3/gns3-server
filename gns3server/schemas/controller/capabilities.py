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


from typing import List, Optional

from pydantic import BaseModel, Field

from .nodes import NodeType


class UbridgeTcCapabilities(BaseModel):
    """
    uBridge tc-module capabilities (kernel-datapath packet filters), probed
    by the compute as its own user.
    """

    netem: List[str] = Field(..., description="netem keywords supported by this uBridge's tc module")
    ebpf: bool = Field(..., description="Whether the eBPF stateful classifier loads on this host")
    ebpf_modes: List[str] = Field(
        ..., description="eBPF classifier modes usable on this host (ebpf is on and the mode token is declared)"
    )
    cbpf: bool = Field(..., description="Whether classic-BPF match-drop classifiers are available")


class Capabilities(BaseModel):
    """
    Capabilities properties.
    """

    version: str = Field(..., description="Compute version number")
    node_types: List[NodeType] = Field(..., description="Node types supported by the compute")
    platform: str = Field(..., description="Platform where the compute is running")
    cpus: int = Field(..., description="Number of CPUs on this compute")
    memory: int = Field(..., description="Amount of memory on this compute")
    disk_size: int = Field(..., description="Disk size on this compute")
    ubridge_tc: Optional[UbridgeTcCapabilities] = Field(
        None, description="uBridge tc-module capabilities; absent when the probe failed or uBridge has no tc module"
    )
