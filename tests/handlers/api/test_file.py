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

"""
This test suite check /files endpoint
"""

import json
import asyncio
import aiohttp

from gns3server.version import __version__


def test_stream(server, tmpdir, loop):
    with open(str(tmpdir / "test.pcap"), 'w+') as f:
        f.write("hello")

    def go(future):
        query = json.dumps({"location": str(tmpdir / "test.pcap")})
        headers = {'content-type': 'application/json'}
        response = yield from aiohttp.request("GET", server.get_url("/files/stream", 1), data=query, headers=headers)
        response.body = yield from response.content.read(5)
        with open(str(tmpdir / "test.pcap"), 'a') as f:
            f.write("world")
        response.body += yield from response.content.read(5)
        response.close()
        future.set_result(response)

    future = asyncio.Future()
    asyncio.async(go(future))
    response = loop.run_until_complete(future)
    assert response.status == 200
    assert response.body == b'helloworld'


def test_stream_file_not_pcap(server, tmpdir, loop):
    def go(future):
        query = json.dumps({"location": str(tmpdir / "test")})
        headers = {'content-type': 'application/json'}
        response = yield from aiohttp.request("GET", server.get_url("/files/stream", 1), data=query, headers=headers)
        response.close()
        future.set_result(response)

    future = asyncio.Future()
    asyncio.async(go(future))
    response = loop.run_until_complete(future)
    assert response.status == 403


def test_stream_file_not_found(server, tmpdir, loop):
    def go(future):
        query = json.dumps({"location": str(tmpdir / "test.pcap")})
        headers = {'content-type': 'application/json'}
        response = yield from aiohttp.request("GET", server.get_url("/files/stream", 1), data=query, headers=headers)
        response.close()
        future.set_result(response)

    future = asyncio.Future()
    asyncio.async(go(future))
    response = loop.run_until_complete(future)
    assert response.status == 404
