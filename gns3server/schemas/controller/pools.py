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

from typing import Optional
from pydantic import ConfigDict, BaseModel, Field
from uuid import UUID
from enum import Enum

from .base import DateTimeModelMixin


class ResourceType(str, Enum):

    project = "project"


class ResourceBase(BaseModel):
    """
    Common resource properties.
    """

    resource_id: UUID
    resource_type: ResourceType = Field(..., description="Type of the resource")
    name: Optional[str] = None
    model_config = ConfigDict(use_enum_values=True)


class ResourceCreate(ResourceBase):
    """
    Properties to create a resource.
    """

    pass


class Resource(DateTimeModelMixin, ResourceBase):

    model_config = ConfigDict(from_attributes=True)


class ResourcePoolBase(BaseModel):
    """
    Common resource pool properties.
    """

    name: str


class ResourcePoolCreate(ResourcePoolBase):
    """
    Properties to create a resource pool.
    """

    pass


class ResourcePoolUpdate(ResourcePoolBase):
    """
    Properties to update a resource pool.
    """

    pass


class ResourcePool(DateTimeModelMixin, ResourcePoolBase):

    resource_pool_id: UUID
    model_config = ConfigDict(from_attributes=True)
