#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import asyncio
import json

from ..utils import parse_version
from ..controller.controller_error import ControllerError
from ..config import Config
from ..version import __version__


import logging
log = logging.getLogger(__name__)


class ComputeError(ControllerError):
    pass


class Compute:
    """
    A GNS3 compute.
    """

    def __init__(self, compute_id, controller=None, protocol="http", host="localhost", port=8000, user=None, password=None):
        assert controller is not None
        log.info("Create compute %s", compute_id)
        self._id = compute_id
        self._protocol = protocol
        self._host = host
        self._port = port
        self._user = None
        self._password = None
        self._connected = False
        self._controller = controller
        self._set_auth(user, password)
        self._session = aiohttp.ClientSession()
        self._version = None

        # If the compute is local but the compute id is local
        # it's a configuration issue
        if compute_id == "local" and Config.instance().get_section_config("Server")["local"] is False:
            raise ComputeError("The local compute is started without --local")

    def __del__(self):
        self._session.close()

    def _set_auth(self, user, password):
        """
        Set authentication parameters
        """
        self._user = user
        self._password = password
        if self._user and self._password:
            self._auth = aiohttp.BasicAuth(self._user, self._password)
        else:
            self._auth = None

    @property
    def version(self):
        """
        :returns: Version of compute node (string or None if not connected)
        """
        return self._version

    @property
    def connected(self):
        """
        :returns: True if compute node is connected
        """
        return self._connected

    @property
    def id(self):
        """
        :returns: Compute identifier (string)
        """
        return self._id

    @property
    def host(self):
        """
        :returns: Compute host (string)
        """
        return self._host

    @property
    def port(self):
        """
        :returns: Compute port (integer)
        """
        return self._port

    @property
    def protocol(self):
        """
        :returns: Compute protocol (string)
        """
        return self._protocol

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, value):
        self._set_auth(value, self._password)

    @property
    def password(self):
        return self._password

    @user.setter
    def password(self, value):
        self._set_auth(self._user, value)

    def __json__(self):
        return {
            "compute_id": self._id,
            "protocol": self._protocol,
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "connected": self._connected
        }

    @asyncio.coroutine
    def steam_file(self, project, path):
        """
        Read file of a project and stream it

        :param project: A project object
        :param path: The path of the file in the project
        :returns: A file stream
        """

        url = self._getUrl("/projects/{}/stream/{}".format(project.id, path))
        response = yield from self._session.request("GET", url, auth=self._auth)
        if response.status == 404:
            raise aiohttp.web.HTTPNotFound(text="{} not found on compute".format(path))
        return response.content

    @asyncio.coroutine
    def http_query(self, method, path, data=None):
        if not self._connected:
            yield from self._connect()
        if not self._connected:
            raise aiohttp.web.HTTPConflict(text="The server {} is not a GNS3 server".format(self._id))
        response = yield from self._run_http_query(method, path, data=data)
        return response

    @asyncio.coroutine
    def _connect(self):
        """
        Check if remote server is accessible
        """
        if not self._connected:
            response = yield from self._run_http_query("GET", "/version")

            if "version" not in response.json:
                raise aiohttp.web.HTTPConflict(text="The server {} is not a GNS3 server".format(self._id))
            self._version = response.json["version"]
            if parse_version(__version__)[:2] != parse_version(response.json["version"])[:2]:
                raise aiohttp.web.HTTPConflict(text="The server {} versions are not compatible {} != {}".format(self._id, __version__, response.json["version"]))

            self._notifications = asyncio.async(self._connect_notification())
            self._connected = True

    @asyncio.coroutine
    def _connect_notification(self):
        """
        Connect to the notification stream
        """
        ws = yield from self._session.ws_connect(self._getUrl("/notifications/ws"))
        while True:
            response = yield from ws.receive()
            if response.tp == aiohttp.MsgType.closed or response.tp == aiohttp.MsgType.error:
                self._connected = False
                break
            msg = json.loads(response.data)
            action = msg.pop("action")
            event = msg.pop("event")
            self._controller.notification.dispatch(action, event, compute_id=self.id)

    def _getUrl(self, path):
        return "{}://{}:{}/v2/compute{}".format(self._protocol, self._host, self._port, path)

    @asyncio.coroutine
    def _run_http_query(self, method, path, data=None):
        with aiohttp.Timeout(10):
            url = self._getUrl(path)
            headers = {'content-type': 'application/json'}
            if data == {}:
                data = None
            elif data is not None:
                if hasattr(data, '__json__'):
                    data = data.__json__()
                data = json.dumps(data)

            response = yield from self._session.request(method, url, headers=headers, data=data, auth=self._auth)
            body = yield from response.read()
            if body:
                body = body.decode()

            if response.status >= 300:
                if response.status == 400:
                    raise aiohttp.web.HTTPBadRequest(text="Bad request {} {}".format(url, body))
                elif response.status == 401:
                    raise aiohttp.web.HTTPUnauthorized(text="Invalid authentication for compute {}".format(self.id))
                elif response.status == 403:
                    raise aiohttp.web.HTTPForbidden(text="Forbidden {} {}".format(url, body))
                elif response.status == 404:
                    raise aiohttp.web.HTTPNotFound(text="{} not found on compute".format(url))
                elif response.status == 409:
                    raise aiohttp.web.HTTPConflict(text="Conflict {} {}".format(url, body))
                elif response.status == 503:
                    raise aiohttp.web.HTTPServiceUnavailable(text="Service unavailable {} {}".format(url, body))
                else:
                    raise NotImplementedError("{} status code is not supported".format(response.status))
            if body and len(body):
                try:
                    response.json = json.loads(body)
                except ValueError:
                    raise aiohttp.web.HTTPConflict(text="The server {} is not a GNS3 server".format(self._id))
            if response.json is None:
                response.json = {}
            return response

    @asyncio.coroutine
    def get(self, path):
        return (yield from self.http_query("GET", path))

    @asyncio.coroutine
    def post(self, path, data={}):
        response = yield from self.http_query("POST", path, data)
        return response

    @asyncio.coroutine
    def put(self, path, data={}):
        response = yield from self.http_query("PUT", path, data)
        return response

    @asyncio.coroutine
    def delete(self, path):
        return (yield from self.http_query("DELETE", path))
