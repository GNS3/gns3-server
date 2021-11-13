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
from gns3server.utils.asyncio import locking
from gns3server.compute.base_manager import BaseManager
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.docker_error import DockerError, DockerHttp304Error, DockerHttp404Error

log = logging.getLogger(__name__)


# Be careful to keep it consistent
DOCKER_MINIMUM_API_VERSION = "1.25"
DOCKER_MINIMUM_VERSION = "1.13"
DOCKER_PREFERRED_API_VERSION = "1.30"
CHUNK_SIZE = 1024 * 8  # 8KB


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
        self._api_version = DOCKER_MINIMUM_API_VERSION

    async def _check_connection(self):

        if not self._connected:
            try:
                self._connected = True
                connector = self.connector()
                version = await self.query("GET", "version")
            except (aiohttp.ClientOSError, FileNotFoundError):
                self._connected = False
                raise DockerError("Can't connect to docker daemon")

            docker_version = parse_version(version['ApiVersion'])

            if docker_version < parse_version(DOCKER_MINIMUM_API_VERSION):
                raise DockerError(
                    "Docker version is {}. GNS3 requires a minimum version of {}".format(
                        version["Version"], DOCKER_MINIMUM_VERSION))

            preferred_api_version = parse_version(DOCKER_PREFERRED_API_VERSION)
            if docker_version >= preferred_api_version:
                self._api_version = DOCKER_PREFERRED_API_VERSION

    def connector(self):

        if self._connector is None or self._connector.closed:
            if not sys.platform.startswith("linux"):
                raise DockerError("Docker is supported only on Linux")
            try:
                self._connector = aiohttp.connector.UnixConnector(self._server_url, limit=None)
            except (aiohttp.ClientOSError, FileNotFoundError):
                raise DockerError("Can't connect to docker daemon")
        return self._connector

    async def unload(self):

        await super().unload()
        if self._connected:
            if self._connector and not self._connector.closed:
                await self._connector.close()
        if self._session and not self._session.closed:
            await self._session.close()

    async def query(self, method, path, data={}, params={}):
        """
        Makes a query to the Docker daemon and decode the request

        :param method: HTTP method
        :param path: Endpoint in API
        :param data: Dictionary with the body. Will be transformed to a JSON
        :param params: Parameters added as a query arg
        """

        response = await self.http_query(method, path, data=data, params=params)
        body = await response.read()
        response.close()
        if body and len(body):
            if response.headers.get('CONTENT-TYPE') == 'application/json':
                body = json.loads(body.decode("utf-8"))
            else:
                body = body.decode("utf-8")
        log.debug("Query Docker %s %s params=%s data=%s Response: %s", method, path, params, data, body)
        return body

    async def http_query(self, method, path, data={}, params={}, timeout=300):
        """
        Makes a query to the docker daemon

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
                await self._check_connection()
            if self._session is None or self._session.closed:
                connector = self.connector()
                self._session = aiohttp.ClientSession(connector=connector)
            response = await self._session.request(method,
                                                   url,
                                                   params=params,
                                                   data=data,
                                                   headers={"content-type": "application/json", },
                                                   timeout=timeout)
        except (aiohttp.ClientResponseError, aiohttp.ClientOSError) as e:
            raise DockerError("Docker has returned an error: {}".format(str(e)))
        except (asyncio.TimeoutError):
            raise DockerError("Docker timeout " + method + " " + path)
        if response.status >= 300:
            body = await response.read()
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

    async def websocket_query(self, path, params={}):
        """
        Opens a websocket connection

        :param path: Endpoint in API
        :param params: Parameters added as a query arg
        :returns: Websocket
        """

        url = "http://docker/v" + self._api_version + "/" + path
        connection = await self._session.ws_connect(url, origin="http://docker", autoping=True)
        return connection

    @locking
    async def pull_image(self, image, progress_callback=None):
        """
        Pulls an image from the Docker repository

        :params image: Image name
        :params progress_callback: A function that receive a log message about image download progress
        """

        try:
            await self.query("GET", "images/{}/json".format(image))
            return  # We already have the image skip the download
        except DockerHttp404Error:
            pass

        if progress_callback:
            progress_callback("Pulling '{}' from docker hub".format(image))
        try:
            response = await self.http_query("POST", "images/create", params={"fromImage": image}, timeout=None)
        except DockerError as e:
            raise DockerError("Could not pull the '{}' image from Docker Hub, please check your Internet connection (original error: {})".format(image, e))
        # The pull api will stream status via an HTTP JSON stream
        content = ""
        while True:
            try:
                chunk = await response.content.read(CHUNK_SIZE)
            except aiohttp.ServerDisconnectedError:
                log.error("Disconnected from server while pulling Docker image '{}' from docker hub".format(image))
                break
            except asyncio.TimeoutError:
                log.error("Timeout while pulling Docker image '{}' from docker hub".format(image))
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

    async def list_images(self):
        """
        Gets Docker image list.

        :returns: list of dicts
        :rtype: list
        """

        images = []
        for image in (await self.query("GET", "images/json", params={"all": 0})):
            if image['RepoTags']:
                for tag in image['RepoTags']:
                    if tag != "<none>:<none>":
                        images.append({'image': tag})
        return sorted(images, key=lambda i: i['image'])
