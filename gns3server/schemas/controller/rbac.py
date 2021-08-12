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

from typing import Optional, List
from pydantic import BaseModel, validator
from uuid import UUID
from enum import Enum

from .base import DateTimeModelMixin


class HTTPMethods(str, Enum):
    """
    HTTP method type.
    """

    get = "GET"
    head = "HEAD"
    post = "POST"
    patch = "PATCH"
    put = "PUT"
    delete = "DELETE"


class PermissionAction(str, Enum):
    """
    Action to perform when permission is matched.
    """

    allow = "ALLOW"
    deny = "DENY"


class PermissionBase(BaseModel):
    """
    Common permission properties.
    """

    methods: List[HTTPMethods]
    path: str
    action: PermissionAction
    description: Optional[str] = None

    class Config:
        use_enum_values = True

    @validator("action", pre=True)
    def action_uppercase(cls, v):
        return v.upper()


class PermissionCreate(PermissionBase):
    """
    Properties to create a permission.
    """

    pass


class PermissionUpdate(PermissionBase):
    """
    Properties to update a role.
    """

    pass


class Permission(DateTimeModelMixin, PermissionBase):

    permission_id: UUID

    class Config:
        orm_mode = True


class RoleBase(BaseModel):
    """
    Common role properties.
    """

    name: Optional[str] = None
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """
    Properties to create a role.
    """

    name: str


class RoleUpdate(RoleBase):
    """
    Properties to update a role.
    """

    pass


class Role(DateTimeModelMixin, RoleBase):

    role_id: UUID
    is_builtin: bool
    permissions: List[Permission]

    class Config:
        orm_mode = True
