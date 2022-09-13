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

from fastapi import APIRouter, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from websockets.exceptions import ConnectionClosed, WebSocketException

from gns3server.controller import Controller
from gns3server import schemas

from .dependencies.authentication import get_current_active_user, get_current_active_user_from_websocket

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", dependencies=[Depends(get_current_active_user)])
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


@router.websocket("/ws")
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
    finally:
        try:
            await websocket.close()
        except OSError:
            pass  # ignore OSError: [Errno 107] Transport endpoint is not connected
