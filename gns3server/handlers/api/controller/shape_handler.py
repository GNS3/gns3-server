# -*- coding: utf-8 -*-
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

import aiohttp

from gns3server.web.route import Route
from gns3server.controller import Controller

from gns3server.schemas.shape import (
    SHAPE_OBJECT_SCHEMA,
)


class ShapeHandler:
    """
    API entry point for Shape
    """

    @Route.get(
        r"/projects/{project_id}/shapes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            200: "List of shapes returned",
        },
        description="List shapes of a project")
    def list_shapes(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.json([v for v in project.shapes.values()])

    @Route.post(
        r"/projects/{project_id}/shapes",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Shape created",
            400: "Invalid request"
        },
        description="Create a new shape instance",
        input=SHAPE_OBJECT_SCHEMA,
        output=SHAPE_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        shape = yield from project.add_shape(**request.json)
        response.set_status(201)
        response.json(shape)

    @Route.put(
        r"/projects/{project_id}/shapes/{shape_id}",
        parameters={
            "project_id": "Project UUID",
            "shape_id": "Shape UUID"
        },
        status_codes={
            201: "Shape updated",
            400: "Invalid request"
        },
        description="Create a new shape instance",
        input=SHAPE_OBJECT_SCHEMA,
        output=SHAPE_OBJECT_SCHEMA)
    def update(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        shape = project.get_shape(request.match_info["shape_id"])
        yield from shape.update(**request.json)
        response.set_status(201)
        response.json(shape)

    @Route.delete(
        r"/projects/{project_id}/shapes/{shape_id}",
        parameters={
            "project_id": "Project UUID",
            "shape_id": "Shape UUID"
        },
        status_codes={
            204: "Shape deleted",
            400: "Invalid request"
        },
        description="Delete a shape instance")
    def delete(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        yield from project.delete_shape(request.match_info["shape_id"])
        response.set_status(204)

