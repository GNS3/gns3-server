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
API routes for appliances.
"""

import logging

from fastapi import APIRouter, Depends, status
from typing import Optional, List
from uuid import UUID

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError
)

from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.db.repositories.rbac import RbacRepository

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege


log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "",
    response_model=List[schemas.Appliance],
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Appliance.Audit"))]
)
async def get_appliances(
        update: Optional[bool] = False,
        symbol_theme: Optional[str] = None
) -> List[schemas.Appliance]:
    """
    Return all appliances known by the controller.

    Required privilege: Appliance.Audit
    """

    controller = Controller.instance()
    if update:
        await controller.appliance_manager.download_appliances()
    controller.appliance_manager.load_appliances(symbol_theme)
    return [c.asdict() for c in controller.appliance_manager.appliances.values()]


@router.get(
    "/{appliance_id}",
    response_model=schemas.Appliance,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Appliance.Audit"))]
)
def get_appliance(appliance_id: UUID) -> schemas.Appliance:
    """
    Get an appliance file.

    Required privilege: Appliance.Audit
    """

    controller = Controller.instance()
    appliance = controller.appliance_manager.appliances.get(str(appliance_id))
    if not appliance:
        raise ControllerNotFoundError(message=f"Could not find appliance '{appliance_id}'")
    return appliance.asdict()


@router.post(
    "/{appliance_id}/version",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Appliance.Allocate"))]
)
def add_appliance_version(appliance_id: UUID, appliance_version: schemas.ApplianceVersion) -> dict:
    """
    Add a version to an appliance.

    Required privilege: Appliance.Allocate
    """

    controller = Controller.instance()
    appliance = controller.appliance_manager.appliances.get(str(appliance_id))
    if not appliance:
        raise ControllerNotFoundError(message=f"Could not find appliance '{appliance_id}'")

    if not appliance.versions:
        raise ControllerBadRequestError(message=f"Appliance '{appliance_id}' do not have versions")

    if not appliance_version.images:
        raise ControllerBadRequestError(message=f"Version '{appliance_version.name}' must contain images")

    for version in appliance.versions:
        if version.get("name") == appliance_version.name:
            raise ControllerError(message=f"Appliance '{appliance_id}' already has version '{appliance_version.name}'")

    appliance.versions.append(appliance_version.model_dump(exclude_unset=True))
    return appliance.asdict()


@router.post(
    "/{appliance_id}/install",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Appliance.Allocate"))]
)
async def install_appliance(
        appliance_id: UUID,
        version: Optional[str] = None,
        images_repo: ImagesRepository = Depends(get_repository(ImagesRepository)),
        templates_repo: TemplatesRepository = Depends(get_repository(TemplatesRepository)),
        current_user: schemas.User = Depends(get_current_active_user),
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Install an appliance.

    Required privilege: Appliance.Allocate
    """

    controller = Controller.instance()
    await controller.appliance_manager.install_appliance(
        appliance_id,
        version,
        images_repo,
        templates_repo,
        rbac_repo,
        current_user
    )
