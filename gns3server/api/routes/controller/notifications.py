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
API routes for controller notifications.
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from websockets.exceptions import ConnectionClosed, WebSocketException

from gns3server.services import auth_service
from gns3server.controller import Controller

from .dependencies.authentication import get_current_active_user

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", dependencies=[Depends(get_current_active_user)])
async def http_notification() -> StreamingResponse:
    """
    Receive controller notifications about the controller from HTTP stream.
    """

    async def event_stream():
        with Controller.instance().notification.controller_queue() as queue:
            while True:
                msg = await queue.get_json(5)
                yield f"{msg}\n".encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/json")


@router.websocket("/ws")
async def notification_ws(websocket: WebSocket, token: str = Query(None)) -> None:
    """
    Receive project notifications about the controller from WebSocket.
    """
    await websocket.accept()

    if token:
        try:
            username = auth_service.get_username_from_token(token)
        except HTTPException:
            log.error("Invalid token received")
            await websocket.close(code=1008)
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
    finally:
        await websocket.close()
