# -*- coding: utf-8 -*-
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
from typing import Optional, Union
from enum import Enum

from .nodes import NodeType


class Category(str, Enum):
    """
    Supported categories
    """

    router = "router"
    switch = "switch"
    guest = "guest"
    firewall = "firewall"


class TemplateBase(BaseModel):
    """
    Common template properties.
    """

    template_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[Category] = None
    default_name_format: Optional[str] = None
    symbol: Optional[str] = None
    builtin: Optional[bool] = None
    template_type: Optional[NodeType] = None
    usage: Optional[str] = None
    compute_id: Optional[str] = None

    class Config:
        extra = "allow"


class TemplateCreate(TemplateBase):
    """
    Properties to create a template.
    """

    name: str
    template_type: NodeType
    compute_id: str


class TemplateUpdate(TemplateBase):

    pass


class Template(TemplateBase):

    template_id: str
    name: str
    category: Category
    symbol: str
    builtin: bool
    template_type: NodeType
    compute_id: Union[str, None]


class TemplateUsage(BaseModel):

    x: int
    y: int
    name: Optional[str] = Field(None, description="Use this name to create a new node")
    compute_id: Optional[str] = Field(None, description="Used if the template doesn't have a default compute")
