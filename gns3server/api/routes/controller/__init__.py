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

from fastapi import APIRouter, Depends

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
from . import images
from . import users
from . import groups
from . import roles
from . import permissions

from .dependencies.authentication import get_current_active_user

router = APIRouter()

router.include_router(controller.router, tags=["Controller"])
router.include_router(users.router, prefix="/users", tags=["Users"])

router.include_router(
    groups.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/groups",
    tags=["Users groups"]
)

router.include_router(
    roles.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/roles",
    tags=["Roles"]
)

router.include_router(
    permissions.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/permissions",
    tags=["Permissions"]
)

router.include_router(
    images.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/images",
    tags=["Images"]
)

router.include_router(
    templates.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/templates",
    tags=["Templates"]
)

router.include_router(
    projects.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/projects",
    tags=["Projects"])

router.include_router(
    nodes.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/projects/{project_id}/nodes",
    tags=["Nodes"]
)

router.include_router(
    links.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/projects/{project_id}/links",
    tags=["Links"]
)

router.include_router(
    drawings.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/projects/{project_id}/drawings",
    tags=["Drawings"])

router.include_router(
    symbols.router,
    prefix="/symbols", tags=["Symbols"]
)

router.include_router(
    snapshots.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/projects/{project_id}/snapshots",
    tags=["Snapshots"])

router.include_router(
    computes.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/computes",
    tags=["Computes"]
)

router.include_router(
    notifications.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/notifications",
    tags=["Notifications"])

router.include_router(
    appliances.router,
    dependencies=[Depends(get_current_active_user)],
    prefix="/appliances",
    tags=["Appliances"]
)

router.include_router(
    gns3vm.router,
    deprecated=True,
    dependencies=[Depends(get_current_active_user)],
    prefix="/gns3vm",
    tags=["GNS3 VM"]
)
