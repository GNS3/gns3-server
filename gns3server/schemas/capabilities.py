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


from pydantic import BaseModel, Field
from typing import List

from .nodes import NodeType


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
