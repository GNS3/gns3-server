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

import asyncio
from aiohttp.web import HTTPForbidden

from ....web.route import Route
from ....config import Config
from ....modules.project_manager import ProjectManager
from ....schemas.hypervisor import HYPERVISOR_CREATE_SCHEMA, HYPERVISOR_OBJECT_SCHEMA
from ....controller import Controller
from ....controller.hypervisor import Hypervisor


import logging
log = logging.getLogger(__name__)


class HypervisorHandler:
    """API entry points for hypervisor management."""

    @classmethod
    @Route.post(
        r"/hypervisors",
        description="Register a hypervisor",
        status_codes={
            201: "Hypervisor added"
        },
        input=HYPERVISOR_CREATE_SCHEMA,
        output=HYPERVISOR_OBJECT_SCHEMA)
    def create(request, response):

        hypervisor = Hypervisor(request.json.pop("hypervisor_id"), **request.json)
        Controller.instance().addHypervisor(hypervisor)

        response.set_status(201)
        response.json(hypervisor)

    @classmethod
    @Route.post(
        r"/hypervisors/shutdown",
        description="Shutdown the local hypervisor",
        status_codes={
            201: "Hypervisor is shutting down",
            403: "Hypervisor shutdown refused"
        })
    def shutdown(request, response):

        config = Config.instance()
        if config.get_section_config("Hypervisor").getboolean("local", False) is False:
            raise HTTPForbidden(text="You can only stop a local hypervisor")

        # close all the projects first
        pm = ProjectManager.instance()
        projects = pm.projects

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

        # then shutdown the hypervisor itself
        from gns3server.web.web_server import WebServer
        server = WebServer.instance()
        asyncio.async(server.shutdown_server())
        response.set_status(201)
