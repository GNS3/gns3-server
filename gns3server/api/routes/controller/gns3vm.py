#!/usr/bin/env python
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
API routes for managing the GNS3 VM.
"""

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from typing import List

from gns3server.controller import Controller
from gns3server import schemas

router = APIRouter()


@router.get("/engines")
async def get_engines() -> List[dict]:
    """
    Return the list of supported engines for the GNS3VM.
    """

    gns3_vm = Controller().instance().gns3vm
    return gns3_vm.engine_list()


@router.get("/engines/{engine}/vms")
async def get_vms(engine: str) -> List[dict]:
    """
    Return all the available VMs for a specific virtualization engine.
    """

    vms = await Controller.instance().gns3vm.list(engine)
    return vms


@router.get("", response_model=schemas.GNS3VM)
async def get_gns3vm_settings() -> schemas.GNS3VM:
    """
    Return the GNS3 VM settings.
    """

    return Controller.instance().gns3vm.asdict()


@router.put("", response_model=schemas.GNS3VM, response_model_exclude_unset=True)
async def update_gns3vm_settings(gns3vm_data: schemas.GNS3VM) -> schemas.GNS3VM:
    """
    Update the GNS3 VM settings.
    """

    controller = Controller().instance()
    gns3_vm = controller.gns3vm
    await gns3_vm.update_settings(jsonable_encoder(gns3vm_data, exclude_unset=True))
    controller.save()
    return gns3_vm.asdict()
