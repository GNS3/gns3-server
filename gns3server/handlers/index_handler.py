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


from ..web.route import Route
from ..hypervisor.port_manager import PortManager
from ..hypervisor.project_manager import ProjectManager
from ..version import __version__


class IndexHandler:

    @classmethod
    @Route.get(
        r"/",
        description="Home page for GNS3Server"
    )
    def index(request, response):
        response.template("index.html")

    @classmethod
    @Route.get(
        r"/status",
        description="Ressources used by GNS3Server"
    )
    def ports(request, response):
        response.template("status.html",
                          port_manager=PortManager.instance(),
                          project_manager=ProjectManager.instance()
                          )

    @classmethod
    @Route.get(
        r"/v1/version",
        description="Old API"
    )
    def get_v1(request, response):
        response.json({"version": __version__})
