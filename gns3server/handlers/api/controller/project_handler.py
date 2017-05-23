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
import aiohttp
import aiohttp.errors
import asyncio
import tempfile

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.controller.import_project import import_project
from gns3server.controller.export_project import export_project
from gns3server.config import Config


from gns3server.schemas.project import (
    PROJECT_OBJECT_SCHEMA,
    PROJECT_UPDATE_SCHEMA,
    PROJECT_LOAD_SCHEMA,
    PROJECT_CREATE_SCHEMA
)

import logging
log = logging.getLogger()


@asyncio.coroutine
def process_websocket(ws):
    """
    Process ping / pong and close message
    """
    try:
        yield from ws.receive()
    except aiohttp.errors.WSServerHandshakeError:
        pass


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
        project = yield from controller.add_project(**request.json)
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

    @Route.put(
        r"/projects/{project_id}",
        status_codes={
            200: "Node updated",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Update a project instance",
        input=PROJECT_UPDATE_SCHEMA,
        output=PROJECT_OBJECT_SCHEMA)
    def update(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])

        # Ignore these because we only use them when creating a project
        request.json.pop("project_id", None)

        yield from project.update(**request.json)
        response.set_status(200)
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
                yield from response.drain()

        if project.auto_close:
            # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
            # if someone else is not connected
            yield from asyncio.sleep(5)
            if not controller.notification.project_has_listeners(project):
                yield from project.close()

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

        asyncio.async(process_websocket(ws))

        with controller.notification.queue(project) as queue:
            while True:
                try:
                    notification = yield from queue.get_json(5)
                except asyncio.futures.CancelledError as e:
                    break
                if ws.closed:
                    break
                ws.send_str(notification)

        if project.auto_close:
            # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
            # if someone else is not connected
            yield from asyncio.sleep(5)
            if not controller.notification.project_has_listeners(project):
                yield from project.close()

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
        project = yield from controller.get_loaded_project(request.match_info["project_id"])

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                datas = yield from export_project(project, tmp_dir, include_images=bool(request.get("include_images", "0")))
                # We need to do that now because export could failed and raise an HTTP error
                # that why response start need to be the later possible
                response.content_type = 'application/gns3project'
                response.headers['CONTENT-DISPOSITION'] = 'attachment; filename="{}.gns3project"'.format(project.name)
                response.enable_chunked_encoding()
                # Very important: do not send a content length otherwise QT closes the connection (curl can consume the feed)
                response.content_length = None
                response.start(request)

                for data in datas:
                    response.write(data)
                    yield from response.drain()

                yield from response.write_eof()
        # Will be raise if you have no space left or permission issue on your temporary directory
        # RuntimeError: something was wrong during the zip process
        except (OSError, RuntimeError) as e:
            raise aiohttp.web.HTTPNotFound(text="Can't export project: {}".format(str(e)))

    @Route.post(
        r"/projects/{project_id}/import",
        description="Import a project from a portable archive",
        parameters={
            "project_id": "Project UUID",
        },
        raw=True,
        output=PROJECT_OBJECT_SCHEMA,
        status_codes={
            200: "Project imported",
            403: "Forbidden to import project"
        })
    def import_project(request, response):

        controller = Controller.instance()

        if request.get("path"):
            config = Config.instance()
            if config.get_section_config("Server").getboolean("local", False) is False:
                response.set_status(403)
                return
        path = request.json.get("path")
        name = request.json.get("name")

        # We write the content to a temporary location and after we extract it all.
        # It could be more optimal to stream this but it is not implemented in Python.
        # Spooled means the file is temporary kept in memory until max_size is reached
        try:
            with tempfile.SpooledTemporaryFile(max_size=10000) as temp:
                while True:
                    packet = yield from request.content.read(512)
                    if not packet:
                        break
                    temp.write(packet)
                project = yield from import_project(controller, request.match_info["project_id"], temp, location=path, name=name)
        except OSError as e:
            raise aiohttp.web.HTTPInternalServerError(text="Could not import the project: {}".format(e))

        response.json(project)
        response.set_status(201)

    @Route.post(
        r"/projects/{project_id}/duplicate",
        description="Duplicate a project",
        parameters={
            "project_id": "Project UUID",
        },
        input=PROJECT_CREATE_SCHEMA,
        output=PROJECT_OBJECT_SCHEMA,
        status_codes={
            201: "Project duplicate",
            403: "The server is not the local server",
            404: "The project doesn't exist"
        })
    def duplicate(request, response):

        controller = Controller.instance()
        project = yield from controller.get_loaded_project(request.match_info["project_id"])

        if request.json.get("path"):
            config = Config.instance()
            if config.get_section_config("Server").getboolean("local", False) is False:
                response.set_status(403)
                return
            location = request.json.get("path")
        else:
            location = None

        new_project = yield from project.duplicate(name=request.json.get("name"), location=location)

        response.json(new_project)
        response.set_status(201)

    @Route.get(
        r"/projects/{project_id}/files/{path:.+}",
        description="Get a file from a project. Beware you have warranty to be able to access only to file global to the project (for example README.txt)",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The file doesn't exist"
        })
    def get_file(request, response):

        controller = Controller.instance()
        project = yield from controller.get_loaded_project(request.match_info["project_id"])
        path = request.match_info["path"]
        path = os.path.normpath(path)

        # Raise error if user try to escape
        if path[0] == ".":
            raise aiohttp.web.HTTPForbidden
        path = os.path.join(project.path, path)

        response.content_type = "application/octet-stream"
        response.set_status(200)
        response.enable_chunked_encoding()
        # Very important: do not send a content length otherwise QT closes the connection (curl can consume the feed)
        response.content_length = None

        try:
            with open(path, "rb") as f:
                response.start(request)
                while True:
                    data = f.read(4096)
                    if not data:
                        break
                    yield from response.write(data)

        except FileNotFoundError:
            raise aiohttp.web.HTTPNotFound()
        except PermissionError:
            raise aiohttp.web.HTTPForbidden()

    @Route.post(
        r"/projects/{project_id}/files/{path:.+}",
        description="Write a file to a project",
        parameters={
            "project_id": "Project UUID",
        },
        raw=True,
        status_codes={
            200: "File returned",
            403: "Permission denied",
            404: "The path doesn't exist"
        })
    def write_file(request, response):

        controller = Controller.instance()
        project = yield from controller.get_loaded_project(request.match_info["project_id"])
        path = request.match_info["path"]
        path = os.path.normpath(path).strip("/")

        # Raise error if user try to escape
        if path[0] == ".":
            raise aiohttp.web.HTTPForbidden
        path = os.path.join(project.path, path)

        response.set_status(200)

        try:
            with open(path, 'wb+') as f:
                while True:
                    packet = yield from request.content.read(512)
                    if not packet:
                        break
                    f.write(packet)
        except FileNotFoundError:
            raise aiohttp.web.HTTPNotFound()
        except PermissionError:
            raise aiohttp.web.HTTPForbidden()
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text=str(e))
