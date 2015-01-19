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
import socket
import pytest
from aiohttp import web
import aiohttp

from gns3server.web.route import Route
#TODO: get rid of *
from gns3server.handlers import *
from gns3server.modules import MODULES
from gns3server.modules.port_manager import PortManager


class Query:
    def __init__(self, loop, host='localhost', port=8001):
        self._loop = loop
        self._port = port
        self._host = host

    def post(self, path, body, **kwargs):
        return self._fetch("POST", path, body, **kwargs)

    def get(self, path, **kwargs):
        return self._fetch("GET", path, **kwargs)

    def delete(self, path, **kwargs):
        return self._fetch("DELETE", path, **kwargs)

    def _get_url(self, path):
        return "http://{}:{}{}".format(self._host, self._port, path)

    def _fetch(self, method, path, body=None, **kwargs):
        """Fetch an url, parse the JSON and return response

        Options:
            - example if True the session is included inside documentation
            - raw do not JSON encode the query
        """
        if body is not None and not kwargs.get("raw", False):
            body = json.dumps(body)

        @asyncio.coroutine
        def go(future):
            response = yield from aiohttp.request(method, self._get_url(path), data=body)
            future.set_result(response)
        future = asyncio.Future()
        asyncio.async(go(future))
        self._loop.run_until_complete(future)
        response = future.result()

        @asyncio.coroutine
        def go(future, response):
            response = yield from response.read()
            future.set_result(response)
        future = asyncio.Future()
        asyncio.async(go(future, response))
        self._loop.run_until_complete(future)
        response.body = future.result()
        response.route = response.headers.get('X-Route', None)

        if response.body is not None:
            try:
                response.json = json.loads(response.body.decode("utf-8"))
            except ValueError:
                response.json = None
        else:
            response.json = {}
        if kwargs.get('example'):
            self._dump_example(method, response.route, body, response)
        return response

    def _dump_example(self, method, path, body, response):
        """Dump the request for the documentation"""
        if path is None:
            return
        with open(self._example_file_path(method, path), 'w+') as f:
            f.write("curl -i -x{} 'http://localhost:8000{}'".format(method, path))
            if body:
                f.write(" -d '{}'".format(re.sub(r"\n", "", json.dumps(json.loads(body), sort_keys=True))))
            f.write("\n\n")

            f.write("{} {} HTTP/1.1\n".format(method, path))
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
            f.write(json.dumps(json.loads(response.body.decode('utf-8')), sort_keys=True, indent=4))
            f.write("\n")

    def _example_file_path(self, method, path):
        path = re.sub('[^a-z0-9]', '', path)
        return "docs/api/examples/{}_{}.txt".format(method.lower(), path)


def _get_unused_port():
    """ Return an unused port on localhost. In rare occasion it can return
    an already used port (race condition)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    addr, port = s.getsockname()
    s.close()
    return port


@pytest.fixture(scope="session")
def loop(request):
    """Return an event loop and destroy it at the end of test"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)  # Replace main loop to avoid conflict between tests

    def tear_down():
        loop.close()
        asyncio.set_event_loop(None)
    request.addfinalizer(tear_down)
    return loop

@pytest.fixture(scope="session")
def server(request, loop):
    port = _get_unused_port()
    host = "localhost"
    app = web.Application()
    for method, route, handler in Route.get_routes():
        app.router.add_route(method, route, handler)
    for module in MODULES:
        instance = module.instance()
        instance.port_manager = PortManager("127.0.0.1", False)
    srv = loop.create_server(app.make_handler(), host, port)
    srv = loop.run_until_complete(srv)

    def tear_down():
        for module in MODULES:
            loop.run_until_complete(module.destroy())
        srv.close()
        srv.wait_closed()
    request.addfinalizer(tear_down)
    return Query(loop, host=host, port=port)
