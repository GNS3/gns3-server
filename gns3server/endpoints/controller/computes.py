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
API endpoints for computes.
"""

from fastapi import APIRouter, status
from fastapi.encoders import jsonable_encoder
from typing import List, Union
from uuid import UUID

from gns3server.controller import Controller
from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints import schemas

router = APIRouter()


@router.post("/",
             summary="Create a new compute",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Compute,
             responses={404: {"model": ErrorMessage, "description": "Could not connect to compute"},
                        409: {"model": ErrorMessage, "description": "Could not create compute"},
                        401: {"model": ErrorMessage, "description": "Invalid authentication for compute"}})
async def create_compute(compute_data: schemas.ComputeCreate):
    """
    Create a new compute on the controller.
    """

    compute = await Controller.instance().add_compute(**jsonable_encoder(compute_data, exclude_unset=True),
                                                      connect=False)
    return compute.__json__()


@router.get("/{compute_id}",
            summary="Get a compute",
            response_model=schemas.Compute,
            response_description="Compute data",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Compute not found"}})
def get_compute(compute_id: Union[str, UUID]):
    """
    Get compute data from the controller.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return compute.__json__()


@router.get("/",
            summary="List of all computes",
            response_model=List[schemas.Compute],
            response_description="List of computes",
            response_model_exclude_unset=True)
async def list_computes():
    """
    Return the list of all computes known by the controller.
    """

    controller = Controller.instance()
    return [c.__json__() for c in controller.computes.values()]


@router.put("/{compute_id}",
            summary="Update a compute",
            response_model=schemas.Compute,
            response_description="Updated compute",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Compute not found"}})
async def update_compute(compute_id: Union[str, UUID], compute_data: schemas.ComputeUpdate):
    """
    Update a compute on the controller.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    # exclude compute_id because we only use it when creating a new compute
    await compute.update(**jsonable_encoder(compute_data, exclude_unset=True, exclude={"compute_id"}))
    return compute.__json__()


@router.delete("/{compute_id}",
               summary="Delete a compute",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def delete_compute(compute_id: Union[str, UUID]):
    """
    Delete a compute from the controller.
    """

    await Controller.instance().delete_compute(str(compute_id))


@router.get("/{compute_id}/{emulator}/images",
            summary="List images",
            response_description="List of images",
            responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def list_images(compute_id: Union[str, UUID], emulator: str):
    """
    Return the list of images available on a compute for a given emulator type.
    """

    controller = Controller.instance()
    compute = controller.get_compute(str(compute_id))
    return await compute.images(emulator)


@router.get("/{compute_id}/{emulator}/{endpoint_path:path}",
            summary="Forward GET request to a compute",
            responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def forward_get(compute_id: Union[str, UUID], emulator: str, endpoint_path: str):
    """
    Forward GET request to a compute. Read the full compute API documentation for available endpoints.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    result = await compute.forward("GET", emulator, endpoint_path)
    return result

@router.post("/{compute_id}/{emulator}/{endpoint_path:path}",
             summary="Forward POST request to a compute",
             responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def forward_post(compute_id: Union[str, UUID], emulator: str, endpoint_path: str, compute_data: dict):
    """
    Forward POST request to a compute. Read the full compute API documentation for available endpoints.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return await compute.forward("POST", emulator, endpoint_path, data=compute_data)


@router.put("/{compute_id}/{emulator}/{endpoint_path:path}",
            summary="Forward PUT request to a compute",
            responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def forward_put(compute_id: Union[str, UUID], emulator: str, endpoint_path: str, compute_data: dict):
    """
    Forward PUT request to a compute. Read the full compute API documentation for available endpoints.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return await compute.forward("PUT", emulator, endpoint_path, data=compute_data)


@router.post("/{compute_id}/auto_idlepc",
             summary="Find a new IDLE-PC value",
             responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def autoidlepc(compute_id: Union[str, UUID], auto_idle_pc: schemas.AutoIdlePC):
    """
    Find a suitable Idle-PC value for a given IOS image. This may take some time.
    """

    controller = Controller.instance()
    return await controller.autoidlepc(str(compute_id),
                                       auto_idle_pc.platform,
                                       auto_idle_pc.image,
                                       auto_idle_pc.ram)


@router.get("/{compute_id}/ports",
            summary="Get ports used by a compute",
            deprecated=True,
            responses={404: {"model": ErrorMessage, "description": "Compute was not found"}})
async def ports(compute_id: Union[str, UUID]):
    """
    Get ports information for a given compute.
    """

    return await Controller.instance().compute_ports(str(compute_id))
