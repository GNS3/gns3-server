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

from fastapi import APIRouter, Request, HTTPException, Depends, Response, status
from typing import List, Optional
from uuid import UUID

from gns3server import schemas
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.services.templates import TemplatesService
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.db.repositories.images import ImagesRepository

from .dependencies.authentication import get_current_active_user
from .dependencies.rbac import has_privilege
from .dependencies.database import get_repository

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find template"}}

router = APIRouter(responses=responses)


@router.post(
    "",
    response_model=schemas.Template,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Template.Allocate"))]
)
async def create_template(
    template_create: schemas.TemplateCreate,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> schemas.Template:
    """
    Create a new template.

    Required privilege: Template.Allocate
    """

    template = await TemplatesService(templates_repo).create_template(template_create)
    return template


@router.get(
    "/{template_id}",
    response_model=schemas.Template,
    response_model_exclude_unset=True,
    dependencies=[Depends(get_current_active_user)],
    #dependencies=[Depends(has_privilege("Template.Audit"))]  # FIXME: this is a temporary workaround due to a bug in the web-ui
)
async def get_template(
    template_id: UUID,
    request: Request,
    response: Response,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Template:
    """
    Return a template.

    Required privilege: Template.Audit
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


@router.put(
    "/{template_id}",
    response_model=schemas.Template,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Template.Modify"))]
)
async def update_template(
    template_id: UUID,
    template_update: schemas.TemplateUpdate,
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> schemas.Template:
    """
    Update a template.

    Required privilege: Template.Modify
    """

    return await TemplatesService(templates_repo).update_template(template_id, template_update)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Template.Allocate"))]
)
async def delete_template(
        template_id: UUID,
        prune_images: Optional[bool] = False,
        templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
        images_repo: RbacRepository = Depends(get_repository(ImagesRepository)),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a template.

    Required privilege: Template.Allocate
    """

    await TemplatesService(templates_repo).delete_template(template_id)
    await rbac_repo.delete_all_ace_starting_with_path(f"/templates/{template_id}")
    if prune_images:
        await images_repo.prune_images()


@router.get(
    "",
    response_model=List[schemas.Template],
    response_model_exclude_unset=True,
    dependencies=[Depends(get_current_active_user)],
    #dependencies=[Depends(has_privilege("Template.Audit"))]  # FIXME: this is a temporary workaround due to a bug in the web-ui
)
async def get_templates(
        templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> List[schemas.Template]:
    """
    Return all templates.

    Required privilege: Template.Audit
    """

    templates = await TemplatesService(templates_repo).get_templates()
    if current_user.is_superadmin:
        return templates
    else:
        user_templates = []
        for template in templates:
            # if template.get("builtin") is True:
            #     user_templates.append(template)
            #     continue
            # template_id = template.get("template_id")
            # authorized = await rbac_repo.check_user_is_authorized(
            #     current_user.user_id, "GET", f"/templates/{template_id}")
            # if authorized:
            user_templates.append(template)
    return user_templates


@router.post(
    "/{template_id}/duplicate",
    response_model=schemas.Template,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Template.Allocate"))]
)
async def duplicate_template(
        template_id: UUID, templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository))
) -> schemas.Template:
    """
    Duplicate a template.

    Required privilege: Template.Allocate
    """

    template = await TemplatesService(templates_repo).duplicate_template(template_id)
    return template
