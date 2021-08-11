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

from fastapi import APIRouter, Request, Depends, status
from typing import List
from gns3server import schemas

from gns3server.utils.images import InvalidImageError, default_images_directory, write_image
from gns3server.db.repositories.images import ImagesRepository
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerForbiddenError,
    ControllerBadRequestError
)

from .dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def get_images(
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> List[schemas.Image]:
    """
    Return all images.
    """

    return await images_repo.get_images()


@router.post("/upload/{image_name}", response_model=schemas.Image, status_code=status.HTTP_201_CREATED)
async def upload_image(
        image_name: str,
        request: Request,
        image_type: schemas.ImageType = schemas.ImageType.qemu,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> schemas.Image:
    """
    Upload an image.
    """

    image_name = urllib.parse.unquote(image_name)
    directory = default_images_directory(image_type)
    path = os.path.abspath(os.path.join(directory, image_name))
    if os.path.commonprefix([directory, path]) != directory:
        raise ControllerForbiddenError(f"Could not write image: {image_name}, '{path}' is forbidden")

    if await images_repo.get_image(image_name):
        raise ControllerBadRequestError(f"Image '{image_name}' already exists")

    try:
        image = await write_image(image_name, image_type, path, request.stream(), images_repo)
    except (OSError, InvalidImageError) as e:
        raise ControllerError(f"Could not save {image_type} image '{image_name}': {e}")

    # TODO: automatically create template based on image checksum
    #from gns3server.controller import Controller
    #controller = Controller.instance()
    #controller.appliance_manager.find_appliance_with_image(image.checksum)

    return image


@router.get("/{image_name}", response_model=schemas.Image)
async def get_image(
        image_name: str,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> schemas.Image:
    """
    Return an image.
    """

    image = await images_repo.get_image(image_name)
    if not image:
        raise ControllerNotFoundError(f"Image '{image_name}' not found")
    return image


@router.delete("/{image_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
        image_name: str,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> None:
    """
    Delete an image.
    """

    image = await images_repo.get_image(image_name)
    if not image:
        raise ControllerNotFoundError(f"Image '{image_name}' not found")

    if await images_repo.get_image_templates(image.id):
        raise ControllerError(f"Image '{image_name}' is used by one or more templates")

    try:
        os.remove(image.path)
    except OSError:
        log.warning(f"Could not delete image file {image.path}")

    success = await images_repo.delete_image(image_name)
    if not success:
        raise ControllerError(f"Image '{image_name}' could not be deleted")
