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

import pytest
from unittest.mock import MagicMock, patch

from tests.utils import asyncio_patch, AsyncioMagicMock
from gns3server.compute.docker import Docker, DOCKER_PREFERRED_API_VERSION, DOCKER_MINIMUM_API_VERSION
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error


@pytest.fixture
async def vm(loop):

    vm = Docker()
    vm._connected = True
    vm._session = MagicMock()
    vm._session.closed = False
    return vm


async def test_query_success(vm):

    response = MagicMock()
    response.status = 200
    response.headers = {'CONTENT-TYPE': 'application/json'}

    async def read():
        return b'{"c": false}'

    response.read.side_effect = read
    vm._session.request = AsyncioMagicMock(return_value=response)
    data = await vm.query("POST", "test", data={"a": True}, params={"b": 1})
    vm._session.request.assert_called_with('POST',
                                           'http://docker/v1.25/test',
                                           data='{"a": true}',
                                           headers={'content-type': 'application/json'},
                                           params={'b': 1},
                                           timeout=300)

    assert data == {"c": False}


async def test_query_error(vm):

    response = MagicMock()
    response.status = 404

    async def read():
        return b"NOT FOUND"

    response.read.side_effect = read
    vm._session.request = AsyncioMagicMock(return_value=response)
    with pytest.raises(DockerError):
        await vm.query("POST", "test", data={"a": True}, params={"b": 1})
    vm._session.request.assert_called_with('POST',
                                           'http://docker/v1.25/test',
                                           data='{"a": true}',
                                           headers={'content-type': 'application/json'},
                                           params={'b': 1},
                                           timeout=300)


async def test_query_error_json(vm):

    response = MagicMock()
    response.status = 404

    async def read():
        return b'{"message": "Error"}'

    response.read.side_effect = read
    vm._session.request = AsyncioMagicMock(return_value=response)
    with pytest.raises(DockerError):
        await vm.query("POST", "test", data={"a": True}, params={"b": 1})
    vm._session.request.assert_called_with('POST',
                                           'http://docker/v1.25/test',
                                           data='{"a": true}',
                                           headers={'content-type': 'application/json'},
                                           params={'b': 1},
                                           timeout=300)


async def test_list_images():

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

    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
        images = await Docker.instance().list_images()
        mock.assert_called_with("GET", "images/json", params={"all": 0})
    assert len(images) == 5
    assert {"image": "ubuntu:12.04"} in images
    assert {"image": "ubuntu:precise"} in images
    assert {"image": "ubuntu:latest"} in images
    assert {"image": "ubuntu:12.10"} in images
    assert {"image": "ubuntu:quantal"} in images


async def test_pull_image():

    class Response:
        """
        Simulate a response split in multiple packets
        """

        def __init__(self):
            self._read = -1

        async def read(self, size):
            self._read += 1
            if self._read == 0:
                return b'{"progress": "0/100",'
            elif self._read == 1:
                return '"id": 42}'
            else:
                None

    mock_query = MagicMock()
    mock_query.content.return_value = Response()

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=mock_query) as mock:
            await Docker.instance().pull_image("ubuntu")
            mock.assert_called_with("POST", "images/create", params={"fromImage": "ubuntu"}, timeout=None)


async def test_docker_check_connection_docker_minimum_version(vm):

    response = {
        'ApiVersion': '1.01',
        'Version': '1.12'
    }

    with patch("gns3server.compute.docker.Docker.connector"), \
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        vm._connected = False
        with pytest.raises(DockerError):
            await vm._check_connection()


async def test_docker_check_connection_docker_preferred_version_against_newer(vm):

    response = {
        'ApiVersion': '1.31'
    }

    with patch("gns3server.compute.docker.Docker.connector"), \
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        vm._connected = False
        await vm._check_connection()
        assert vm._api_version == DOCKER_PREFERRED_API_VERSION


async def test_docker_check_connection_docker_preferred_version_against_older(vm):

    response = {
        'ApiVersion': '1.27',
    }

    with patch("gns3server.compute.docker.Docker.connector"), \
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        vm._connected = False
        await vm._check_connection()
        assert vm._api_version == DOCKER_MINIMUM_API_VERSION
