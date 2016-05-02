#!/usr/bin/env python
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

import pytest
import asyncio
from unittest.mock import MagicMock

from tests.utils import asyncio_patch
from gns3server.modules.docker import Docker
from gns3server.modules.docker.docker_error import DockerError


@pytest.fixture
def vm():
    vm = Docker()
    vm._connected = True
    vm._connector = MagicMock()
    vm._connector.closed = False
    return vm


def test_query_success(loop, vm):

    response = MagicMock()
    response.status = 200
    response.headers = {'CONTENT-TYPE': 'application/json'}

    @asyncio.coroutine
    def read():
        return b'{"c": false}'

    response.read.side_effect = read
    with asyncio_patch("aiohttp.request", return_value=response) as mock:
        data = loop.run_until_complete(asyncio.async(vm.query("POST", "test", data={"a": True}, params={"b": 1})))
    mock.assert_called_with('POST',
                            'http://docker/test',
                            connector=vm._connector,
                            data='{"a": true}',
                            headers={'content-type': 'application/json'},
                            params={'b': 1})

    assert data == {"c": False}


def test_query_error(loop, vm):

    response = MagicMock()
    response.status = 404

    @asyncio.coroutine
    def read():
        return b"NOT FOUND"

    response.read.side_effect = read
    with asyncio_patch("aiohttp.request", return_value=response) as mock:
        with pytest.raises(DockerError):
            data = loop.run_until_complete(asyncio.async(vm.query("POST", "test", data={"a": True}, params={"b": 1})))
    mock.assert_called_with('POST',
                            'http://docker/test',
                            connector=vm._connector,
                            data='{"a": true}',
                            headers={'content-type': 'application/json'},
                            params={'b': 1})


def test_query_error_json(loop, vm):

    response = MagicMock()
    response.status = 404

    @asyncio.coroutine
    def read():
        return b'{"message": "Error"}'

    response.read.side_effect = read
    with asyncio_patch("aiohttp.request", return_value=response) as mock:
        with pytest.raises(DockerError):
            data = loop.run_until_complete(asyncio.async(vm.query("POST", "test", data={"a": True}, params={"b": 1})))
    mock.assert_called_with('POST',
                            'http://docker/test',
                            connector=vm._connector,
                            data='{"a": true}',
                            headers={'content-type': 'application/json'},
                            params={'b': 1})


def test_list_images(loop):
    response = [
        {
            "RepoTags": [
                "ubuntu:12.04",
                "ubuntu:precise",
                "ubuntu:latest"
            ],
            "Id": "8dbd9e392a964056420e5d58ca5cc376ef18e2de93b5cc90e868a1bbc8318c1c",
            "Created": 1365714795,
            "Size": 131506275,
            "VirtualSize": 131506275
        },
        {
            "RepoTags": [
                "ubuntu:12.10",
                "ubuntu:quantal",
                "<none>:<none>"
            ],
            "ParentId": "27cf784147099545",
            "Id": "b750fe79269d2ec9a3c593ef05b4332b1d1a02a62b4accb2c21d589ff2f5f2dc",
            "Created": 1364102658,
            "Size": 24653,
            "VirtualSize": 180116135
        }
    ]

    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        images = loop.run_until_complete(asyncio.async(Docker.instance().list_images()))
        mock.assert_called_with("GET", "images/json", params={"all": 0})
    assert len(images) == 5
    assert {"image": "ubuntu:12.04"} in images
    assert {"image": "ubuntu:precise"} in images
    assert {"image": "ubuntu:latest"} in images
    assert {"image": "ubuntu:12.10"} in images
    assert {"image": "ubuntu:quantal"} in images
