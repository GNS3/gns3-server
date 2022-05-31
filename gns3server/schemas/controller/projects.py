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


from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from uuid import UUID
from enum import Enum


class ProjectStatus(str, Enum):
    """
    Supported project statuses.
    """

    opened = "opened"
    closed = "closed"


class Supplier(BaseModel):

    logo: str = Field(..., description="Path to the project supplier logo")
    url: Optional[HttpUrl] = Field(None, description="URL to the project supplier site")


class Variable(BaseModel):

    name: str = Field(..., description="Variable name")
    value: Optional[str] = Field(None, description="Variable value")


class ProjectBase(BaseModel):
    """
    Common properties for projects.
    """

    name: str
    project_id: Optional[UUID] = None
    path: Optional[str] = Field(None, description="Project directory")
    auto_close: Optional[bool] = Field(None, description="Close project when last client leaves")
    auto_open: Optional[bool] = Field(None, description="Project opens when GNS3 starts")
    auto_start: Optional[bool] = Field(None, description="Project starts when opened")
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


class ProjectCreate(ProjectBase):
    """
    Properties for project creation.
    """

    pass


class ProjectDuplicate(ProjectBase):
    """
    Properties for project duplication.
    """

    reset_mac_addresses: Optional[bool] = Field(False, description="Reset MAC addresses for this project")


class ProjectUpdate(ProjectBase):
    """
    Properties for project update.
    """

    name: Optional[str] = None


class Project(ProjectBase):

    project_id: UUID
    name: Optional[str] = None
    status: Optional[ProjectStatus] = None
    filename: Optional[str] = None


class ProjectFile(BaseModel):

    path: str = Field(..., description="File path")
    md5sum: str = Field(..., description="File checksum")


class ProjectCompression(str, Enum):
    """
    Supported project compression.
    """

    none = "none"
    zip = "zip"
    bzip2 = "bzip2"
    lzma = "lzma"
    zstd = "zstd"
