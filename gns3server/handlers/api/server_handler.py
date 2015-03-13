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
from aiohttp.web import HTTPForbidden
import asyncio

class ServerHandler:

    @classmethod
    @Route.post(
        r"/server/shutdown",
        description="Shutdown the local server",
        status_codes={
            201: "Server is shutting down",
            403: "Server shutdown refused"
        })
    def shutdown(request, response):

        config = Config.instance()
        if config.get_section_config("Server").getboolean("local", False) is False:
            raise HTTPForbidden(text="You can only stop a local server")

        from gns3server.server import Server
        server = Server.instance()
        asyncio.async(server.shutdown_server())
        response.set_status(201)
