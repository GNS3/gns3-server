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
API routes for drawings.
"""

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from typing import List
from uuid import UUID

from gns3server.controller import Controller
from gns3server.db.repositories.rbac import RbacRepository
from gns3server import schemas

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

responses = {404: {"model": schemas.ErrorMessage, "description": "Project or drawing not found"}}

router = APIRouter(responses=responses)


@router.get(
    "",
    response_model=List[schemas.Drawing],
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Drawing.Audit"))]
)
async def get_drawings(project_id: UUID) -> List[schemas.Drawing]:
    """
    Return the list of all drawings for a given project.

    Required privilege: Drawing.Audit
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    if project.status == "closed":
        # allow to retrieve drawings from a closed project
        return project.drawings.values()
    return [v.asdict() for v in project.drawings.values()]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Drawing,
    dependencies=[Depends(has_privilege("Drawing.Allocate"))]
)
async def create_drawing(project_id: UUID, drawing_data: schemas.Drawing) -> schemas.Drawing:
    """
    Create a new drawing.

    Required privilege: Drawing.Allocate
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    drawing = await project.add_drawing(**jsonable_encoder(drawing_data, exclude_unset=True))
    return drawing.asdict()


@router.get(
    "/{drawing_id}",
    response_model=schemas.Drawing,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Drawing.Audit"))]
)
async def get_drawing(project_id: UUID, drawing_id: UUID) -> schemas.Drawing:
    """
    Return a drawing.

    Required privilege: Drawing.Audit
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    drawing = project.get_drawing(str(drawing_id))
    return drawing.asdict()


@router.put(
    "/{drawing_id}",
    response_model=schemas.Drawing,
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Drawing.Modify"))]
)
async def update_drawing(project_id: UUID, drawing_id: UUID, drawing_data: schemas.Drawing) -> schemas.Drawing:
    """
    Update a drawing.

    Required privilege: Drawing.Modify
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    drawing = project.get_drawing(str(drawing_id))
    await drawing.update(**jsonable_encoder(drawing_data, exclude_unset=True))
    return drawing.asdict()


@router.delete(
    "/{drawing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Drawing.Allocate"))]
)
async def delete_drawing(
        project_id: UUID,
        drawing_id: UUID,
        rbac_repo: RbacRepository = Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a drawing.

    Required privilege: Drawing.Allocate
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.delete_drawing(str(drawing_id))
    await rbac_repo.delete_all_ace_starting_with_path(f"/drawings/{drawing_id}")
