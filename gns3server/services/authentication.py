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


from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

from typing import Optional
from fastapi import HTTPException, status
from gns3server.schemas.tokens import TokenData
from gns3server.controller.controller_error import ControllerError
from gns3server.config import Config
from pydantic import ValidationError

import logging
log = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:

    def __init__(self):

        self._server_config = Config.instance().get_section_config("Server")

    def hash_password(self, password: str) -> str:

        return pwd_context.hash(password)

    def verify_password(self, password, hashed_password) -> bool:

        return pwd_context.verify(password, hashed_password)

    def get_secret_key(self):
        """
        Should only be used by tests.
        """

        return self._server_config.get("jwt_secret_key", None)

    def get_algorithm(self):
        """
        Should only be used by tests.
        """

        return self._server_config.get("jwt_algorithm", None)

    def create_access_token(
            self,
            username,
            secret_key: str = None,
            expires_in: int = 0
    ) -> str:

        if not expires_in:
            expires_in = self._server_config.getint("jwt_access_token_expire_minutes", 1440)
        expire = datetime.utcnow() + timedelta(minutes=expires_in)
        to_encode = {"sub": username, "exp": expire}
        if secret_key is None:
            secret_key = self._server_config.get("jwt_secret_key", None)
        if secret_key is None:
            raise ControllerError("No JWT secret key has been configured")
        algorithm = self._server_config.get("jwt_algorithm", "HS256")
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
        return encoded_jwt

    def get_username_from_token(self, token: str, secret_key: str = None) -> Optional[str]:

        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            if secret_key is None:
                secret_key = self._server_config.get("jwt_secret_key", None)
            if secret_key is None:
                raise ControllerError("No JWT secret key has been configured")
            algorithm = self._server_config.get("jwt_algorithm", "HS256")
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except (JWTError, ValidationError):
            raise credentials_exception
        return token_data.username
