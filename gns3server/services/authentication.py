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

from joserfc import jwt
from joserfc.jwk import OctKey
from joserfc.errors import JoseError, BadSignatureError
import base64
import json
import time
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


def _extract_alg(token: str) -> str:
    """Best-effort extraction of the unverified JWT header "alg" value — for logging only."""

    try:
        header_segment = token.split(".", 1)[0]
        header = json.loads(base64.urlsafe_b64decode(header_segment + "=" * (-len(header_segment) % 4)))
        return str(header.get("alg", "<missing>"))
    except Exception:
        return "<undecodable>"


class AuthService:

    def hash_password(self, password: str) -> str:

        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password=password.encode('utf-8'), salt=salt)
        return hashed_password.decode('utf-8')

    def verify_password(self, password, hashed_password) -> bool:

        return bcrypt.checkpw(password=password.encode('utf-8'), hashed_password=hashed_password.encode('utf-8'))

    def _create_token(self, username, token_version, token_type, expires_in, secret_key=None) -> str:
        """Shared helper to create any kind of signed JWT token."""

        expire = datetime.now(timezone.utc) + timedelta(minutes=expires_in)
        to_encode = {"sub": username, "exp": expire, "ver": token_version, "type": token_type}
        if secret_key is None:
            secret_key = Config.instance().settings.Controller.jwt_secret_key
        if secret_key is None:
            secret_key = DEFAULT_JWT_SECRET_KEY
            log.error("A JWT secret key must be configured to secure the server, using an unsecured default key!")
        algorithm = Config.instance().settings.Controller.jwt_algorithm
        key = OctKey.import_key(secret_key)
        encoded_jwt = jwt.encode({"alg": algorithm}, to_encode, key)
        return encoded_jwt

    def create_access_token(self, username, token_version: int = 0, secret_key: str = None, expires_in: int = 0) -> str:

        if not expires_in:
            expires_in = Config.instance().settings.Controller.jwt_access_token_expire_minutes
        return self._create_token(username, token_version, "access", expires_in, secret_key)

    def create_refresh_token(self, username, token_version: int = 0, secret_key: str = None, expires_in: int = 0) -> str:

        if not expires_in:
            expires_in = Config.instance().settings.Controller.jwt_refresh_token_expire_minutes
        return self._create_token(username, token_version, "refresh", expires_in, secret_key)

    def get_token_data(self, token: str, secret_key: str = None) -> TokenData:

        def auth_error(detail: str) -> HTTPException:
            return HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail,
                headers={"WWW-Authenticate": "Bearer"},
            )

        if secret_key is None:
            secret_key = Config.instance().settings.Controller.jwt_secret_key
        if secret_key is None:
            secret_key = DEFAULT_JWT_SECRET_KEY
            log.error("A JWT secret key must be configured to secure the server, using an unsecured default key!")
        algorithm = Config.instance().settings.Controller.jwt_algorithm
        key = OctKey.import_key(secret_key)
        try:
            payload = jwt.decode(token, key, algorithms=[algorithm])
            username: str = payload.claims.get("sub")
            if username is None:
                raise auth_error("Invalid token: missing subject claim")
            # Validate the exp claim — joserfc does not validate time-based claims by default
            token_exp: int = payload.claims.get("exp", 0)
            if token_exp and time.time() > token_exp:
                raise auth_error("Token has expired")
            token_version: int = payload.claims.get("ver", 0)
            token_use: str = payload.claims.get("type", "access")
            token_data = TokenData(username=username, token_version=token_version, token_use=token_use)
        except BadSignatureError as e:
            log.warning("JWT rejected: bad signature (header alg: '%s', error: %s)", _extract_alg(token), e)
            raise auth_error("Invalid token signature")
        except (JoseError, ValidationError, ValueError) as e:
            log.warning("JWT rejected: %s: %s (header alg: '%s')", type(e).__name__, e, _extract_alg(token))
            raise auth_error(f"Invalid token ({type(e).__name__})")
        return token_data

    def get_username_from_token(self, token: str, secret_key: str = None) -> Optional[str]:
        return self.get_token_data(token, secret_key).username
