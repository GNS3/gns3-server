#!/usr/bin/env python
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

import aiohttp
import socket

import logging
log = logging.getLogger(__name__)


class HTTPClient:
    """
    HTTP client for request to computes and external services.
    """

    _aiohttp_client: aiohttp.ClientSession = None

    @classmethod
    def get_client(cls) -> aiohttp.ClientSession:
        if cls._aiohttp_client is None:
            cls._aiohttp_client = aiohttp.ClientSession(connector=aiohttp.TCPConnector(family=socket.AF_INET))
        return cls._aiohttp_client

    @classmethod
    async def close_session(cls):
        if cls._aiohttp_client:
            await cls._aiohttp_client.close()
            cls._aiohttp_client = None

    @classmethod
    def request(cls, method: str, url: str, user: str = None, password: str = None, **kwargs):

        client = cls.get_client()
        basic_auth = None
        if user:
            if not password:
                password = ""
            try:
                basic_auth = aiohttp.BasicAuth(user, password, "utf-8")
            except ValueError as e:
                log.error(f"Basic authentication set-up error: {e}")

        return client.request(method, url, auth=basic_auth, **kwargs)

    @classmethod
    def get(cls, path, **kwargs):
        return cls.request("GET", path, **kwargs)

    @classmethod
    def post(cls, path, **kwargs):
        return cls.request("POST", path, **kwargs)

    @classmethod
    def put(cls, path, **kwargs):
        return cls.request("PUT", path, **kwargs)
