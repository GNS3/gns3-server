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
