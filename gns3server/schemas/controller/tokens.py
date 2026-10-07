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
from uuid import UUID

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    username: str
    token_version: int = 0
    token_use: str = "access"


class RefreshTokenRequest(BaseModel):
    """Schema for requesting a token refresh."""

    refresh_token: str


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str


class ApiKey(BaseModel):
    """API key metadata. The secret is never returned after creation."""

    api_key_id: UUID
    name: str
    key_prefix: str
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None
    revoked: bool


class ApiKeyCreated(BaseModel):
    """A newly created API key. The full key is returned only once."""

    api_key_id: UUID
    api_key: str
    name: str
    key_prefix: str
    created_at: Optional[str] = None


class ApiKeyMessage(BaseModel):
    """Confirmation message returned when an API key is revoked or restored."""

    message: str
