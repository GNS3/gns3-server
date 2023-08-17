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
API routes for images.
"""

import os
import urllib.parse

from fastapi import APIRouter, Request, status, Response, HTTPException
from fastapi.responses import FileResponse
from typing import List

from gns3server.compute.docker import Docker
from gns3server.compute.dynamips import Dynamips
from gns3server.compute.iou import IOU
from gns3server.compute.qemu import Qemu

router = APIRouter()


@router.get("/docker/images")
async def get_docker_images() -> List[dict]:
    """
    Get all Docker images.
    """

    docker_manager = Docker.instance()
    return await docker_manager.list_images()


@router.get("/dynamips/images")
async def get_dynamips_images() -> List[dict]:
    """
    Get all Dynamips images.
    """

    dynamips_manager = Dynamips.instance()
    return await dynamips_manager.list_images()


@router.post("/dynamips/images/{filename:path}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_dynamips_image(filename: str, request: Request) -> None:
    """
    Upload a Dynamips IOS image.
    """

    dynamips_manager = Dynamips.instance()
    await dynamips_manager.write_image(urllib.parse.unquote(filename), request.stream())


@router.get("/dynamips/images/{filename:path}")
async def download_dynamips_image(filename: str) -> FileResponse:
    """
    Download a Dynamips IOS image.
    """

    filename = urllib.parse.unquote(filename)

    # Raise error if user try to escape
    if filename[0] == "." or os.path.sep in filename:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    dynamips_manager = Dynamips.instance()
    image_path = dynamips_manager.get_abs_image_path(filename)

    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(image_path, media_type="application/octet-stream")


@router.get("/iou/images")
async def get_iou_images() -> List[dict]:
    """
    Get all IOU images.
    """

    iou_manager = IOU.instance()
    return await iou_manager.list_images()


@router.post("/iou/images/{filename:path}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_iou_image(filename: str, request: Request) -> None:
    """
    Upload an IOU image.
    """

    iou_manager = IOU.instance()
    await iou_manager.write_image(urllib.parse.unquote(filename), request.stream())


@router.get("/iou/images/{filename:path}")
async def download_iou_image(filename: str) -> FileResponse:
    """
    Download an IOU image.
    """

    filename = urllib.parse.unquote(filename)

    # Raise error if user try to escape
    if filename[0] == "." or os.path.sep in filename:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    iou_manager = IOU.instance()
    image_path = iou_manager.get_abs_image_path(filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(image_path, media_type="application/octet-stream")


@router.get("/qemu/images")
async def get_qemu_images() -> List[dict]:

    qemu_manager = Qemu.instance()
    return await qemu_manager.list_images()


@router.post("/qemu/images/{filename:path}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_qemu_image(filename: str, request: Request) -> None:

    qemu_manager = Qemu.instance()
    await qemu_manager.write_image(urllib.parse.unquote(filename), request.stream())


@router.get("/qemu/images/{filename:path}")
async def download_qemu_image(filename: str) -> FileResponse:

    filename = urllib.parse.unquote(filename)

    # Raise error if user try to escape
    if filename[0] == "." or os.path.sep in filename:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    qemu_manager = Qemu.instance()
    image_path = qemu_manager.get_abs_image_path(filename)

    if not os.path.exists(image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return FileResponse(image_path, media_type="application/octet-stream")
