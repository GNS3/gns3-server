#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

"""
API routes for API key management.
"""

import secrets
import bcrypt
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, status, HTTPException

from gns3server import schemas
from gns3server.db.repositories.api_keys import ApiKeysRepository
from .dependencies.database import get_repository
from .dependencies.authentication import get_current_active_user

import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix="/access/api-keys", tags=["API Keys"])

API_KEY_PREFIX = "gns3_"
API_KEY_BYTES = 32


def _generate_api_key(api_key_id: UUID = None) -> tuple[str, str, str, UUID]:
    if api_key_id is None:
        api_key_id = uuid4()
    random_bytes = secrets.token_hex(API_KEY_BYTES)
    raw_key = f"gns3_{api_key_id}_{random_bytes}"
    # Only hash the random secret part, so auth can extract api_key_id and do O(1) lookup
    key_hash = bcrypt.hashpw(random_bytes.encode(), bcrypt.gensalt()).decode()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix, api_key_id


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: schemas.ApiKeyCreate,
    current_user: schemas.User = Depends(get_current_active_user),
    api_keys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
) -> dict:
    """Create a new API key. The full key is returned only once."""

    raw_key, key_hash, key_prefix, new_key_id = _generate_api_key()
    db_key = await api_keys_repo.create_api_key(
        api_key_id=new_key_id,
        user_id=current_user.user_id,
        name=api_key_data.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    return {
        "api_key_id": str(db_key.api_key_id),
        "api_key": raw_key,
        "name": db_key.name,
        "key_prefix": db_key.key_prefix,
        "created_at": db_key.created_at.isoformat() if db_key.created_at else None,
    }


@router.get("")
async def list_api_keys(
    current_user: schemas.User = Depends(get_current_active_user),
    api_keys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
) -> list[dict]:
    """List all API keys for the current user."""

    keys = await api_keys_repo.get_api_keys_by_user(current_user.user_id)
    return [
        {
            "api_key_id": str(k.api_key_id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "revoked": k.revoked,
        }
        for k in keys
    ]


@router.post("/{api_key_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_api_key(
    api_key_id: UUID,
    current_user: schemas.User = Depends(get_current_active_user),
    api_keys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
) -> dict:
    """Revoke an API key. It will immediately stop working, but can be restored."""

    key = await api_keys_repo.get_api_key(api_key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot modify another user's API key")

    await api_keys_repo.revoke_api_key(api_key_id)
    return {"message": f"API key '{key.name}' revoked"}


@router.post("/{api_key_id}/restore", status_code=status.HTTP_200_OK)
async def restore_api_key(
    api_key_id: UUID,
    current_user: schemas.User = Depends(get_current_active_user),
    api_keys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
) -> dict:
    """Restore a previously revoked API key."""

    key = await api_keys_repo.get_api_key(api_key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot modify another user's API key")

    await api_keys_repo.restore_api_key(api_key_id)
    return {"message": f"API key '{key.name}' restored"}


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    api_key_id: UUID,
    current_user: schemas.User = Depends(get_current_active_user),
    api_keys_repo: ApiKeysRepository = Depends(get_repository(ApiKeysRepository)),
) -> None:
    """Permanently delete an API key. Cannot be undone."""

    key = await api_keys_repo.get_api_key(api_key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's API key")

    await api_keys_repo.delete_api_key(api_key_id)
