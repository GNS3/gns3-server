# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import sys

from gns3server.web.route import Route
from gns3server.config import Config
from gns3server.schemas.capabilities import CAPABILITIES_SCHEMA
from gns3server.version import __version__
from gns3server.compute import MODULES
from aiohttp.web import HTTPConflict


class CapabilitiesHandler:

    @Route.get(
        r"/capabilities",
        description="Retrieve the capabilities of the server",
        output=CAPABILITIES_SCHEMA)
    def get(request, response):

        node_types = []
        for module in MODULES:
            node_types.extend(module.node_types())

        response.json({
            "version": __version__,
            "platform": sys.platform,
            "node_types": node_types
        })
