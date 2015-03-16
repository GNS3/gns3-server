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

from ...web.route import Route
from ...config import Config
from ...schemas.version import VERSION_SCHEMA
from ...version import __version__
from aiohttp.web import HTTPConflict


class VersionHandler:

    @classmethod
    @Route.get(
        r"/version",
        description="Retrieve the server version number",
        output=VERSION_SCHEMA)
    def version(request, response):

        config = Config.instance()
        local_server = config.get_section_config("Server").getboolean("local", False)
        response.json({"version": __version__, "local": local_server})

    @classmethod
    @Route.post(
        r"/version",
        description="Check if version is the same as the server",
        output=VERSION_SCHEMA,
        input=VERSION_SCHEMA,
        status_codes={
            200: "Same version",
            409: "Invalid version"
        })
    def check_version(request, response):
        if request.json["version"] != __version__:
            raise HTTPConflict(text="Client version {} differs with server version {}".format(request.json["version"], __version__))
        response.json({"version": __version__})
