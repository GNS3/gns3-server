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
from gns3server.controller import Controller
from gns3server.schemas.node import NODE_OBJECT_SCHEMA
from gns3server.schemas.appliance import APPLIANCE_USAGE_SCHEMA

import hashlib
import json

from gns3server.schemas.appliance import (
    APPLIANCE_OBJECT_SCHEMA,
    APPLIANCE_UPDATE_SCHEMA,
    APPLIANCE_CREATE_SCHEMA
)

import logging
log = logging.getLogger(__name__)


class ApplianceHandler:
    """API entry points for appliance management."""

    @Route.get(
        r"/appliances/templates",
        description="List of appliance templates",
        status_codes={
            200: "Appliance template list returned"
        })
    async def list_templates(request, response):

        controller = Controller.instance()
        if request.query.get("update", "no") == "yes":
            await controller.download_appliance_templates()
        controller.load_appliance_templates()
        response.json([c for c in controller.appliance_templates.values()])

    @Route.post(
        r"/appliances",
        description="Create a new appliance",
        status_codes={
            201: "Appliance created",
            400: "Invalid request"
        },
        input=APPLIANCE_CREATE_SCHEMA,
        output=APPLIANCE_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        appliance = controller.add_appliance(request.json)
        response.set_status(201)
        response.json(appliance)

    @Route.get(
        r"/appliances/{appliance_id}",
        status_codes={
            200: "Appliance found",
            400: "Invalid request",
            404: "Appliance doesn't exist"
        },
        description="Get an appliance",
        output=APPLIANCE_OBJECT_SCHEMA)
    def get(request, response):

        request_etag = request.headers.get("If-None-Match", "")
        controller = Controller.instance()
        appliance = controller.get_appliance(request.match_info["appliance_id"])
        data = json.dumps(appliance.__json__())
        appliance_etag = '"' + hashlib.md5(data.encode()).hexdigest() + '"'
        if appliance_etag == request_etag:
            response.set_status(304)
        else:
            response.headers["ETag"] = appliance_etag
            response.set_status(200)
            response.json(appliance)

    @Route.put(
        r"/appliances/{appliance_id}",
        status_codes={
            200: "Appliance updated",
            400: "Invalid request",
            404: "Appliance doesn't exist"
        },
        description="Update an appliance",
        input=APPLIANCE_UPDATE_SCHEMA,
        output=APPLIANCE_OBJECT_SCHEMA)
    def update(request, response):

        controller = Controller.instance()
        appliance = controller.get_appliance(request.match_info["appliance_id"])
        # Ignore these because we only use them when creating a appliance
        request.json.pop("appliance_id", None)
        request.json.pop("appliance_type", None)
        request.json.pop("compute_id", None)
        request.json.pop("builtin", None)
        appliance.update(**request.json)
        response.set_status(200)
        response.json(appliance)

    @Route.delete(
        r"/appliances/{appliance_id}",
        parameters={
            "appliance_id": "Node UUID"
        },
        status_codes={
            204: "Appliance deleted",
            400: "Invalid request",
            404: "Appliance doesn't exist"
        },
        description="Delete an appliance")
    def delete(request, response):

        controller = Controller.instance()
        controller.delete_appliance(request.match_info["appliance_id"])
        response.set_status(204)

    @Route.get(
        r"/appliances",
        description="List of appliance",
        status_codes={
            200: "Appliance list returned"
        })
    def list(request, response):

        controller = Controller.instance()
        response.json([c for c in controller.appliances.values()])

    @Route.post(
        r"/projects/{project_id}/appliances/{appliance_id}",
        description="Create a node from an appliance",
        parameters={
            "project_id": "Project UUID",
            "appliance_id": "Appliance UUID"
        },
        status_codes={
            201: "Node created",
            404: "The project or appliance doesn't exist"
        },
        input=APPLIANCE_USAGE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    async def create_node_from_appliance(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        await project.add_node_from_appliance(request.match_info["appliance_id"],
                                              x=request.json["x"],
                                              y=request.json["y"],
                                              compute_id=request.json.get("compute_id"))
        response.set_status(201)
