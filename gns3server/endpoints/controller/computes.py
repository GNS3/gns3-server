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
from gns3server import schemas

router = APIRouter()

responses = {
    404: {"model": schemas.ErrorMessage, "description": "Compute not found"}
}


@router.post("",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Compute,
             responses={404: {"model": schemas.ErrorMessage, "description": "Could not connect to compute"},
                        409: {"model": schemas.ErrorMessage, "description": "Could not create compute"},
                        401: {"model": schemas.ErrorMessage, "description": "Invalid authentication for compute"}})
async def create_compute(compute_data: schemas.ComputeCreate):
    """
    Create a new compute on the controller.
    """

    compute = await Controller.instance().add_compute(**jsonable_encoder(compute_data, exclude_unset=True),
                                                      connect=False)
    return compute.__json__()


@router.get("/{compute_id}",
            response_model=schemas.Compute,
            response_model_exclude_unset=True,
            responses=responses)
def get_compute(compute_id: Union[str, UUID]):
    """
    Return a compute from the controller.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return compute.__json__()


@router.get("",
            response_model=List[schemas.Compute],
            response_model_exclude_unset=True)
async def get_computes():
    """
    Return all computes known by the controller.
    """

    controller = Controller.instance()
    return [c.__json__() for c in controller.computes.values()]


@router.put("/{compute_id}",
            response_model=schemas.Compute,
            response_model_exclude_unset=True,
            responses=responses)
async def update_compute(compute_id: Union[str, UUID], compute_data: schemas.ComputeUpdate):
    """
    Update a compute on the controller.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    # exclude compute_id because we only use it when creating a new compute
    await compute.update(**jsonable_encoder(compute_data, exclude_unset=True, exclude={"compute_id"}))
    return compute.__json__()


@router.delete("/{compute_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses=responses)
async def delete_compute(compute_id: Union[str, UUID]):
    """
    Delete a compute from the controller.
    """

    await Controller.instance().delete_compute(str(compute_id))


@router.get("/{compute_id}/{emulator}/images",
            responses=responses)
async def get_images(compute_id: Union[str, UUID], emulator: str):
    """
    Return the list of images available on a compute for a given emulator type.
    """

    controller = Controller.instance()
    compute = controller.get_compute(str(compute_id))
    return await compute.images(emulator)


@router.get("/{compute_id}/{emulator}/{endpoint_path:path}",
            responses=responses)
async def forward_get(compute_id: Union[str, UUID], emulator: str, endpoint_path: str):
    """
    Forward a GET request to a compute.
    Read the full compute API documentation for available endpoints.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    result = await compute.forward("GET", emulator, endpoint_path)
    return result


@router.post("/{compute_id}/{emulator}/{endpoint_path:path}",
             responses=responses)
async def forward_post(compute_id: Union[str, UUID], emulator: str, endpoint_path: str, compute_data: dict):
    """
    Forward a POST request to a compute.
    Read the full compute API documentation for available endpoints.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return await compute.forward("POST", emulator, endpoint_path, data=compute_data)


@router.put("/{compute_id}/{emulator}/{endpoint_path:path}",
            responses=responses)
async def forward_put(compute_id: Union[str, UUID], emulator: str, endpoint_path: str, compute_data: dict):
    """
    Forward a PUT request to a compute.
    Read the full compute API documentation for available endpoints.
    """

    compute = Controller.instance().get_compute(str(compute_id))
    return await compute.forward("PUT", emulator, endpoint_path, data=compute_data)


@router.post("/{compute_id}/auto_idlepc",
             responses=responses)
async def autoidlepc(compute_id: Union[str, UUID], auto_idle_pc: schemas.AutoIdlePC):
    """
    Find a suitable Idle-PC value for a given IOS image. This may take a few minutes.
    """

    controller = Controller.instance()
    return await controller.autoidlepc(str(compute_id),
                                       auto_idle_pc.platform,
                                       auto_idle_pc.image,
                                       auto_idle_pc.ram)


@router.get("/{compute_id}/ports",
            deprecated=True,
            responses=responses)
async def ports(compute_id: Union[str, UUID]):
    """
    Return ports information for a given compute.
    """

    return await Controller.instance().compute_ports(str(compute_id))
