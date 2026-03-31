#!/usr/bin/env python
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

"""
API routes for symbols.
"""

import os

from fastapi import APIRouter, Request, Depends, Response, status
from fastapi.responses import FileResponse
from typing import List

from gns3server.controller import Controller
from gns3server import schemas
from gns3server.controller.controller_error import ControllerError, ControllerNotFoundError, ControllerForbiddenError
from gns3server.utils.get_resource import get_resource

from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)


router = APIRouter()


@router.get(
    "",
    dependencies=[Depends(has_privilege("Symbol.Audit"))]
)
def get_symbols() -> List[dict]:
    """
    Return all symbols.

    Required privilege: Symbol.Audit
    """

    controller = Controller.instance()
    return controller.symbols.list()


@router.get(
    "/{symbol_id:path}/raw",
    responses={404: {"model": schemas.ErrorMessage, "description": "Could not find symbol"}},
    # FIXME: this is a temporary workaround due to a bug in the web-ui: https://github.com/GNS3/gns3-web-ui/issues/1466
    # dependencies=[Depends(has_privilege("Symbol.Audit"))]
)
async def get_symbol(symbol_id: str) -> FileResponse:
    """
    Download a symbol file.

    Required privilege: Symbol.Audit
    """

    controller = Controller.instance()
    try:
        symbol = controller.symbols.get_path(symbol_id)
        return FileResponse(symbol)
    except (KeyError, OSError) as e:
        raise ControllerNotFoundError(f"Could not get symbol file: {e}")


@router.get(
    "/{symbol_id:path}/dimensions",
    responses={404: {"model": schemas.ErrorMessage, "description": "Could not find symbol"}},
    dependencies=[Depends(has_privilege("Symbol.Audit"))]
)
async def get_symbol_dimensions(symbol_id: str) -> dict:
    """
    Get a symbol dimensions.

    Required privilege: Symbol.Audit
    """

    controller = Controller.instance()
    try:
        width, height, _ = controller.symbols.get_size(symbol_id)
        symbol_dimensions = {"width": width, "height": height}
        return symbol_dimensions
    except (KeyError, OSError, ValueError) as e:
        raise ControllerNotFoundError(f"Could not get symbol file: {e}")


@router.get("/default_symbols", dependencies=[Depends(has_privilege("Symbol.Audit"))])
def get_default_symbols() -> dict:
    """
    Return all default symbols.

    Required privilege: Symbol.Audit
    """

    controller = Controller.instance()
    return controller.symbols.default_symbols()


@router.post(
    "/{symbol_id:path}/raw",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Symbol.Allocate"))]
)
async def upload_symbol(symbol_id: str, request: Request) -> None:
    """
    Upload a symbol file.

    Required privilege: Symbol.Allocate
    """

    controller = Controller.instance()
    path = os.path.join(controller.symbols.symbols_path(), os.path.basename(symbol_id))

    try:
        with open(path, "wb") as f:
            f.write(await request.body())
    except (UnicodeEncodeError, OSError) as e:
        raise ControllerError(f"Could not write symbol file '{path}': {e}")

    # Reset the symbol list
    controller.symbols.list()


@router.delete(
    "/{symbol_id:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Symbol.Allocate"))]
)
async def delete_symbol(symbol_id: str) -> None:
    """
    Delete a custom symbol file.

    Required privilege: Symbol.Allocate
    """

    controller = Controller.instance()

    # Cannot delete built-in symbols
    if symbol_id.startswith(":/"):
        raise ControllerForbiddenError("Cannot delete built-in symbols")

    try:
        symbol_path = controller.symbols.get_path(symbol_id)
    except (KeyError, ControllerNotFoundError) as e:
        raise ControllerNotFoundError(f"Symbol '{symbol_id}' not found: {e}")

    # Check if it's a built-in symbol (in resource directory)
    symbols_resource_dir = get_resource("symbols")
    if symbols_resource_dir and os.path.commonprefix([symbols_resource_dir, symbol_path]) == symbols_resource_dir:
        raise ControllerForbiddenError("Cannot delete built-in symbols")

    # Delete the file
    try:
        os.remove(symbol_path)
        log.info(f"Deleted symbol file '{symbol_path}'")
    except OSError as e:
        raise ControllerError(f"Could not delete symbol file '{symbol_path}': {e}")

    # Clear the symbol size cache
    controller.symbols._symbol_size_cache.pop(symbol_id, None)

    # Reset the symbol list
    controller.symbols.list()
