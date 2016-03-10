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

import aiohttp
import asyncio


from ....web.route import Route
from ....schemas.project import PROJECT_OBJECT_SCHEMA, PROJECT_CREATE_SCHEMA
from ....controller import Controller
from ....controller.project import Project


import logging
log = logging.getLogger()


class ProjectHandler:

    @classmethod
    @Route.post(
        r"/projects",
        description="Create a new project on the server",
        status_codes={
            201: "Project created",
            409: "Project already created"
        },
        output=PROJECT_OBJECT_SCHEMA,
        input=PROJECT_CREATE_SCHEMA)
    def create_project(request, response):

        controller = Controller.instance()
        project = Project(name=request.json.get("name"),
                          path=request.json.get("path"),
                          project_id=request.json.get("project_id"),
                          temporary=request.json.get("temporary", False))
        yield from controller.addProject(project)
        response.set_status(201)
        response.json(project)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/commit",
        description="Write changes on disk",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            204: "Changes have been written on disk",
            404: "The project doesn't exist"
        })
    def commit(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        yield from project.commit()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/close",
        description="Close a project",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            204: "The project has been closed",
            404: "The project doesn't exist"
        })
    def close(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        yield from project.close()
        controller.removeProject(project)
        response.set_status(204)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}",
        description="Delete a project from disk",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            204: "Changes have been written on disk",
            404: "The project doesn't exist"
        })
    def delete(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        yield from project.delete()
        controller.removeProject(project)
        response.set_status(204)
