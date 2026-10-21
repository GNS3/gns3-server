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
Optional optimistic concurrency (ETag / If-Match) for controller resources.
"""

import asyncio
import contextlib
import hashlib
import json
from typing import Any, AsyncIterator, Optional

from fastapi import Header, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder

from gns3server import schemas

ETAG_RESPONSE_HEADERS: dict[str, Any] = {
    "ETag": {
        "description": "Entity tag of the current representation of the resource",
        "schema": {"type": "string"},
    }
}

PRECONDITION_FAILED_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_412_PRECONDITION_FAILED: {
        "model": schemas.ErrorMessage,
        "description": "The If-Match header does not match the current ETag of the resource",
    }
}

GET_RESPONSES: dict[int | str, dict[str, Any]] = {status.HTTP_200_OK: {"headers": ETAG_RESPONSE_HEADERS}}

PUT_RESPONSES: dict[int | str, dict[str, Any]] = {**GET_RESPONSES, **PRECONDITION_FAILED_RESPONSE}

_locks: dict[str, list[Any]] = {}


def compute_etag(resource: Any) -> str:
    """
    Compute a strong entity tag from the serialized resource.
    """

    payload = json.dumps(jsonable_encoder(resource), sort_keys=True, separators=(",", ":"), default=str)
    return f'"{hashlib.sha256(payload.encode()).hexdigest()[:32]}"'


def set_etag(response: Response, resource: Any) -> None:
    """
    Add the ETag header of the resource to the response.
    """

    response.headers["ETag"] = compute_etag(resource)


def if_match_header(
    if_match: Optional[str] = Header(
        None,
        alias="If-Match",
        description="Only apply the update if this entity tag matches the current resource",
    ),
) -> Optional[str]:
    """
    Dependency returning the raw If-Match request header.
    """

    return if_match


def check_if_match(if_match: Optional[str], resource: Any) -> None:
    """
    Raise a 412 error if If-Match is present and does not match the resource.
    """

    if if_match is None:
        return
    candidates = [tag.strip() for tag in if_match.split(",")]
    if "*" in candidates:
        return
    if compute_etag(resource) not in candidates:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="The resource was modified since it was last retrieved (If-Match does not match the current ETag)",
        )


@contextlib.asynccontextmanager
async def serialize_updates(key: str) -> AsyncIterator[None]:
    """
    Serialize updates of the same resource so that the If-Match check and the update are atomic.
    """

    entry = _locks.setdefault(key, [asyncio.Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            yield
    finally:
        entry[1] -= 1
        if entry[1] <= 0:
            _locks.pop(key, None)
