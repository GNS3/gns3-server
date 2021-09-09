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

import psutil
import platform

from gns3server.web.route import Route
from gns3server.config import Config
from gns3server.schemas.version import VERSION_SCHEMA
from gns3server.schemas.server_statistics import SERVER_STATISTICS_SCHEMA
from gns3server.compute.port_manager import PortManager
from gns3server.utils.cpu_percent import CpuPercent
from gns3server.utils.path import get_default_project_directory
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
        r"/statistics",
        description="Retrieve server statistics",
        output=SERVER_STATISTICS_SCHEMA,
        status_codes={
            200: "Statistics information returned",
            409: "Conflict"
        })
    def statistics(request, response):

        try:
            memory_total = psutil.virtual_memory().total
            memory_free = psutil.virtual_memory().available
            memory_used = memory_total - memory_free  # actual memory usage in a cross platform fashion
            swap_total = psutil.swap_memory().total
            swap_free = psutil.swap_memory().free
            swap_used = psutil.swap_memory().used
            cpu_percent = int(CpuPercent.get())
            load_average_percent = [int(x / psutil.cpu_count() * 100) for x in psutil.getloadavg()]
            memory_percent = int(psutil.virtual_memory().percent)
            swap_percent = int(psutil.swap_memory().percent)
            disk_usage_percent = int(psutil.disk_usage(get_default_project_directory()).percent)
        except psutil.Error as e:
            raise HTTPConflict(text="Psutil error detected: {}".format(e))
        response.json({"memory_total": memory_total,
                       "memory_free": memory_free,
                       "memory_used": memory_used,
                       "swap_total": swap_total,
                       "swap_free": swap_free,
                       "swap_used": swap_used,
                       "cpu_usage_percent": cpu_percent,
                       "memory_usage_percent": memory_percent,
                       "swap_usage_percent": swap_percent,
                       "disk_usage_percent": disk_usage_percent,
                       "load_average_percent": load_average_percent})

    @Route.get(
        r"/debug",
        description="Return debug information about the compute",
        status_codes={
            201: "Written"
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

