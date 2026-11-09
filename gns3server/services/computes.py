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
from typing import List, Optional, Union
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

# runtime state kept in memory by the controller, absent from the database
# rows: the response schema types all of them as optional
RUNTIME_FIELDS = ("connected", "last_error", "cpu_usage_percent", "memory_usage_percent", "disk_usage_percent")


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


def _compute_name(compute: Union[models.Compute, dict]) -> str:

    if isinstance(compute, dict):
        return compute["name"]
    return str(compute.name)


class ComputesService:
    def __init__(self, computes_repo: ComputesRepository):

        self._computes_repo = computes_repo
        self._controller = Controller.instance()

    def _with_runtime_state(self, db_compute: models.Compute) -> Union[models.Compute, dict]:
        """
        Overlay the runtime state the controller keeps in memory (connected
        flag, last error, resource usage) on top of the static database row.
        The capabilities payload is not part of the overlay: it is large and
        clients that need it fetch computes one by one.
        """

        compute = self._controller.computes.get(str(db_compute.compute_id))
        if compute is None:
            return db_compute  # never loaded by the controller: static row only
        values = db_compute.asdict()
        values.update({field: getattr(compute, field) for field in RUNTIME_FIELDS})
        return values

    async def get_computes(self, name: Optional[str] = None) -> List[Union[models.Compute, dict]]:
        """
        Every compute known by the controller: the database rows overlaid
        with their runtime state, plus the built-in local compute which
        only lives in the controller and never goes to the database.
        """

        computes: List[Union[models.Compute, dict]] = [
            self._with_runtime_state(db_compute) for db_compute in await self._computes_repo.get_computes()
        ]
        local_compute = self._controller.computes.get("local")
        if local_compute is not None:
            # drop unset fields (e.g. user) as the response schema types them as str;
            # capabilities stay out of the list, see _with_runtime_state
            computes.append({k: v for k, v in local_compute.asdict().items() if v is not None and k != "capabilities"})
        if name is not None:
            computes = [compute for compute in computes if _compute_name(compute) == name]
        return computes

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
        compute = self._controller.computes.get(str(compute_id))
        if compute is None:
            return db_compute
        # overlay the runtime state, including the capabilities payload the
        # compute reports once connected (absent from the database row)
        values = db_compute.asdict()
        values.update({field: getattr(compute, field) for field in RUNTIME_FIELDS})
        if compute.capabilities:
            values["capabilities"] = compute.capabilities
        return values

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
