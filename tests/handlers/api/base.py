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

    def __init__(self, loop, host='localhost', port=8001):
        self._loop = loop
        self._port = port
        self._host = host

    def post(self, path, body={}, **kwargs):
        return self._fetch("POST", path, body, **kwargs)

    def put(self, path, body={}, **kwargs):
        return self._fetch("PUT", path, body, **kwargs)

    def get(self, path, **kwargs):
        return self._fetch("GET", path, **kwargs)

    def delete(self, path, **kwargs):
        return self._fetch("DELETE", path, **kwargs)

    def get_url(self, path, version):
        if version is None:
            return "http://{}:{}{}".format(self._host, self._port, path)
        return "http://{}:{}/v{}{}".format(self._host, self._port, version, path)

    def _fetch(self, method, path, body=None, api_version=1, **kwargs):
        """Fetch an url, parse the JSON and return response

        Options:
            - example if True the session is included inside documentation
            - raw do not JSON encode the query
            - api_version Version of API, None if no version
        """
        if body is not None and not kwargs.get("raw", False):
            body = json.dumps(body)

        @asyncio.coroutine
        def go_request(future):
            response = yield from aiohttp.request(method, self.get_url(path, api_version), data=body)
            future.set_result(response)
        future = asyncio.Future()
        asyncio.async(go_request(future))
        self._loop.run_until_complete(future)
        response = future.result()

        @asyncio.coroutine
        def go_read(future, response):
            response = yield from response.read()
            future.set_result(response)
        future = asyncio.Future()
        asyncio.async(go_read(future, response))
        self._loop.run_until_complete(future)
        response.body = future.result()
        x_route = response.headers.get('X-Route', None)
        if x_route is not None:
            response.route = x_route.replace("/v1", "")

        if response.body is not None:
            if response.headers.get("CONTENT-TYPE", "") == "application/json":
                try:
                    response.json = json.loads(response.body.decode("utf-8"))
                except ValueError:
                    response.json = None
            else:
                try:
                    response.html = response.body.decode("utf-8")
                except UnicodeDecodeError:
                    response.html = None
        else:
            response.json = {}
            response.html = ""
        if kwargs.get('example') and os.environ.get("PYTEST_BUILD_DOCUMENTATION") == "1":
            self._dump_example(method, response.route, api_version, path, body, response)
        return response

    def _dump_example(self, method, route, api_version, path, body, response):
        """Dump the request for the documentation"""
        if path is None:
            return
        with open(self._example_file_path(method, route), 'w+') as f:
            f.write("curl -i -X {} 'http://localhost:3080/v{}{}'".format(method, api_version, path))
            if body:
                f.write(" -d '{}'".format(re.sub(r"\n", "", json.dumps(json.loads(body), sort_keys=True))))
            f.write("\n\n")

            f.write("{} /v{}{} HTTP/1.1\n".format(method, api_version, path))
            if body:
                f.write(json.dumps(json.loads(body), sort_keys=True, indent=4))
            f.write("\n\n\n")
            f.write("HTTP/1.1 {}\n".format(response.status))
            for header, value in sorted(response.headers.items()):
                if header == 'DATE':
                    # We fix the date otherwise the example is always different
                    value = "Thu, 08 Jan 2015 16:09:15 GMT"
                f.write("{}: {}\n".format(header, value))
            f.write("\n")
            if response.body:
                f.write(json.dumps(json.loads(response.body.decode('utf-8')), sort_keys=True, indent=4))
                f.write("\n")

    def _example_file_path(self, method, path):
        path = re.sub('[^a-z0-9]', '', path)
        return "docs/api/examples/{}_{}.txt".format(method.lower(), path)
