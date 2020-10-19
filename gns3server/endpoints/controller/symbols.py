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
API endpoints for symbols.
"""

import os

from fastapi import APIRouter, Request, status
from fastapi.responses import FileResponse

from gns3server.controller import Controller
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.controller.controller_error import ControllerError, ControllerNotFoundError

import logging
log = logging.getLogger(__name__)


router = APIRouter()


@router.get("")
def get_symbols():

    controller = Controller.instance()
    return controller.symbols.list()


@router.get("/{symbol_id:path}/raw",
            responses={404: {"model": ErrorMessage, "description": "Could not find symbol"}})
async def get_symbol(symbol_id: str):
    """
    Download a symbol file.
    """

    controller = Controller.instance()
    try:
        symbol = controller.symbols.get_path(symbol_id)
        return FileResponse(symbol)
    except (KeyError, OSError) as e:
        return ControllerNotFoundError("Could not get symbol file: {}".format(e))


@router.post("/{symbol_id:path}/raw",
             status_code=status.HTTP_204_NO_CONTENT)
async def upload_symbol(symbol_id: str, request: Request):
    """
    Upload a symbol file.
    """

    controller = Controller.instance()
    path = os.path.join(controller.symbols.symbols_path(), os.path.basename(symbol_id))

    try:
        with open(path, "wb") as f:
            f.write(await request.body())
    except (UnicodeEncodeError, OSError) as e:
        raise ControllerError("Could not write symbol file '{}': {}".format(path, e))

    # Reset the symbol list
    controller.symbols.list()


@router.get("/default_symbols")
def get_default_symbols():
    """
    Return all default symbols.
    """

    controller = Controller.instance()
    return controller.symbols.default_symbols()
