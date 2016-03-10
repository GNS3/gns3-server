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

from ..controller.controller_error import ControllerError
from ..config import Config
from ..version import __version__


import logging
log = logging.getLogger(__name__)


class HypervisorError(ControllerError):
    pass


class Hypervisor:
    """
    A GNS3 hypervisor.
    """

    def __init__(self, hypervisor_id, protocol="http", host="localhost", port=8000, user=None, password=None):
        log.info("Create hypervisor %s", hypervisor_id)
        self._id = hypervisor_id
        self._protocol = protocol
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._connected = False
        # The remote hypervisor version
        # TODO: For the moment it's fake we return the controller version
        self._version = __version__

        # If the hypervisor is local but the hypervisor id is local
        # it's a configuration issue
        if hypervisor_id == "local" and Config.instance().get_section_config("Server")["local"] is False:
            raise HypervisorError("The local hypervisor is started without --local")

    @property
    def id(self):
        """
        :returns: Hypervisor identifier (string)
        """
        return self._id

    @property
    def host(self):
        """
        :returns: Hypervisor host (string)
        """
        return self._host

    def __json__(self):
        return {
            "hypervisor_id": self._id,
            "protocol": self._protocol,
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "connected": self._connected,
            "version": self._version
        }

    @asyncio.coroutine
    def _httpQuery(self, method, path, data=None):
        with aiohttp.Timeout(10):
            with aiohttp.ClientSession() as session:
                url = "{}://{}:{}/v2/hypervisor{}".format(self._protocol, self._host, self._port, path)
                headers = {'content-type': 'application/json'}
                if hasattr(data, '__json__'):
                    data = data.__json__()
                data = json.dumps(data)
                response = yield from session.request(method, url, headers=headers, data=data)
                print(response.status)
                assert response.status < 300
                body = yield from response.read()
                yield from response.release()
        return body

    @asyncio.coroutine
    def post(self, path, data):
        yield from self._httpQuery("POST", path, data)
