#
# Copyright (C) 2021 GNS3 Technologies Inc.
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
API routes for templates.
"""

import hashlib
import json

import logging

log = logging.getLogger(__name__)

from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from typing import List
from uuid import UUID

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.services.templates import TemplatesService
from .dependencies.database import get_repository

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find template"}}

router = APIRouter(responses=responses)


@router.post("/templates", response_model=schemas.Template, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_create: schemas.TemplateCreate,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Template:
    """
    Create a new template.
    """

    return await TemplatesService(templates_repo).create_template(template_create)


@router.get("/templates/{template_id}", response_model=schemas.Template, response_model_exclude_unset=True)
async def get_template(
    template_id: UUID,
    request: Request,
    response: Response,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Template:
    """
    Return a template.
    """

    request_etag = request.headers.get("If-None-Match", "")
    template = await TemplatesService(templates_repo).get_template(template_id)
    data = json.dumps(template)
    template_etag = '"' + hashlib.md5(data.encode()).hexdigest() + '"'
    if template_etag == request_etag:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)
    else:
        response.headers["ETag"] = template_etag
        return template


@router.put("/templates/{template_id}", response_model=schemas.Template, response_model_exclude_unset=True)
async def update_template(
    template_id: UUID,
    template_update: schemas.TemplateUpdate,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Template:
    """
    Update a template.
    """

    return await TemplatesService(templates_repo).update_template(template_id, template_update)


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template(
    template_id: UUID, templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> None:
    """
    Delete a template.
    """

    await TemplatesService(templates_repo).delete_template(template_id)


@router.get("/templates", response_model=List[schemas.Template], response_model_exclude_unset=True)
async def get_templates(
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> List[schemas.Template]:
    """
    Return all templates.
    """

    return await TemplatesService(templates_repo).get_templates()


@router.post("/templates/{template_id}/duplicate", response_model=schemas.Template, status_code=status.HTTP_201_CREATED)
async def duplicate_template(
    template_id: UUID, templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> schemas.Template:
    """
    Duplicate a template.
    """

    return await TemplatesService(templates_repo).duplicate_template(template_id)


@router.post(
    "/projects/{project_id}/templates/{template_id}",
    response_model=schemas.Node,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or template"}},
)
async def create_node_from_template(
    project_id: UUID,
    template_id: UUID,
    template_usage: schemas.TemplateUsage,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Node:
    """
    Create a new node from a template.
    """

    template = await TemplatesService(templates_repo).get_template(template_id)
    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    node = await project.add_node_from_template(
        template, x=template_usage.x, y=template_usage.y, compute_id=template_usage.compute_id
    )
    return node.asdict()
