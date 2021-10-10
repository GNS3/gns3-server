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
API routes for images.
"""

import os
import logging
import urllib.parse

from fastapi import APIRouter, Request, Response, Depends, status
from sqlalchemy.orm.exc import MultipleResultsFound
from typing import List
from gns3server import schemas
from pydantic import ValidationError

from gns3server.utils.images import InvalidImageError, default_images_directory, write_image
from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.services.templates import TemplatesService
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerForbiddenError,
    ControllerBadRequestError
)

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=List[schemas.Image])
async def get_images(
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> List[schemas.Image]:
    """
    Return all images.
    """

    return await images_repo.get_images()


@router.post("/upload/{image_path:path}", response_model=schemas.Image, status_code=status.HTTP_201_CREATED)
async def upload_image(
        image_path: str,
        request: Request,
        image_type: schemas.ImageType = schemas.ImageType.qemu,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
        templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> schemas.Image:
    """
    Upload an image.

    Example: curl -X POST http://host:port/v3/images/upload/my_image_name.qcow2?image_type=qemu \
    -H 'Authorization: Bearer <token>' --data-binary @"/path/to/image.qcow2"
    """

    image_path = urllib.parse.unquote(image_path)
    image_dir, image_name = os.path.split(image_path)
    directory = default_images_directory(image_type)
    full_path = os.path.abspath(os.path.join(directory, image_dir, image_name))
    if os.path.commonprefix([directory, full_path]) != directory:
        raise ControllerForbiddenError(f"Cannot write image, '{image_path}' is forbidden")

    if await images_repo.get_image(image_path):
        raise ControllerBadRequestError(f"Image '{image_path}' already exists")

    try:
        image = await write_image(image_name, image_type, full_path, request.stream(), images_repo)
    except (OSError, InvalidImageError) as e:
        raise ControllerError(f"Could not save {image_type} image '{image_path}': {e}")

    try:
        # attempt to automatically create a template based on image checksum
        template = await Controller.instance().appliance_manager.install_appliance_from_image(
            image.checksum,
            images_repo,
            directory
        )

        if template:
            template_create = schemas.TemplateCreate(**template)
            template = await TemplatesService(templates_repo).create_template(template_create)
            template_id = template.get("template_id")
            await rbac_repo.add_permission_to_user_with_path(current_user.user_id, f"/templates/{template_id}/*")
            log.info(f"Template '{template.get('name')}' version {template.get('version')} "
                     f"has been created using image '{image_name}'")

    except (ControllerError, ValidationError, InvalidImageError) as e:
        log.warning(f"Could not automatically create template using image '{image_path}': {e}")

    return image


@router.get("/{image_path:path}", response_model=schemas.Image)
async def get_image(
        image_path: str,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> schemas.Image:
    """
    Return an image.
    """

    image_path = urllib.parse.unquote(image_path)
    image = await images_repo.get_image(image_path)
    if not image:
        raise ControllerNotFoundError(f"Image '{image_path}' not found")
    return image


@router.delete("/{image_path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
        image_path: str,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> None:
    """
    Delete an image.
    """

    image_path = urllib.parse.unquote(image_path)

    try:
        image = await images_repo.get_image(image_path)
    except MultipleResultsFound:
        raise ControllerBadRequestError(f"Image '{image_path}' matches multiple images. "
                                        f"Please include the relative path of the image")

    if not image:
        raise ControllerNotFoundError(f"Image '{image_path}' not found")

    if await images_repo.get_image_templates(image.image_id):
        raise ControllerError(f"Image '{image_path}' is used by one or more templates")

    try:
        os.remove(image.path)
    except OSError:
        log.warning(f"Could not delete image file {image.path}")

    success = await images_repo.delete_image(image_path)
    if not success:
        raise ControllerError(f"Image '{image_path}' could not be deleted")


@router.post("/prune", status_code=status.HTTP_204_NO_CONTENT)
async def prune_images(
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> Response:
    """
    Prune images not attached to any template.
    """

    await images_repo.prune_images()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
