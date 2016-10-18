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


from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.compute.port_manager import PortManager
from gns3server.compute.project_manager import ProjectManager
from gns3server.version import __version__


class IndexHandler:

    @Route.get(
        r"/",
        description="Home page of the GNS3 server"
    )
    def index(request, response):
        response.template("index.html")

    @Route.get(
        r"/upload",
        description="Placeholder page for the old /upload"
    )
    def upload(request, response):
        response.template("upload.html")

    @Route.get(
        r"/compute",
        description="Resources used by the GNS3 compute servers"
    )
    def compute(request, response):
        response.template("compute.html",
                          port_manager=PortManager.instance(),
                          project_manager=ProjectManager.instance())

    @Route.get(
        r"/controller",
        description="Resources used by the GNS3 controller server"
    )
    def controller(request, response):
        response.template("controller.html",
                          controller=Controller.instance())

    @Route.get(
        r"/projects/{project_id}",
        description="List of the GNS3 projects"
    )
    def project(request, response):
        controller = Controller.instance()
        response.template("project.html",
                          project=controller.get_project(request.match_info["project_id"]))

    @Route.get(
        r"/v1/version",
        description="Old 1.0 API"
    )
    def get_v1(request, response):
        response.json({"version": __version__})
