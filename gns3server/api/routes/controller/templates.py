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
API routes for templates.
"""

import hashlib
import json
import pydantic

import logging
log = logging.getLogger(__name__)

from fastapi import APIRouter, Request, Response, HTTPException, Depends, status
from typing import List
from uuid import UUID

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerNotFoundError,
    ControllerForbiddenError
)

from .dependencies.database import get_repository

router = APIRouter()

responses = {
    404: {"model": schemas.ErrorMessage, "description": "Could not find template"}
}


@router.post("/templates", response_model=schemas.Template, status_code=status.HTTP_201_CREATED)
async def create_template(
        new_template: schemas.TemplateCreate,
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> dict:
    """
    Create a new template.
    """

    try:
        return await template_repo.create_template(new_template)
    except pydantic.ValidationError as e:
        raise ControllerBadRequestError(f"JSON schema error received while creating new template: {e}")


@router.get("/templates/{template_id}",
            response_model=schemas.Template,
            response_model_exclude_unset=True,
            responses=responses)
async def get_template(
        template_id: UUID,
        request: Request,
        response: Response,
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> dict:
    """
    Return a template.
    """

    request_etag = request.headers.get("If-None-Match", "")
    template = await template_repo.get_template(template_id)
    if not template:
        raise ControllerNotFoundError(f"Template '{template_id}' not found")
    data = json.dumps(template)
    template_etag = '"' + hashlib.md5(data.encode()).hexdigest() + '"'
    if template_etag == request_etag:
        raise HTTPException(status_code=status.HTTP_304_NOT_MODIFIED)
    else:
        response.headers["ETag"] = template_etag
        return template


@router.put("/templates/{template_id}",
            response_model=schemas.Template,
            response_model_exclude_unset=True,
            responses=responses)
async def update_template(
        template_id: UUID,
        template_data: schemas.TemplateUpdate,
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> dict:
    """
    Update a template.
    """

    if template_repo.get_builtin_template(template_id):
        raise ControllerForbiddenError(f"Template '{template_id}' cannot be updated because it is built-in")
    template = await template_repo.update_template(template_id, template_data)
    if not template:
        raise ControllerNotFoundError(f"Template '{template_id}' not found")
    return template


@router.delete("/templates/{template_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_template(
        template_id: UUID,
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> None:
    """
    Delete a template.
    """

    if template_repo.get_builtin_template(template_id):
        raise ControllerForbiddenError(f"Template '{template_id}' cannot be deleted because it is built-in")
    success = await template_repo.delete_template(template_id)
    if not success:
        raise ControllerNotFoundError(f"Template '{template_id}' not found")


@router.get("/templates",
            response_model=List[schemas.Template],
            response_model_exclude_unset=True)
async def get_templates(
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> List[dict]:
    """
    Return all templates.
    """

    templates = await template_repo.get_templates()
    return templates


@router.post("/templates/{template_id}/duplicate",
             response_model=schemas.Template,
             status_code=status.HTTP_201_CREATED,
             responses=responses)
async def duplicate_template(
        template_id: UUID,
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> dict:
    """
    Duplicate a template.
    """

    if template_repo.get_builtin_template(template_id):
        raise ControllerForbiddenError(f"Template '{template_id}' cannot be duplicated because it is built-in")
    template = await template_repo.duplicate_template(template_id)
    if not template:
        raise ControllerNotFoundError(f"Template '{template_id}' not found")
    return template


@router.post("/projects/{project_id}/templates/{template_id}",
             response_model=schemas.Node,
             status_code=status.HTTP_201_CREATED,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not find project or template"}})
async def create_node_from_template(
        project_id: UUID,
        template_id: UUID,
        template_usage: schemas.TemplateUsage,
        template_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> schemas.Node:
    """
    Create a new node from a template.
    """

    template = await template_repo.get_template(template_id)
    if not template:
        raise ControllerNotFoundError(f"Template '{template_id}' not found")
    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    node = await project.add_node_from_template(template,
                                                x=template_usage.x,
                                                y=template_usage.y,
                                                compute_id=template_usage.compute_id)
    return node.__json__()
