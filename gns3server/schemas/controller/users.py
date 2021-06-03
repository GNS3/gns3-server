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
from pydantic import EmailStr, BaseModel, Field, SecretStr
from uuid import UUID

from .base import DateTimeModelMixin


class UserBase(BaseModel):
    """
    Common user properties.
    """

    username: Optional[str] = Field(None, min_length=3, regex="[a-zA-Z0-9_-]+$")
    email: Optional[EmailStr]
    full_name: Optional[str]


class UserCreate(UserBase):
    """
    Properties to create an user.
    """

    username: str = Field(..., min_length=3, regex="[a-zA-Z0-9_-]+$")
    password: SecretStr = Field(..., min_length=6, max_length=100)


class UserUpdate(UserBase):
    """
    Properties to update an user.
    """

    password: Optional[SecretStr] = Field(None, min_length=6, max_length=100)


class User(DateTimeModelMixin, UserBase):

    user_id: UUID
    is_active: bool = True
    is_superadmin: bool = False

    class Config:
        orm_mode = True


class UserGroupBase(BaseModel):
    """
    Common user group properties.
    """

    name: Optional[str] = Field(None, min_length=3, regex="[a-zA-Z0-9_-]+$")


class UserGroupCreate(UserGroupBase):
    """
    Properties to create an user group.
    """

    name: Optional[str] = Field(..., min_length=3, regex="[a-zA-Z0-9_-]+$")


class UserGroupUpdate(UserGroupBase):
    """
    Properties to update an user group.
    """

    pass


class UserGroup(DateTimeModelMixin, UserGroupBase):

    user_group_id: UUID
    builtin: bool

    class Config:
        orm_mode = True


class Credentials(BaseModel):

    username: str
    password: str
