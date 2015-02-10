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

import os
from ..web.route import Route
from ..schemas.dynamips import ROUTER_CREATE_SCHEMA
from ..schemas.dynamips import ROUTER_OBJECT_SCHEMA
from ..modules.dynamips import Dynamips
from ..modules.project_manager import ProjectManager


class DynamipsHandler:

    """
    API entry points for Dynamips.
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/dynamips/routers",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request",
            409: "Conflict"
        },
        description="Create a new Dynamips router instance",
        input=ROUTER_CREATE_SCHEMA)
        #output=ROUTER_OBJECT_SCHEMA)
    def create(request, response):

        dynamips_manager = Dynamips.instance()
        vm = yield from dynamips_manager.create_vm(request.json.pop("name"),
                                                   request.match_info["project_id"],
                                                   request.json.get("vm_id"))

        #for name, value in request.json.items():
        #    if hasattr(vm, name) and getattr(vm, name) != value:
        #        setattr(vm, name, value)

        response.set_status(201)
        response.json(vm)
