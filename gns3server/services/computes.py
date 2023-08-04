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


from uuid import UUID
from typing import List, Union

from gns3server import schemas
import gns3server.db.models as models

from gns3server.db.repositories.computes import ComputesRepository
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerNotFoundError,
    ControllerForbiddenError,
)


class ComputesService:
    def __init__(self, computes_repo: ComputesRepository):

        self._computes_repo = computes_repo
        self._controller = Controller.instance()

    async def get_computes(self) -> List[models.Compute]:

        db_computes = await self._computes_repo.get_computes()
        return db_computes

    async def create_compute(self, compute_create: schemas.ComputeCreate, connect: bool = False) -> models.Compute:

        if await self._computes_repo.get_compute(compute_create.compute_id):
            raise ControllerBadRequestError(f"Compute '{compute_create.compute_id}' is already registered")
        db_compute = await self._computes_repo.create_compute(compute_create)
        compute = await self._controller.add_compute(
            compute_id=str(db_compute.compute_id),
            connect=connect,
            **compute_create.model_dump(exclude_unset=True, exclude={"compute_id"}),
        )
        self._controller.notification.controller_emit("compute.created", compute.asdict())
        return db_compute

    async def get_compute(self, compute_id: Union[str, UUID]) -> models.Compute:

        db_compute = await self._computes_repo.get_compute(compute_id)
        if not db_compute:
            raise ControllerNotFoundError(f"Compute '{compute_id}' not found")
        return db_compute

    async def update_compute(
        self, compute_id: Union[str, UUID], compute_update: schemas.ComputeUpdate
    ) -> models.Compute:

        compute = self._controller.get_compute(str(compute_id))
        await compute.update(**compute_update.model_dump(exclude_unset=True))
        db_compute = await self._computes_repo.update_compute(compute_id, compute_update)
        if not db_compute:
            raise ControllerNotFoundError(f"Compute '{compute_id}' not found")
        self._controller.notification.controller_emit("compute.updated", compute.asdict())
        return db_compute

    async def delete_compute(self, compute_id: Union[str, UUID]) -> None:

        if await self._computes_repo.delete_compute(compute_id):
            await self._controller.delete_compute(str(compute_id))
            self._controller.notification.controller_emit("compute.deleted", {"compute_id": str(compute_id)})
        else:
            raise ControllerNotFoundError(f"Compute '{compute_id}' not found")
