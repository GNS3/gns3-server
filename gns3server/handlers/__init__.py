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

import sys
import os

from gns3server.handlers.api.version_handler import VersionHandler
from gns3server.handlers.api.network_handler import NetworkHandler
from gns3server.handlers.api.project_handler import ProjectHandler
from gns3server.handlers.api.dynamips_device_handler import DynamipsDeviceHandler
from gns3server.handlers.api.dynamips_vm_handler import DynamipsVMHandler
from gns3server.handlers.api.qemu_handler import QEMUHandler
from gns3server.handlers.api.virtualbox_handler import VirtualBoxHandler
from gns3server.handlers.api.vpcs_handler import VPCSHandler
from gns3server.handlers.api.config_handler import ConfigHandler
from gns3server.handlers.api.server_handler import ServerHandler
from gns3server.handlers.upload_handler import UploadHandler
from ..web.route import Route

if sys.platform.startswith("linux") or hasattr(sys, "_called_from_test"):
    from gns3server.handlers.api.iou_handler import IOUHandler

class HomePage:

    @classmethod
    @Route.get(
        r"/",
        description="Home page for GNS3Server",
        api_version=None
    )
    def index(request, response):
        response.template("homepage.html")
