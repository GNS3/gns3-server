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

import os
import aiohttp

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.compute.port_manager import PortManager
from gns3server.compute.project_manager import ProjectManager
from gns3server.version import __version__
from gns3server.utils.get_resource import get_resource 


class IndexHandler:

    @Route.get(
        r"/",
        description="Home page of the GNS3 server"
    )
    async def index(request, response):

        raise aiohttp.web.HTTPFound(location="/static/web-ui/bundled")

    @Route.get(
        r"/debug",
        description="Old index page"
    )
    def upload(request, response):
        response.template("index.html")

    @Route.get(
        r"/upload",
        description="Placeholder page for the old /upload"
    )
    def upload(request, response):
        response.template("upload.html")

    @Route.get(
        r"/compute",
        description="Resources used by the GNS3 computes"
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
        r"/static/web-ui/{filename:.+}",
        parameters={
            "filename": "Static filename"
        },
        status_codes={
            200: "Static file returned",
            404: "Static cannot be found",
        },
        raw=True,
        description="Get static resource")
    async def webui(request, response):
        filename = request.match_info["filename"]
        filename = os.path.normpath(filename).strip("/")
        filename = os.path.join('static', 'web-ui', filename)

        # Raise error if user try to escape
        if filename[0] == "." or '/../' in filename:
            raise aiohttp.web.HTTPForbidden()

        static = get_resource(filename)

        if static is None or not os.path.exists(static):
            static = get_resource(os.path.join('static', 'web-ui', 'index.html'))

        # guesstype prefers to have text/html type than application/javascript
        # which results with warnings in Firefox 66 on Windows
        # Ref. gns3-server#1559
        _, ext = os.path.splitext(static)
        mimetype = ext == '.js' and 'application/javascript' or None

        await response.stream_file(static, status=200, set_content_type=mimetype)

    @Route.get(
        r"/v1/version",
        description="Old 1.0 API"
    )
    def get_v1(request, response):
        response.json({"version": __version__})
