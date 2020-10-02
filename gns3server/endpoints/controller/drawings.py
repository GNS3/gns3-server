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
API endpoints for drawings.
"""

from fastapi import APIRouter, status
from fastapi.encoders import jsonable_encoder
from typing import List
from uuid import UUID

from gns3server.controller import Controller
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints.schemas.drawings import Drawing

router = APIRouter()


@router.get("/projects/{project_id}/drawings",
            summary="List of all drawings",
            response_model=List[Drawing],
            response_description="List of drawings",
            response_model_exclude_unset=True)
async def list_drawings(project_id: UUID):
    """
    Return the list of all drawings for a given project.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    return [v.__json__() for v in project.drawings.values()]


@router.post("/projects/{project_id}/drawings",
             summary="Create a new drawing",
             status_code=status.HTTP_201_CREATED,
             response_model=Drawing,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
async def create_drawing(project_id: UUID, drawing_data: Drawing):

    project = await Controller.instance().get_loaded_project(str(project_id))
    drawing = await project.add_drawing(**jsonable_encoder(drawing_data, exclude_unset=True))
    return drawing.__json__()


@router.get("/projects/{project_id}/drawings/{drawing_id}",
            summary="Get a drawing",
            response_model=Drawing,
            response_description="Drawing data",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Project or drawing not found"}})
async def get_drawing(project_id: UUID, drawing_id: UUID):
    """
    Get drawing data for a given project from the controller.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    drawing = project.get_drawing(str(drawing_id))
    return drawing.__json__()


@router.put("/projects/{project_id}/drawings/{drawing_id}",
            summary="Update a drawing",
            response_model=Drawing,
            response_description="Updated drawing",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Project or drawing not found"}})
async def update_drawing(project_id: UUID, drawing_id: UUID, drawing_data: Drawing):
    """
    Update a drawing for a given project on the controller.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    drawing = project.get_drawing(str(drawing_id))
    await drawing.update(**jsonable_encoder(drawing_data, exclude_unset=True))
    return drawing.__json__()


@router.delete("/projects/{project_id}/drawings/{drawing_id}",
               summary="Delete a drawing",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": ErrorMessage, "description": "Project or drawing not found"}})
async def delete_drawing(project_id: UUID, drawing_id: UUID):
    """
    Update a drawing for a given project from the controller.
    """

    project = await Controller.instance().get_loaded_project(str(project_id))
    await project.delete_drawing(str(drawing_id))
