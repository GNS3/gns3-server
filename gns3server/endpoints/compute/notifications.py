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
API endpoints for compute notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.exceptions import WebSocketException
from typing import List

from gns3server.compute.notification_manager import NotificationManager

import logging
log = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):

        self.active_connections.remove(websocket)

    async def close_active_connections(self):

        for websocket in self.active_connections:
            await websocket.close()

    async def send_text(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/notifications/ws")
async def compute_notifications(websocket: WebSocket):

    log.info("Client has disconnected from compute WebSocket")
    notifications = NotificationManager.instance()
    await manager.connect(websocket)
    try:
        log.info("New client has connected to compute WebSocket")
        with notifications.queue() as queue:
            while True:
                notification = await queue.get_json(5)
                await manager.send_text(notification, websocket)
    except (WebSocketException, WebSocketDisconnect) as e:
        log.info("Client has disconnected from compute WebSocket: {}".format(e))
    finally:
        await websocket.close()
        manager.disconnect(websocket)
