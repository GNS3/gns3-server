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
API routes for compute notifications.
"""

import base64
import binascii

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, HTTPException
from fastapi.security.utils import get_authorization_scheme_param
from websockets.exceptions import ConnectionClosed, WebSocketException

from gns3server.compute.notification_manager import NotificationManager

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/notifications/ws")
async def notification_ws(websocket: WebSocket) -> None:
    """
    Receive project notifications about the project from WebSocket.
    """

    await websocket.accept()

    # handle basic HTTP authentication
    invalid_user_credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Basic"},
    )

    try:
        authorization = websocket.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "basic":
            raise invalid_user_credentials_exc
        try:
            data = base64.b64decode(param).decode("ascii")
        except (ValueError, UnicodeDecodeError, binascii.Error):
            raise invalid_user_credentials_exc
        username, separator, password = data.partition(":")
        if not separator:
            raise invalid_user_credentials_exc
    except invalid_user_credentials_exc as e:
        websocket_error = {"action": "log.error", "event": {"message": f"Could not authenticate while connecting to "
                                                                       f"compute WebSocket: {e.detail}"}}
        await websocket.send_json(websocket_error)
        return await websocket.close(code=1008)

    log.info(f"New client {websocket.client.host}:{websocket.client.port} has connected to compute WebSocket")
    try:
        with NotificationManager.instance().queue() as queue:
            while True:
                notification = await queue.get_json(5)
                await websocket.send_text(notification)
    except (ConnectionClosed, WebSocketDisconnect):
        log.info(f"Client {websocket.client.host}:{websocket.client.port} has disconnected from compute WebSocket")
    except WebSocketException as e:
        log.warning(f"Error while sending to controller event to WebSocket client: {e}")
    finally:
        try:
            await websocket.close()
        except OSError:
            pass  # ignore OSError: [Errno 107] Transport endpoint is not connected

if __name__ == "__main__":

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
