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


import asyncio
from typing import List, Union
from uuid import UUID

import gns3server.db.models as models
from gns3server import schemas
from gns3server.controller import Controller
from gns3server.controller.compute import Compute
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerError,
    ControllerNotFoundError,
)
from gns3server.db.repositories.computes import ComputesRepository


async def _connect_in_background(compute: Compute) -> None:

    try:
        await compute.connect()
    except ControllerError:
        # the connection failure is reported via compute.updated and the
        # retry backoff is already scheduled by the connect attempt itself
        pass


# fire-and-forget background connections: keep a reference so the task is not
# garbage-collected mid-flight, drop it once it is done
_background_connect_tasks: set[asyncio.Task] = set()


def _schedule_background_connect(compute: Compute) -> None:

    task = asyncio.ensure_future(_connect_in_background(compute))
    _background_connect_tasks.add(task)
    task.add_done_callback(_background_connect_tasks.discard)


class ComputesService:
    def __init__(self, computes_repo: ComputesRepository):

        self._computes_repo = computes_repo
        self._controller = Controller.instance()

    async def get_computes(self) -> List[models.Compute]:

        db_computes = await self._computes_repo.get_computes()
        return db_computes

    async def create_compute(self, compute_create: schemas.ComputeCreate, connect: bool = False) -> models.Compute:

        if compute_create.compute_id and await self._computes_repo.get_compute(compute_create.compute_id):
            raise ControllerBadRequestError(f"Compute '{compute_create.compute_id}' is already registered")
        db_compute = await self._computes_repo.create_compute(compute_create)
        compute = await self._controller.add_compute(
            compute_id=str(db_compute.compute_id),
            connect=connect,
            **compute_create.model_dump(exclude_unset=True, exclude={"compute_id"}),
        )
        self._controller.notification.controller_emit("compute.created", compute.asdict())

        # auto_connect connects in the background — including when the compute
        # was already registered on the controller — so the create request
        # never waits for, or fails on, the connection. An explicit
        # ?connect=true keeps its synchronous behavior via add_compute.
        if compute_create.auto_connect and not compute.connected:
            _schedule_background_connect(compute)
        return db_compute

    async def get_compute(self, compute_id: Union[str, UUID]) -> Union[models.Compute, dict]:

        if str(compute_id) == "local":
            # the built-in local compute only lives in the controller, not in the database;
            # drop unset fields (e.g. user) as the response schema types them as str
            return {k: v for k, v in self._controller.get_compute("local").asdict().items() if v is not None}
        db_compute = await self._computes_repo.get_compute(compute_id)
        if not db_compute:
            raise ControllerNotFoundError(f"Compute '{compute_id}' not found")
        return db_compute

    async def update_compute(
        self, compute_id: Union[str, UUID], compute_update: schemas.ComputeUpdate
    ) -> models.Compute:

        compute = self._controller.get_compute(str(compute_id))

        # remember the previous value to detect the false -> true transition below
        previous_auto_connect = False
        if compute_update.auto_connect:
            previous_db_compute = await self._computes_repo.get_compute(compute_id)
            if previous_db_compute:
                previous_auto_connect = bool(previous_db_compute.auto_connect)

        await compute.update(**compute_update.model_dump(exclude_unset=True))
        db_compute = await self._computes_repo.update_compute(compute_id, compute_update)
        if not db_compute:
            raise ControllerNotFoundError(f"Compute '{compute_id}' not found")
        self._controller.notification.controller_emit("compute.updated", compute.asdict())

        # Enabling auto_connect (false -> true) connects in the background: the
        # request returns immediately and the connection status flips via
        # compute.updated. The true -> true case is skipped on purpose so that
        # saving an edit does not reconnect a manually disconnected compute.
        if compute_update.auto_connect and not previous_auto_connect and not compute.connected:
            _schedule_background_connect(compute)
        return db_compute

    async def delete_compute(self, compute_id: Union[str, UUID]) -> None:

        if await self._computes_repo.delete_compute(compute_id):
            await self._controller.delete_compute(str(compute_id))
            self._controller.notification.controller_emit("compute.deleted", {"compute_id": str(compute_id)})
        else:
            raise ControllerNotFoundError(f"Compute '{compute_id}' not found")
