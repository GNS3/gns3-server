#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import os
from gns3server.web.route import Route
from gns3server.controller import Controller


import logging
log = logging.getLogger(__name__)


class SymbolHandler:
    """API entry points for symbols management."""

    @Route.get(
        r"/symbols",
        description="List of symbols",
        status_codes={
            200: "Symbols list returned"
        })
    def list(request, response):

        controller = Controller.instance()
        response.json(controller.symbols.list())

    @Route.get(
        r"/symbols/{symbol_id:.+}/raw",
        description="Get the symbol file",
        status_codes={
            200: "Symbol returned"
        })
    def raw(request, response):

        controller = Controller.instance()
        try:
            yield from response.file(controller.symbols.get_path(request.match_info["symbol_id"]))
        except (KeyError, FileNotFoundError, PermissionError):
            response.set_status(404)

    @Route.post(
        r"/symbols/{symbol_id:.+}/raw",
        description="Write the symbol file",
        status_codes={
            200: "Symbol returned"
        },
        raw=True)
    def upload(request, response):
        controller = Controller.instance()
        path = os.path.join(controller.symbols.symbols_path(), os.path.basename(request.match_info["symbol_id"]))
        with open(path, 'wb+') as f:
            while True:
                packet = yield from request.content.read(512)
                if not packet:
                    break
                f.write(packet)
        # Reset the symbol list
        controller.symbols.list()
        response.set_status(204)
