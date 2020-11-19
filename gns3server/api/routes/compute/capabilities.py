# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

"""
API routes for capabilities
"""

import sys
import psutil

from fastapi import APIRouter

from gns3server.version import __version__
from gns3server.compute import MODULES
from gns3server.utils.path import get_default_project_directory
from gns3server import schemas

router = APIRouter()


@router.get("/capabilities",
            response_model=schemas.Capabilities
)
def get_compute_capabilities():

    node_types = []
    for module in MODULES:
        node_types.extend(module.node_types())

    return {"version": __version__,
            "platform": sys.platform,
            "cpus": psutil.cpu_count(logical=True),
            "memory": psutil.virtual_memory().total,
            "disk_size": psutil.disk_usage(get_default_project_directory()).total,
            "node_types": node_types}
