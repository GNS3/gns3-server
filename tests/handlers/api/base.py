# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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


"""Base code use for all API tests"""

import json
import re
import asyncio
import aiohttp
import os


class Query:
    """
    Helper to make queries against the test server
    """

    def __init__(self, http_client, prefix='', api_version=None):
        """
        :param prefix: Prefix added before path (ex: /compute)
        :param api_version: Version of the API
        """

        self._http_client = http_client
        self._prefix = prefix
        self._api_version = api_version

    def post(self, path, body={}, **kwargs):
        return self._request("POST", path, body, **kwargs)

    def put(self, path, body={}, **kwargs):
        return self._request("PUT", path, body, **kwargs)

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def delete(self, path, **kwargs):
        return self._request("DELETE", path, **kwargs)

    def patch(self, path, **kwargs):
        return self._request("PATCH", path, **kwargs)

    def get_url(self, path):
        if self._api_version is None:
            return "/{}{}".format(self._prefix, path)
        return "/v{}{}{}".format(self._api_version, self._prefix, path)

    # async def websocket(self, path):
    #     """
    #     Return a websocket connected to the path
    #     """
    #
    #     #self._session = aiohttp.ClientSession()
    #     response = await self._http_client.ws_connect(self.get_url(path))
    #     return response
    #
    #     # async def go_request(future):
    #     #     self._session = aiohttp.ClientSession()
    #     #     response = await self._session.ws_connect(self.get_url(path))
    #     #     future.set_result(response)
    #     #
    #     # future = asyncio.Future()
    #     # asyncio.ensure_future(go_request(future))
    #     # self._loop.run_until_complete(future)
    #     # return future.result()

    async def _request(self, method, path, body=None, raw=False, **kwargs):

        if body is not None and raw is False:
            body = json.dumps(body)

        async with self._http_client.request(method, self.get_url(path), data=body, **kwargs) as response:
            response.body = await response.read()
            x_route = response.headers.get('X-Route', None)
            if x_route is not None:
                response.route = x_route.replace("/v{}".format(self._api_version), "")
                response.route = response.route .replace(self._prefix, "")

            #response.json = {}
            #response.html = ""
            if response.body is not None:
                if response.content_type == "application/json":
                    try:
                        response.json = await response.json(encoding="utf-8")
                    except ValueError:
                        response.json = None
                else:
                    try:
                        response.html = await response.text("utf-8")
                    except UnicodeDecodeError:
                        response.html = None
            return response
