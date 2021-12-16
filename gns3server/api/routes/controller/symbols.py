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
from gns3server.controller.controller_error import ControllerError, ControllerNotFoundError

from .dependencies.authentication import get_current_active_user

import logging

log = logging.getLogger(__name__)


router = APIRouter()


@router.get("")
def get_symbols() -> List[str]:

    controller = Controller.instance()
    return controller.symbols.list()


@router.get(
    "/{symbol_id:path}/raw", responses={404: {"model": schemas.ErrorMessage, "description": "Could not find symbol"}}
)
async def get_symbol(symbol_id: str) -> FileResponse:
    """
    Download a symbol file.
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
)
async def get_symbol_dimensions(symbol_id: str) -> dict:
    """
    Get a symbol dimensions.
    """

    controller = Controller.instance()
    try:
        width, height, _ = controller.symbols.get_size(symbol_id)
        symbol_dimensions = {"width": width, "height": height}
        return symbol_dimensions
    except (KeyError, OSError, ValueError) as e:
        raise ControllerNotFoundError(f"Could not get symbol file: {e}")


@router.get("/default_symbols")
def get_default_symbols() -> dict:
    """
    Return all default symbols.
    """

    controller = Controller.instance()
    return controller.symbols.default_symbols()


@router.post(
    "/{symbol_id:path}/raw",
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_204_NO_CONTENT
)
async def upload_symbol(symbol_id: str, request: Request) -> Response:
    """
    Upload a symbol file.
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

    return Response(status_code=status.HTTP_204_NO_CONTENT)