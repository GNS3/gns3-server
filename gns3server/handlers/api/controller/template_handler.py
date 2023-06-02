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
from gns3server.schemas.template import TEMPLATE_USAGE_SCHEMA

import hashlib
import json

from gns3server.schemas.template import (
    TEMPLATE_OBJECT_SCHEMA,
    TEMPLATE_UPDATE_SCHEMA,
    TEMPLATE_CREATE_SCHEMA
)

import logging
log = logging.getLogger(__name__)


class TemplateHandler:
    """
    API entry points for template management.
    """

    @Route.post(
        r"/templates",
        description="Create a new template",
        status_codes={
            201: "Template created",
            400: "Invalid request"
        },
        input=TEMPLATE_CREATE_SCHEMA,
        output=TEMPLATE_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        template = controller.template_manager.add_template(request.json)
        # Reset the symbol list
        controller.symbols.list()
        response.set_status(201)
        response.json(template)

    @Route.get(
        r"/templates/{template_id}",
        status_codes={
            200: "Template found",
            400: "Invalid request",
            404: "Template doesn't exist"
        },
        description="Get an template",
        output=TEMPLATE_OBJECT_SCHEMA)
    def get(request, response):

        request_etag = request.headers.get("If-None-Match", "")
        controller = Controller.instance()
        template = controller.template_manager.get_template(request.match_info["template_id"])
        data = json.dumps(template.__json__())
        template_etag = '"' + hashlib.md5(data.encode()).hexdigest() + '"'
        if template_etag == request_etag:
            response.set_status(304)
        else:
            response.headers["ETag"] = template_etag
            response.set_status(200)
            response.json(template)

    @Route.put(
        r"/templates/{template_id}",
        status_codes={
            200: "Template updated",
            400: "Invalid request",
            404: "Template doesn't exist"
        },
        description="Update an template",
        input=TEMPLATE_UPDATE_SCHEMA,
        output=TEMPLATE_OBJECT_SCHEMA)
    def update(request, response):

        controller = Controller.instance()
        template = controller.template_manager.get_template(request.match_info["template_id"])
        # Ignore these because we only use them when creating a template
        request.json.pop("template_id", None)
        request.json.pop("template_type", None)
        request.json.pop("compute_id", None)
        request.json.pop("builtin", None)
        template.update(**request.json)
        response.set_status(200)
        response.json(template)

    @Route.delete(
        r"/templates/{template_id}",
        parameters={
            "template_id": "template UUID"
        },
        status_codes={
            204: "Template deleted",
            400: "Invalid request",
            404: "Template doesn't exist"
        },
        description="Delete an template")
    def delete(request, response):

        controller = Controller.instance()
        controller.template_manager.delete_template(request.match_info["template_id"])
        response.set_status(204)

    @Route.get(
        r"/templates",
        description="List of template",
        status_codes={
            200: "Template list returned"
        })
    def list(request, response):

        controller = Controller.instance()
        response.json([c for c in controller.template_manager.templates.values()])

    @Route.post(
        r"/templates/{template_id}/duplicate",
        parameters={
            "template_id": "Template UUID"
        },
        status_codes={
            201: "Template duplicated",
            400: "Invalid request",
            404: "Template doesn't exist"
        },
        description="Duplicate an template",
        output=TEMPLATE_OBJECT_SCHEMA)
    async def duplicate(request, response):

        controller = Controller.instance()
        template = controller.template_manager.duplicate_template(request.match_info["template_id"])
        response.set_status(201)
        response.json(template)

    @Route.post(
        r"/projects/{project_id}/templates/{template_id}",
        description="Create a node from a template",
        parameters={
            "project_id": "Project UUID",
            "template_id": "Template UUID"
        },
        status_codes={
            201: "Node created",
            404: "The project or template doesn't exist"
        },
        input=TEMPLATE_USAGE_SCHEMA,
        output=NODE_OBJECT_SCHEMA)
    async def create_node_from_template(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        node = await project.add_node_from_template(request.match_info["template_id"],
                                                    x=request.json["x"],
                                                    y=request.json["y"],
                                                    name=request.json.get("name"),
                                                    compute_id=request.json.get("compute_id"))
        response.set_status(201)
        response.json(node)
