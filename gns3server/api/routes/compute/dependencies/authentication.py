#
# Copyright (C) 2021 GNS3 Technologies Inc.
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

import secrets
import base64
import binascii
import logging

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.security.utils import get_authorization_scheme_param
from gns3server.config import Config
from typing import Optional, Union

log = logging.getLogger(__name__)
security = HTTPBasic()


def compute_authentication(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> None:

    server_settings = Config.instance().settings.Server
    username = secrets.compare_digest(credentials.username, server_settings.compute_username)
    password = secrets.compare_digest(credentials.password, server_settings.compute_password.get_secret_value())
    if not (username and password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid compute username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

async def ws_compute_authentication(websocket: WebSocket) -> Union[None, WebSocket]:
    """
    """

    await websocket.accept()

    # handle basic HTTP authentication
    invalid_user_credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
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

        server_settings = Config.instance().settings.Server
        username = secrets.compare_digest(username, server_settings.compute_username)
        password = secrets.compare_digest(password, server_settings.compute_password.get_secret_value())
        if not (username and password):
            raise invalid_user_credentials_exc

    except HTTPException as e:
        err_msg = f"Could not authenticate while connecting to compute WebSocket: {e.detail}"
        websocket_error = {"action": "log.error", "event": {"message": err_msg}}
        await websocket.send_json(websocket_error)
        log.error(err_msg)
        return await websocket.close(code=1008)
    return websocket
