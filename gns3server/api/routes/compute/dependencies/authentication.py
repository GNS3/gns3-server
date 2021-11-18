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

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from gns3server.config import Config
from typing import Optional

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
