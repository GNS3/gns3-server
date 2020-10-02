# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

"""
API endpoints for controller notifications.
"""


from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from websockets.exceptions import WebSocketException
from gns3server.controller import Controller

router = APIRouter()

import logging
log = logging.getLogger(__name__)


# @router.get("/")
# async def notification(request: Request):
#     """
#     Receive notifications about the controller from HTTP
#     """
#
#     controller = Controller.instance()
#
#     await response.prepare(request)
#     response = Response(content, media_type="application/json")
#
#     with controller.notification.controller_queue() as queue:
#         while True:
#             msg = await queue.get_json(5)
#             await response.write(("{}\n".format(msg)).encode("utf-8"))
#
#
#             await response(scope, receive, send)


@router.websocket("/ws")
async def notification_ws(websocket: WebSocket):
    """
    Receive notifications about the controller from a Websocket
    """

    controller = Controller.instance()
    await websocket.accept()
    log.info("New client has connected to controller WebSocket")
    try:
        with controller.notification.controller_queue() as queue:
            while True:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)
    except (WebSocketException, WebSocketDisconnect):
        log.info("Client has disconnected from controller WebSocket")
        await websocket.close()
