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

import os
import psutil
import platform

from gns3server.web.route import Route
from gns3server.config import Config
from gns3server.schemas.version import VERSION_SCHEMA
from gns3server.compute.port_manager import PortManager
from gns3server.version import __version__
from aiohttp.web import HTTPConflict


class ServerHandler:

    @Route.get(
        r"/version",
        description="Retrieve the server version number",
        output=VERSION_SCHEMA)
    def version(request, response):

        config = Config.instance()
        local_server = config.get_section_config("Server").getboolean("local", False)
        response.json({"version": __version__, "local": local_server})


    @Route.get(
        r"/debug",
        description="Return debug informations about the compute",
        status_codes={
            201: "Writed"
        })
    def debug(request, response):
        response.content_type = "text/plain"
        response.text = ServerHandler._getDebugData()

    @staticmethod
    def _getDebugData():
        try:
            addrs = ["* {}: {}".format(key, val) for key, val in psutil.net_if_addrs().items()]
        except UnicodeDecodeError:
            addrs = ["INVALID ADDR WITH UNICODE CHARACTERS"]

        data = """Version: {version}
OS: {os}
Python: {python}
CPU: {cpu}
Memory: {memory}

Networks:
{addrs}
""".format(
            version=__version__,
            os=platform.platform(),
            python=platform.python_version(),
            memory=psutil.virtual_memory(),
            cpu=psutil.cpu_times(),
            addrs="\n".join(addrs)
        )

        try:
            connections = psutil.net_connections()
        # You need to be root for OSX
        except psutil.AccessDenied:
            connections = None

        if connections:
            data += "\n\nConnections:\n"
            for port in PortManager.instance().tcp_ports:
                found = False
                for open_port in connections:
                    if open_port.laddr[1] == port:
                        found = True
                data += "TCP {}: {}\n".format(port, found)
            for port in PortManager.instance().udp_ports:
                found = False
                for open_port in connections:
                    if open_port.laddr[1] == port:
                        found = True
                data += "UDP {}: {}\n".format(port, found)
        return data

