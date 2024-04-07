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

import asyncio
import signal
import os

from fastapi import APIRouter, Request, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from fastapi.routing import Mount
from websockets.exceptions import ConnectionClosed, WebSocketException

from typing import List

from gns3server.config import Config
from gns3server.controller import Controller
from gns3server.version import __version__
from gns3server.controller.controller_error import ControllerError, ControllerForbiddenError
from gns3server import schemas

from .dependencies.authentication import get_current_active_user, get_current_active_user_from_websocket

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/version",
    response_model=schemas.Version,
)
def get_version(request: Request) -> dict:
    """
    Return the server version number.
    """

    # retrieve the controller host information from the mounted
    # compute subapp
    controller_host = None
    for route in request.app.routes:
        if isinstance(route, Mount) and route.name == "compute":
            controller_host = route.app.state.controller_host

    local_server = Config.instance().settings.Server.local
    return {
        "controller_host": controller_host,
        "version": __version__,
        "local": local_server
    }


@router.post(
    "/version",
    response_model=schemas.Version,
    response_model_exclude_defaults=True,
    responses={409: {"model": schemas.ErrorMessage, "description": "Invalid version"}},
)
def check_version(version: schemas.Version) -> dict:
    """
    Check if version is the same as the server.
    """

    if version.version != __version__:
        raise ControllerError(f"Client version {version.version} is not the same as server version {__version__}")
    return {"version": __version__}


@router.post(
    "/reload",
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reload() -> None:
    """
    Reload the controller
    """

    await Controller.instance().reload()


@router.post(
    "/shutdown",
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={403: {"model": schemas.ErrorMessage, "description": "Server shutdown not allowed"}},
)
async def shutdown() -> None:
    """
    Shutdown the server
    """

    if Config.instance().settings.Server.local is False:
        raise ControllerForbiddenError("You can only stop a local server")

    log.info("Start shutting down the server")
    # close all the projects first
    controller = Controller.instance()
    projects = controller.projects.values()

    tasks = []
    for project in projects:
        tasks.append(asyncio.ensure_future(project.close()))

    if tasks:
        done, _ = await asyncio.wait(tasks)
        for future in done:
            try:
                future.result()
            except Exception as e:
                log.error(f"Could not close project: {e}", exc_info=1)
                continue

    # then shutdown the server itself
    os.kill(os.getpid(), signal.SIGTERM)


@router.get(
    "/iou_license",
    dependencies=[Depends(get_current_active_user)],
    response_model=schemas.IOULicense
)
def get_iou_license() -> schemas.IOULicense:
    """
    Return the IOU license settings
    """

    return Controller.instance().iou_license


@router.put(
    "/iou_license",
    dependencies=[Depends(get_current_active_user)],
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.IOULicense
)
async def update_iou_license(iou_license: schemas.IOULicense) -> schemas.IOULicense:
    """
    Update the IOU license settings.
    """

    controller = Controller().instance()
    current_iou_license = controller.iou_license
    current_iou_license.update(jsonable_encoder(iou_license))
    controller.save()
    return current_iou_license


@router.get("/statistics", dependencies=[Depends(get_current_active_user)])
async def statistics() -> List[dict]:
    """
    Return server statistics.
    """

    compute_statistics = []
    for compute in list(Controller.instance().computes.values()):
        try:
            r = await compute.get("/statistics")
            compute_statistics.append({"compute_id": compute.id, "compute_name": compute.name, "statistics": r.json})
        except ControllerError as e:
            log.error(f"Could not retrieve statistics on compute {compute.name}: {e}")
    return compute_statistics


@router.get("/notifications", dependencies=[Depends(get_current_active_user)])
async def controller_http_notifications(request: Request) -> StreamingResponse:
    """
    Receive controller notifications about the controller from HTTP stream.
    """

    from gns3server.api.server import app
    log.info(f"New client {request.client.host}:{request.client.port} has connected to controller HTTP "
             f"notification stream")

    async def event_stream():
        try:
            with Controller.instance().notification.controller_queue() as queue:
                while not app.state.exiting:
                    msg = await queue.get_json(5)
                    yield f"{msg}\n".encode("utf-8")
        finally:
            log.info(f"Client {request.client.host}:{request.client.port} has disconnected from controller HTTP "
                     f"notification stream")
    return StreamingResponse(event_stream(), media_type="application/json")


@router.websocket("/notifications/ws")
async def controller_ws_notifications(
        websocket: WebSocket,
        current_user: schemas.User = Depends(get_current_active_user_from_websocket)
) -> None:
    """
    Receive project notifications about the controller from WebSocket.
    """

    if current_user is None:
        return

    log.info(f"New client {websocket.client.host}:{websocket.client.port} has connected to controller WebSocket")
    try:
        with Controller.instance().notification.controller_queue() as queue:
            while True:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)
    except (ConnectionClosed, WebSocketDisconnect):
        log.info(f"Client {websocket.client.host}:{websocket.client.port} has disconnected from controller WebSocket")
    except WebSocketException as e:
        log.warning(f"Error while sending to controller event to WebSocket client: {e}")


# @Route.post(
#     r"/debug",
#     description="Dump debug information to disk (debug directory in config directory). Work only for local server",
#     status_codes={
#         201: "Written"
#     })
# async def debug(request, response):
#
#     config = Config.instance()
#     if config.get_section_config("Server").getboolean("local", False) is False:
#         raise ControllerForbiddenError("You can only debug a local server")
#
#     debug_dir = os.path.join(config.config_dir, "debug")
#     try:
#         if os.path.exists(debug_dir):
#             shutil.rmtree(debug_dir)
#         os.makedirs(debug_dir)
#         with open(os.path.join(debug_dir, "controller.txt"), "w+") as f:
#             f.write(ServerHandler._getDebugData())
#     except Exception as e:
#         # If something is wrong we log the info to the log and we hope the log will be include correctly to the debug export
#         log.error("Could not export debug information {}".format(e), exc_info=1)
#
#     try:
#         if Controller.instance().gns3vm.engine == "vmware":
#             vmx_path = Controller.instance().gns3vm.current_engine().vmx_path
#             if vmx_path:
#                 shutil.copy(vmx_path, os.path.join(debug_dir, os.path.basename(vmx_path)))
#     except OSError as e:
#         # If something is wrong we log the info to the log and we hope the log will be include correctly to the debug export
#         log.error("Could not copy VMware VMX file {}".format(e), exc_info=1)
#
#     for compute in list(Controller.instance().computes.values()):
#         try:
#             r = await compute.get("/debug", raw=True)
#             data = r.body.decode("utf-8")
#         except Exception as e:
#             data = str(e)
#         with open(os.path.join(debug_dir, "compute_{}.txt".format(compute.id)), "w+") as f:
#             f.write("Compute ID: {}\n".format(compute.id))
#             f.write(data)
#
#     response.set_status(201)
#
# @staticmethod
# def _getDebugData():
#     try:
#         connections = psutil.net_connections()
#     # You need to be root for OSX
#     except psutil.AccessDenied:
#         connections = None
#
#     try:
#         addrs = ["* {}: {}".format(key, val) for key, val in psutil.net_if_addrs().items()]
#     except UnicodeDecodeError:
#         addrs = ["INVALID ADDR WITH UNICODE CHARACTERS"]
#
#     data = """Version: {version}
# OS: {os}
# Python: {python}
# CPU: {cpu}
# Memory: {memory}
#
# Networks:
# {addrs}
#
# Open connections:
# {connections}
#
# Processus:
# """.format(
#         version=__version__,
#         os=platform.platform(),
#         python=platform.python_version(),
#         memory=psutil.virtual_memory(),
#         cpu=psutil.cpu_times(),
#         connections=connections,
#         addrs="\n".join(addrs)
#     )
#     for proc in psutil.process_iter():
#         try:
#             psinfo = proc.as_dict(attrs=["name", "exe"])
#             data += "* {} {}\n".format(psinfo["name"], psinfo["exe"])
#         except psutil.NoSuchProcess:
#             pass
#
#     data += "\n\nProjects"
#     for project in Controller.instance().projects.values():
#         data += "\n\nProject name: {}\nProject ID: {}\n".format(project.name, project.id)
#         if project.status != "closed":
#             for link in project.links.values():
#                 data += "Link {}: {}".format(link.id, link.debug_link_data)
#
#     return data
