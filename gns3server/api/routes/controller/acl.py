#!/usr/bin/env python
#
# Copyright (C) 2023 GNS3 Technologies Inc.
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
API routes for ACL.
"""

import re

from fastapi import APIRouter, Depends, Request, status
from fastapi.routing import APIRoute
from uuid import UUID
from typing import List


from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerNotFoundError
)

from gns3server.controller import Controller
from gns3server.db.repositories.users import UsersRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.db.repositories.pools import ResourcePoolsRepository
from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/endpoints",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("ACE.Audit"))]
)
async def endpoints(
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
        templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
        pools_repo: ResourcePoolsRepository = Depends(get_repository(ResourcePoolsRepository))
) -> List[dict]:
    """
    List all endpoints to be used in ACL entries.
    """

    controller = Controller.instance()
    endpoints = [{"endpoint": "/", "name": "All endpoints", "endpoint_type": "root"}]

    def add_to_endpoints(endpoint: str, name: str, endpoint_type: str) -> None:
        if endpoint not in endpoints:
            endpoints.append({"endpoint": endpoint, "name": name, "endpoint_type": endpoint_type})

    # projects
    add_to_endpoints("/projects", "All projects", "project")
    projects = [p for p in controller.projects.values()]
    for project in projects:
        add_to_endpoints(f"/projects/{project.id}", f'Project "{project.name}"', "project")

        if project.status == "closed":
            nodes = project.nodes.values()
            links = project.links.values()
        else:
            nodes = [v.asdict() for v in project.nodes.values()]
            links = [v.asdict() for v in project.links.values()]

        # nodes
        add_to_endpoints(f"/projects/{project.id}/nodes", f'All nodes in project "{project.name}"', "node")
        for node in nodes:
            add_to_endpoints(
                f"/projects/{project.id}/nodes/{node['node_id']}",
                f'Node "{node["name"]}" in project "{project.name}"',
                endpoint_type="node"
            )

        # links
        add_to_endpoints(f"/projects/{project.id}/links", f'All links in project "{project.name}"', "link")
        for link in links:
            node_id_1 = link["nodes"][0]["node_id"]
            node_id_2 = link["nodes"][1]["node_id"]
            node_name_1 = node_name_2 = "N/A"
            for node in nodes:
                if node["node_id"] == node_id_1:
                    node_name_1 = node["name"]
                if node["node_id"] == node_id_2:
                    node_name_2 = node["name"]
            add_to_endpoints(
                f"/projects/{project.id}/links/{link['link_id']}",
                f'Link from "{node_name_1}" to "{node_name_2}" in project "{project.name}"',
                endpoint_type="link"
            )

    # users
    add_to_endpoints("/access/users", "All users", "user")
    users = await users_repo.get_users()
    for user in users:
        add_to_endpoints(f"/users/{user.user_id}", f'User "{user.username}"', "user")

    # groups
    add_to_endpoints("/access/groups", "All groups", "group")
    groups = await users_repo.get_user_groups()
    for group in groups:
        add_to_endpoints(f"/groups/{group.user_group_id}", f'Group "{group.name}"', "group")

    # roles
    add_to_endpoints("/access/roles", "All roles", "role")
    roles = await rbac_repo.get_roles()
    for role in roles:
        add_to_endpoints(f"/roles/{role.role_id}", f'Role "{role.name}"', "role")

    # images
    add_to_endpoints("/images", "All images", "image")
    images = await images_repo.get_images()
    for image in images:
        add_to_endpoints(f"/images/{image.filename}", f'Image "{image.filename}"', "image")

    # templates
    add_to_endpoints("/templates", "All templates", "template")
    templates = await templates_repo.get_templates()
    for template in templates:
        add_to_endpoints(f"/templates/{template.template_id}", f'Template "{template.name}"', "template")

    # resource pools
    add_to_endpoints("/pools", "All resource pools", "pool")
    pools = await pools_repo.get_resource_pools()
    for pool in pools:
        add_to_endpoints(f"/pools/{pool.resource_pool_id}", f'Resource pool "{pool.name}"', "pool")
    return endpoints


@router.get(
    "",
    response_model=List[schemas.ACE],
    dependencies=[Depends(has_privilege("ACE.Audit"))]
)
async def get_aces(
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.ACE]:
    """
    Get all ACL entries.

    Required privilege: ACE.Audit
    """

    return await rbac_repo.get_aces()


@router.post(
    "",
    response_model=schemas.ACE,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("ACE.Allocate"))]
)
async def create_ace(
        request: Request,
        ace_create: schemas.ACECreate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.ACE:
    """
    Create a new ACL entry.

    Required privilege: ACE.Allocate
    """

    for route in request.app.routes:
        if isinstance(route, APIRoute):

            # remove the prefix (e.g. "/v3") from the route path
            route_path = re.sub(r"^/v[0-9]", "", route.path)
            # replace route path ID parameters by a UUID regex
            route_path = re.sub(r"{\w+_id}", "[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", route_path)
            # replace remaining route path parameters by a word matching regex
            route_path = re.sub(r"/{[\w:]+}", r"/\\w+", route_path)

            if re.fullmatch(route_path, ace_create.path):
                log.info(f"Creating ACE for route path {route_path}")
                return await rbac_repo.create_ace(ace_create)

    raise ControllerBadRequestError(f"Path '{ace_create.path}' doesn't match any existing endpoint")


@router.get(
    "/{ace_id}",
    response_model=schemas.ACE,
    dependencies=[Depends(has_privilege("ACE.Audit"))]
)
async def get_ace(
        ace_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> schemas.ACE:
    """
    Get an ACL entry.

    Required privilege: ACE.Audit
    """

    ace = await rbac_repo.get_ace(ace_id)
    if not ace:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' not found")
    return ace


@router.put(
    "/{ace_id}",
    response_model=schemas.ACE,
    dependencies=[Depends(has_privilege("ACE.Modify"))]
)
async def update_ace(
        ace_id: UUID,
        ace_update: schemas.ACEUpdate,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.ACE:
    """
    Update an ACL entry.

    Required privilege: ACE.Modify
    """

    ace = await rbac_repo.get_ace(ace_id)
    if not ace:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' not found")

    return await rbac_repo.update_ace(ace_id, ace_update)


@router.delete(
    "/{ace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("ACE.Allocate"))]
)
async def delete_ace(
    ace_id: UUID,
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
) -> None:
    """
    Delete an ACL entry.

    Required privilege: ACE.Allocate
    """

    ace = await rbac_repo.get_ace(ace_id)
    if not ace:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' not found")

    success = await rbac_repo.delete_ace(ace_id)
    if not success:
        raise ControllerNotFoundError(f"ACL entry '{ace_id}' could not be deleted")
