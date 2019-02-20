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
    def list_templates(request, response):

        controller = Controller.instance()
        response.json([c for c in controller.appliance_templates.values()])

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
            "appliance_id": "Appliance template UUID"
        },
        status_codes={
            201: "Node created",
            404: "The project or template doesn't exist"
        },
        input=APPLIANCE_USAGE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    def create_node_from_appliance(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        node = yield from project.add_node_from_appliance(request.match_info["appliance_id"],
                                                          x=request.json["x"],
                                                          y=request.json["y"],
                                                          compute_id=request.json.get("compute_id"))
        response.set_status(201)
        response.json(node)
