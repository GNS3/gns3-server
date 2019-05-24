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

from gns3server.web.route import Route
from gns3server.compute.port_manager import PortManager
from gns3server.compute.project_manager import ProjectManager
from gns3server.utils.interfaces import interfaces


class NetworkHandler:

    @Route.post(
        r"/projects/{project_id}/ports/udp",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            201: "UDP port allocated",
            404: "The project doesn't exist"
        },
        description="Allocate an UDP port on the server")
    def allocate_udp_port(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["project_id"])
        m = PortManager.instance()
        udp_port = m.get_free_udp_port(project)
        response.set_status(201)
        response.json({"udp_port": udp_port})

    @Route.get(
        r"/network/interfaces",
        description="List all the network interfaces available on the server")
    def network_interfaces(request, response):

        network_interfaces = interfaces()
        response.json(network_interfaces)

    @Route.get(
        r"/network/ports",
        description="List all the ports used by the server")
    def network_ports(request, response):

        m = PortManager.instance()
        response.json(m)
