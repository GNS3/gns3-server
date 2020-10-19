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

import asyncio

from fastapi import APIRouter, WebSocket
from fastapi.responses import StreamingResponse
from starlette.endpoints import WebSocketEndpoint

from gns3server.controller import Controller

import logging
log = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def http_notification():
    """
    Receive controller notifications about the controller from HTTP stream.
    """

    async def event_stream():

        with Controller.instance().notification.controller_queue() as queue:
            while True:
                msg = await queue.get_json(5)
                yield ("{}\n".format(msg)).encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/json")


@router.websocket_route("/ws")
class ControllerWebSocketNotifications(WebSocketEndpoint):
    """
    Receive controller notifications about the controller from WebSocket stream.
    """

    async def on_connect(self, websocket: WebSocket) -> None:

        await websocket.accept()
        log.info(f"New client {websocket.client.host}:{websocket.client.port} has connected to controller WebSocket")

        self._notification_task = asyncio.ensure_future(self._stream_notifications(websocket=websocket))

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:

        self._notification_task.cancel()
        log.info(f"Client {websocket.client.host}:{websocket.client.port} has disconnected from controller WebSocket"
                 f" with close code {close_code}")

    async def _stream_notifications(self, websocket: WebSocket) -> None:

        with Controller.instance().notifications.queue() as queue:
            while True:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)
