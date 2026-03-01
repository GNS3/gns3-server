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
from typing import Optional, Dict, List, Any
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
    password: SecretStr = Field(..., min_length=8, max_length=100)


class UserUpdate(UserBase):
    """
    Properties to update a user.
    """

    password: Optional[SecretStr] = Field(None, min_length=8, max_length=100)


class LoggedInUserUpdate(BaseModel):
    """
    Properties to update a logged-in user.
    """

    password: Optional[SecretStr] = Field(None, min_length=8, max_length=100)
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


# User settings schemas

class UserSettingBase(BaseModel):
    """
    Common user setting properties.
    """

    key: str
    value: Optional[str] = None


class UserSettingCreate(UserSettingBase):
    """
    Properties to create a user setting.
    """

    value: str


class UserSettingUpdate(BaseModel):
    """
    Properties to update a user setting.
    """

    value: str


class UserSetting(DateTimeModelMixin, UserSettingBase):
    """
    Complete user setting model.
    """

    setting_id: UUID
    user_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UserSettingsResponse(BaseModel):
    """
    Response for getting all user settings.
    """

    user_id: UUID
    settings: Dict[str, str]


class UserSettingsUpdate(BaseModel):
    """
    Request to update multiple user settings.
    """

    settings: Dict[str, str]


class UserSettingValue(BaseModel):
    """
    Request to update a single user setting.
    """

    value: str


# Model profile schemas for multi-model configuration

class ModelProfile(BaseModel):
    """
    A single model configuration profile.
    Allow extra fields for future extensibility.
    """

    name: str = Field(..., min_length=1, max_length=50)
    provider: str = Field(default="openai")
    model: str
    api_key: str
    base_url: str = ""  # Optional, uses provider default if empty
    temperature: str = "0.7"

    model_config = ConfigDict(extra="allow")  # Allow extra fields


class ModelProfileCreate(BaseModel):
    """
    Request to create a new model profile.
    Allow extra fields for future extensibility.
    """

    name: str = Field(..., min_length=1, max_length=50)
    provider: str = "openai"
    model: str
    api_key: str
    base_url: str = ""  # Optional, uses provider default if empty
    temperature: str = "0.7"

    model_config = ConfigDict(extra="allow")  # Allow extra fields


class ModelProfileUpdate(BaseModel):
    """
    Request to update a model profile.
    Allow extra fields for future extensibility.
    """

    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[str] = None

    model_config = ConfigDict(extra="allow")  # Allow extra fields


class ModelConfigsResponse(BaseModel):
    """
    Response containing all model profiles and active profile.
    Includes version for optimistic locking.
    """

    profiles: List[ModelProfile]
    active: str
    version: int  # Version for optimistic locking


class ActiveProfileRequest(BaseModel):
    """
    Request to set the active model profile.
    """

    profile_name: str
    expected_version: Optional[int] = None  # For optimistic locking
