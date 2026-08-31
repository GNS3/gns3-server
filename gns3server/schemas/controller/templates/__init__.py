#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

from pydantic import ConfigDict, BaseModel, Field
from typing import Optional, List
from enum import Enum
from uuid import UUID

from ..nodes import NodeType
from ..base import DateTimeModelMixin


class Category(str, Enum):
    """
    Supported categories
    """

    router = "router"
    switch = "switch"
    guest = "guest"
    firewall = "firewall"


class ApplianceMetadata(BaseModel):
    """
    Metadata kept on a template installed from an appliance: vendor
    information, default credentials and other fields that describe
    the appliance but are not node properties.
    """

    model_config = ConfigDict(extra="allow")

    appliance_id: Optional[str] = Field(
        None, description="ID of the appliance the template was installed from"
    )
    description: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_url: Optional[str] = None
    vendor_logo_url: Optional[str] = None
    documentation_url: Optional[str] = None
    product_name: Optional[str] = None
    product_url: Optional[str] = None
    status: Optional[str] = None
    availability: Optional[str] = None
    maintainer: Optional[str] = None
    maintainer_email: Optional[str] = None
    installation_instructions: Optional[str] = None
    default_username: Optional[str] = None
    default_password: Optional[str] = None


class TemplateBase(BaseModel):
    """
    Common template properties.
    """

    template_id: Optional[UUID] = None
    name: Optional[str] = None
    version: Optional[str] = None
    category: Optional[Category] = None
    default_name_format: Optional[str] = None
    symbol: Optional[str] = None
    template_type: Optional[NodeType] = None
    compute_id: Optional[str] = None
    usage: Optional[str] = ""
    netmiko_device_type: Optional[str] = Field(
        None,
        description="Device type for Netmiko-based automation tools (e.g. 'cisco_xr' or 'nokia_srl')",
        pattern=r"^[a-z0-9_]+$|^$",
    )
    tags: Optional[List[str]] = Field(
        default_factory=list,
        description="User-defined metadata tags (e.g. 'vendor:cisco' or 'model:7200')"
    )
    appliance_metadata: Optional[ApplianceMetadata] = Field(
        None,
        description="Metadata inherited from the appliance the template was installed from"
    )


class TemplateCreate(TemplateBase):
    """
    Properties to create a template.
    """

    name: str
    template_type: NodeType
    model_config = ConfigDict(extra="allow")


class TemplateUpdate(TemplateBase):
    model_config = ConfigDict(extra="allow")


class Template(DateTimeModelMixin, TemplateBase):

    template_id: UUID
    name: str
    category: Category
    symbol: str
    builtin: bool
    template_type: NodeType
    model_config = ConfigDict(extra="allow", from_attributes=True)


class TemplateUsage(BaseModel):

    x: int
    y: int
    name: Optional[str] = Field(None, description="Use this name to create a new node")
    compute_id: Optional[str] = Field(None, description="Used if the template doesn't have a default compute")
