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
    async def list_drawings(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
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
    async def create(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        drawing = await project.add_drawing(**request.json)
        response.set_status(201)
        response.json(drawing)

    @Route.get(
        r"/projects/{project_id}/drawings/{drawing_id}",
        parameters={
            "project_id": "Project UUID",
            "drawing_id": "Drawing UUID"
        },
        status_codes={
            200: "Drawing found",
            400: "Invalid request",
            404: "Drawing doesn't exist"
        },
        description="Get a drawing instance",
        output=DRAWING_OBJECT_SCHEMA)
    async def get_drawing(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        drawing = project.get_drawing(request.match_info["drawing_id"])
        response.set_status(200)
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
        description="Update a drawing instance",
        input=DRAWING_OBJECT_SCHEMA,
        output=DRAWING_OBJECT_SCHEMA)
    async def update(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        drawing = project.get_drawing(request.match_info["drawing_id"])
        await drawing.update(**request.json)
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
    async def delete(request, response):

        project = await Controller.instance().get_loaded_project(request.match_info["project_id"])
        await project.delete_drawing(request.match_info["drawing_id"])
        response.set_status(204)
