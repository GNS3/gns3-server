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

import asyncio
from fastapi import APIRouter, WebSocket
from gns3server.compute.notification_manager import NotificationManager
from starlette.endpoints import WebSocketEndpoint

import logging
log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket_route("/notifications/ws")
class ComputeWebSocketNotifications(WebSocketEndpoint):
    """
    Receive compute notifications about the controller from WebSocket stream.
    """

    async def on_connect(self, websocket: WebSocket) -> None:

        await websocket.accept()
        log.info(f"New client {websocket.client.host}:{websocket.client.port} has connected to compute WebSocket")
        self._notification_task = asyncio.ensure_future(self._stream_notifications(websocket))

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:

        self._notification_task.cancel()
        log.info(f"Client {websocket.client.host}:{websocket.client.port} has disconnected from controller WebSocket"
                 f" with close code {close_code}")

    async def _stream_notifications(self, websocket: WebSocket) -> None:

        with NotificationManager.instance().queue() as queue:
            while True:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)


if __name__ == '__main__':

    import uvicorn
    from fastapi import FastAPI
    from starlette.responses import HTMLResponse

    app = FastAPI()
    app.include_router(router)

    html = """
    <!DOCTYPE html>
    <html>
        <body>
            <ul id='messages'>
            </ul>
            <script>
                var ws = new WebSocket("ws://localhost:8000/notifications/ws");        
                ws.onmessage = function(event) {
                    var messages = document.getElementById('messages')
                    var message = document.createElement('li')
                    var content = document.createTextNode(event.data)
                    message.appendChild(content)
                    messages.appendChild(message)
                };
            </script>
        </body>
    </html>
    """

    @app.get("/")
    async def get() -> HTMLResponse:
        return HTMLResponse(html)

    uvicorn.run(app, host="localhost", port=8000)
