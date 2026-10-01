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
import tempfile

from fastapi import APIRouter, Request, Response, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from starlette.requests import ClientDisconnect
from sqlalchemy.orm.exc import MultipleResultsFound
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Literal

from gns3server import schemas
from gns3server.config import Config
from gns3server.compute.qemu import Qemu
from gns3server.utils.images import (
    InvalidImageError,
    write_image,
    read_image_info,
    default_images_directory,
    get_builtin_disks,
)
import gns3server.db.models as models
from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.controller import Controller
from gns3server.services.image_reconciliation import get_image_reconciliation_service
from gns3server.utils.image_inventory import contained_path, image_lock, publish_image, fingerprint, ImageLockBusy
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerForbiddenError,
    ControllerBadRequestError,
)

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

log = logging.getLogger(__name__)

router = APIRouter()


def image_destination(image_path):
    root = os.path.realpath(os.path.expanduser(Config.instance().settings.Server.images_path))
    full_path = os.path.abspath(os.path.join(root, image_path))
    if not contained_path(os.path.realpath(full_path), root):
        raise ControllerForbiddenError(f"Cannot write image, '{image_path}' is forbidden")
    return full_path


@router.post(
    "/sync",
    response_model=schemas.ImageSyncJob,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(has_privilege("Image.Allocate"))],
)
async def sync_images(options: schemas.ImageSyncRequest, request: Request, response: Response):
    """Reconcile configured image directories without deleting files or references."""
    try:
        job = await get_image_reconciliation_service(request.app).start(**options.model_dump())
    except ImageLockBusy:
        raise ControllerError("Image synchronization is already running or shutting down")
    response.headers["Location"] = str(request.url_for("get_image_sync_job", job_id=job["job_id"]))
    return job


@router.get(
    "/sync/jobs/{job_id}", response_model=schemas.ImageSyncJob, dependencies=[Depends(has_privilege("Image.Audit"))]
)
async def get_image_sync_job(
    job_id: str, request: Request, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)
):
    """Get progress and a page of errors (first 1,000 errors retained per job)."""
    job = await get_image_reconciliation_service(request.app).get_job(job_id, offset, limit)
    if job is None:
        raise ControllerNotFoundError(f"Image synchronization job '{job_id}' not found")
    return job


@router.post(
    "/qemu/{image_path:path}",
    response_model=schemas.Image,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Image.Allocate"))],
)
async def create_qemu_image(
    image_path: str,
    image_data: schemas.QemuDiskImageCreate,
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> models.Image:
    """
    Create a new blank Qemu image.

    Required privilege: Image.Allocate
    """

    allow_raw_image = Config.instance().settings.Server.allow_raw_images
    if image_data.format == schemas.QemuDiskImageFormat.raw and not allow_raw_image:
        raise ControllerBadRequestError("Raw images are not allowed")

    disk_image_path = urllib.parse.unquote(image_path)
    image_dir, image_name = os.path.split(disk_image_path)
    # check if the path is within the default images directory
    disk_image_path = image_destination(disk_image_path)

    if not image_dir:
        # put the image in the default images directory for Qemu
        directory = default_images_directory(image_type="qemu")
        os.makedirs(directory, exist_ok=True)
        disk_image_path = image_destination(os.path.join(directory, image_name))

    async with image_lock(disk_image_path):
        if os.path.lexists(disk_image_path):
            raise ControllerBadRequestError(f"Disk image '{disk_image_path}' already exists")
        os.makedirs(os.path.dirname(disk_image_path), exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".gns3-create-", suffix=".tmp", dir=os.path.dirname(disk_image_path))
        os.close(fd)
        try:
            options = jsonable_encoder(image_data, exclude_unset=True)
            await Qemu.instance().create_disk_image(temporary, options)
            image_info = await read_image_info(temporary, "qemu", allow_raw_image=allow_raw_image)
            publish_image(temporary, disk_image_path)
            image_info.update(
                path=disk_image_path, image_name=image_name, file_fingerprint=fingerprint(disk_image_path)
            )
            return await images_repo.save_verified_image(image_info)
        except (OSError, InvalidImageError, SQLAlchemyError) as e:
            raise ControllerError(f"Could not create disk image '{disk_image_path}': {e}") from e
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


@router.get("", response_model=List[schemas.Image], dependencies=[Depends(has_privilege("Image.Audit"))])
async def get_images(
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
    image_type: Optional[schemas.ImageType] = None,
    availability: Optional[Literal["unknown", "available", "missing", "unavailable", "invalid"]] = None,
) -> List[models.Image]:
    """
    Return all images.

    Required privilege: Image.Audit
    """

    return await images_repo.get_images(image_type, availability)


@router.post(
    "/upload/{image_path:path}",
    response_model=schemas.Image,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Image.Allocate"))],
)
async def upload_image(
    image_path: str,
    request: Request,
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
    current_user: schemas.User = Depends(get_current_active_user),
    rbac_repo: RbacRepository = Depends(get_repository(RbacRepository)),
    install_appliances: Optional[bool] = False,
) -> models.Image:
    """
    Upload an image.

    Example: curl -X POST http://host:port/v3/images/upload/my_image_name.qcow2 \
    -H 'Authorization: Bearer <token>' --data-binary @"/path/to/image.qcow2"

    Required privilege: Image.Allocate
    """

    image_path = urllib.parse.unquote(image_path)
    image_dir, image_name = os.path.split(image_path)
    # check if the path is within the default images directory
    full_path = image_destination(image_path)

    # If the client sends X-MD5-Checksum, check for a duplicate before consuming the upload stream
    checksum_header = request.headers.get("X-MD5-Checksum")
    if checksum_header:
        check_dir = os.path.dirname(full_path) if image_dir else None
        duplicate = await images_repo.get_image_by_checksum(checksum_header, check_dir)
        if duplicate:
            location = f" in '{check_dir}'" if check_dir else ""
            raise ControllerError(f"Image '{duplicate.filename}' with the same checksum already exists{location}")

    try:
        allow_raw_image = Config.instance().settings.Server.allow_raw_images
        image = await write_image(image_path, full_path, request.stream(), images_repo, allow_raw_image=allow_raw_image)
    except (OSError, InvalidImageError, ClientDisconnect, SQLAlchemyError) as e:
        service = getattr(request.app.state, "image_reconciliation", None)
        if service:
            service.dirty.set()
        raise ControllerError(f"Could not save image '{image_path}': {e}")

    if install_appliances:
        # attempt to automatically create templates based on image checksum
        await Controller.instance().appliance_manager.install_appliances_from_image(
            image_path,
            image.checksum,
            images_repo,
            templates_repo,
            rbac_repo,
            current_user,
            os.path.dirname(image.path),
        )

    return image


@router.delete(
    "/prune", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(has_privilege("Image.Allocate"))]
)
async def prune_images(
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> None:
    """
    Prune images not attached to any template.

    Images referenced by a node in any project (opened or closed) are kept.

    Required privilege: Image.Allocate
    """

    skip_images = get_builtin_disks()
    # a single pass over all projects' node properties protects every
    # referenced file name at once
    referenced_filenames = Controller.instance().collect_referenced_image_filenames()
    await images_repo.prune_images(
        list(skip_images) + list(referenced_filenames), is_in_use=Controller.instance().find_projects_using_image
    )


@router.post("/install", status_code=status.HTTP_200_OK, dependencies=[Depends(has_privilege("Image.Allocate"))])
async def install_images(
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
    templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
) -> dict:
    """
    Attempt to automatically create templates based on image checksums.

    Returns the list of created templates and the list of skipped
    candidates (with the reason why they were skipped).

    Required privilege: Image.Allocate
    """

    created = []
    skipped = []
    skip_images = get_builtin_disks()
    images = await images_repo.get_images()
    for image in images:
        if not await images_repo.is_usable(image):
            skipped.append(
                {"name": image.filename, "reason": "image is missing, changed or unreadable; synchronize images first"}
            )
            continue
        if skip_images and image.filename in skip_images:
            log.debug(f"Skipping image '{image.path}' for image installation")
            continue
        templates = await images_repo.get_image_templates(image.image_id)
        if templates:
            # the image is already used by a template
            log.warning(f"Image '{image.path}' is used by one or more templates")
            skipped.append(
                {
                    "name": image.filename,
                    "reason": "image is already used by one or more templates",
                }
            )
            continue
        results = await Controller.instance().appliance_manager.install_appliances_from_image(
            image.path, image.checksum, images_repo, templates_repo, None, None, os.path.dirname(image.path)
        )
        for result in results:
            if result.get("status") == "created":
                created.append({k: v for k, v in result.items() if k != "status"})
            else:
                skipped.append({k: v for k, v in result.items() if k != "status"})
    return {"created": created, "skipped": skipped}


@router.get("/{image_path:path}", response_model=schemas.Image, dependencies=[Depends(has_privilege("Image.Audit"))])
async def get_image(
    image_path: str,
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> models.Image:
    """
    Return an image.

    Required privilege: Image.Audit
    """

    image_path = urllib.parse.unquote(image_path)
    image = await images_repo.get_image(image_path)
    if not image:
        raise ControllerNotFoundError(f"Image '{image_path}' not found")
    return image


@router.delete(
    "/{image_path:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Image.Allocate"))],
)
async def delete_image(
    image_path: str,
    images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
) -> None:
    """
    Delete an image.

    Required privilege: Image.Allocate
    """

    image_path = urllib.parse.unquote(image_path)

    try:
        image = await images_repo.get_image(image_path)
    except MultipleResultsFound:
        raise ControllerBadRequestError(
            f"Image '{image_path}' matches multiple images. Please include the absolute path of the image"
        )

    if not image:
        raise ControllerNotFoundError(f"Image '{image_path}' not found")

    templates = await images_repo.get_image_templates(image.image_id)
    if templates:
        template_names = ", ".join([str(template.name) for template in templates])
        raise ControllerError(f"Image '{image_path}' is used by one or more templates: {template_names}")

    project_names = Controller.instance().find_projects_using_image(image.filename)
    if project_names:
        raise ControllerError(f"Image '{image_path}' is used by one or more projects: {', '.join(project_names)}")

    path = image.path
    revision = (image.image_id, image.checksum, image.file_fingerprint)
    async with image_lock(path):
        image = await images_repo.get_image(path, refresh=True)
        if image is None or (image.image_id, image.checksum, image.file_fingerprint) != revision:
            raise ControllerError(f"Image '{image_path}' changed while waiting for deletion; refresh and retry")
        # Recheck usage after waiting for a concurrent writer/scanner.
        if await images_repo.get_image_templates(image.image_id) or Controller.instance().find_projects_using_image(
            image.filename
        ):
            raise ControllerError(f"Image '{image_path}' is in use")
        try:
            os.remove(image.path)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise ControllerError(f"Could not delete image file '{image.path}': {e}") from e
        if not await images_repo.delete_image_exact(image.image_id):
            raise ControllerError(f"Image '{image_path}' could not be deleted")
