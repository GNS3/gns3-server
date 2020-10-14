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

from fastapi import APIRouter

from . import controller
from . import appliances
from . import computes
from . import drawings
from . import gns3vm
from . import links
from . import nodes
from . import notifications
from . import projects
from . import snapshots
from . import symbols
from . import templates

router = APIRouter()
router.include_router(controller.router, tags=["controller"])
router.include_router(appliances.router, prefix="/appliances", tags=["appliances"])
router.include_router(computes.router, prefix="/computes", tags=["computes"])
router.include_router(drawings.router, prefix="/projects/{project_id}/drawings", tags=["drawings"])
router.include_router(gns3vm.router, prefix="/gns3vm", tags=["GNS3 VM"])
router.include_router(links.router, prefix="/projects/{project_id}/links", tags=["links"])
router.include_router(nodes.router, prefix="/projects/{project_id}/nodes", tags=["nodes"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(snapshots.router, prefix="/projects/{project_id}/snapshots", tags=["snapshots"])
router.include_router(symbols.router, prefix="/symbols", tags=["symbols"])
router.include_router(templates.router, tags=["templates"])
