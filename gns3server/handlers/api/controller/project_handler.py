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
import asyncio
import tempfile
import zipfile
import aiofiles
import time

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.controller.import_project import import_project
from gns3server.controller.export_project import export_project
from gns3server.utils.asyncio import aiozipstream
from gns3server.utils.path import is_safe_path
from gns3server.config import Config


from gns3server.schemas.project import (
    PROJECT_OBJECT_SCHEMA,
    PROJECT_UPDATE_SCHEMA,
    PROJECT_LOAD_SCHEMA,
    PROJECT_CREATE_SCHEMA,
    PROJECT_DUPLICATE_SCHEMA
)

import logging
log = logging.getLogger()


async def process_websocket(ws):
    """
    Process ping / pong and close message
    """
    try:
        await ws.receive()
    except aiohttp.WSServerHandshakeError:
        pass

CHUNK_SIZE = 1024 * 8  # 8KB


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
    async def create_project(request, response):

        controller = Controller.instance()
        project = await controller.add_project(**request.json)
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
    async def update(request, response):
        project = Controller.instance().get_project(request.match_info["project_id"])

        # Ignore these because we only use them when creating a project
        request.json.pop("project_id", None)

        await project.update(**request.json)
        response.set_status(200)
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
    async def delete(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        await project.delete()
        controller.remove_project(project)
        response.set_status(204)

    @Route.get(
        r"/projects/{project_id}/stats",
        description="Get a project statistics",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            200: "Project statistics returned",
            404: "The project doesn't exist"
        })
    def get(request, response):
        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.json(project.stats())

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
    async def close(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        await project.close()
        response.set_status(204)

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
    async def open(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        await project.open()
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
    async def load(request, response):

        controller = Controller.instance()
        config = Config.instance()
        dot_gns3_file = request.json.get("path")
        if config.get_section_config("Server").getboolean("local", False) is False:
            log.error("Cannot load '{}' because the server has not been started with the '--local' parameter".format(dot_gns3_file))
            response.set_status(403)
            return
        project = await controller.load_project(dot_gns3_file,)
        response.set_status(201)
        response.json(project)

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
    async def notification(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.content_type = "application/json"
        response.set_status(200)
        response.enable_chunked_encoding()
        await response.prepare(request)
        log.info("New client has connected to the notification stream for project ID '{}' (HTTP long-polling method)".format(project.id))

        try:
            with controller.notification.project_queue(project.id) as queue:
                while True:
                    msg = await queue.get_json(5)
                    await response.write(("{}\n".format(msg)).encode("utf-8"))
        finally:
            log.info("Client has disconnected from notification for project ID '{}' (HTTP long-polling method)".format(project.id))
            if project.auto_close:
                # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
                # if someone else is not connected
                await asyncio.sleep(5)
                if not controller.notification.project_has_listeners(project.id):
                    log.info("Project '{}' is automatically closing due to no client listening".format(project.id))
                    await project.close()


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
    async def notification_ws(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)

        request.app['websockets'].add(ws)
        asyncio.ensure_future(process_websocket(ws))
        log.info("New client has connected to the notification stream for project ID '{}' (WebSocket method)".format(project.id))
        try:
            with controller.notification.project_queue(project.id) as queue:
                while True:
                    notification = await queue.get_json(5)
                    if ws.closed:
                        break
                    await ws.send_str(notification)
        finally:
            log.info("Client has disconnected from notification stream for project ID '{}' (WebSocket method)".format(project.id))
            if not ws.closed:
                await ws.close()
            request.app['websockets'].discard(ws)
            if project.auto_close:
                # To avoid trouble with client connecting disconnecting we sleep few seconds before checking
                # if someone else is not connected
                await asyncio.sleep(5)
                if not controller.notification.project_has_listeners(project.id):
                    log.info("Project '{}' is automatically closing due to no client listening".format(project.id))
                    await project.close()

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
    async def export_project(request, response):

        controller = Controller.instance()
        project = await controller.get_loaded_project(request.match_info["project_id"])
        if request.query.get("include_snapshots", "no").lower() == "yes":
            include_snapshots = True
        else:
            include_snapshots = False
        if request.query.get("include_images", "no").lower() == "yes":
            include_images = True
        else:
            include_images = False
        if request.query.get("reset_mac_addresses", "no").lower() == "yes":
            reset_mac_addresses = True
        else:
            reset_mac_addresses = False

        compression_query = request.query.get("compression", "zip").lower()
        if compression_query == "zip":
            compression = zipfile.ZIP_DEFLATED
        elif compression_query == "none":
            compression = zipfile.ZIP_STORED
        elif compression_query == "bzip2":
            compression = zipfile.ZIP_BZIP2
        elif compression_query == "lzma":
            compression = zipfile.ZIP_LZMA

        try:
            begin = time.time()
            # use the parent directory as a temporary working dir
            working_dir = os.path.abspath(os.path.join(project.path, os.pardir))
            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                with aiozipstream.ZipFile(compression=compression) as zstream:
                    await export_project(zstream, project, tmpdir, include_snapshots=include_snapshots, include_images=include_images, reset_mac_addresses=reset_mac_addresses)

                    # We need to do that now because export could failed and raise an HTTP error
                    # that why response start need to be the later possible
                    response.content_type = 'application/gns3project'
                    response.headers['CONTENT-DISPOSITION'] = 'attachment; filename="{}.gns3project"'.format(project.name)
                    response.enable_chunked_encoding()
                    await response.prepare(request)

                    async for chunk in zstream:
                        await response.write(chunk)

            log.info("Project '{}' exported in {:.4f} seconds".format(project.name, time.time() - begin))

        # Will be raise if you have no space left or permission issue on your temporary directory
        # RuntimeError: something was wrong during the zip process
        except (ValueError, OSError, RuntimeError) as e:
            raise aiohttp.web.HTTPNotFound(text="Cannot export project: {}".format(str(e)))

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
    async def import_project(request, response):

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
        try:
            begin = time.time()
            # use the parent directory or projects dir as a temporary working dir
            if path:
                working_dir = os.path.abspath(os.path.join(path, os.pardir))
            else:
                working_dir = controller.projects_directory()
            with tempfile.TemporaryDirectory(dir=working_dir) as tmpdir:
                temp_project_path = os.path.join(tmpdir, "project.zip")
                async with aiofiles.open(temp_project_path, 'wb') as f:
                    while True:
                        chunk = await request.content.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        await f.write(chunk)

                with open(temp_project_path, "rb") as f:
                    project = await import_project(controller, request.match_info["project_id"], f, location=path, name=name)

            log.info("Project '{}' imported in {:.4f} seconds".format(project.name, time.time() - begin))
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
        input=PROJECT_DUPLICATE_SCHEMA,
        output=PROJECT_OBJECT_SCHEMA,
        status_codes={
            201: "Project duplicate",
            403: "The server is not the local server",
            404: "The project doesn't exist"
        })
    async def duplicate(request, response):

        controller = Controller.instance()
        project = await controller.get_loaded_project(request.match_info["project_id"])

        if request.json.get("path"):
            config = Config.instance()
            if config.get_section_config("Server").getboolean("local", False) is False:
                response.set_status(403)
                return
            location = request.json.get("path")
        else:
            location = None

        reset_mac_addresses = request.json.get("reset_mac_addresses", False)

        new_project = await project.duplicate(name=request.json.get("name"), location=location, reset_mac_addresses=reset_mac_addresses)

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
    async def get_file(request, response):

        controller = Controller.instance()
        project = await controller.get_loaded_project(request.match_info["project_id"])
        path = os.path.normpath(request.match_info["path"])

        # Raise error if user try to escape
        if not is_safe_path(path, project.path):
            raise aiohttp.web.HTTPForbidden()
        path = os.path.join(project.path, path)
        await response.stream_file(path)

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
    async def write_file(request, response):

        controller = Controller.instance()
        project = await controller.get_loaded_project(request.match_info["project_id"])
        path = os.path.normpath(request.match_info["path"])

        # Raise error if user try to escape
        if not is_safe_path(path, project.path):
            raise aiohttp.web.HTTPForbidden()
        path = os.path.join(project.path, path)
        response.set_status(201)

        try:
            async with aiofiles.open(path, 'wb+') as f:
                while True:
                    try:
                        chunk = await request.content.read(CHUNK_SIZE)
                    except asyncio.TimeoutError:
                        raise aiohttp.web.HTTPRequestTimeout(text="Timeout when writing to file '{}'".format(path))
                    if not chunk:
                        break
                    await f.write(chunk)
        except FileNotFoundError:
            raise aiohttp.web.HTTPNotFound()
        except PermissionError:
            raise aiohttp.web.HTTPForbidden()
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text=str(e))
