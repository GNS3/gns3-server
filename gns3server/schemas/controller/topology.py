#!/usr/bin/env python
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

#
# This file contains the validation for checking a .gns3 file
#

from .computes import Compute
from .drawings import Drawing
from .links import Link
from .nodes import Node

from .projects import Supplier, Variable

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from uuid import UUID


class TopologyType(str, Enum):

    topology = "topology"


class TopologyContent(BaseModel):

    computes: List[Compute] = Field(..., description="List of computes")
    drawings: List[Drawing] = Field(..., description="List of drawings")
    links: List[Link] = Field(..., description="List of links")
    nodes: List[Node] = Field(..., description="List of nodes")


class Topology(BaseModel):

    project_id: UUID = Field(..., description="Project UUID")
    type: TopologyType = Field(..., description="Type of file. It's always topology")
    revision: int = Field(..., description="Version of the .gns3 specification")
    version: str = Field(..., description="Version of the GNS3 software which have update the file for the last time")
    name: str = Field(..., description="Name of the project")
    topology: TopologyContent = Field(..., description="Topology content")
    auto_start: Optional[bool] = Field(None, description="Start the topology when opened")
    auto_close: Optional[bool] = Field(None, description="Close the topology when no client is connected")
    scene_height: Optional[int] = Field(None, description="Height of the drawing area")
    scene_width: Optional[int] = Field(None, description="Width of the drawing area")
    zoom: Optional[int] = Field(None, description="Zoom of the drawing area")
    show_layers: Optional[bool] = Field(None, description="Show layers on the drawing area")
    snap_to_grid: Optional[bool] = Field(None, description="Snap to grid on the drawing area")
    show_grid: Optional[bool] = Field(None, description="Show the grid on the drawing area")
    grid_size: Optional[int] = Field(None, description="Grid size for the drawing area for nodes")
    drawing_grid_size: Optional[int] = Field(None, description="Grid size for the drawing area for drawings")
    show_interface_labels: Optional[bool] = Field(None, description="Show interface labels on the drawing area")
    supplier: Optional[Supplier] = Field(None, description="Supplier of the project")
    variables: Optional[List[Variable]] = Field(None, description="Variables required to run the project")


def main():

    import json
    import sys

    with open(sys.argv[1]) as f:
        data = json.load(f)
        Topology.model_validate(data)


if __name__ == "__main__":
    main()
