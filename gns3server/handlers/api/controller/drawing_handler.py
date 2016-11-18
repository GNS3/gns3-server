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

from gns3server.schemas.drawing import (
    DRAWING_OBJECT_SCHEMA,
)


class DrawingHandler:
    """
    API entry point for Drawing
    """

    @Route.get(
        r"/projects/{project_id}/drawings",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            200: "List of drawings returned",
        },
        description="List drawings of a project")
    def list_drawings(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        response.json([v for v in project.drawings.values()])

    @Route.post(
        r"/projects/{project_id}/drawings",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Drawing created",
            400: "Invalid request"
        },
        description="Create a new drawing instance",
        input=DRAWING_OBJECT_SCHEMA,
        output=DRAWING_OBJECT_SCHEMA)
    def create(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        drawing = yield from project.add_drawing(**request.json)
        response.set_status(201)
        response.json(drawing)

    @Route.put(
        r"/projects/{project_id}/drawings/{drawing_id}",
        parameters={
            "project_id": "Project UUID",
            "drawing_id": "Drawing UUID"
        },
        status_codes={
            201: "Drawing updated",
            400: "Invalid request"
        },
        description="Create a new drawing instance",
        input=DRAWING_OBJECT_SCHEMA,
        output=DRAWING_OBJECT_SCHEMA)
    def update(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        drawing = project.get_drawing(request.match_info["drawing_id"])
        yield from drawing.update(**request.json)
        response.set_status(201)
        response.json(drawing)

    @Route.delete(
        r"/projects/{project_id}/drawings/{drawing_id}",
        parameters={
            "project_id": "Project UUID",
            "drawing_id": "Drawing UUID"
        },
        status_codes={
            204: "Drawing deleted",
            400: "Invalid request"
        },
        description="Delete a drawing instance")
    def delete(request, response):

        project = yield from Controller.instance().get_loaded_project(request.match_info["project_id"])
        yield from project.delete_drawing(request.match_info["drawing_id"])
        response.set_status(204)
