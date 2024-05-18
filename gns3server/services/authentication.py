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
from datetime import datetime, timedelta, timezone
import bcrypt

from typing import Optional
from fastapi import HTTPException, status
from gns3server.schemas.controller.tokens import TokenData
from gns3server.config import Config
from pydantic import ValidationError

import logging

log = logging.getLogger(__name__)

DEFAULT_JWT_SECRET_KEY = "efd08eccec3bd0a1be2e086670e5efa90969c68d07e072d7354a76cea5e33d4e"


class AuthService:

    def hash_password(self, password: str) -> str:

        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password=password.encode('utf-8'), salt=salt)
        return hashed_password.decode('utf-8')

    def verify_password(self, password, hashed_password) -> bool:

        return bcrypt.checkpw(password=password.encode('utf-8'), hashed_password=hashed_password.encode('utf-8'))

    def create_access_token(self, username, secret_key: str = None, expires_in: int = 0) -> str:

        if not expires_in:
            expires_in = Config.instance().settings.Controller.jwt_access_token_expire_minutes
        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_in)
        to_encode = {"sub": username, "exp": expire}
        if secret_key is None:
            secret_key = Config.instance().settings.Controller.jwt_secret_key
        if secret_key is None:
            secret_key = DEFAULT_JWT_SECRET_KEY
            log.error("A JWT secret key must be configured to secure the server, using an unsecured default key!")
        algorithm = Config.instance().settings.Controller.jwt_algorithm
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
                secret_key = Config.instance().settings.Controller.jwt_secret_key
            if secret_key is None:
                secret_key = DEFAULT_JWT_SECRET_KEY
                log.error("A JWT secret key must be configured to secure the server, using an unsecured default key!")
            algorithm = Config.instance().settings.Controller.jwt_algorithm
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except (JWTError, ValidationError):
            raise credentials_exception
        return token_data.username
