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


from ..controller.controller_error import ControllerError
from ..config import Config
from ..version import __version__


import logging
log = logging.getLogger(__name__)


class ServerError(ControllerError):
    pass


class Server:
    """
    A GNS3 server.
    """

    def __init__(self, server_id, protocol="http", host="localhost", port=8000, user=None, password=None):
        log.info("Create server %s", server_id)
        self._id = server_id
        self._protocol = protocol
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._connected = False
        # The remote server version
        # TODO: For the moment it's fake we return the controller version
        self._version = __version__

        # If the server is local but the server id is local
        # it's a configuration issue
        if server_id == "local" and Config.instance().get_section_config("Server")["local"] is False:
            raise ServerError("The local server is started without --local")

    @property
    def id(self):
        """
        :returns: Server identifier (string)
        """
        return self._id

    @property
    def host(self):
        """
        :returns: Server host (string)
        """
        return self._host

    def __json__(self):
        return {
            "server_id": self._id,
            "protocol": self._protocol,
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "connected": self._connected,
            "version": self._version
        }
