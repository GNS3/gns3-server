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
Docker server module.
"""

import sys
import json
import asyncio
import logging
import aiohttp
from gns3server.utils import parse_version
from gns3server.utils.asyncio import locked_coroutine
from gns3server.compute.base_manager import BaseManager
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.docker_error import DockerError, DockerHttp304Error, DockerHttp404Error

log = logging.getLogger(__name__)


# Be carefull to keep it consistent
DOCKER_MINIMUM_API_VERSION = "1.25"
DOCKER_MINIMUM_VERSION = "1.13"


class Docker(BaseManager):

    _NODE_CLASS = DockerVM

    def __init__(self):
        super().__init__()
        self._server_url = '/var/run/docker.sock'
        self._connected = False
        # Allow locking during ubridge operations
        self.ubridge_lock = asyncio.Lock()
        self._connector = None
        self._session = None

    @asyncio.coroutine
    def _check_connection(self):
        if not self._connected:
            try:
                self._connected = True
                connector = self.connector()
                version = yield from self.query("GET", "version")
            except (aiohttp.errors.ClientOSError, FileNotFoundError):
                self._connected = False
                raise DockerError("Can't connect to docker daemon")
            if parse_version(version["ApiVersion"]) < parse_version(DOCKER_MINIMUM_API_VERSION):
                raise DockerError("Docker version is {}. GNS3 requires a minimum version of {}".format(version["Version"], DOCKER_MINIMUM_VERSION))

    def connector(self):
        if self._connector is None or self._connector.closed:
            if not sys.platform.startswith("linux"):
                raise DockerError("Docker is supported only on Linux")
            try:
                self._connector = aiohttp.connector.UnixConnector(self._server_url, conn_timeout=2, limit=None)
            except (aiohttp.errors.ClientOSError, FileNotFoundError):
                raise DockerError("Can't connect to docker daemon")
        return self._connector

    @asyncio.coroutine
    def unload(self):
        yield from super().unload()
        if self._connected:
            if self._connector and not self._connector.closed:
                yield from self._connector.close()

    @asyncio.coroutine
    def query(self, method, path, data={}, params={}):
        """
        Make a query to the docker daemon and decode the request

        :param method: HTTP method
        :param path: Endpoint in API
        :param data: Dictionnary with the body. Will be transformed to a JSON
        :param params: Parameters added as a query arg
        """

        response = yield from self.http_query(method, path, data=data, params=params)
        body = yield from response.read()
        if body and len(body):
            if response.headers['CONTENT-TYPE'] == 'application/json':
                body = json.loads(body.decode("utf-8"))
            else:
                body = body.decode("utf-8")
        log.debug("Query Docker %s %s params=%s data=%s Response: %s", method, path, params, data, body)
        return body

    @asyncio.coroutine
    def http_query(self, method, path, data={}, params={}, timeout=300):
        """
        Make a query to the docker daemon

        :param method: HTTP method
        :param path: Endpoint in API
        :param data: Dictionnary with the body. Will be transformed to a JSON
        :param params: Parameters added as a query arg
        :param timeout: Timeout
        :returns: HTTP response
        """
        data = json.dumps(data)
        if timeout is None:
            timeout = 60 * 60 * 24 * 31  # One month timeout

        if path == 'version':
            url = "http://docker/v1.12/" + path         # API of docker v1.0
        else:
            url = "http://docker/v" + DOCKER_MINIMUM_API_VERSION + "/" + path
        try:
            if path != "version":  # version is use by check connection
                yield from self._check_connection()
            if self._session is None or self._session.closed:
                connector = self.connector()
                self._session = aiohttp.ClientSession(connector=connector)
            response = yield from self._session.request(
                method,
                url,
                params=params,
                data=data,
                headers={"content-type": "application/json", },
                timeout=timeout
            )
        except (aiohttp.ClientResponseError, aiohttp.ClientOSError) as e:
            raise DockerError("Docker has returned an error: {}".format(str(e)))
        except (asyncio.TimeoutError):
            raise DockerError("Docker timeout " + method + " " + path)
        if response.status >= 300:
            body = yield from response.read()
            try:
                body = json.loads(body.decode("utf-8"))["message"]
            except ValueError:
                pass
            log.debug("Query Docker %s %s params=%s data=%s Response: %s", method, path, params, data, body)
            if response.status == 304:
                raise DockerHttp304Error("Docker has returned an error: {} {}".format(response.status, body))
            elif response.status == 404:
                raise DockerHttp404Error("Docker has returned an error: {} {}".format(response.status, body))
            else:
                raise DockerError("Docker has returned an error: {} {}".format(response.status, body))
        return response

    @asyncio.coroutine
    def websocket_query(self, path, params={}):
        """
        Open a websocket connection

        :param path: Endpoint in API
        :param params: Parameters added as a query arg
        :returns: Websocket
        """

        url = "http://docker/v" + DOCKER_MINIMUM_API_VERSION + "/" + path
        connection = yield from aiohttp.ws_connect(url,
                                                   connector=self.connector(),
                                                   origin="http://docker",
                                                   autoping=True)
        return connection

    @locked_coroutine
    def pull_image(self, image, progress_callback=None):
        """
        Pull image from docker repository

        :params image: Image name
        :params progress_callback: A function that receive a log message about image download progress
        """

        try:
            yield from self.query("GET", "images/{}/json".format(image))
            return  # We already have the image skip the download
        except DockerHttp404Error:
            pass

        if progress_callback:
            progress_callback("Pull {} from docker hub".format(image))
        response = yield from self.http_query("POST", "images/create", params={"fromImage": image}, timeout=None)
        # The pull api will stream status via an HTTP JSON stream
        content = ""
        while True:
            try:
                chunk = yield from response.content.read(1024)
            except aiohttp.errors.ServerDisconnectedError:
                break
            if not chunk:
                break
            content += chunk.decode("utf-8")

            try:
                while True:
                    content = content.lstrip(" \r\n\t")
                    answer, index = json.JSONDecoder().raw_decode(content)
                    if "progress" in answer and progress_callback:
                        progress_callback("Pulling image {}:{}: {}".format(image, answer["id"], answer["progress"]))
                    content = content[index:]
            except ValueError:  # Partial JSON
                pass
        response.close()
        if progress_callback:
            progress_callback("Success pulling image {}".format(image))

    @asyncio.coroutine
    def list_images(self):
        """Gets Docker image list.

        :returns: list of dicts
        :rtype: list
        """
        images = []
        for image in (yield from self.query("GET", "images/json", params={"all": 0})):
            if image['RepoTags']:
                for tag in image['RepoTags']:
                    if tag != "<none>:<none>":
                        images.append({'image': tag})
        return sorted(images, key=lambda i: i['image'])
