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

from datetime import datetime
from typing import Optional
from pydantic import ConfigDict, EmailStr, BaseModel, Field, SecretStr
from uuid import UUID

from .base import DateTimeModelMixin


class UserBase(BaseModel):
    """
    Common user properties.
    """

    username: Optional[str] = Field(None, min_length=3, pattern="[a-zA-Z0-9_-]+$")
    is_active: bool = True
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """
    Properties to create a user.
    """

    username: str = Field(..., min_length=3, pattern="[a-zA-Z0-9_-]+$")
    password: SecretStr = Field(..., min_length=6, max_length=100)


class UserUpdate(UserBase):
    """
    Properties to update a user.
    """

    password: Optional[SecretStr] = Field(None, min_length=6, max_length=100)


class LoggedInUserUpdate(BaseModel):
    """
    Properties to update a logged-in user.
    """

    password: Optional[SecretStr] = Field(None, min_length=6, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


class User(DateTimeModelMixin, UserBase):

    user_id: UUID
    last_login: Optional[datetime] = None
    is_superadmin: bool = False
    model_config = ConfigDict(from_attributes=True)


class UserGroupBase(BaseModel):
    """
    Common user group properties.
    """

    name: Optional[str] = Field(None, min_length=3, pattern="[a-zA-Z0-9_-]+$")


class UserGroupCreate(UserGroupBase):
    """
    Properties to create a user group.
    """

    name: Optional[str] = Field(..., min_length=3, pattern="[a-zA-Z0-9_-]+$")


class UserGroupUpdate(UserGroupBase):
    """
    Properties to update a user group.
    """

    pass


class UserGroup(DateTimeModelMixin, UserGroupBase):

    user_group_id: UUID
    is_builtin: bool
    model_config = ConfigDict(from_attributes=True)


class Credentials(BaseModel):

    username: str
    password: str
