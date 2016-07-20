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


from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.config import Config


from gns3server.schemas.project import (
    PROJECT_OBJECT_SCHEMA,
    PROJECT_LOAD_SCHEMA,
    PROJECT_CREATE_SCHEMA
)

import logging
log = logging.getLogger()


class ProjectHandler:

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
        project = yield from controller.add_project(name=request.json.get("name"),
                                                    path=request.json.get("path"),
                                                    project_id=request.json.get("project_id"))
        response.set_status(201)
        response.json(project)

    @Route.get(
        r"/projects",
        description="List projects",
        status_codes={
            200: "List of projects",
        })
    def list_projects(request, response):
        controller = Controller.instance()
        response.json([p for p in controller.projects.values()])

    @Route.get(
        r"/projects/{project_id}",
        description="Get a project",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            200: "Project information returned",
            404: "The project doesn't exist"
        })
    def get(request, response):
        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.json(project)

    @Route.post(
        r"/projects/{project_id}/close",
        description="Close a project",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            204: "The project has been closed",
            404: "The project doesn't exist"
        },
        output=PROJECT_OBJECT_SCHEMA)
    def close(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        yield from project.close()
        response.set_status(201)
        response.json(project)

    @Route.post(
        r"/projects/{project_id}/open",
        description="Open a project",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            201: "The project has been opened",
            404: "The project doesn't exist"
        },
        output=PROJECT_OBJECT_SCHEMA)
    def open(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        yield from project.open()
        response.set_status(201)
        response.json(project)

    @Route.post(
        r"/projects/load",
        description="Open a project (only local server)",
        parameters={
            "path": ".gns3 path",
        },
        status_codes={
            201: "The project has been opened",
            403: "The server is not the local server"
        },
        input=PROJECT_LOAD_SCHEMA,
        output=PROJECT_OBJECT_SCHEMA)
    def load(request, response):

        controller = Controller.instance()
        config = Config.instance()
        if config.get_section_config("Server").getboolean("local", False) is False:
            response.set_status(403)
            return
        project = yield from controller.load_project(request.json.get("path"),)
        response.set_status(201)
        response.json(project)

    @Route.delete(
        r"/projects/{project_id}",
        description="Delete a project from disk",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            204: "Changes have been written on disk",
            404: "The project doesn't exist"
        })
    def delete(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        yield from project.delete()
        controller.remove_project(project)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/notifications",
        description="Receive notifications about projects",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            200: "End of stream",
            404: "The project doesn't exist"
        })
    def notification(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])

        response.content_type = "application/json"
        response.set_status(200)
        response.enable_chunked_encoding()
        # Very important: do not send a content length otherwise QT closes the connection (curl can consume the feed)
        response.content_length = None

        response.start(request)
        with controller.notification.queue(project) as queue:
            while True:
                try:
                    msg = yield from queue.get_json(5)
                    response.write(("{}\n".format(msg)).encode("utf-8"))
                except asyncio.futures.CancelledError as e:
                    break

    @Route.get(
        r"/projects/{project_id}/notifications/ws",
        description="Receive notifications about projects from a Websocket",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            200: "End of stream",
            404: "The project doesn't exist"
        })
    def notification_ws(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])

        ws = aiohttp.web.WebSocketResponse()
        yield from ws.prepare(request)

        with controller.notification.queue(project) as queue:
            while True:
                try:
                    notification = yield from queue.get_json(5)
                except asyncio.futures.CancelledError as e:
                    break
                ws.send_str(notification)
        return ws

    @Route.get(
        r"/projects/{project_id}/export",
        description="Export a project as a portable archive",
        parameters={
            "project_id": "Project UUID",
        },
        raw=True,
        status_codes={
            200: "File returned",
            404: "The project doesn't exist"
        })
    def export_project(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])

        response.content_type = 'application/gns3project'
        response.headers['CONTENT-DISPOSITION'] = 'attachment; filename="{}.gns3project"'.format(project.name)
        response.enable_chunked_encoding()
        # Very important: do not send a content length otherwise QT closes the connection (curl can consume the feed)
        response.content_length = None
        response.start(request)

        for data in project.export(include_images=bool(request.GET.get("include_images", "0"))):
            response.write(data)
            yield from response.drain()

        yield from response.write_eof()
