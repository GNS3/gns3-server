#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
#

import logging
from typing import Any, List, Optional, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import gns3server.db.models as models

from .base import BaseRepository

log = logging.getLogger(__name__)

# a record still in this state while its job is not in the live registry was
# cut short by a controller restart: the copies made so far are real projects
INTERRUPTED_ERROR = "The controller was restarted while this distribution was running"


class DistributionRecordsRepository(BaseRepository):
    """
    Durable records of project distribution jobs. The live state of a running
    job lives in the in-memory registry; every state change is written through
    here so the history survives a controller restart.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        super().__init__(db_session)

    async def create_record(
        self, distribution_id: UUID, project_id: UUID, name: str, created_by: str, total: int
    ) -> models.DistributionRecord:
        db_record = models.DistributionRecord(
            distribution_id=distribution_id,
            project_id=project_id,
            name=name,
            created_by=created_by,
            total=total,
            status="running",
            results=[],
        )
        self._db_session.add(db_record)
        await self._db_session.commit()
        await self._db_session.refresh(db_record)
        return db_record

    async def update_record(
        self,
        distribution_id: UUID,
        status: str,
        error: Optional[str],
        cancel_requested: bool,
        results: List[dict],
    ) -> bool:
        """
        Write the current state of a distribution job to its record. Returns
        False when no record matches (the job predates persistence, or the
        initial insert failed).
        """

        query = (
            update(models.DistributionRecord)
            .where(models.DistributionRecord.distribution_id == distribution_id)
            .values(status=status, error=error, cancel_requested=cancel_requested, results=results)
        )
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return cast(CursorResult, result).rowcount > 0

    async def get_record(self, distribution_id: UUID) -> Optional[models.DistributionRecord]:
        query = select(models.DistributionRecord).where(models.DistributionRecord.distribution_id == distribution_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def delete_record(self, distribution_id: UUID) -> bool:
        """
        Delete one record (manual cleanup of the history by its creator or a
        superadmin). Returns False when no record matches.
        """

        query = delete(models.DistributionRecord).where(models.DistributionRecord.distribution_id == distribution_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return cast(CursorResult, result).rowcount > 0

    async def delete_records_for_project(self, project_id: UUID) -> int:
        """
        Delete every record of a project (the project itself is being
        deleted). Returns the number of records deleted.
        """

        query = delete(models.DistributionRecord).where(models.DistributionRecord.project_id == project_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return cast(CursorResult, result).rowcount

    async def get_records_for_project(self, project_id: UUID) -> List[models.DistributionRecord]:
        query = (
            select(models.DistributionRecord)
            .where(models.DistributionRecord.project_id == project_id)
            .order_by(models.DistributionRecord.created_at.desc())
        )
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_records_by_creator(self, created_by: str) -> List[models.DistributionRecord]:
        query = (
            select(models.DistributionRecord)
            .where(models.DistributionRecord.created_by == created_by)
            .order_by(models.DistributionRecord.created_at.desc())
        )
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_all_records(self) -> List[models.DistributionRecord]:
        query = select(models.DistributionRecord).order_by(models.DistributionRecord.created_at.desc())
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def mark_interrupted(self, live_distribution_ids: List[UUID]) -> int:
        """
        Close out the records left "running" or "cancelling" by a controller
        restart: their jobs are gone from the live registry and will never
        update the row again. A running job becomes "failed" (some recipients
        may never get their copy), a cancelling one becomes "cancelled" (the
        remaining recipients were skipped, as requested). Returns the number
        of records closed out.
        """

        closed_out = 0
        conditions: List[Any] = []
        if live_distribution_ids:
            conditions.append(models.DistributionRecord.distribution_id.not_in(live_distribution_ids))
        for from_status, to_status, error in (
            ("running", "failed", INTERRUPTED_ERROR),
            ("cancelling", "cancelled", None),
        ):
            query = (
                update(models.DistributionRecord)
                .where(models.DistributionRecord.status == from_status, *conditions)
                .values(status=to_status, error=error)
            )
            result = await self._db_session.execute(query)
            closed_out += cast(CursorResult, result).rowcount
        await self._db_session.commit()
        if closed_out:
            log.info(f"{closed_out} distribution record(s) left unfinished by a controller restart were closed out")
        return closed_out
