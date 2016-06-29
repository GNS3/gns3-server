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

from gns3server.web.route import Route
from gns3server.config import Config
from gns3server.controller import Controller
from gns3server.schemas.version import VERSION_SCHEMA
from gns3server.version import __version__

from aiohttp.web import HTTPConflict, HTTPForbidden

import asyncio
import logging

log = logging.getLogger(__name__)


class ServerHandler:

    @classmethod
    @Route.post(
        r"/shutdown",
        description="Shutdown the local server",
        status_codes={
            201: "Server is shutting down",
            403: "Server shutdown refused"
        })
    def shutdown(request, response):

        config = Config.instance()
        if config.get_section_config("Server").getboolean("local", False) is False:
            raise HTTPForbidden(text="You can only stop a local server")

        log.info("Start shutting down the server")

        # close all the projects first
        controller = Controller.instance()
        projects = controller.projects.values()

        tasks = []
        for project in projects:
            tasks.append(asyncio.async(project.close()))

        if tasks:
            done, _ = yield from asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    log.error("Could not close project {}".format(e), exc_info=1)
                    continue

        # then shutdown the server itself
        from gns3server.web.web_server import WebServer
        server = WebServer.instance()
        asyncio.async(server.shutdown_server())
        response.set_status(201)

    @Route.get(
        r"/version",
        description="Retrieve the server version number",
        output=VERSION_SCHEMA)
    def version(request, response):

        config = Config.instance()
        local_server = config.get_section_config("Server").getboolean("local", False)
        response.json({"version": __version__, "local": local_server})

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

    @Route.get(
        r"/settings",
        description="Retrieve gui settings from the server. Temporary will we removed in later release")
    def read_settings(request, response):

        response.json(Controller.instance().settings)

    @Route.post(
        r"/settings",
        description="Write gui settings on the server. Temporary will we removed in later releas",
        status_codes={
            201: "Writed"
        })
    def write_settings(request, response):
        controller = Controller.instance()
        controller.settings = request.json
        controller.save()
        response.json(controller.settings)
        response.set_status(201)
